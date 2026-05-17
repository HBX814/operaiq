import { NextRequest, NextResponse } from "next/server";

const MCP_BASE_URL = process.env.MCP_SERVER_URL || "http://localhost:8080";
const MCP_RPC_URL = MCP_BASE_URL.endsWith("/mcp") ? MCP_BASE_URL : `${MCP_BASE_URL}/mcp`;
const TOKEN = process.env.MCP_API_TOKEN || "test-token";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const severity = searchParams.get("severity") || "all";

  try {
    const res = await fetch(MCP_RPC_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${TOKEN}` },
      body: JSON.stringify({
        jsonrpc: "2.0", id: 1,
        method: "tools/call",
        params: { name: "list_active_alerts", arguments: { severity_filter: severity } },
      }),
    });

    if (!res.ok) return NextResponse.json(DEMO_INCIDENTS);
    const data = await res.json();
    return NextResponse.json(
      data.result?.content?.[0]?.text ? JSON.parse(data.result.content[0].text) : DEMO_INCIDENTS
    );
  } catch {
    return NextResponse.json(DEMO_INCIDENTS);
  }
}

const DEMO_INCIDENTS = [
  { incident_id: "inc-001", title: "Payment Gateway Timeout", service: "payments", severity: "critical", status: "open", timestamp: new Date(Date.now() - 12 * 60000).toISOString() },
  { incident_id: "inc-002", title: "Auth Service Latency Spike", service: "auth", severity: "warning", status: "open", timestamp: new Date(Date.now() - 28 * 60000).toISOString() },
  { incident_id: "inc-003", title: "Search Index Stale", service: "search", severity: "info", status: "open", timestamp: new Date(Date.now() - 45 * 60000).toISOString() },
];
