from google.adk.apps import App
from src.agent_core import root_agent

# Create the ADK application instance
app = App(
    name="rightsready",
    root_agent=root_agent
)
