import { NextRequest, NextResponse } from "next/server";

const MCP_BASE_URL = process.env.MCP_SERVER_URL || "http://localhost:8080";
const MCP_RPC_URL = MCP_BASE_URL.endsWith("/mcp") ? MCP_BASE_URL : `${MCP_BASE_URL}/mcp`;
const TOKEN = process.env.MCP_API_TOKEN || "test-token";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const service = searchParams.get("service") || "payments";
  const metric_type = searchParams.get("metric_type") || "error_rate";
  const minutes_back = searchParams.get("minutes_back") || "60";

  try {
    const res = await fetch(MCP_RPC_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${TOKEN}`,
      },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 1,
        method: "tools/call",
        params: {
          name: "query_metrics",
          arguments: { service, metric_type, minutes_back: parseInt(minutes_back) },
        },
      }),
    });

    if (!res.ok) {
      // Return demo data when backend is not running
      return NextResponse.json(generateDemoMetrics(service, metric_type === "error_rate"));
    }

    const data = await res.json();
    return NextResponse.json(data.result?.content?.[0]?.text
      ? JSON.parse(data.result.content[0].text)
      : generateDemoMetrics(service, false));
  } catch {
    return NextResponse.json(generateDemoMetrics(service, service === "payments"));
  }
}

function generateDemoMetrics(service: string, spike: boolean) {
  return Array.from({ length: 24 }, (_, i) => ({
    timestamp: new Date(Date.now() - (23 - i) * 5 * 60000).toISOString(),
    value: spike && i > 18
      ? 2 + Math.random() * 15
      : 0.5 + Math.random() * 2,
  }));
}
