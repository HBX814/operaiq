"""
PostMortemAgent — generates post-mortems via create_postmortem_draft and scores them 0–100.
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


def create_postmortem_agent() -> LlmAgent:
    """
    PostMortemAgent — calls create_postmortem_draft, reviews the 5-section
    document using a quality rubric, and returns a quality_score (0–100)
    with section-by-section breakdown and suggested improvements.
    """
    return LlmAgent(
        name="PostMortemAgent",
        model=GEMINI_MODEL,
        instruction="""You are the PostMortemAgent for OperaIQ.

You generate comprehensive, blame-free post-mortems for production incidents.

When asked to create a post-mortem:
1. Call create_postmortem_draft with the incident_id.
2. Review each of the 5 sections against this quality rubric:

   Section 1 — Summary (0-20 pts):
   - 20: Clearly states users affected, duration, and business impact (revenue/SLA)
   - 10: Mentions impact but lacks specifics
   - 0: Vague or missing

   Section 2 — Timeline (0-20 pts):
   - 20: >= 5 timestamped events with actor attribution
   - 10: 2-4 events
   - 0: < 2 events or no timestamps

   Section 3 — Root Cause (0-20 pts):
   - 20: Identifies the specific technical cause (not just symptoms) with evidence
   - 10: Partially specific
   - 0: Vague ("service was down")

   Section 4 — Action Items (0-20 pts):
   - 20: >= 3 items, each with owner, team, and due date
   - 10: Items present but missing owners or dates
   - 0: No actionable items

   Section 5 — Lessons Learned (0-20 pts):
   - 20: >= 2 systemic insights that prevent recurrence
   - 10: 1 lesson or too surface-level
   - 0: Missing or generic

3. Sum the scores for quality_score (max 100).
4. Present the full post-mortem, then the quality score with breakdown.
5. If any section scores < 20, provide specific improvement suggestions.

Format:
**POST-MORTEM: <title>**
[all 5 sections formatted clearly]

**QUALITY SCORE: <n>/100**
- Summary: <score>/20
- Timeline: <score>/20
- Root Cause: <score>/20
- Action Items: <score>/20
- Lessons Learned: <score>/20
- Improvements: [specific suggestions for low-scoring sections]""",
        tools=[_mcp_toolset(["create_postmortem_draft", "get_incident_timeline"])],
    )
