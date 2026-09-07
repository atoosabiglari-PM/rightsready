import pytest
import asyncio
import os
from unittest.mock import MagicMock, AsyncMock, patch
from src.tools_mcp import MCPRuntimeBridge

@pytest.mark.asyncio
async def test_mcp_bridge_runtime_call():
    """
    Verify that the MCPRuntimeBridge correctly executes the MCP protocol.
    This test mocks the transport to prove that 'call_tool' is invoked.
    """
    bridge = MCPRuntimeBridge(command="python", args=["mock_server.py"])

    # Mock the MCP session and tools
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.content = [MagicMock(text="Mocked ClickHouse Result")]
    mock_result.is_error = False
    mock_session.call_tool.return_value = mock_result

    bridge.session = mock_session

    sql = "SELECT count() FROM assets"
    result = await bridge.run_query(sql)

    # Assertions
    assert result["content"] == ["Mocked ClickHouse Result"]
    assert not result["is_error"]

    # Verify the specific MCP tool was called with the expected arguments
    mock_session.call_tool.assert_called_once_with(
        "run_query",
        arguments={"query": sql}
    )


def test_mcp_command_resolution():
    """Verify priority: ENV > PATH > Module > UV."""
    # 1. Test ENV override
    with patch.dict(os.environ, {"MCP_CLICKHOUSE_EXECUTABLE": "/custom/path/bin"}):
        bridge = MCPRuntimeBridge()
        assert bridge.server_params.command == "/custom/path/bin"
        assert bridge.server_params.args == []

    # 2. Test PATH resolution
    with patch.dict(os.environ, {}, clear=True):
        with patch("shutil.which", side_effect=lambda cmd: "/bin/mcp-clickhouse" if cmd == "mcp-clickhouse" else None):
            bridge = MCPRuntimeBridge()
            assert bridge.server_params.command == "/bin/mcp-clickhouse"
            assert bridge.server_params.args == []

    # 3. Test Module fallback
    with patch.dict(os.environ, {}, clear=True):
        with patch("shutil.which", return_value=None), \
             patch("importlib.util.find_spec", return_value=True), \
             patch("sys.executable", "/usr/bin/python3"):
            bridge = MCPRuntimeBridge()
            assert bridge.server_params.command == "/usr/bin/python3"
            assert bridge.server_params.args == ["-m", "mcp_clickhouse.main"]

    # 4. Test UV fallback
    with patch.dict(os.environ, {}, clear=True):
        with patch("shutil.which", side_effect=lambda cmd: "/bin/uv" if cmd == "uv" else None), \
             patch("importlib.util.find_spec", return_value=False):
            bridge = MCPRuntimeBridge()
            assert bridge.server_params.command == "/bin/uv"
            assert bridge.server_params.args == ["run", "--with", "mcp-clickhouse", "--python", "3.12", "mcp-clickhouse"]

def test_agent_tool_registration():
    """
    Ensure the ADK root_agent correctly registers the required tools,
    including the MCP-based query tool.
    """
    from src.agent_core import root_agent

    tool_names = [getattr(t, "name", getattr(t, "__name__", type(t).__name__)) for t in root_agent.tools]

    assert "deterministic_validate" in tool_names
    assert "deterministic_clearance" in tool_names
    assert "deterministic_pipeline_execute" in tool_names
    assert "agent_query_warehouse" in tool_names
