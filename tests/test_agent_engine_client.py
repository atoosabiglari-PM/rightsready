import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import os
import uuid
import json
from src.agent_engine_client import AgentEngineClient

@pytest.fixture
def mock_env():
    with patch.dict(os.environ, {
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "GOOGLE_CLOUD_LOCATION": "us-central1",
        "RIGHTSREADY_AGENT_ENGINE_RESOURCE": "projects/test/locations/test/agentEngines/test"
    }):
        yield

# --- 3B.4 Regression Tests ---
@pytest.mark.asyncio
async def test_async_stream_query_returns_text(mock_env):
    with patch("vertexai.init"), patch("vertexai.agent_engines.get") as mock_get:
        mock_agent = MagicMock()
        mock_get.return_value = mock_agent

        async def mock_stream(*args, **kwargs):
            yield {"content": {"role": "model", "parts": [{"text": "final answer"}]}}
        mock_agent.async_stream_query = mock_stream

        client = AgentEngineClient()
        assert await client.async_stream_query("Hello?") == "final answer"

@pytest.mark.asyncio
async def test_analyze_clearance_success(mock_env):
    with patch("vertexai.init"), patch("vertexai.agent_engines.get") as mock_get:
        mock_agent = MagicMock()
        mock_get.return_value = mock_agent

        async def mock_stream(*args, **kwargs):
            yield {"content": {"role": "model", "parts": [{"text": "Final explanation"}]}}
            yield {"content": {"parts": [{"function_response": {"name": "deterministic_clearance", "response": {"status": "CLEARED"}}}]}}
        mock_agent.async_stream_query = mock_stream

        client = AgentEngineClient()
        result = await client.analyze_clearance("Analyze")
        assert result["answer"] == "Final explanation"
        assert result["clearance_result"] == {"status": "CLEARED"}

@pytest.mark.asyncio
async def test_analyze_clearance_ignores_unrelated(mock_env):
    with patch("vertexai.init"), patch("vertexai.agent_engines.get") as mock_get:
        mock_agent = MagicMock()
        mock_get.return_value = mock_agent

        async def mock_stream(*args, **kwargs):
            yield {"content": {"role": "model", "parts": [{"text": "text"}]}}
            yield {"content": {"parts": [{"function_response": {"name": "other_tool", "response": {}}}]}}
            yield {"content": {"parts": [{"function_response": {"name": "deterministic_clearance", "response": {"status": "CLEARED"}}}]}}
        mock_agent.async_stream_query = mock_stream

        client = AgentEngineClient()
        result = await client.analyze_clearance("Analyze")
        assert result["clearance_result"] == {"status": "CLEARED"}

@pytest.mark.asyncio
async def test_analyze_clearance_fails_no_tool(mock_env):
    with patch("vertexai.init"), patch("vertexai.agent_engines.get") as mock_get:
        mock_agent = MagicMock()
        mock_get.return_value = mock_agent

        async def mock_stream(*args, **kwargs):
            yield {"content": {"role": "model", "parts": [{"text": "text"}]}}
        mock_agent.async_stream_query = mock_stream

        client = AgentEngineClient()
        with pytest.raises(Exception, match="deterministic_clearance result not found"):
            await client.analyze_clearance("Analyze")

# --- 3B.5 Warehouse Tool Tests ---
@pytest.mark.asyncio
async def test_ask_with_evidence_success(mock_env):
    with patch("vertexai.init"), patch("vertexai.agent_engines.get") as mock_get:
        mock_agent = MagicMock()
        mock_get.return_value = mock_agent

        payload = {"columns": ["c1"], "rows": [[1]]}
        async def mock_stream(*args, **kwargs):
            yield {"content": {"role": "model", "parts": [{"text": "Explanation"}]}}
            yield {"content": {"parts": [{"function_response": {"name": "agent_query_warehouse", "response": {"content": [json.dumps(payload)], "is_error": False}}}]}}
        mock_agent.async_stream_query = mock_stream

        client = AgentEngineClient()
        result = await client.ask_with_evidence("Query")
        assert result["answer"] == "Explanation"
        assert result["warehouse_evidence"]["columns"] == ["c1"]
        assert result["warehouse_evidence"]["rows"] == [[1]]

@pytest.mark.asyncio
async def test_ask_with_evidence_ignores_deterministic_clearance(mock_env):
    with patch("vertexai.init"), patch("vertexai.agent_engines.get") as mock_get:
        mock_agent = MagicMock()
        mock_get.return_value = mock_agent

        async def mock_stream(*args, **kwargs):
            yield {"content": {"role": "model", "parts": [{"text": "text"}]}}
            yield {"content": {"parts": [{"function_response": {"name": "deterministic_clearance", "response": {"status": "CLEARED"}}}]}}
        mock_agent.async_stream_query = mock_stream

        client = AgentEngineClient()
        result = await client.ask_with_evidence("Query")
        assert "warehouse_evidence" not in result

@pytest.mark.asyncio
async def test_ask_with_evidence_is_error_fails(mock_env):
    with patch("vertexai.init"), patch("vertexai.agent_engines.get") as mock_get:
        mock_agent = MagicMock()
        mock_get.return_value = mock_agent

        async def mock_stream(*args, **kwargs):
            yield {"content": {"role": "model", "parts": [{"text": "text"}]}}
            yield {"content": {"parts": [{"function_response": {"name": "agent_query_warehouse", "response": {"is_error": True}}}]}}
        mock_agent.async_stream_query = mock_stream

        client = AgentEngineClient()
        with pytest.raises(ValueError, match="Tool execution failed"):
            await client.ask_with_evidence("Query")

@pytest.mark.asyncio
async def test_ask_with_evidence_malformed_json_fails(mock_env):
    with patch("vertexai.init"), patch("vertexai.agent_engines.get") as mock_get:
        mock_agent = MagicMock()
        mock_get.return_value = mock_agent

        async def mock_stream(*args, **kwargs):
            yield {"content": {"role": "model", "parts": [{"text": "text"}]}}
            yield {"content": {"parts": [{"function_response": {"name": "agent_query_warehouse", "response": {"content": ["invalid"], "is_error": False}}}]}}
        mock_agent.async_stream_query = mock_stream

        client = AgentEngineClient()
        with pytest.raises(ValueError, match="Malformed JSON content"):
            await client.ask_with_evidence("Query")

@pytest.mark.asyncio
async def test_ask_with_evidence_missing_fields_fails(mock_env):
    with patch("vertexai.init"), patch("vertexai.agent_engines.get") as mock_get:
        mock_agent = MagicMock()
        mock_get.return_value = mock_agent

        payload = {"columns": ["c1"]} # Missing rows
        async def mock_stream(*args, **kwargs):
            yield {"content": {"role": "model", "parts": [{"text": "text"}]}}
            yield {"content": {"parts": [{"function_response": {"name": "agent_query_warehouse", "response": {"content": [json.dumps(payload)], "is_error": False}}}]}}
        mock_agent.async_stream_query = mock_stream

        client = AgentEngineClient()
        with pytest.raises(ValueError, match="Invalid evidence schema"):
            await client.ask_with_evidence("Query")
