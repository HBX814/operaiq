"""
OperaIQ Agent Orchestration — Google ADK multi-agent system.

Three specialized agents orchestrated by a root Coordinator:
  1. TriageAgent    — Analyzes metrics + timeline to assess severity
  2. RemediationAgent — Executes rollbacks and alert silencing (operator-gated)
  3. PostMortemAgent  — Generates and scores post-mortems

Entry points:
  POST /triage              — SSE stream of triage analysis
  POST /remediate           — SSE stream; pauses for approval before state changes
  POST /remediate/approve   — Approve a pending remediation action
  POST /remediate/deny      — Deny a pending remediation action
  POST /postmortem          — Generates post-mortem, returns doc ID
  WS   /ws/{session_id}     — WebSocket for general agentic chat
  POST /agent/{session_id}  — HTTP single-turn agent interaction
"""

import os
import json
import logging
import asyncio
import base64
from typing import AsyncIterator
from uuid import uuid4

try:
    from google.adk.agents import LlmAgent
    Agent = LlmAgent  # LlmAgent is the canonical agent class in google-adk
except ImportError:
    # google-adk not installed locally (IDE/dev environment) — runtime will have it
    LlmAgent = None  # type: ignore[assignment]
    Agent = None  # type: ignore[assignment]

try:
    from google.adk.tools.mcp_tool.mcp_toolset import McpToolset as MCPToolset, StreamableHTTPConnectionParams as _MCPParams
    _USE_HTTP = True
except ImportError:
    try:
        from google.adk.tools.mcp_tool.mcp_toolset import McpToolset as MCPToolset, SseConnectionParams as _MCPParams
        _USE_HTTP = False
    except ImportError:
        MCPToolset = None
        _MCPParams = None
        _USE_HTTP = False

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn

logger = logging.getLogger("operaiq.agents")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:8080")
MCP_API_TOKEN = os.environ.get("MCP_API_TOKEN", os.environ.get("TEST_OPERATOR_TOKEN", "test-token"))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
APP_NAME = "operaiq-agents"

if GEMINI_API_KEY:
    os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY

# In-memory store for pending remediation approvals
# {session_id: {"future": asyncio.Future, "action": dict}}
_pending_approvals: dict[str, dict] = {}


def _mcp_url() -> str:
    """Build the MCP server endpoint URL for the Streamable HTTP transport."""
    base = MCP_SERVER_URL.rstrip("/")
    if not base.endswith("/sse"):
        base = f"{base}/sse"
    return base


def _mcp_toolset(tool_filter: list[str] | None = None):
    """Create an MCP toolset pointing to our MCP server with auth headers.
    Supports both Streamable HTTP and SSE transports depending on ADK version.
    Falls back to a no-op list if MCPToolset is not available (unit tests).
    """
    if MCPToolset is None:
        return None  # Graceful degradation for test environments

    url = _mcp_url()
    auth_headers = {"Authorization": f"Bearer {MCP_API_TOKEN}"}

    try:
        if _USE_HTTP:
            # ADK >= 1.0 with StreamableHTTP support
            params = _MCPParams(url=url, headers=auth_headers)
        else:
            # ADK with SSE transport — use /sse suffix
            params = _MCPParams(url=f"{url}/sse", headers=auth_headers)

        return MCPToolset(
            connection_params=params,
            tool_filter=tool_filter,
        )
    except Exception as exc:
        logger.warning(f"MCPToolset init failed (non-fatal in dev): {exc}")
        return None


# ---------------------------------------------------------------------------
# Agent Definitions
# ---------------------------------------------------------------------------

