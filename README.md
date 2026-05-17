# OperaIQ — AI-Powered Production Intelligence Platform

OperaIQ is an open, developer-first production intelligence system that combines a Small-Scale Event Plane (synthetic or real), a FastMCP-based tool & resource surface, and a multi-agent orchestration layer built on the Google ADK. It is designed to help SREs and engineers triage incidents faster, run safe remediation actions (operator-gated), and automatically generate high-quality post-mortems — all from a single conversational surface and a real-time dashboard.

Key capabilities:
- Real-time ingestion of production events (deployments, metrics, incidents)
- Semantic runbook search using ChromaDB embeddings
- JSON-RPC / Streamable HTTP MCP tool surface (audit-logged and rate-limited)
- Multi-agent orchestration (Triage, Remediation, Postmortem) via Google ADK
- Operator-gated state changes (explicit approval required for rollbacks/silences)
- Rich Next.js dashboard with SSE/WebSocket streaming for live operator workflows

---

## What this repository contains (high level)

- `mcp-server/` — The FastMCP server that exposes tools (query_metrics, trigger_rollback, search_runbooks, create_postmortem_draft, etc.) and resources (deployments, incidents, runbooks). It handles auth, auditing, and rate limiting.
- `agents/` — Agent orchestration service. Contains the Coordinator and specialized agents (`TriageAgent`, `RemediationAgent`, `PostMortemAgent`) implemented using Google ADK. Streams SSE or WebSocket responses back to the frontend.
- `frontend/` — Next.js 15 dashboard and Agent Chat Drawer UI. Calls MCP server and streams agent events.
- `data/` — Utilities for demo & seeding: `generator.py` produces synthetic events, `seed_runbooks.py` populates ChromaDB runbooks.
- `chroma_db/` — Persistent ChromaDB directory used for the runbook vector store (committed here as an example DB file for local demos).
- `infra/` — Deployment scripts and Cloud Run YAML manifests.
- `design/` — Static HTML mockups and reference UIs used during design.

---

## Architecture (concise)

OperaIQ follows a simple, extensible flow:

1. Event Plane: events (deployments, metrics, incidents) are published (synthetic via `data/generator.py` or real pipelines) to Pub/Sub and landed into BigQuery.
2. MCP Server: `mcp-server` exposes a toolset (JSON-RPC / Streamable HTTP) so agents and frontend can call composable tools.
3. Agents: `agents` connect to the MCP server using the ADK and run triage, remediation, and postmortem workflows. They stream progress as SSE/WebSocket events.
4. Frontend: `frontend` renders live KPIs, incidents, and an Agent Chat Drawer that shows streaming tool calls, text, and approvals. Operators approve/deny remediation actions from the UI.

The repository includes an example mermaid architecture diagram (kept intentionally compact inside this README).

---

## Quickstart (developer-focused)

1) Clone and configure:

```bash
git clone https://github.com/YOUR_ORG/operaiq.git
cd operaiq
cp .env.example .env
# set GEMINI_API_KEY, GCP_PROJECT_ID and local dev tokens
```

2) Seed runbooks (local demo):

```bash
python -m pip install chromadb sentence-transformers
python data/seed_runbooks.py
```

3) Start MCP server (dev):

```bash
python -m pip install -r mcp-server/requirements.txt
uvicorn mcp-server.main:app --reload --port 8080
```

4) Start Agents (dev):

```bash
python -m pip install -r agents/requirements.txt
uvicorn agents.main:app --reload --port 8081
```

