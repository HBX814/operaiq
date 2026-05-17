export const CONFIG = {
  MCP_SERVER_URL:
    process.env.NEXT_PUBLIC_MCP_SERVER_URL ||
    "https://operaiq-mcp-server-349176795620.us-central1.run.app",
  AGENTS_URL:
    process.env.NEXT_PUBLIC_AGENTS_WS_URL ||
    process.env.NEXT_PUBLIC_AGENT_WS_URL ||
    "https://operaiq-agents-349176795620.us-central1.run.app",
} as const
