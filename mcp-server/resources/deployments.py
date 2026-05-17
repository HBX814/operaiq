"""
MCP Resources: recent_deployments — exposes the last 50 deployments as a static resource.
"""

import os
import logging
from typing import Any
from google.cloud import bigquery

logger = logging.getLogger("operaiq.resources.deployments")

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "operaiq")
DATASET_ID = os.environ.get(
    "BIGQUERY_DATASET", os.environ.get("BQ_DATASET", "operaiq")
)
EVENTS_TABLE = f"{PROJECT_ID}.{DATASET_ID}.events"


def register_deployment_resources(mcp) -> None:

    @mcp.resource("resource://deployments/recent")
    async def recent_deployments() -> list[dict[str, Any]]:
        """
        Returns the 50 most recent deployments across all services.
        Used by the agent to understand recent change history before triage.
        """
        client = bigquery.Client(project=PROJECT_ID)
        query = """
            SELECT deployment_id, service, version, status, timestamp, region
            FROM `{events_table}`
            WHERE event_type = 'deployment'
            ORDER BY timestamp DESC
            LIMIT 50
        """.format(events_table=EVENTS_TABLE)
        try:
            rows = list(client.query(query).result())
        except Exception as exc:
            logger.error(f"recent_deployments resource failed: {exc}")
            return []

        return [
            {
                "deployment_id": r.deployment_id,
                "service": r.service,
                "version": r.version,
                "status": r.status,
                "timestamp": r.timestamp.isoformat(),
                "region": r.region,
            }
            for r in rows
        ]
