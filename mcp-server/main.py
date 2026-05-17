"""
OperaIQ MCP Server — main entry point.

Transport: Streamable HTTP via FastMCP, mounted on FastAPI at /mcp.
Auth: OAuth 2.0 Bearer token validation on every request.
Audit: Every tool call logged to BigQuery audit_log.
Rate Limiting: 60 calls/min per caller_id (token bucket).
"""

import os
import sys
import json
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastmcp import FastMCP

# Internal modules
from auth import verify_token, TokenClaims
from audit import AuditLogger, get_audit_logger
from tools.metrics import register_metrics_tools
from tools.incidents import register_incident_tools
from tools.runbooks import register_runbook_tools
from tools.remediation import register_remediation_tools
from tools.postmortem import register_postmortem_tools
from resources.deployments import register_deployment_resources
from resources.incidents import register_incident_resources
from resources.runbooks import register_runbook_resources

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("operaiq.mcp")

# ---------------------------------------------------------------------------
# Rate limiter (token bucket, 60 req/min per caller)
# ---------------------------------------------------------------------------
import time
from collections import defaultdict

_rate_buckets: dict[str, dict[str, float]] = defaultdict(
    lambda: {"tokens": float(RATE_LIMIT), "last_refill": time.monotonic()}
)
RATE_LIMIT = 60  # requests per 60 seconds
RATE_WINDOW_SECONDS = 60.0
RATE_REFILL_PER_SECOND = RATE_LIMIT / RATE_WINDOW_SECONDS


def _check_rate_limit(caller_id: str) -> bool:
    """Returns True if allowed, False if rate-limited."""
    now = time.monotonic()
    bucket = _rate_buckets[caller_id]
    elapsed = max(0.0, now - bucket["last_refill"])
    bucket["tokens"] = min(
        float(RATE_LIMIT), bucket["tokens"] + (elapsed * RATE_REFILL_PER_SECOND)
    )
    bucket["last_refill"] = now

    if bucket["tokens"] < 1.0:
        return False

    bucket["tokens"] -= 1.0
    return True


# ---------------------------------------------------------------------------
# FastMCP instance
# ---------------------------------------------------------------------------
mcp = FastMCP(
    name="OperaIQ Production Intelligence MCP Server",
    instructions=(
        "You are connected to the OperaIQ MCP server. "
        "You can query real-time production metrics, manage incidents, "
        "search runbooks, trigger rollbacks, and create post-mortems. "
        "All actions require authentication and are audit-logged."
    ),
)

# Register all tools
register_metrics_tools(mcp)
register_incident_tools(mcp)
register_runbook_tools(mcp)
register_remediation_tools(mcp)
register_postmortem_tools(mcp)

# Register all resources
register_deployment_resources(mcp)
register_incident_resources(mcp)
register_runbook_resources(mcp)


