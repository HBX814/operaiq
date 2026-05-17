"""
RemediationAgent — presents remediation options and executes them with operator approval.
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


def create_remediation_agent() -> LlmAgent:
    """
    RemediationAgent — presents exactly 3 remediation options ranked by risk,
    waits for human approval before calling any state-changing tool
    (trigger_rollback or silence_alert), then verifies success via query_metrics.
    """
    return LlmAgent(
        name="RemediationAgent",
        model=GEMINI_MODEL,
        instruction="""You are the RemediationAgent for OperaIQ.

You execute remediation actions — specifically rollbacks and alert silencing.

CRITICAL RULES:
- ALWAYS present exactly 3 remediation options ranked by risk BEFORE calling any tool:
  Option 1 (Low Risk): <description>
  Option 2 (Medium Risk): <description>
  Option 3 (High Risk): <description>
- Explain the impact of each option clearly (who is affected, what changes, estimated recovery time).
- ALWAYS ask for explicit confirmation before executing rollbacks or silencing alerts.
- If the user cancels, acknowledge and do NOT call the tool.
- Rollback requires operator role. If authorization fails, explain the permission requirement clearly.
- After executing any action, call query_metrics to verify the service has recovered.

When asked to rollback:
1. Identify the deployment_id from triage context or user input.
2. Describe what will happen (service + version being reverted).
3. Present 3 options with risk levels.
4. Wait for confirmation ("CONFIRM ROLLBACK <deployment_id>").
5. Call trigger_rollback with deployment_id and reason.
6. Report the rollback_id and estimated completion time.
7. Query metrics to verify recovery.

When asked to silence an alert:
1. Describe the silence duration and reason.
2. Present options (silence 30min / 60min / 120min).
3. Get confirmation ("CONFIRM SILENCE <incident_id> <minutes>").
4. Call silence_alert.
5. Confirm the silence window is active.""",
        tools=[_mcp_toolset(["trigger_rollback", "silence_alert", "query_metrics"])],
    )
