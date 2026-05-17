import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

const QuerySchema = z.object({
  query: z.string().min(1, "query is required"),
  top_k: z.coerce.number().int().min(1).max(20).default(3),
});

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;

  const parsed = QuerySchema.safeParse({
    query: searchParams.get("query") ?? "",
    top_k: searchParams.get("top_k") ?? "3",
  });

  if (!parsed.success) {
    return NextResponse.json(
      { error: "Invalid parameters", issues: parsed.error.flatten() },
      { status: 422 }
    );
  }

  const { query, top_k } = parsed.data;

  const MCP_BASE_URL = process.env.MCP_SERVER_URL ?? "http://localhost:8080";
  const MCP_RPC_URL = MCP_BASE_URL.endsWith("/mcp") ? MCP_BASE_URL : `${MCP_BASE_URL}/mcp`;
  const TOKEN = process.env.MCP_API_TOKEN ?? process.env.NEXT_PUBLIC_API_TOKEN ?? "test-token";

  try {
    const response = await fetch(MCP_RPC_URL, {
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
          name: "search_runbooks",
          arguments: { query, top_k },
        },
      }),
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: `MCP server error: ${response.status}` },
        { status: 502 }
      );
    }

    const json = await response.json();

    if (json.error) {
      return NextResponse.json(
        { error: json.error.message },
        { status: 500 }
      );
    }

    const text = json.result?.content?.[0]?.text ?? "[]";
    const results = JSON.parse(text);

    return NextResponse.json(results);
  } catch (err) {
    console.error("[/api/runbooks] Error:", err);
    return NextResponse.json(
      { error: "Failed to search runbooks", detail: String(err) },
      { status: 500 }
    );
  }
}