5) Start frontend:

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
# Open http://localhost:3000
```

6) (Optional) Run generator to populate demo events:

```bash
python data/generator.py
```

---

## Detailed File & Directory Reference

This section describes important files and their roles so maintainers and contributors can quickly understand the codebase.

- `mcp-server/main.py` — MCP server entrypoint. Registers tools and resources on a `FastMCP` instance, mounts it on FastAPI, and provides middleware for OAuth token validation, rate limiting (60 req/min by default), and audit logging into BigQuery. Also exposes an admin endpoint `/admin/seed-runbooks` used by `data/seed_runbooks.py`.

- `mcp-server/tools/` — Tool registrations used by external agents and the frontend. Key modules:
  - `metrics.py` — `query_metrics` tool implementation that queries BigQuery time-series data.
  - `incidents.py` — `get_incident_timeline` and `list_active_alerts` tool implementations.
  - `runbooks.py` — `search_runbooks` implementation backed by ChromaDB.
  - `remediation.py` — `trigger_rollback` & `silence_alert` implementations; these tools publish events to Pub/Sub and write audit entries.
  - `postmortem.py` — `create_postmortem_draft` which proxies to Gemini and saves drafts to Firestore.

- `mcp-server/resources/` — Resource endpoints (read-only) exposed to agents/tools for `deployments/recent`, `incidents/open`, and `runbooks/{service}`.

- `agents/main.py` — Agent orchestration FastAPI service. Defines factory functions that create ADK `LlmAgent` instances (Triage, Remediation, Postmortem) wired to the MCP toolset. Offers SSE endpoints (`/triage`, `/remediate`, `/postmortem`) and a WebSocket endpoint for chat sessions. Contains approval flow logic for state-changing tools.

- `agents/triage_agent.py` — TriageAgent factory and instructions. Calls `get_incident_timeline`, `query_metrics`, and `search_runbooks` in parallel and synthesizes a structured triage report.

- `agents/remediation_agent.py` — RemediationAgent factory. Presents exactly 3 remediation options (low/medium/high risk), requests operator confirmation, and calls `trigger_rollback` or `silence_alert` upon approval. Post-action it verifies recovery by calling `query_metrics`.

- `agents/postmortem_agent.py` — PostMortemAgent factory. Calls `create_postmortem_draft`, scores the draft using a rubric (summary, timeline, root cause, action items, lessons learned) and returns a quality score with improvements.

- `data/generator.py` — Synthetic production event generator. Produces deployments, metrics, and incidents and publishes to Pub/Sub (or prints them in `DRY_RUN` mode). Useful for demos and local testing.

- `data/seed_runbooks.py` — Seeds ChromaDB with idempotent runbook documents used by `search_runbooks`. The runbooks in `RUNBOOKS` are realistic operational procedures for sample services (payments, auth, inventory, notifications, search).

- `frontend/` — Next.js 15 application. Notable parts:
  - `src/app/` — server components and API routes that proxy calls to the MCP server (e.g. `api/incidents/route.ts`, `api/deployments/route.ts`).
  - `src/components/AgentChatDrawer.tsx` — UI that renders streaming agent messages, tool call cards, and approval buttons.
  - `src/components/IncidentFeed.tsx` — Live incident list with quick actions.
  - `src/lib/mcp-client.ts` — Lightweight client for interacting with the MCP server from the frontend.

- `chroma_db/` — Example ChromaDB persistent storage folder (committed for convenience in local demos). In production, provide a durable persistent location via environment variable `CHROMADB_PERSIST_DIR`.

- `infra/` — Deployment helpers and Cloud Run YAMLs. Use these to deploy `mcp-server`, `agents`, and `data` generator jobs.

- `tests/` and `agents/tests` — Unit and integration tests for the server and agent workflows. Run with `pytest` for Python and Playwright for frontend e2e tests.

---

## Workflow: end-to-end operator scenario

1. Anomaly occurs (e.g., deployment failed or metric spike). Either the real pipeline publishes it or `data/generator.py` produces it for demos.
2. Event lands in BigQuery; incident entries become visible to the frontend via `mcp-server` resources.
3. Operator opens the dashboard and engages the Agent Chat Drawer on the incident.
4. The CoordinatorAgent delegates to `TriageAgent` which calls `get_incident_timeline`, `search_runbooks`, and `query_metrics` to form a triage summary.
5. If `TriageAgent` recommends remediation, `RemediationAgent` prepares three safety-ranked options and requests operator approval in the chat.
6. Operator approves an option. The agents call `trigger_rollback` (or `silence_alert`) via MCP. These calls are audited into BigQuery and may publish Pub/Sub rollback events.
7. Once remediation completes, the `PostMortemAgent` can generate a draft and a quality score; operators edit and publish the postmortem via the Post-Mortem Center.

This flow emphasizes human-in-the-loop safety for all state-changing actions while automating context assembly and hypothesis generation.

---

## How OperaIQ is different

- Agentic orchestration + MCP: OperaIQ combines a composable MCP tool surface with agent orchestration (Coordinator + specialized agents). Many systems either provide a ``runbook`` search or an alerting UI — OperaIQ brings agents, tools, and human approvals together.
- Semantic Runbooks: Instead of keyword search, OperaIQ uses ChromaDB embeddings for semantic retrieval of runbook sections, making troubleshooting faster and more relevant.
- Operator-gated automation: Remediation actions (rollbacks, silences) require explicit operator confirmation and strict role checks, balancing automation with safety.
- Postmortem scoring: The platform produces draft postmortems programmatically and scores them against a rubric so teams can triage which postmortems need human improvement.
- Streamable UX: SSE/WebSocket streaming surfaces live agent thought processes and tool calls (tool_call / tool_result / awaiting_approval), improving operator trust and debuggability.

Compared to out-of-the-box offerings (PagerDuty, Opsgenie, etc.), OperaIQ is opinionated for SRE workflows and integrates LLM-powered assistants tightly with the operational toolchain (BigQuery, Pub/Sub, Firestore, ChromaDB), making it more extensible for developer workflows and reproducible automation experiments.

---

## Why this is useful for developers & SREs

- Faster Triage: Agents assemble timeline + metrics + runbooks automatically, saving the first 5–15 minutes of manual context-gathering during incidents.
- Safer Automation: Each state-changing automation requires explicit approval and is audit-logged, reducing blast radius while allowing fast remediation.
- Knowledge capture: Runbooks and generated postmortems are stored and searchable; postmortem scoring nudges teams toward higher-quality documentation.
- Testable Locally: `data/generator.py` and `chroma_db` allow repeatable local testing of agent workflows.
- Extensible: `mcp-server` exposes a clear tool & resource API so teams can add custom tools (e.g., `restart_pods`, `scale_service`) or integrate additional data sources.

---

## Contributing

- When adding tools to `mcp-server/tools`, add corresponding unit tests under `mcp-server/tests`.
- Keep agent instructions concise and add unit tests for edge-case behavior (especially for approval flows in `agents/main.py`).

---

## Link :
[OperaIQ Dashboard](https://operaiq-frontend-349176795620.us-central1.run.app/dashboard)


