import os
import uuid
import vertexai
from typing import Any, Dict
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

    async def ask_with_evidence(self, prompt: str) -> Dict[str, Any]:
        """
        Invokes the agent, collects the final response and the optional
        agent_query_warehouse tool response.
        """
        user_id = str(uuid.uuid4())
        final_text = None
        warehouse_evidence = None

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

            # Extract agent_query_warehouse function response
            content = event.get("content", {})
            for part in content.get("parts", []):
                function_response = part.get("function_response")
                if function_response and function_response.get("name") == "agent_query_warehouse":
                    warehouse_evidence = self._normalize_warehouse_evidence(function_response.get("response"))

        if final_text is None:
            raise Exception("Agent Engine failed to return a valid response.")

        result = {"answer": final_text}
        if warehouse_evidence:
            result["warehouse_evidence"] = warehouse_evidence

        return result

    def _normalize_warehouse_evidence(self, response: Any) -> Dict[str, Any]:
        """
        Parses and normalizes the warehouse tool response safely.
        """
        import json
        if not isinstance(response, dict) or response.get("is_error"):
            raise ValueError("Tool execution failed.")

        content = response.get("content")
        if not isinstance(content, list) or not content:
            raise ValueError("Malformed response content.")

        # Assume the first string part contains the JSON payload
        try:
            data = json.loads(content[0])
        except (json.JSONDecodeError, TypeError, IndexError):
            raise ValueError("Malformed JSON content.")

        if not isinstance(data.get("columns"), list) or not isinstance(data.get("rows"), list):
            raise ValueError("Invalid evidence schema.")

        return {
            "source": "ClickHouse via MCP",
            "tool": "agent_query_warehouse",
            "columns": data["columns"],
            "rows": data["rows"]
        }

    async def analyze_clearance(self, prompt: str) -> Dict[str, Any]:
        """
        Invokes the agent, collects the final response and the authoritative
        deterministic_clearance tool response.
        """
        user_id = str(uuid.uuid4())
        final_text = None
        clearance_result = None

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

            # Extract deterministic_clearance function response
            content = event.get("content", {})
            for part in content.get("parts", []):
                function_response = part.get("function_response")
                if function_response and function_response.get("name") == "deterministic_clearance":
                    clearance_result = function_response.get("response")

        if final_text is None:
            raise Exception("Agent Engine failed to return a valid response.")

        if clearance_result is None:
            raise Exception("Authoritative deterministic_clearance result not found.")

        return {
            "answer": final_text,
            "clearance_result": clearance_result
        }

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
