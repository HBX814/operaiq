/**
 * OperaIQ MCP Streamable HTTP Client
 *
 * Typed wrapper for calling every MCP tool on the mcp-server over
 * Streamable HTTP (JSON-RPC 2.0). Requires a valid Bearer token.
 *
 * Usage:
 *   const client = new MCPClient({ baseUrl: "http://localhost:8080/mcp", token: "..." });
 *   const metrics = await client.queryMetrics({ service: "payments", metric_type: "error_rate" });
 */

import { z } from "zod";

// ---------------------------------------------------------------------------
// Zod schemas for every tool's response
// ---------------------------------------------------------------------------

export const MetricPointSchema = z.object({
  timestamp: z.string(),
  value: z.number(),
});
export type MetricPoint = z.infer<typeof MetricPointSchema>;

export const IncidentSchema = z.object({
  incident_id: z.string(),
  title: z.string(),
  service: z.string(),
  severity: z.enum(["critical", "warning", "info"]),
  status: z.enum(["open", "resolved"]),
  timestamp: z.string(),
  triggered_by_deployment_id: z.string().optional(),
});
export type Incident = z.infer<typeof IncidentSchema>;

export const CorrelatedEventSchema = z.object({
  event_type: z.string(),
  timestamp: z.string(),
  metric_type: z.string().optional(),
  value: z.number().optional(),
  deployment_id: z.string().optional(),
  version: z.string().optional(),
  status: z.string().optional(),
});

export const IncidentTimelineSchema = z.object({
  incident: IncidentSchema,
  correlated_events: z.array(CorrelatedEventSchema),
  timeline_window_minutes: z.number(),
});
export type IncidentTimeline = z.infer<typeof IncidentTimelineSchema>;

export const RunbookResultSchema = z.object({
  id: z.string(),
  service: z.string(),
  title: z.string(),
  content_snippet: z.string(),
  full_content: z.string().optional(),
  similarity_score: z.number(),
  last_updated: z.string().optional(),
});
export type RunbookResult = z.infer<typeof RunbookResultSchema>;

export const RollbackResultSchema = z.object({
  rollback_id: z.string(),
  status: z.string(),
  estimated_completion_seconds: z.number(),
});
export type RollbackResult = z.infer<typeof RollbackResultSchema>;

export const SilenceResultSchema = z.object({
  status: z.string(),
  incident_id: z.string(),
  duration_minutes: z.number(),
  expires_at: z.string(),
  silence_id: z.string().optional(),
});
export type SilenceResult = z.infer<typeof SilenceResultSchema>;

export const PostMortemDraftSchema = z.object({
  postmortem_id: z.string(),
  incident_id: z.string(),
  summary: z.string().optional(),
  timeline: z.string().optional(),
  root_cause: z.string().optional(),
  action_items: z.string().optional(),
  lessons_learned: z.string().optional(),
  created_at: z.string().optional(),
});
export type PostMortemDraft = z.infer<typeof PostMortemDraftSchema>;

export const DeploymentSchema = z.object({
  deployment_id: z.string(),
  service: z.string(),
  version: z.string(),
  status: z.enum(["success", "failed"]),
  timestamp: z.string(),
  region: z.string(),
});
export type Deployment = z.infer<typeof DeploymentSchema>;

// ---------------------------------------------------------------------------
// MCP Client
// ---------------------------------------------------------------------------

export interface MCPClientConfig {
  baseUrl: string;
  token: string;
}

interface JsonRpcRequest {
  jsonrpc: "2.0";
  id: number;
  method: string;
  params: Record<string, unknown>;
}

interface JsonRpcResponse<T = unknown> {
  jsonrpc: "2.0";
  id: number;
  result?: {
    content: Array<{ type: string; text: string }>;
    isError?: boolean;
  };
  error?: { code: number; message: string; data?: unknown };
}

let _requestId = 1;

export class MCPClient {
  private baseUrl: string;
  private token: string;

  constructor(config: MCPClientConfig) {
    this.baseUrl = config.baseUrl;
    this.token = config.token;
  }

