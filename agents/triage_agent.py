"""
TriageAgent — analyzes incidents, metrics, and runbooks to produce a triage report.
Imported by agents/main.py as a factory function.
"""

import os
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, SseServerParams

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:8080")
MCP_API_TOKEN = os.environ.get("MCP_API_TOKEN", os.environ.get("TEST_OPERATOR_TOKEN", "test-token"))


def _mcp_sse_url() -> str:
    base = MCP_SERVER_URL.rstrip("/")
    if not base.endswith("/mcp"):
        base = f"{base}/mcp"
    return f"{base}/sse"


def _mcp_toolset(tool_filter: list[str] | None = None) -> MCPToolset:
    return MCPToolset(
        connection_params=SseServerParams(
            url=_mcp_sse_url(),
            headers={"Authorization": f"Bearer {MCP_API_TOKEN}"},
        ),
        tool_filter=tool_filter,
    )


def create_triage_agent() -> LlmAgent:
    """
    TriageAgent — calls get_incident_timeline and search_runbooks in parallel,
    then queries metrics for the affected service, and synthesizes a structured
    triage report with severity, root cause, affected components, ranked actions,
    runbook sections, and similar past incidents.
    """
    return LlmAgent(
        name="TriageAgent",
        model=GEMINI_MODEL,
        instruction="""You are the TriageAgent for OperaIQ, a production operations platform.

Your job is to quickly analyze production incidents and assess their severity and likely root cause.

When given an incident ID or alert:
1. Call get_incident_timeline to retrieve the full incident details and correlated events.
2. In parallel (if possible), call search_runbooks with the service + incident title as query.
3. Call query_metrics for the affected service (error_rate and p99_latency_ms) for the last 60 min.
4. Synthesize your findings into a structured triage report:

   **TRIAGE SUMMARY**
   - Severity: <critical/warning/info>
   - Likely Root Cause: <1-2 specific sentences citing evidence> (<confidence>% confidence)
   - Affected Components: <list>
   - Recommended Immediate Actions (ranked by priority):
     1. <action>
     2. <action>
     3. <action>
   - Relevant Runbook Sections: <title and key steps>
   - Similar Past Incidents: <any patterns observed>

Be concise and actionable. Operators are under pressure.""",
        tools=[_mcp_toolset(["get_incident_timeline", "query_metrics", "search_runbooks"])],
    )
