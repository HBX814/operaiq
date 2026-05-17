import asyncio
from main import mcp

async def p():
    try:
        tools = await mcp._mcp_server.list_tools()
        print([t.name for t in tools])
    except Exception as e:
        print("mcp._mcp_server failed:", e)

    try:
        tools = mcp._tools
        print([t.name for t in tools.values()])
    except Exception as e:
        pass

asyncio.run(p())
