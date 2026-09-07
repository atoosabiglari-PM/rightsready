from google.adk.runners import InMemoryRunner
from google.genai import types
from src.adk_app import app

async def run_adk_prompt(
    prompt: str,
    user_id: str = "test-user",
    session_id: str = "test-session"
) -> str:
    """
    Runs a prompt through the local ADK runtime and returns the final text response.
    """
    runner = InMemoryRunner(app=app)
    
    # Create the session
    await runner.session_service.create_session(
        app_name=app.name,
        user_id=user_id,
        session_id=session_id
    )

    # Construct the user message
    message = types.Content(
        parts=[types.Part.from_text(text=prompt)],
        role="user"
    )

    # Run the prompt
    final_text = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=message
    ):
        if event.is_final_response():
            # Safely extract text from the final event content parts
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        final_text += part.text
                        
    return final_text
