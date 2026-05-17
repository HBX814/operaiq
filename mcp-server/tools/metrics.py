"""
MCP Tool: query_metrics
Queries BigQuery for time-series metric data using parameterized queries only.
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastmcp.tools.tool import Tool

from google.cloud import bigquery

logger = logging.getLogger("operaiq.tools.metrics")

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "operaiq")
DATASET_ID = os.environ.get(
    "BIGQUERY_DATASET", os.environ.get("BQ_DATASET", "operaiq")
)
EVENTS_TABLE = f"{PROJECT_ID}.{DATASET_ID}.events"


def get_bq_client() -> bigquery.Client:
    return bigquery.Client(project=PROJECT_ID)


def _add_tool_with_param_descriptions(
    mcp,
    fn,
    description: str,
    param_descriptions: dict[str, str],
) -> None:
    tool = Tool.from_function(fn, description=description)
    properties = tool.parameters.get("properties", {})
    for name, desc in param_descriptions.items():
        if name in properties:
            properties[name]["description"] = desc
    mcp.add_tool(tool)


def register_metrics_tools(mcp) -> None:
    """Register all metrics-related tools onto the FastMCP instance."""

    async def query_metrics(
        service: str,
        metric_type: str,
        minutes_back: int = 60,
    ) -> list[dict[str, Any]]:
        """
        Query production metrics for a service.

        Args:
            service: Service name (payments, auth, inventory, notifications, search).
            metric_type: One of error_rate, p99_latency_ms, cpu_percent, request_rate.
            minutes_back: How many minutes of history to retrieve (default: 60).

        Returns:
            List of {timestamp, value} dicts ordered by time ascending.
        """
        if minutes_back < 1 or minutes_back > 10080:  # max 1 week
            raise ValueError("minutes_back must be between 1 and 10080")

        env = os.environ.get("ENV", "production").lower()
        if env in {"test", "development", "dev"}:
            now = datetime.now(timezone.utc)
            return [
                {
                    "timestamp": (now - timedelta(minutes=i)).isoformat(),
                    "value": 0.0,
                }
                for i in range(min(5, minutes_back))
            ]

        client = get_bq_client()

        # IMPORTANT: Always use parameterized queries — never f-strings with user input
        query = """
            SELECT
                TIMESTAMP_TRUNC(`timestamp`, MINUTE) AS timestamp,
                AVG(value) AS value
            FROM `{events_table}`
            WHERE
                event_type = 'metric'
                AND service = @service
                AND metric_type = @metric_type
                AND `timestamp` >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @minutes_back MINUTE)
            GROUP BY 1
            ORDER BY 1 ASC
        """.format(events_table=EVENTS_TABLE)

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("service", "STRING", service),
                bigquery.ScalarQueryParameter("metric_type", "STRING", metric_type),
                bigquery.ScalarQueryParameter("minutes_back", "INT64", minutes_back),
            ]
        )

        try:
            rows = list(client.query(query, job_config=job_config).result())
            return [
                {
                    "timestamp": row.timestamp.isoformat(),
                    "value": float(row.value),
                }
                for row in rows
            ]
        except Exception as exc:
            logger.error(f"query_metrics failed: {exc}")
            raise RuntimeError(f"Failed to query metrics: {exc}") from exc

    _add_tool_with_param_descriptions(
        mcp,
        query_metrics,
        description=(
            "Retrieves time-series metric data for a specific service from BigQuery. "
            "Use this to understand trends in error rate, latency, CPU usage, or request rate "
            "over the specified time window."
        ),
        param_descriptions={
            "service": "Service name (payments, auth, inventory, notifications, search).",
            "metric_type": "Metric type: error_rate, p99_latency_ms, cpu_percent, request_rate.",
            "minutes_back": "How many minutes of history to retrieve (1-10080).",
        },
    )
