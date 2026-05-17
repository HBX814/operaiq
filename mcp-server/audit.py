"""
BigQuery audit logging for OperaIQ MCP Server.

Every tool invocation writes one row to operaiq.audit_log with:
  caller_id, tool_name, input_params (JSON), result_status, latency_ms, timestamp
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional

from google.cloud import bigquery
from google.cloud.bigquery import SchemaField

logger = logging.getLogger("operaiq.audit")

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "operaiq")
DATASET_ID = os.environ.get(
    "BIGQUERY_DATASET", os.environ.get("BQ_DATASET", "operaiq")
)
AUDIT_TABLE = "audit_log"
FULL_TABLE = f"{PROJECT_ID}.{DATASET_ID}.{AUDIT_TABLE}"


class AuditLogger:
    """Async-safe BigQuery audit logger using streaming inserts."""

    def __init__(self) -> None:
        self._client: Optional[bigquery.Client] = None
        self._lock = asyncio.Lock()

    def _get_client(self) -> bigquery.Client:
        if self._client is None:
            self._client = bigquery.Client(project=PROJECT_ID)
        return self._client

    async def log(
        self,
        caller_id: str,
        tool_name: str,
        input_params: dict[str, Any],
        result_status: str,
        latency_ms: int,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Async streaming insert to BigQuery audit_log table.
        Non-blocking: runs the synchronous BQ insert in a thread pool executor.
        """
        row = {
            "caller_id": caller_id,
            "tool_name": tool_name,
            "input_params": json.dumps(input_params),
            "result_status": result_status,
            "latency_ms": latency_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_message": error_message,
        }

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._insert_row, row)
        except Exception as exc:  # noqa: BLE001
            # Audit logging must never break the tool call itself
            logger.error(f"Audit log write failed: {exc}")

    def _insert_row(self, row: dict) -> None:
        """Synchronous BigQuery streaming insert (runs in thread pool)."""
        client = self._get_client()
        errors = client.insert_rows_json(FULL_TABLE, [row])
        if errors:
            logger.error(f"BigQuery insert errors: {errors}")


# Module-level singleton used by tool decorators
_default_audit_logger = AuditLogger()


def get_audit_logger() -> AuditLogger:
    return _default_audit_logger


def audited_tool(tool_name: str):
    """
    Decorator factory for MCP tools.
    Automatically logs tool invocation start and end to BigQuery.
    
    Usage:
        @audited_tool("query_metrics")
        async def query_metrics(service: str, ..., caller_id: str = "") -> ...:
            ...
    """
    import functools

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            caller_id = kwargs.pop("caller_id", "unknown")
            input_params = {k: v for k, v in kwargs.items()}
            start_ms = time.monotonic()
            result_status = "success"
            error_msg = None

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as exc:
                result_status = "error"
                error_msg = str(exc)
                raise
            finally:
                latency_ms = int((time.monotonic() - start_ms) * 1000)
                audit = get_audit_logger()
                asyncio.create_task(
                    audit.log(
                        caller_id=caller_id,
                        tool_name=tool_name,
                        input_params=input_params,
                        result_status=result_status,
                        latency_ms=latency_ms,
                        error_message=error_msg,
                    )
                )

        return wrapper

    return decorator
