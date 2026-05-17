"""
MCP Tool: get_incident_timeline, list_active_alerts
Queries BigQuery for incident data and correlated events.
"""

import os
import logging
from datetime import timezone
from typing import Any, Optional

from fastmcp.tools.tool import Tool

from google.cloud import bigquery

logger = logging.getLogger("operaiq.tools.incidents")

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


def register_incident_tools(mcp) -> None:

    async def get_incident_timeline(incident_id: str) -> dict[str, Any]:
        """
        Get full incident details plus correlated events.

        Args:
            incident_id: UUID of the incident to retrieve.

        Returns:
            Dict with incident details and correlated_events list.
        """
        client = get_bq_client()

        # Step 1: Fetch the incident
        incident_query = """
            SELECT *
            FROM `{events_table}`
            WHERE event_type = 'incident'
              AND incident_id = @incident_id
            LIMIT 1
        """.format(events_table=EVENTS_TABLE)
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("incident_id", "STRING", incident_id),
            ]
        )

        try:
            incident_rows = list(
                client.query(incident_query, job_config=job_config).result()
            )
        except Exception as exc:
            logger.error(f"get_incident_timeline: BQ query failed: {exc}")
            raise RuntimeError(f"Failed to fetch incident: {exc}") from exc

        if not incident_rows:
            raise ValueError(f"Incident not found: {incident_id}")

        incident_row = incident_rows[0]
        incident = {
            "incident_id": incident_row.incident_id,
            "title": incident_row.title,
            "service": incident_row.service,
            "severity": incident_row.severity,
            "status": incident_row.status,
            "timestamp": incident_row.timestamp.isoformat(),
            "triggered_by_deployment_id": incident_row.triggered_by_deployment_id,
        }
        service = incident_row.service
        incident_time = incident_row.timestamp

        # Step 2: Fetch correlated events (±10 minutes, same service)
        corr_query = """
            SELECT event_type, timestamp, metric_type, value, deployment_id,
                   version, status AS event_status
            FROM `{events_table}`
            WHERE service = @service
              AND event_type IN ('metric', 'deployment')
              AND `timestamp` BETWEEN
                    TIMESTAMP_SUB(@incident_time, INTERVAL 10 MINUTE)
                    AND
                    TIMESTAMP_ADD(@incident_time, INTERVAL 10 MINUTE)
            ORDER BY `timestamp` ASC
            LIMIT 100
        """.format(events_table=EVENTS_TABLE)
        corr_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("service", "STRING", service),
                bigquery.ScalarQueryParameter(
                    "incident_time", "TIMESTAMP", incident_time.isoformat()
                ),
            ]
        )

        try:
            corr_rows = list(client.query(corr_query, job_config=corr_config).result())
        except Exception as exc:
            logger.error(f"get_incident_timeline: correlated events query failed: {exc}")
            corr_rows = []

        correlated_events = []
        for row in corr_rows:
            event = {"event_type": row.event_type, "timestamp": row.timestamp.isoformat()}
            if row.event_type == "metric":
                event["metric_type"] = row.metric_type
                event["value"] = float(row.value) if row.value is not None else None
            elif row.event_type == "deployment":
                event["deployment_id"] = row.deployment_id
                event["version"] = row.version
                event["status"] = row.event_status
            correlated_events.append(event)

        return {
            "incident": incident,
            "correlated_events": correlated_events,
            "timeline_window_minutes": 10,
        }

    async def list_active_alerts(severity_filter: str = "all") -> list[dict[str, Any]]:
        """
        List open incidents, optionally filtered by severity.

        Args:
            severity_filter: 'all', 'critical', 'warning', or 'info'.

        Returns:
            List of open incident dicts, ordered by timestamp DESC.
        """
        valid_severities = {"all", "critical", "warning", "info"}
        if severity_filter not in valid_severities:
            raise ValueError(f"severity_filter must be one of {valid_severities}")

        client = get_bq_client()

        if severity_filter == "all":
            where_clause = "status = 'open'"
            params = []
        else:
            where_clause = "status = 'open' AND severity = @severity"
            params = [bigquery.ScalarQueryParameter("severity", "STRING", severity_filter)]

        query = """
            SELECT incident_id, title, service, severity, status, timestamp,
                   triggered_by_deployment_id
            FROM `{events_table}`
            WHERE event_type = 'incident'
              AND {where_clause}
            ORDER BY timestamp DESC
            LIMIT 100
        """.format(events_table=EVENTS_TABLE, where_clause=where_clause)

        job_config = bigquery.QueryJobConfig(query_parameters=params)

        try:
            rows = list(client.query(query, job_config=job_config).result())
        except Exception as exc:
            logger.error(f"list_active_alerts failed: {exc}")
            raise RuntimeError(f"Failed to list alerts: {exc}") from exc

        return [
            {
                "incident_id": row.incident_id,
                "title": row.title,
                "service": row.service,
                "severity": row.severity,
                "status": row.status,
                "timestamp": row.timestamp.isoformat(),
                "triggered_by_deployment_id": row.triggered_by_deployment_id,
            }
            for row in rows
        ]

    _add_tool_with_param_descriptions(
        mcp,
        get_incident_timeline,
        description=(
            "Retrieves the full timeline for a specific incident, including the incident details "
            "plus all correlated events (metrics spikes and deployments) for the same service "
            "within ±10 minutes of when the incident was created. Essential for root cause analysis."
        ),
        param_descriptions={
            "incident_id": "Incident UUID to retrieve timeline and correlated events.",
        },
    )

    _add_tool_with_param_descriptions(
        mcp,
        list_active_alerts,
        description=(
            "Lists all currently open incidents from BigQuery, optionally filtered by severity. "
            "Use this to get a real-time snapshot of production health and active problems."
        ),
        param_descriptions={
            "severity_filter": "Severity filter: all, critical, warning, or info.",
        },
    )
