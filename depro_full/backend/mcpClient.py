from mcpServer.server import call_tool

def call_mcp_tool(tool_name: str, args: dict):
    """
    Thin client for calling MCP tools.
    Can later be replaced with HTTP / STDIO MCP calls.
    """
    print(f"\n🔧 MCP TOOL CALL → {tool_name}")
    return call_tool(tool_name, args)
