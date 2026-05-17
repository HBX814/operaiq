/**
 * OperaIQ API Client — typed wrapper over Next.js API routes + agent WebSocket.
 */

const WS_AGENT_BASE = process.env.NEXT_PUBLIC_AGENT_WS_URL || "ws://localhost:8081";
const TOKEN = process.env.NEXT_PUBLIC_API_TOKEN || "test-token";

function authHeaders() {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${TOKEN}`,
  };
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type Severity = "critical" | "warning" | "info";
export type IncidentStatus = "open" | "resolved";

export interface Incident {
  incident_id: string;
  title: string;
  service: string;
  severity: Severity;
  status: IncidentStatus;
  timestamp: string;
  triggered_by_deployment_id?: string;
}

export interface MetricPoint {
  timestamp: string;
  value: number;
}

export interface Deployment {
  deployment_id: string;
  service: string;
  version: string;
  status: "success" | "failed";
  timestamp: string;
  region: string;
}

export interface RunbookResult {
  id: string;
  service: string;
  title: string;
  content_snippet: string;
  full_content: string;
  similarity_score: number;
  last_updated: string;
}

export interface IncidentTimeline {
  incident: Incident;
  correlated_events: Array<{
    event_type: string;
    timestamp: string;
    metric_type?: string;
    value?: number;
    deployment_id?: string;
    version?: string;
    status?: string;
  }>;
  timeline_window_minutes: number;
}

export interface AgentMessage {
  type: "thinking" | "tool_call" | "chunk" | "complete" | "error";
  content?: string;
  tool?: string;
  input?: Record<string, unknown>;
  session_id?: string;
  message?: string;
  tool_calls?: Array<{ tool: string; input?: Record<string, unknown> }>;
}

// ---------------------------------------------------------------------------
// Dashboard API
// ---------------------------------------------------------------------------

export async function fetchActiveIncidents(
  severityFilter = "all"
): Promise<Incident[]> {
  const res = await fetch(`/api/incidents?severity=${severityFilter}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Failed to fetch incidents: ${res.status}`);
  return res.json();
}

export async function fetchMetrics(
  service: string,
  metricType: string,
  minutesBack = 60
): Promise<MetricPoint[]> {
  const params = new URLSearchParams({ service, metric_type: metricType, minutes_back: String(minutesBack) });
  const res = await fetch(`/api/metrics?${params}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch metrics: ${res.status}`);
  return res.json();
}

export async function fetchRecentDeployments(): Promise<Deployment[]> {
  const res = await fetch("/api/deployments", { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch deployments: ${res.status}`);
  return res.json();
}

export async function fetchIncidentTimeline(
  incidentId: string
): Promise<IncidentTimeline> {
  const res = await fetch(`/api/incidents/${incidentId}/timeline`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Failed to fetch incident timeline: ${res.status}`);
  return res.json();
}

export async function triggerRollback(
  deploymentId: string,
  reason: string
): Promise<{ rollback_id: string; status: string; estimated_completion_seconds: number }> {
  const res = await fetch("/api/rollback", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ deployment_id: deploymentId, reason }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Rollback failed: ${res.status}`);
  }
  return res.json();
}

export async function searchRunbooks(query: string, topK = 3): Promise<RunbookResult[]> {
  const res = await fetch(`/api/runbooks?query=${encodeURIComponent(query)}&top_k=${topK}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Runbook search failed: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// WebSocket Agent
// ---------------------------------------------------------------------------

export function createAgentWebSocket(
  sessionId: string,
  onMessage: (msg: AgentMessage) => void,
  onClose?: () => void
): {
  send: (message: string) => void;
  close: () => void;
} {
  const wsUrl = `${WS_AGENT_BASE}/ws/${sessionId}`;
  const ws = new WebSocket(wsUrl);

  ws.onmessage = (event) => {
    try {
      const msg: AgentMessage = JSON.parse(event.data);
      onMessage(msg);
    } catch {
      console.error("Failed to parse agent message:", event.data);
    }
  };

  ws.onclose = () => {
    onClose?.();
  };

  ws.onerror = (err) => {
    console.error("WebSocket error:", err);
    onMessage({ type: "error", message: "Connection error" });
  };

  return {
    send: (message: string) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ message }));
      }
    },
    close: () => ws.close(),
  };
}