def create_triage_agent() -> LlmAgent:
    """Analyzes an incident and its metric timeline to assess root cause."""
    return LlmAgent(
        name="TriageAgent",
        model=GEMINI_MODEL,
        instruction="""You are the TriageAgent for OperaIQ, a production operations platform.

Your job is to quickly analyze production incidents and assess their severity and likely root cause.

When given an incident ID or alert:
1. Call get_incident_timeline to retrieve the full incident details and correlated events.
2. Call query_metrics for the affected service to understand the metric trend.
3. Call search_runbooks to find relevant troubleshooting procedures.
4. Synthesize your findings into a concise triage summary:
   - Severity assessment (critical/warning/info)
   - Likely root cause (be specific, cite evidence from events)
   - Immediate recommended action (rollback/investigate/monitor)
   - Relevant runbook steps to follow

Be concise and actionable. Operators are under pressure.
Format your response as:
**TRIAGE SUMMARY**
- Severity: <level>
- Root Cause: <1-2 sentences>
- Recommended Action: <specific action>
- Runbook: <key steps>""",
        tools=[t for t in [_mcp_toolset(["get_incident_timeline", "query_metrics", "search_runbooks"])] if t],
    )


def create_remediation_agent() -> LlmAgent:
    """Executes remediation actions (rollbacks, silencing) with operator approval."""
    return LlmAgent(
        name="RemediationAgent",
        model=GEMINI_MODEL,
        instruction="""You are the RemediationAgent for OperaIQ.

You execute remediation actions — specifically rollbacks and alert silencing.

IMPORTANT RULES:
- ALWAYS explain what you are about to do BEFORE calling trigger_rollback or silence_alert.
- Present exactly 3 remediation options ranked by risk (low/medium/high).
- Explain the impact of each option clearly.
- ALWAYS ask for explicit confirmation before executing state-changing actions.
- If the user cancels, acknowledge and do NOT call the tool.
- Rollback requires operator role. If authorization fails, explain the permission requirement clearly.

When asked to rollback:
1. Identify the deployment_id (from triage context or user input).
2. Describe what will happen (service + version being reverted).
3. Present 3 options with risk levels.
4. Wait for confirmation.
5. Call trigger_rollback with the deployment_id and reason.
6. Report the rollback_id and estimated completion time.
7. Verify success by querying metrics again.

When asked to silence an alert:
1. Describe the silence duration and reason.
2. Get confirmation.
3. Call silence_alert.
4. Confirm the silence window.""",
        tools=[t for t in [_mcp_toolset(["trigger_rollback", "silence_alert", "query_metrics"])] if t],
    )


def create_postmortem_agent() -> LlmAgent:
    """Generates and quality-scores post-mortems."""
    return LlmAgent(
        name="PostMortemAgent",
        model=GEMINI_MODEL,
        instruction="""You are the PostMortemAgent for OperaIQ.

You generate comprehensive post-mortems for production incidents.

When asked to create a post-mortem:
1. Call create_postmortem_draft with the incident_id.
2. Review the generated sections for completeness:
   - Does the summary clearly state impact (users affected, duration, business impact)?
   - Is the timeline accurate and detailed enough?
   - Does the root cause go beyond symptoms to actual causes?
   - Are action items specific, measurable, and have clear owners?
   - Are lessons learned genuinely insightful?
3. Calculate a quality score (0-100):
   - +20: Summary mentions user impact + business impact
   - +20: Timeline has >= 5 events
   - +20: Root cause is specific (not vague)
   - +20: >= 3 action items with owners and due dates
   - +20: >= 2 lessons learned

Present the post-mortem in a readable format, then state the quality score with explanation.
Suggest specific improvements for any sections scoring 0.

Your response format:
**POST-MORTEM: <title>**
[formatted sections]

**QUALITY SCORE: <n>/100**
- Breakdown: [section scores]
- Suggested improvements: [if any]""",
        tools=[t for t in [_mcp_toolset(["create_postmortem_draft", "get_incident_timeline"])] if t],
    )


def create_coordinator_agent(triage, remediation, postmortem) -> LlmAgent:
    """Root orchestrator that routes user requests to specialized sub-agents."""
    return LlmAgent(
        name="CoordinatorAgent",
        model=GEMINI_MODEL,
        instruction="""You are the CoordinatorAgent for OperaIQ, an AI-powered production operations platform.

You route user requests to specialized sub-agents:
- TriageAgent: Analyzing incidents, metrics, and finding runbook procedures
- RemediationAgent: Executing rollbacks and silencing alerts (requires operator confirmation)
- PostMortemAgent: Generating and scoring post-mortem documents

Routing rules:
- "investigate", "what's wrong", "analyze", "triage", "metrics", "runbook" → TriageAgent
- "rollback", "silence", "fix", "remediate", "deploy" → RemediationAgent
- "post-mortem", "postmortem", "write up", "document" → PostMortemAgent
- General production questions → Answer directly if possible, else delegate

Always introduce yourself briefly on the first message.
Maintain context across the conversation — if the user is in the middle of a triage,
pass that context to the RemediationAgent if they ask to act on it.

Be professional, concise, and production-focused.""",
        sub_agents=[triage, remediation, postmortem],
    )


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------

