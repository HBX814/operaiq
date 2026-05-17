import { NextRequest, NextResponse } from "next/server";

const MCP_BASE_URL = process.env.MCP_SERVER_URL || "http://localhost:8080";
const MCP_RPC_URL = MCP_BASE_URL.endsWith("/mcp") ? MCP_BASE_URL : `${MCP_BASE_URL}/mcp`;
const TOKEN = process.env.MCP_API_TOKEN || "test-token";

export async function GET() {
  try {
    const res = await fetch(MCP_RPC_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${TOKEN}` },
      body: JSON.stringify({
        jsonrpc: "2.0", id: 1,
        method: "resources/read",
        params: { uri: "operaiq://deployments/recent" },
      }),
    });

    if (!res.ok) return NextResponse.json(DEMO_DEPLOYMENTS);
    const data = await res.json();
    return NextResponse.json(
      data.result?.contents?.[0]?.text ? JSON.parse(data.result.contents[0].text) : DEMO_DEPLOYMENTS
    );
  } catch {
    return NextResponse.json(DEMO_DEPLOYMENTS);
  }
}

const DEMO_DEPLOYMENTS = [
  { deployment_id: "dep-001", service: "payments", version: "2.3.7", status: "failed", timestamp: new Date(Date.now() - 15 * 60000).toISOString(), region: "us-central1" },
  { deployment_id: "dep-002", service: "auth", version: "1.9.2", status: "success", timestamp: new Date(Date.now() - 42 * 60000).toISOString(), region: "us-central1" },
  { deployment_id: "dep-003", service: "search", version: "3.1.0", status: "success", timestamp: new Date(Date.now() - 95 * 60000).toISOString(), region: "us-central1" },
];
