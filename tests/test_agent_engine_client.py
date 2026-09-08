import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import os
import uuid
from src.agent_engine_client import AgentEngineClient

@pytest.fixture
def mock_env():
    with patch.dict(os.environ, {
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "GOOGLE_CLOUD_LOCATION": "us-central1",
        "RIGHTSREADY_AGENT_ENGINE_RESOURCE": "projects/test/locations/test/agentEngines/test"
    }):
        yield

def test_config_missing_fails():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(EnvironmentError):
            AgentEngineClient()

def test_init_and_get(mock_env):
    with patch("vertexai.init") as mock_init, \
         patch("vertexai.agent_engines.get") as mock_get:

        client = AgentEngineClient()

        mock_init.assert_called_once_with(project="test-project", location="us-central1")
        mock_get.assert_called_once_with("projects/test/locations/test/agentEngines/test")

@pytest.mark.asyncio
async def test_async_stream_query_success(mock_env):
    with patch("vertexai.init"), \
         patch("vertexai.agent_engines.get") as mock_get:

        mock_agent = MagicMock()
        mock_get.return_value = mock_agent

        # Define the async stream
        async def mock_stream(*args, **kwargs):
            yield {"content": {"parts": [{"text": "intermediate explanation"}], "role": "model"}}
            yield {"content": {"parts": [{"text": "final"}, {"text": " answer"}], "role": "model"}} # Multiple text parts

        mock_agent.async_stream_query = mock_stream

        client = AgentEngineClient()
        answer = await client.async_stream_query("Hello?")

        assert answer == "final answer"

@pytest.mark.asyncio
async def test_analyze_clearance_success(mock_env):
    with patch("vertexai.init"), \
         patch("vertexai.agent_engines.get") as mock_get:

        mock_agent = MagicMock()
        mock_get.return_value = mock_agent

        # Define the async stream with tool response
        async def mock_stream(*args, **kwargs):
            yield {"content": {"parts": [{"text": "final explanation"}], "role": "model"}}
            # Tool response with correct structure
            yield {
                "content": {
                    "parts": [{
                        "function_response": {
                            "name": "deterministic_clearance",
                            "response": {
                                "status": "NOT_CLEARED",
                                "summary": {"total_usages": 5, "cleared": 2, "not_cleared": 3},
                                "decisions": []
                            }
                        }
                    }]
                }
            }

        mock_agent.async_stream_query = mock_stream

        client = AgentEngineClient()
        result = await client.analyze_clearance("Analyze this")

        assert result["answer"] == "final explanation"
        assert result["clearance_result"]["status"] == "NOT_CLEARED"

@pytest.mark.asyncio
async def test_analyze_clearance_ignores_other_tool(mock_env):
    with patch("vertexai.init"), \
         patch("vertexai.agent_engines.get") as mock_get:

        mock_agent = MagicMock()
        mock_get.return_value = mock_agent

        # Define the async stream with other tool and then deterministic
        async def mock_stream(*args, **kwargs):
            yield {"content": {"parts": [{"text": "explanation"}], "role": "model"}}
            # Another tool
            yield {
                "content": {
                    "parts": [{
                        "function_response": {
                            "name": "agent_query_warehouse",
                            "response": {"data": "ignore_me"}
                        }
                    }]
                }
            }
            # Deterministic tool
            yield {
                "content": {
                    "parts": [{
                        "function_response": {
                            "name": "deterministic_clearance",
                            "response": {
                                "status": "CLEARED",
                                "summary": {"total_usages": 1, "cleared": 1, "not_cleared": 0},
                                "decisions": []
                            }
                        }
                    }]
                }
            }

        mock_agent.async_stream_query = mock_stream

        client = AgentEngineClient()
        result = await client.analyze_clearance("Analyze this")

        assert result["clearance_result"]["status"] == "CLEARED"

@pytest.mark.asyncio
async def test_analyze_clearance_fails_closed_no_tool(mock_env):
    with patch("vertexai.init"), \
         patch("vertexai.agent_engines.get") as mock_get:

        mock_agent = MagicMock()
        mock_get.return_value = mock_agent

        # Define the async stream without tool response
        async def mock_stream(*args, **kwargs):
            yield {"content": {"parts": [{"text": "final explanation"}], "role": "model"}}

        mock_agent.async_stream_query = mock_stream

        client = AgentEngineClient()
        with pytest.raises(Exception, match="Authoritative deterministic_clearance result not found."):
            await client.analyze_clearance("Analyze this")