async def _run_agent_sse(
    agent: LlmAgent,
    message: str,
    session_id: str,
    session_service: InMemorySessionService,
    check_approval: bool = False,
    approval_session_id: str | None = None,
) -> AsyncIterator[str]:
    """
    Run an ADK agent and yield SSE-formatted event strings.

    Event types:
      tool_call       — agent is calling an MCP tool
      tool_result     — result returned from MCP tool
      text            — text chunk from agent
      awaiting_approval — agent wants human sign-off before state-changing tool
      done            — agent finished, summary included
      error           — unhandled exception
    """
    def _sse(event_type: str, data: dict) -> str:
        return f"data: {json.dumps({'type': event_type, **data})}\n\n"

    runner = Runner(
        agent=agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    user_id = f"sse-user-{session_id}"
    try:
        await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
    except Exception:
        pass  # session might already exist

    content = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=message)],
    )

    full_text = ""
    tool_calls_log = []

    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content,
        ):
            # ── Tool call event ──────────────────────────────────────────────
            if hasattr(event, "tool_call") and event.tool_call:
                tc = event.tool_call
                tool_name = tc.name
                tool_input = dict(tc.args) if tc.args else {}

                # Check if this is a state-changing tool that needs approval
                state_changing = {"trigger_rollback", "silence_alert"}
                if check_approval and tool_name in state_changing and approval_session_id:
                    # Emit awaiting_approval — frontend must POST /remediate/approve or /deny
                    action = {"tool": tool_name, "input": tool_input}
                    future: asyncio.Future = asyncio.get_event_loop().create_future()
                    _pending_approvals[approval_session_id] = {
                        "future": future,
                        "action": action,
                    }
                    yield _sse("awaiting_approval", {"action": action, "session_id": approval_session_id})

                    # Wait for approval (max 5 min)
                    try:
                        approved = await asyncio.wait_for(future, timeout=300)
                    except asyncio.TimeoutError:
                        approved = False

                    if not approved:
                        yield _sse("text", {"content": f"❌ Action `{tool_name}` denied by operator. Skipping."})
                        continue

                tool_calls_log.append({"tool": tool_name, "input": tool_input})
                yield _sse("tool_call", {"tool": tool_name, "input": tool_input})

            # ── Tool result event ────────────────────────────────────────────
            if hasattr(event, "tool_response") and event.tool_response:
                tr = event.tool_response
                yield _sse("tool_result", {
                    "tool": tr.name if hasattr(tr, "name") else "unknown",
                    "result": tr.response if hasattr(tr, "response") else str(tr),
                })

            # ── Text chunks ──────────────────────────────────────────────────
            if hasattr(event, "content") and event.content:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        full_text += part.text
                        yield _sse("text", {"content": part.text})

        yield _sse("done", {"summary": full_text, "tool_calls": tool_calls_log})

    except Exception as exc:
        logger.error(f"SSE agent error: {exc}")
        yield _sse("error", {"message": str(exc)})


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(title="OperaIQ Agent Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://operaiq-frontend-349176795620.us-central1.run.app", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

session_service = InMemorySessionService()


@app.get("/")
async def root():
    return {
        "service": "operaiq-agent-service",
        "version": "1.0.0",
        "status": "ok",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
async def health():
    return {"status": "ok", "service": "agent-service"}


# ---------------------------------------------------------------------------
# SSE Endpoints
# ---------------------------------------------------------------------------

@app.post("/triage")
async def triage_endpoint(body: dict):
    """
    POST /triage  — accepts {incident_id: str}
    Streams SSE: tool_call / tool_result / text / done / error
    """
    incident_id = body.get("incident_id")
    if not incident_id:
        raise HTTPException(status_code=422, detail="'incident_id' required")

    session_id = body.get("session_id", str(uuid4()))
    message = (
        f"Please triage incident {incident_id}. "
        "Call get_incident_timeline, then query_metrics for the affected service, "
        "then search_runbooks. Provide a structured triage report."
    )

    agent = create_triage_agent()

    async def _gen():
        async for chunk in _run_agent_sse(agent, message, session_id, session_service):
            yield chunk

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.post("/remediate")
async def remediate_endpoint(body: dict):
    """
    POST /remediate  — accepts {incident_id: str, suggested_action: str}
    Streams SSE. Pauses with 'awaiting_approval' before state-changing tools.
    Frontend must POST to /remediate/approve or /remediate/deny with the session_id.
    """
    incident_id = body.get("incident_id")
    suggested_action = body.get("suggested_action", "")
    if not incident_id:
        raise HTTPException(status_code=422, detail="'incident_id' required")

    session_id = body.get("session_id", str(uuid4()))
    message = (
        f"Please remediate incident {incident_id}. "
        f"Suggested action: {suggested_action}. "
        "Present 3 options ranked by risk. Await approval before executing."
    )

    agent = create_remediation_agent()

    async def _gen():
        async for chunk in _run_agent_sse(
            agent,
            message,
            session_id,
            session_service,
            check_approval=True,
            approval_session_id=session_id,
        ):
            yield chunk

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.post("/remediate/approve")
async def remediate_approve(body: dict):
    """Approve a pending remediation action."""
    session_id = body.get("session_id")
    if not session_id or session_id not in _pending_approvals:
        raise HTTPException(status_code=404, detail="No pending approval for this session_id")

    entry = _pending_approvals.pop(session_id)
    entry["future"].set_result(True)
    return {"status": "approved", "session_id": session_id, "action": entry["action"]}


@app.post("/remediate/deny")
async def remediate_deny(body: dict):
    """Deny a pending remediation action."""
    session_id = body.get("session_id")
    if not session_id or session_id not in _pending_approvals:
        raise HTTPException(status_code=404, detail="No pending approval for this session_id")

    entry = _pending_approvals.pop(session_id)
    entry["future"].set_result(False)
    return {"status": "denied", "session_id": session_id, "action": entry["action"]}


@app.post("/postmortem")
async def postmortem_endpoint(body: dict):
    """
    POST /postmortem  — accepts {incident_id: str}
    Runs PostMortemAgent synchronously, returns {postmortem_id, quality_score, document_url}.
    """
    incident_id = body.get("incident_id")
    if not incident_id:
        raise HTTPException(status_code=422, detail="'incident_id' required")

    session_id = str(uuid4())
    message = (
        f"Create a post-mortem for incident {incident_id}. "
        "Call create_postmortem_draft, then review and score it 0-100."
    )

    agent = create_postmortem_agent()

    full_text = ""
    postmortem_id = None

    async for chunk_str in _run_agent_sse(agent, message, session_id, session_service):
        try:
            data = json.loads(chunk_str.removeprefix("data: "))
            if data.get("type") == "done":
                full_text = data.get("summary", "")
            elif data.get("type") == "tool_result":
                result = data.get("result", {})
                if isinstance(result, dict) and "postmortem_id" in result:
                    postmortem_id = result["postmortem_id"]
        except Exception:
            pass

    return {
        "postmortem_id": postmortem_id or f"pm-{incident_id}",
        "document_url": f"/postmortems/{postmortem_id or incident_id}",
        "summary": full_text[:500],
    }


# ---------------------------------------------------------------------------
# WebSocket endpoint (general agentic chat)
# ---------------------------------------------------------------------------
@app.websocket("/ws/{session_id}")
async def websocket_agent(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for streaming agent responses in the chat drawer."""
    await websocket.accept()
    logger.info(f"WebSocket connected: session={session_id}")

    triage = create_triage_agent()
    remediation = create_remediation_agent()
    postmortem = create_postmortem_agent()
    coordinator = create_coordinator_agent(triage, remediation, postmortem)

    runner = Runner(
        agent=coordinator,
        app_name=APP_NAME,
        session_service=session_service,
    )

    user_id = "ws-user"
    try:
        await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
    except Exception:
        pass

    try:
        while True:
            raw = await websocket.receive_text()
            payload = json.loads(raw)
            user_message = payload.get("message", "")

            if not user_message:
                continue

            content = genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=user_message)],
            )

            await websocket.send_json({"type": "thinking", "session_id": session_id})

            full_response = ""
            tool_calls = []

            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=content,
            ):
                if hasattr(event, "tool_call") and event.tool_call:
                    tc = event.tool_call
                    tool_calls.append({"tool": tc.name, "input": dict(tc.args) if tc.args else {}})
                    await websocket.send_json({
                        "type": "tool_call",
                        "tool": tc.name,
                        "input": dict(tc.args) if tc.args else {},
                    })

                if hasattr(event, "content") and event.content:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            full_response += part.text
                            await websocket.send_json({
                                "type": "chunk",
                                "content": part.text,
                            })

            await websocket.send_json({
                "type": "complete",
                "content": full_response,
                "tool_calls": tool_calls,
                "session_id": session_id,
            })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: session={session_id}")
    except Exception as exc:
        logger.error(f"WebSocket error: {exc}")
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass


# ---------------------------------------------------------------------------
# HTTP single-turn endpoint
# ---------------------------------------------------------------------------
@app.post("/agent/{session_id}")
async def http_agent(session_id: str, body: dict):
    """HTTP endpoint for single-turn agent interactions (non-streaming)."""
    user_message = body.get("message", "")
    if not user_message:
        raise HTTPException(status_code=400, detail="'message' field required")

    triage = create_triage_agent()
    remediation = create_remediation_agent()
    postmortem = create_postmortem_agent()
    coordinator = create_coordinator_agent(triage, remediation, postmortem)

    runner = Runner(
        agent=coordinator,
        app_name=APP_NAME,
        session_service=session_service,
    )

    user_id = "http-user"
    try:
        await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
    except Exception:
        pass

    content = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=user_message)],
    )

    full_response = ""
    tool_calls = []

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):
        if hasattr(event, "tool_call") and event.tool_call:
            tool_calls.append({"tool": event.tool_call.name})
        if hasattr(event, "content") and event.content:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    full_response += part.text

    return {
        "session_id": session_id,
        "response": full_response,
        "tool_calls": tool_calls,
    }


# ---------------------------------------------------------------------------
# Pub/Sub push endpoint
# ---------------------------------------------------------------------------
@app.post("/pubsub")
async def pubsub_endpoint(request: Request, background_tasks: BackgroundTasks):
    """
    POST /pubsub — endpoint for GCP Pub/Sub push subscription.
    """
    try:
        body = await request.json()
        message = body.get("message", {})
        data_b64 = message.get("data")
        
        if data_b64:
            data_json = base64.b64decode(data_b64).decode("utf-8")
            event_data = json.loads(data_json)
            
            logger.info(f"Received Pub/Sub event: {event_data}")
            event_type = event_data.get("type", "")
            
            if event_type == "incident":
                incident_id = event_data.get("incident_id", "unknown")
                logger.info(f"Triggering background triage for incident {incident_id}")
                
                # Run the triage agent in background
                session_id = f"pubsub-triage-{incident_id}-{uuid4().hex[:8]}"
                agent_msg = (
                    f"Please triage incident {incident_id}. "
                    "Call get_incident_timeline, then query_metrics for the affected service, "
                    "then search_runbooks. Provide a structured triage report."
                )
                
                async def run_triage_bg():
                    triage_agent = create_triage_agent()
                    try:
                        async for _ in _run_agent_sse(triage_agent, agent_msg, session_id, session_service):
                            pass
                        logger.info(f"Background triage completed for {incident_id}")
                    except Exception as e:
                        logger.error(f"Background triage failed: {e}")
                
                background_tasks.add_task(run_triage_bg)
                
    except Exception as exc:
        logger.error(f"Error processing pubsub message: {exc}")
        
    return {"status": "received"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8081"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False, log_level="info")
