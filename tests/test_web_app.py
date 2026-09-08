import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch
from src.web_app import app

client = TestClient(app)

@pytest.fixture
def mock_agent_client():
    with patch("src.web_app.get_agent_client") as mock:
        mock_client = MagicMock()
        # Ensure async_stream_query is an AsyncMock
        mock_client.async_stream_query = AsyncMock()
        mock.return_value = mock_client
        yield mock_client

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_homepage():
    response = client.get("/")
    assert response.status_code == 200
    assert "RightsReady" in response.text
    assert "Project Aurora" in response.text

def test_ask_empty_question():
    response = client.post("/api/ask", json={"question": ""})
    assert response.status_code == 400

def test_ask_whitespace_only():
    response = client.post("/api/ask", json={"question": "   "})
    assert response.status_code == 400

def test_ask_success(mock_agent_client):
    mock_agent_client.async_stream_query.return_value = "Mocked answer"
    response = client.post("/api/ask", json={"question": "Test question"})
    assert response.status_code == 200
    assert response.json() == {"answer": "Mocked answer"}
    mock_agent_client.async_stream_query.assert_called_once_with("Test question")

def test_ask_whitespace_stripping(mock_agent_client):
    mock_agent_client.async_stream_query.return_value = "Mocked answer"
    response = client.post("/api/ask", json={"question": "   Test question   "})
    assert response.status_code == 200
    assert response.json() == {"answer": "Mocked answer"}
    mock_agent_client.async_stream_query.assert_called_once_with("Test question")

def test_analyze_success(mock_agent_client):
    mock_agent_client.async_stream_query.return_value = "Mocked clearance"
    response = client.post("/api/analyze")
    assert response.status_code == 200
    assert response.json() == {"answer": "Mocked clearance"}

def test_agent_failure(mock_agent_client):
    mock_agent_client.async_stream_query.side_effect = Exception("Failed")
    response = client.post("/api/ask", json={"question": "Test question"})
    assert response.status_code == 500
    assert "Agent Engine invocation failed." in response.json()["detail"]
