import pytest
import asyncio
import os
from unittest.mock import MagicMock, AsyncMock, patch
from src.agent_core import rightsready_tools
from src.tools_mcp import MCPRuntimeBridge
from src.tools_deterministic import deterministic_clearance

# =============================================================================
# LEVEL 1: GOVERNANCE & DETERMINISTIC AUTHORITY
# =============================================================================

def test_deterministic_clearance_authority():
    """
    Prove that deterministic_clearance returns authoritative results
    that Gemini must report.
    """
    # Test with a known file (Project Aurora Valid)
    # Note: project_aurora_valid.json correctly results in NOT_CLEARED
    # due to specific territory and date gaps.
    file_path = "data/fixtures/project_aurora_valid.json"
    result = deterministic_clearance(file_path)
    
    assert result["status"] == "NOT_CLEARED"
    assert "decisions" in result
    assert result["summary"]["not_cleared"] > 0

def test_deterministic_clearance_blocked():
    """
    Prove that deterministic_clearance correctly blocks malformed packages.
    """
    file_path = "data/fixtures/project_aurora_quarantine_test.json"
    result = deterministic_clearance(file_path)
    
    assert result["status"] == "BLOCKED"
    assert "issues" in result

def test_tool_registration():
    """
    Verify all required tools are registered in the Vertex AI Tool object.
    """
    declarations = rightsready_tools.to_dict()["function_declarations"]
    names = [d["name"] for d in declarations]
    
    assert "deterministic_validate" in names
    assert "deterministic_clearance" in names
    assert "deterministic_pipeline_execute" in names
    assert "agent_query_warehouse" in names

# =============================================================================
# LEVEL 2: MCP PROTOCOL VERIFICATION (Unit)
# =============================================================================

@pytest.mark.asyncio
async def test_mcp_bridge_protocol_layer():
    """
    Prove that agent_query_warehouse goes through the MCP protocol layer.
    We mock the MCP session to verify call_tool is used.
    """
    bridge = MCPRuntimeBridge(command="python", args=["mock_mcp.py"])
    
    # Mock the internal MCP session
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.content = [MagicMock(text='[{"count": 5}]')]
    mock_result.isError = False
    mock_session.call_tool.return_value = mock_result
    
    bridge.session = mock_session
    
    query = "SELECT count() FROM assets"
    response = await bridge.run_query(query)
    
    assert response["content"] == ['[{"count": 5}]']
    assert not response["is_error"]
    
    # Verify the official MCP 'run_query' tool was called
    mock_session.call_tool.assert_called_once_with(
        "run_query",
        arguments={"query": query}
    )

# =============================================================================
# LEVEL 3: MCP RUNTIME INTEGRATION (Real Subprocess Verification)
# =============================================================================

@pytest.mark.asyncio
async def test_mcp_runtime_live_integration():
    """
    STRICT INTEGRATION VERIFICATION:
    Proves RightsReady -> MCP Protocol -> official mcp-clickhouse -> Live ClickHouse.
    
    Verifies that the database tables in 'rightsready' can be listed through MCP.
    """
    # SKIP if environment variables missing
    for var in ["CLICKHOUSE_HOST", "CLICKHOUSE_USER", "CLICKHOUSE_PASSWORD", "CLICKHOUSE_DATABASE"]:
        if not os.environ.get(var):
            pytest.skip(f"Environment variable {var} not set")

    from src.tools_mcp import MCPRuntimeBridge
    
    bridge = MCPRuntimeBridge()
    try:
        await bridge.connect()
        
        # Call the MCP 'list_tables' tool
        # According to the MCP ClickHouse server spec, it should list tables.
        # If the server uses a different tool name, we check list_tools first.
        tools = await bridge.session.list_tools()
        tool_names = [t.name for t in tools.tools]
        
        assert "list_tables" in tool_names
        
        # List tables in the 'rightsready' database
        result = await bridge.session.call_tool(
            "list_tables", 
            arguments={"database": "rightsready"}
        )
        
        # Verify result content contains the expected tables
        content_text = "".join([c.text for c in result.content if hasattr(c, 'text')])
        
        expected_tables = ["productions", "assets", "licenses", "asset_usage"]
        for table in expected_tables:
            assert table in content_text, f"Table {table} not found in MCP response: {content_text}"
            
        print(f"\n[MCP LIVE INTEGRATION SUCCESS]: Verified tables: {expected_tables}")
        
    finally:
        await bridge.disconnect()
