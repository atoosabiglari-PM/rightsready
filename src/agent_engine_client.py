import os
import uuid
import vertexai
from vertexai import agent_engines

class AgentEngineClient:
    def __init__(self):
        self.project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        self.location = os.environ.get("GOOGLE_CLOUD_LOCATION")
        self.resource_name = os.environ.get("RIGHTSREADY_AGENT_ENGINE_RESOURCE")

        if not all([self.project, self.location, self.resource_name]):
            raise EnvironmentError("Missing required environment variables for Agent Engine.")

        vertexai.init(project=self.project, location=self.location)
        self.agent = agent_engines.get(self.resource_name)

    async def async_stream_query(self, prompt: str) -> str:
        """
        Invokes the agent and collects the final response.
        """
        user_id = str(uuid.uuid4())
        final_text = None
        
        async for event in self.agent.async_stream_query(
            message=prompt,
            user_id=user_id
        ):
            # Extract text from model response events
            content = event.get("content", {})
            if content.get("role") == "model" and "parts" in content:
                event_text = ""
                for part in content["parts"]:
                    if "text" in part:
                        event_text += part["text"]
                
                if event_text:
                    final_text = event_text
        
        if final_text is None:
            raise Exception("Agent Engine failed to return a valid response.")
            
        return final_text

# Singleton instance
_client = None

def get_agent_client():
    global _client
    if _client is None:
        _client = AgentEngineClient()
    return _client
