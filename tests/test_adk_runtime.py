import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from google.genai import types
from src.adk_runtime import run_adk_prompt
from src.adk_app import app

@pytest.mark.asyncio
async def test_run_adk_prompt_full_flow():
    # Setup mocks
    mock_runner = MagicMock()
    # create_session must be an AsyncMock
    mock_runner.session_service.create_session = AsyncMock()
    
    # Define an async generator for run_async
    async def async_generator(*args, **kwargs):
        # Construct mock event for types.Content structure
        event = MagicMock()
        event.is_final_response.return_value = True
        
        # event.content.parts structure
        part = MagicMock()
        part.text = "Hello, world!"
        
        content = MagicMock()
        content.parts = [part]
        event.content = content
        
        yield event
    
    mock_runner.run_async.side_effect = async_generator
    
    # Patch InMemoryRunner
    with patch("src.adk_runtime.InMemoryRunner") as MockRunner:
        MockRunner.return_value = mock_runner
        
        user_id = "test-user-123"
        session_id = "test-session-456"
        prompt = "Hello"
        
        # Call the function
        result = await run_adk_prompt(prompt, user_id=user_id, session_id=session_id)
        
        # Assertions
        
        # Verify InMemoryRunner construction
        MockRunner.assert_called_once_with(app=app)
        
        # Verify result
        assert result == "Hello, world!"
        
        # Verify create_session awaited exactly once
        mock_runner.session_service.create_session.assert_awaited_once_with(
            app_name=app.name,
            user_id=user_id,
            session_id=session_id
        )
        
        # Verify run_async called exactly once
        mock_runner.run_async.assert_called_once()
        
        # Inspect arguments of run_async
        args, kwargs = mock_runner.run_async.call_args
        assert kwargs["user_id"] == user_id
        assert kwargs["session_id"] == session_id
        
        # Verify types.Content structure in new_message
        new_message = kwargs["new_message"]
        assert isinstance(new_message, types.Content)
        assert new_message.role == "user"
        assert len(new_message.parts) == 1
        assert new_message.parts[0].text == prompt
