import asyncio
import json
import os
from typing import Any, Dict, Optional, List
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class MCPRuntimeBridge:
    """
    A runtime bridge that communicates with the official mcp-clickhouse server
    using the Model Context Protocol (MCP).
    """

    def __init__(self, command: Optional[str] = None, args: Optional[List[str]] = None):
        # Resolve 'uv' executable: environment override -> resolve from PATH -> fallback
        if not command:
            command = os.environ.get("UV_EXECUTABLE")
            if not command:
                import shutil
                command = shutil.which("uv") or "/usr/local/bin/uv"

        # Default to the official mcp-clickhouse server using 'uv'
        self.server_params = StdioServerParameters(
            command=command,
            args=args or [
                "run",
                "--with",
                "mcp-clickhouse",
                "--python",
                "3.12",
                "mcp-clickhouse"
            ],
            env=os.environ.copy()
        )
        self.session: Optional[ClientSession] = None
        self._exit_stack: Optional[AsyncExitStack] = None

    async def connect(self):
        """Establish connection to the MCP server via stdio."""
        self._exit_stack = AsyncExitStack()
        
        # Connect to the server process via stdio
        read_stream, write_stream = await self._exit_stack.enter_async_context(
            stdio_client(self.server_params)
        )
        
        # Initialize the MCP session
        self.session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        
        await self.session.initialize()

    async def disconnect(self):
        """Clean up the MCP connection."""
        if self._exit_stack:
            await self._exit_stack.aclose()
            self.session = None

    async def run_query(self, query: str) -> Dict[str, Any]:
        """
        Execute a read-only SQL query via the MCP server's 'list_tables' or 'run_query' tool.
        This is the ONLY allowed path for agent-driven ClickHouse reads.
        """
        if not self.session:
            raise RuntimeError("MCP session not connected. Call connect() first.")

        # Call the official mcp-clickhouse tool 'run_query'
        result = await self.session.call_tool(
            "run_query",
            arguments={"query": query}
        )

        return {
            "content": [c.text for c in result.content if hasattr(c, 'text')],
            "is_error": result.isError
        }

async def agent_query_warehouse(sql: str) -> Dict[str, Any]:
    """
    Primary tool for Gemini to perform read-only analytical queries.
    Uses the official MCP protocol bridge.
    """
    # Force read-only by checking for destructive keywords (Basic safety layer)
    forbidden = ["DROP", "DELETE", "TRUNCATE", "UPDATE", "INSERT", "ALTER"]
    if any(cmd in sql.upper() for cmd in forbidden):
        return {"is_error": True, "content": ["Error: Only SELECT queries are permitted via the agent interface."]}

    bridge = MCPRuntimeBridge()
    try:
        await bridge.connect()
        return await bridge.run_query(sql)
    except Exception as e:
        return {"is_error": True, "content": [f"MCP Error: {str(e)}"]}
    finally:
        await bridge.disconnect()
