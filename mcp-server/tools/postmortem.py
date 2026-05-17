"""
MCP Tool: create_postmortem_draft
Calls Gemini 2.0 Flash to generate a structured post-mortem from incident data.
"""

import os
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastmcp.tools.tool import Tool

try:
    # google-genai >= 1.0 (new SDK)
    import google.genai as genai
    from google.genai import types as genai_types
    _USE_NEW_SDK = True
except ImportError:
    # Fallback to deprecated google.generativeai
    import google.generativeai as genai  # type: ignore
    _USE_NEW_SDK = False
from google.cloud import firestore

logger = logging.getLogger("operaiq.tools.postmortem")

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "operaiq")
DATASET_ID = os.environ.get(
    "BIGQUERY_DATASET", os.environ.get("BQ_DATASET", "operaiq")
)
EVENTS_TABLE = f"{PROJECT_ID}.{DATASET_ID}.events"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
POSTMORTEMS_COLLECTION = os.environ.get(
    "FIRESTORE_COLLECTION_POSTMORTEMS", "postmortems"
)


def get_firestore() -> firestore.AsyncClient:
    return firestore.AsyncClient(project=PROJECT_ID)


def _build_prompt(incident: dict, correlated_events: list, recent_deployments: list) -> str:
    return f"""You are an expert SRE writing a post-mortem for a production incident.
Write a structured post-mortem with EXACTLY these 5 sections.
Be factual, blame-free, and include measurable action items.

INCIDENT DETAILS:
- ID: {incident.get('incident_id')}
- Title: {incident.get('title')}
- Service: {incident.get('service')}
- Severity: {incident.get('severity')}
- Status: {incident.get('status')}
- Time: {incident.get('timestamp')}

CORRELATED EVENTS:
{_format_events(correlated_events)}

RECENT DEPLOYMENTS:
{_format_events(recent_deployments)}

Write the post-mortem in this EXACT JSON format:
{{
  "summary": "2-3 sentence executive summary of what happened and impact",
  "timeline": [
    {{"time": "HH:MM UTC", "event": "description"}},
    ...
  ],
  "root_cause": "Detailed technical root cause analysis (3-5 sentences)",
  "action_items": [
    {{"item": "action description", "owner": "team/role", "due_date": "YYYY-MM-DD", "priority": "high/medium/low"}},
    ...
  ],
  "lessons_learned": [
    "Lesson 1",
    "Lesson 2",
    ...
  ]
}}

Respond with ONLY the JSON, no markdown code blocks."""


def _format_events(events: list) -> str:
    if not events:
        return "  (none)"
    lines = []
    for e in events[:10]:  # limit to avoid token overflow
        lines.append(f"  - {e}")
    return "\n".join(lines)


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


def register_postmortem_tools(mcp) -> None:

    async def create_postmortem_draft(incident_id: str) -> dict[str, Any]:
        """
        Generate a post-mortem draft for an incident.

        Args:
            incident_id: UUID of the incident.

        Returns:
            {postmortem_id, document_url, quality_score, sections}
        """
        # Import here to avoid circular imports
        from tools.incidents import get_bq_client
        from google.cloud import bigquery

        # Fetch incident timeline
        client = get_bq_client()
        incident_query = """
            SELECT * FROM `{events_table}`
            WHERE event_type = 'incident' AND incident_id = @incident_id
            LIMIT 1
        """.format(events_table=EVENTS_TABLE)
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("incident_id", "STRING", incident_id)
            ]
        )
        rows = list(client.query(incident_query, job_config=job_config).result())
        if not rows:
            raise ValueError(f"Incident not found: {incident_id}")

        inc = rows[0]
        incident = {
            "incident_id": inc.incident_id,
            "title": inc.title,
            "service": inc.service,
            "severity": inc.severity,
            "status": inc.status,
            "timestamp": inc.timestamp.isoformat(),
        }

        # Fetch correlated events
        corr_query = """
            SELECT event_type, timestamp, metric_type, value, deployment_id, version, status
            FROM `{events_table}`
            WHERE service = @service
              AND event_type IN ('metric', 'deployment')
              AND timestamp BETWEEN
                TIMESTAMP_SUB(@ts, INTERVAL 10 MINUTE)
                AND TIMESTAMP_ADD(@ts, INTERVAL 10 MINUTE)
            ORDER BY timestamp ASC LIMIT 20
        """.format(events_table=EVENTS_TABLE)
        corr_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("service", "STRING", inc.service),
                bigquery.ScalarQueryParameter("ts", "TIMESTAMP", inc.timestamp.isoformat()),
            ]
        )
        corr_rows = list(client.query(corr_query, job_config=corr_config).result())
        correlated_events = [dict(r) for r in corr_rows]

        # Fetch last 5 deployments
        dep_query = """
            SELECT deployment_id, version, status, timestamp
            FROM `{events_table}`
            WHERE event_type = 'deployment' AND service = @service
            ORDER BY timestamp DESC LIMIT 5
        """.format(events_table=EVENTS_TABLE)
        dep_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("service", "STRING", inc.service)]
        )
        dep_rows = list(client.query(dep_query, job_config=dep_config).result())
        recent_deployments = [dict(r) for r in dep_rows]

        # Build the prompt from gathered incident data
        ai_prompt = _build_prompt(incident, correlated_events, recent_deployments)

        # Call Gemini using the appropriate SDK
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY environment variable not set")

        try:
            if _USE_NEW_SDK:
                # google-genai >= 1.0
                genai_client = genai.Client(api_key=GEMINI_API_KEY)
                response = genai_client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=ai_prompt,
                )
                raw_text = response.text
            else:
                # Legacy google.generativeai
                genai.configure(api_key=GEMINI_API_KEY)  # type: ignore
                model = genai.GenerativeModel(GEMINI_MODEL)  # type: ignore
                response = model.generate_content(ai_prompt)
                raw_text = response.text

            import json
            sections = json.loads(raw_text)
        except Exception as exc:
            logger.error(f"Gemini generation failed: {exc}")
            raise RuntimeError(f"Post-mortem generation failed: {exc}") from exc

        # Save to Firestore
        postmortem_id = incident_id
        now = datetime.now(timezone.utc).isoformat()
        db = get_firestore()
        doc_data = {
            "postmortem_id": postmortem_id,
            "incident_id": incident_id,
            "incident_title": incident.get("title"),
            "service": incident.get("service"),
            "created_at": now,
            "sections": sections,
            "quality_score": None,  # Scored by PostMortemAgent
        }
        await db.collection(POSTMORTEMS_COLLECTION).document(postmortem_id).set(doc_data)

        return {
            "postmortem_id": postmortem_id,
            "document_url": f"/postmortems/{postmortem_id}",
            "sections": sections,
        }

    _add_tool_with_param_descriptions(
        mcp,
        create_postmortem_draft,
        description=(
            "Generates an AI-powered post-mortem draft for an incident using Gemini 2.0 Flash. "
            "Automatically fetches the incident timeline and synthesizes a structured document with "
            "5 sections: Summary, Timeline, Root Cause, Action Items, Lessons Learned. "
            "Saves the draft to Firestore and returns the document ID."
        ),
        param_descriptions={
            "incident_id": "Incident UUID to generate a post-mortem draft for.",
        },
    )
