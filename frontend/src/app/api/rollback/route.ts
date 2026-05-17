import { NextRequest, NextResponse } from "next/server";

const MCP_BASE_URL = process.env.MCP_SERVER_URL || "http://localhost:8080";
const MCP_RPC_URL = MCP_BASE_URL.endsWith("/mcp") ? MCP_BASE_URL : `${MCP_BASE_URL}/mcp`;
const TOKEN = process.env.MCP_API_TOKEN || process.env.NEXT_PUBLIC_API_TOKEN || "test-operator-token";

export async function POST(request: NextRequest) {
  const body = await request.json();
  const { deployment_id, reason } = body;

  if (!deployment_id || !reason) {
    return NextResponse.json({ detail: "deployment_id and reason are required" }, { status: 400 });
  }

  try {
    const res = await fetch(MCP_RPC_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${TOKEN}` },
      body: JSON.stringify({
        jsonrpc: "2.0", id: 1,
        method: "tools/call",
        params: {
          name: "trigger_rollback",
          arguments: { deployment_id, reason, caller_id: "frontend-user", caller_roles: ["operator"] },
        },
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return NextResponse.json({ detail: err.detail || "Rollback failed" }, { status: res.status });
    }

    const data = await res.json();
    const result = data.result?.content?.[0]?.text
      ? JSON.parse(data.result.content[0].text)
      : { rollback_id: `rb-${Date.now()}`, status: "initiated", estimated_completion_seconds: 120 };

    return NextResponse.json(result);
  } catch {
    // Demo fallback
    return NextResponse.json({
      rollback_id: `rb-${Date.now()}`,
      status: "initiated",
      estimated_completion_seconds: 120,
    });
  }
}
