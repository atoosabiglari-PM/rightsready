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
            yield {"role": "tool"} # Tool event, should be ignored
            yield {"content": {"parts": [{"text": "final"}, {"text": " answer"}], "role": "model"}} # Multiple text parts
        
        mock_agent.async_stream_query = mock_stream
        
        client = AgentEngineClient()
        answer = await client.async_stream_query("Hello?")
        
        assert answer == "final answer"

@pytest.mark.asyncio
async def test_async_stream_query_failure(mock_env):
    with patch("vertexai.init"), \
         patch("vertexai.agent_engines.get") as mock_get:
        
        mock_agent = MagicMock()
        mock_get.return_value = mock_agent
        
        # Define empty async stream
        async def mock_stream(*args, **kwargs):
            yield {}
        
        mock_agent.async_stream_query = mock_stream
        
        client = AgentEngineClient()
        with pytest.raises(Exception, match="Agent Engine failed to return a valid response."):
            await client.async_stream_query("Hello?")