# ---------------------------------------------------------------------------
# MCP Prompt template: incident_triage_prompt
# Consumed by TriageAgent to seed its first message with full context.
# ---------------------------------------------------------------------------
@mcp.prompt()
async def incident_triage_prompt(incident_id: str) -> str:
    """Returns a fully-populated triage prompt including the incident timeline,
    the 3 most relevant runbook sections, and the last 5 deployments for the
    affected service. Feed this directly to TriageAgent as the first message."""
    import json
    import os
    from google.cloud import bigquery
    import chromadb

    PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "operaiq")
    DATASET_ID = os.environ.get(
        "BIGQUERY_DATASET", os.environ.get("BQ_DATASET", "operaiq")
    )
    EVENTS_TABLE = f"{PROJECT_ID}.{DATASET_ID}.events"
    CHROMADB_DIR = os.environ.get("CHROMADB_PERSIST_DIR", "./chroma_db")

    # ── Fetch incident + correlated events from BigQuery ─────────────────────
    try:
        bq = bigquery.Client(project=PROJECT_ID)

        inc_job = bq.query(
            """
            SELECT incident_id, title, service, severity, status, timestamp,
                   triggered_by_deployment_id
            FROM `{events_table}`
            WHERE event_type = 'incident' AND incident_id = @incident_id
            LIMIT 1
            """.format(events_table=EVENTS_TABLE),
            job_config=bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("incident_id", "STRING", incident_id)
                ]
            ),
        )
        inc_rows = list(inc_job.result())

        if not inc_rows:
            return f"[ERROR: Incident {incident_id} not found in BigQuery]"

        row = inc_rows[0]
        incident = {
            "incident_id": row.incident_id,
            "title": row.title,
            "service": row.service,
            "severity": row.severity,
            "status": row.status,
            "timestamp": row.timestamp.isoformat(),
        }
        service = row.service
        incident_time = row.timestamp

        corr_job = bq.query(
            """
            SELECT event_type, timestamp, metric_type, value, deployment_id, version, status
            FROM `{events_table}`
            WHERE service = @service
              AND event_type IN ('metric', 'deployment')
              AND `timestamp` BETWEEN
                TIMESTAMP_SUB(@ts, INTERVAL 10 MINUTE)
                AND TIMESTAMP_ADD(@ts, INTERVAL 10 MINUTE)
            ORDER BY `timestamp` ASC LIMIT 50
            """.format(events_table=EVENTS_TABLE),
            job_config=bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("service", "STRING", service),
                    bigquery.ScalarQueryParameter(
                        "ts", "TIMESTAMP", incident_time.isoformat()
                    ),
                ]
            ),
        )
        correlated = [
            {
                "event_type": r.event_type,
                "timestamp": r.timestamp.isoformat(),
                **({"metric_type": r.metric_type, "value": float(r.value or 0)}
                   if r.event_type == "metric" else {}),
                **({"deployment_id": r.deployment_id, "version": r.version,
                    "status": r.status}
                   if r.event_type == "deployment" else {}),
            }
            for r in corr_job.result()
        ]
    except Exception as exc:
        incident = {"error": str(exc)}
        correlated = []
        service = "unknown"

    # ── Semantic runbook search ───────────────────────────────────────────────
    try:
        from chromadb.utils import embedding_functions
        chroma = chromadb.PersistentClient(path=CHROMADB_DIR)
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        col = chroma.get_or_create_collection("runbooks", embedding_function=ef)
        rb_results = col.query(
            query_texts=[f"{service} {incident.get('title', '')}"],
            n_results=min(3, col.count()),
            include=["documents", "metadatas"],
        )
        runbook_text = "\n".join(
            f"- [{m.get('title', '?')}]: {d[:400]}"
            for d, m in zip(
                rb_results["documents"][0], rb_results["metadatas"][0]
            )
        )
    except Exception:
        runbook_text = "Runbook search unavailable."

    deployments = [e for e in correlated if e.get("event_type") == "deployment"][:5]
    dep_text = "\n".join(
        f"- {d.get('version', '?')} ({d.get('status', '?')}) at {d.get('timestamp', '?')}"
        for d in deployments
    ) or "No recent deployments."

    return f"""You are triaging a production incident. Here is all available context:

=== INCIDENT ===
{json.dumps(incident, indent=2, default=str)}

=== CORRELATED EVENTS (±10 min) ===
{json.dumps(correlated, indent=2, default=str)}

=== RECENT DEPLOYMENTS (last 5) ===
{dep_text}

=== RELEVANT RUNBOOK SECTIONS (top 3) ===
{runbook_text}

Based on the above context, please provide a structured triage report with:
1. Severity Assessment
2. Likely Root Cause (with confidence %)
3. Affected Components
4. Recommended Immediate Actions (ranked)
5. Relevant Runbook Steps
6. Similar Past Incidents (if any)
"""


# Mount FastMCP as Streamable HTTP
# FastMCP 2.3+ uses http_app(); older versions use streamable_http_app()
try:
    mcp_app = mcp.http_app()
except AttributeError:
    mcp_app = mcp.streamable_http_app()
try:
    mcp_app.router.redirect_slashes = False
except Exception:
    pass

# ---------------------------------------------------------------------------
# FastAPI app with auth + audit middleware
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("OperaIQ MCP Server starting up...")
    audit_logger = AuditLogger()
    app.state.audit_logger = audit_logger
    
    # Enter the mounted mcp_app's lifespan to initialize its task group
    async with mcp_app.router.lifespan_context(mcp_app):
        yield
        
    logger.info("OperaIQ MCP Server shutting down...")

app = FastAPI(
    title="OperaIQ MCP Server",
    description="Production Intelligence MCP over Streamable HTTP",
    version="1.0.0",
    lifespan=lifespan,
)
app.router.redirect_slashes = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://operaiq-frontend-349176795620.us-central1.run.app", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def auth_and_audit_middleware(request: Request, call_next):
    """
    1. Skip auth for health checks and docs.
    2. Validate Bearer token.
    3. Check rate limit.
    """
    # Paths that bypass auth
    bypass_paths = {"/", "/health", "/docs", "/openapi.json", "/redoc"}
    if request.url.path in bypass_paths or request.method == "OPTIONS":
        return await call_next(request)

    # Extract Bearer token
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401, content={"detail": "Missing or invalid Authorization header"})

    token = auth_header.removeprefix("Bearer ").strip()

    try:
        claims: TokenClaims = await verify_token(token)
    except Exception as exc:
        logger.warning(f"Token verification failed: {exc}")
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401, content={"detail": f"Invalid token: {exc}"})

    # Rate limiting
    if not _check_rate_limit(claims.caller_id):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=429,
            content={"detail": f"Rate limit exceeded: max {RATE_LIMIT} calls per minute"},
        )

    # Store claims on request state for tools to access
    request.state.claims = claims
    request.state.caller_id = claims.caller_id

    tool_name = "mcp_stream"
    input_params: dict[str, object] = {"path": request.url.path}
    if request.url.path.startswith("/mcp") and request.method == "POST":
        try:
            raw_body = await request.body()
            if raw_body:
                payload = json.loads(raw_body)
                input_params = payload.get("params", {}) if isinstance(payload, dict) else {"raw": payload}
                if isinstance(payload, dict):
                    tool_method = payload.get("method")
                    if tool_method == "tools/call":
                        tool_name = str(payload.get("params", {}).get("name", "tools/call"))
                    elif isinstance(tool_method, str):
                        tool_name = tool_method
        except Exception as exc:
            logger.debug(f"Unable to parse MCP audit body: {exc}")

    start_ms = time.monotonic()
    response = await call_next(request)
    
    is_mcp_call = request.url.path.rstrip("/").startswith("/mcp")
    if is_mcp_call and request.method == "POST":
        audit_logger = getattr(request.app.state, "audit_logger", None) or get_audit_logger()
        await audit_logger.log(
            caller_id=request.state.caller_id,
            tool_name=tool_name,
            input_params=input_params,
            result_status="success" if response.status_code < 400 else "error",
            latency_ms=int((time.monotonic() - start_ms) * 1000),
            error_message=f"HTTP {response.status_code}" if response.status_code >= 400 else None,
        )

    return response


