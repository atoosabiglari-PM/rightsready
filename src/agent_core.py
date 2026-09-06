import os
from vertexai.generative_models import GenerativeModel, Tool, FunctionDeclaration
from src.tools_deterministic import (
    deterministic_validate,
    deterministic_clearance,
    deterministic_pipeline_execute
)
from src.tools_mcp import agent_query_warehouse

# Register tools using the Vertex AI ADK FunctionDeclaration
rightsready_tools = Tool(
    function_declarations=[
        FunctionDeclaration.from_func(deterministic_validate),
        FunctionDeclaration.from_func(deterministic_clearance),
        FunctionDeclaration.from_func(deterministic_pipeline_execute),
        FunctionDeclaration.from_func(agent_query_warehouse),
    ]
)

class RightsReadyAgent:
    """
    The authoritative RightsReady Gemini Agent.
    Built with Vertex AI ADK.
    """

    SYSTEM_INSTRUCTION = """
    You are the RightsReady AI Orchestrator. 
    You manage media rights clearance by deferring to deterministic tools.

    GOVERNANCE RULES:
    1. You are a reporter and facilitator. You NEVER make clearance decisions yourself.
    2. The 'deterministic_clearance' and 'deterministic_pipeline_execute' tools are AUTHORITATIVE.
    3. If a tool returns 'NOT_CLEARED', 'BLOCKED', 'QUARANTINED', 'TERRITORY_GAP', or 'LICENSE_EXPIRED', you MUST report this result exactly. You have no authority to override or ignore it.
    4. For all data warehouse reads, you MUST use the 'agent_query_warehouse' tool (which uses the official MCP protocol). 
    5. Do not attempt to access the database directly.
    6. If validation fails, explain the specific issues provided by the 'deterministic_validate' tool.

    TONE: Senior, precise, and governance-oriented.
    """

    def __init__(self, model_name: str = "gemini-1.5-pro"):
        # Note: In production, Vertex AI initialization happens via cloud environment.
        self.model = GenerativeModel(
            model_name=model_name,
            system_instruction=self.SYSTEM_INSTRUCTION,
            tools=[rightsready_tools]
        )
        self.chat = self.model.start_chat()

    def handle_request(self, prompt: str):
        """
        Send a request to the agent.
        """
        # This is a synchronous wrapper for Milestone 1.
        response = self.chat.send_message(prompt)
        return response.text
