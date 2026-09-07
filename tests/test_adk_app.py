from src.adk_app import app
from src.agent_core import root_agent
from google.adk.apps import App

def test_app_is_adk_app():
    assert isinstance(app, App)

def test_app_root_agent_is_correct():
    assert app.root_agent is root_agent

def test_app_name_is_correct():
    assert app.name == "rightsready"