  private async call<T>(
    toolName: string,
    args: Record<string, unknown>,
    schema: z.ZodType<T>
  ): Promise<T> {
    const payload: JsonRpcRequest = {
      jsonrpc: "2.0",
      id: _requestId++,
      method: "tools/call",
      params: { name: toolName, arguments: args },
    };

    const response = await fetch(this.baseUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.token}`,
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`MCP request failed: ${response.status} ${response.statusText}`);
    }

    const json: JsonRpcResponse = await response.json();

    if (json.error) {
      throw new Error(`MCP tool error [${json.error.code}]: ${json.error.message}`);
    }

    const content = json.result?.content?.[0];
    if (!content?.text) {
      throw new Error(`Unexpected MCP response shape for tool '${toolName}'`);
    }

    const parsed = JSON.parse(content.text);
    return schema.parse(parsed);
  }

  // ── Tool: query_metrics ────────────────────────────────────────────────────
  async queryMetrics(args: {
    service: string;
    metric_type: string;
    minutes_back?: number;
  }): Promise<MetricPoint[]> {
    return this.call("query_metrics", args, z.array(MetricPointSchema));
  }

  // ── Tool: get_incident_timeline ───────────────────────────────────────────
  async getIncidentTimeline(incidentId: string): Promise<IncidentTimeline> {
    return this.call(
      "get_incident_timeline",
      { incident_id: incidentId },
      IncidentTimelineSchema
    );
  }

  // ── Tool: search_runbooks ─────────────────────────────────────────────────
  async searchRunbooks(args: {
    query: string;
    top_k?: number;
  }): Promise<RunbookResult[]> {
    return this.call("search_runbooks", args, z.array(RunbookResultSchema));
  }

  // ── Tool: list_active_alerts ──────────────────────────────────────────────
  async listActiveAlerts(severityFilter = "all"): Promise<Incident[]> {
    return this.call(
      "list_active_alerts",
      { severity_filter: severityFilter },
      z.array(IncidentSchema)
    );
  }

  // ── Tool: trigger_rollback ────────────────────────────────────────────────
  async triggerRollback(args: {
    deployment_id: string;
    reason: string;
  }): Promise<RollbackResult> {
    return this.call("trigger_rollback", args, RollbackResultSchema);
  }

  // ── Tool: silence_alert ───────────────────────────────────────────────────
  async silenceAlert(args: {
    incident_id: string;
    duration_minutes: number;
    reason: string;
  }): Promise<SilenceResult> {
    return this.call("silence_alert", args, SilenceResultSchema);
  }

  // ── Tool: create_postmortem_draft ─────────────────────────────────────────
  async createPostmortemDraft(incidentId: string): Promise<PostMortemDraft> {
    return this.call(
      "create_postmortem_draft",
      { incident_id: incidentId },
      PostMortemDraftSchema
    );
  }

  // ── Resource: recent deployments ─────────────────────────────────────────
  async getRecentDeployments(): Promise<Deployment[]> {
    const response = await fetch(this.baseUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.token}`,
      },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: _requestId++,
        method: "resources/read",
        params: { uri: "operaiq://deployments/recent" },
      }),
    });
    if (!response.ok) throw new Error(`Resource fetch failed: ${response.status}`);
    const json = await response.json();
    const text = json.result?.contents?.[0]?.text ?? "[]";
    return z.array(DeploymentSchema).parse(JSON.parse(text));
  }

  // ── Resource: open incidents ──────────────────────────────────────────────
  async getOpenIncidents(): Promise<Incident[]> {
    const response = await fetch(this.baseUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.token}`,
      },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: _requestId++,
        method: "resources/read",
        params: { uri: "operaiq://incidents/active" },
      }),
    });
    if (!response.ok) throw new Error(`Resource fetch failed: ${response.status}`);
    const json = await response.json();
    const text = json.result?.contents?.[0]?.text ?? "[]";
    return z.array(IncidentSchema).parse(JSON.parse(text));
  }
}

// ---------------------------------------------------------------------------
// Singleton — reads config from env at runtime (Next.js API routes only)
// ---------------------------------------------------------------------------
export function getMCPClient(): MCPClient {
  const baseUrl = normalizeMcpUrl(
    process.env.MCP_SERVER_URL ?? "http://localhost:8080"
  );
  const token =
    process.env.MCP_API_TOKEN ?? process.env.NEXT_PUBLIC_API_TOKEN ?? "test-token";
  return new MCPClient({ baseUrl, token });
}

function normalizeMcpUrl(baseUrl: string): string {
  const trimmed = baseUrl.replace(/\/$/, "");
  return trimmed.endsWith("/mcp") ? trimmed : `${trimmed}/mcp`;
}
