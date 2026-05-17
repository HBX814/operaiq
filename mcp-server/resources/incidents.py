"""
MCP Resources: active_incidents — exposes currently open incidents as a static resource.
"""

import os
import logging
from typing import Any
from google.cloud import bigquery

logger = logging.getLogger("operaiq.resources.incidents")

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "operaiq")
DATASET_ID = os.environ.get(
    "BIGQUERY_DATASET", os.environ.get("BQ_DATASET", "operaiq")
)
EVENTS_TABLE = f"{PROJECT_ID}.{DATASET_ID}.events"


def register_incident_resources(mcp) -> None:

    @mcp.resource("resource://incidents/open")
    async def open_incidents() -> list[dict[str, Any]]:
        """
        Returns currently open incidents, ordered by severity then time.
        Provides the agent with an immediate view of production health.
        """
        client = bigquery.Client(project=PROJECT_ID)
        query = """
            SELECT incident_id, title, service, severity, status, timestamp
            FROM `{events_table}`
            WHERE event_type = 'incident' AND status = 'open'
            ORDER BY
                CASE severity
                    WHEN 'critical' THEN 1
                    WHEN 'warning' THEN 2
                    WHEN 'info' THEN 3
                    ELSE 4
                END,
                timestamp DESC
            LIMIT 100
        """.format(events_table=EVENTS_TABLE)
        try:
            rows = list(client.query(query).result())
        except Exception as exc:
            logger.error(f"open_incidents resource failed: {exc}")
            return []

        return [
            {
                "incident_id": r.incident_id,
                "title": r.title,
                "service": r.service,
                "severity": r.severity,
                "status": r.status,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in rows
        ]