@app.get("/")
async def root():
    return {
        "service": "operaiq-mcp-server",
        "version": "1.0.0",
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
        "mcp": "/mcp",
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "operaiq-mcp-server", "version": "1.0.0"}


@app.post("/admin/seed-runbooks")
async def seed_runbooks():
    """
    Seeds the ChromaDB runbook knowledge base.
    Call this once after fresh deployment to initialize runbook search.
    Safe to call multiple times — upserts existing documents.
    """
    try:
        from tools.runbooks import _get_collection
        collection = _get_collection()
        count_before = collection.count()

        from data.seed_runbooks import RUNBOOKS
        
        ids = [rb["id"] for rb in RUNBOOKS]
        documents = [rb["content"] for rb in RUNBOOKS]
        metadatas = [
            {
                "service": rb.get("service", "unknown"),
                "title": rb["title"],
                "last_updated": rb["last_updated"],
            }
            for rb in RUNBOOKS
        ]
        
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

        count_after = collection.count()
        return {
            "status": "ok",
            "documents_before": count_before,
            "documents_after": count_after,
            "seeded": count_after - count_before,
        }
    except Exception as exc:
        logger.error(f"Seed runbooks failed: {exc}")
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(exc)})


@app.get("/mcp/tools/list")
async def list_mcp_tools():
    tools = await mcp._tool_manager.list_tools()
    return {
        "tools": [
            t.to_mcp_tool().model_dump(by_alias=True, exclude_none=True)
            for t in tools
        ]
    }


@app.get("/mcp/resources/list")
async def list_mcp_resources():
    resources = await mcp._resource_manager.list_resources()
    templates = await mcp._resource_manager.list_resource_templates()

    resource_items = [
        r.to_mcp_resource().model_dump(by_alias=True, exclude_none=True)
        for r in resources
    ]
    template_items = [
        {
            **t.to_mcp_template().model_dump(by_alias=True, exclude_none=True),
            "template": True,
        }
        for t in templates
    ]

    return {
        "resources": resource_items + template_items,
        "resourceTemplates": template_items,
    }


@app.post("/mcp")
async def mcp_compatibility_endpoint(request: Request):
    """
    Compatibility endpoint for tests that post JSON-RPC directly to /mcp.

    The streamable MCP transport still lives under the mounted app; this path
    simply executes registered tools and returns a JSON-RPC shaped payload.
    """
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            status_code=200,
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Invalid JSON payload"},
            },
        )

    if not isinstance(payload, dict):
        return JSONResponse(
            status_code=200,
            content={
                "jsonrpc": "2.0",
                "id": payload.get("id") if isinstance(payload, dict) else None,
                "error": {"code": -32600, "message": "Invalid request"},
            },
        )

    request_id = payload.get("id")
    method = payload.get("method")

    if method == "tools/call":
        params = payload.get("params", {}) or {}
        tool_name = params.get("name")
        arguments = params.get("arguments", {}) or {}

        if not tool_name:
            return JSONResponse(
                status_code=200,
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32602, "message": "Missing tool name"},
                },
            )

        try:
            content = await mcp._tool_manager.call_tool(str(tool_name), arguments)
            return JSONResponse(
                status_code=200,
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [item.model_dump(by_alias=True, exclude_none=True) for item in content]
                    },
                },
            )
        except Exception as exc:
            return JSONResponse(
                status_code=200,
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32000, "message": str(exc)},
                },
            )

    if method == "initialize":
        return JSONResponse(
            status_code=200,
            content={
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": payload.get("params", {}).get("protocolVersion", "2025-03-26"),
                    "serverInfo": {
                        "name": "OperaIQ Production Intelligence MCP Server",
                        "version": "1.0.0",
                    },
                    "capabilities": {},
                },
            },
        )

    if method == "notifications/initialized":
        return JSONResponse(
            status_code=202,
            content={"jsonrpc": "2.0", "id": request_id, "result": {"acknowledged": True}},
        )

    return JSONResponse(
        status_code=200,
        content={
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Unsupported method: {method}"},
        },
    )



app.mount("/mcp", mcp_app)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.environ.get("ENV", "production") == "development",
        log_level="info",
    )
