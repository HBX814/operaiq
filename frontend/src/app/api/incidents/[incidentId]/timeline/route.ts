import { NextRequest, NextResponse } from "next/server";

const MCP_BASE_URL = process.env.MCP_SERVER_URL || "http://localhost:8080";
const MCP_RPC_URL = MCP_BASE_URL.endsWith("/mcp") ? MCP_BASE_URL : `${MCP_BASE_URL}/mcp`;
const TOKEN = process.env.MCP_API_TOKEN || "test-token";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ incidentId: string }> }
) {
  const { incidentId } = await params;
  if (!incidentId) {
    return NextResponse.json({ detail: "incidentId is required" }, { status: 400 });
  }

  try {
    const res = await fetch(MCP_RPC_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${TOKEN}`,
      },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: Date.now(),
        method: "tools/call",
        params: {
          name: "get_incident_timeline",
          arguments: { incident_id: incidentId },
        },
      }),
    });

    if (!res.ok) {
      return NextResponse.json(generateDemoTimeline(incidentId));
    }

    const data = await res.json();
    const text = data.result?.content?.[0]?.text;
    return NextResponse.json(text ? JSON.parse(text) : generateDemoTimeline(incidentId));
  } catch {
    return NextResponse.json(generateDemoTimeline(incidentId));
  }
}

function generateDemoTimeline(incidentId: string) {
  const now = Date.now();
  return {
    incident: {
      incident_id: incidentId,
      title: "Payment Gateway Timeout",
      service: "payments",
      severity: "critical",
      status: "open",
      timestamp: new Date(now - 12 * 60000).toISOString(),
      triggered_by_deployment_id: "dep-001",
    },
    correlated_events: [
      {
        event_type: "deployment",
        timestamp: new Date(now - 15 * 60000).toISOString(),
        deployment_id: "dep-001",
        version: "2.3.7",
        status: "failed",
      },
      {
        event_type: "metric",
        timestamp: new Date(now - 13 * 60000).toISOString(),
        metric_type: "error_rate",
        value: 18.4,
      },
    ],
    timeline_window_minutes: 10,
  };
}
