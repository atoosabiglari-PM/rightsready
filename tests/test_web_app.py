import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch
from src.web_app import app

client = TestClient(app)

@pytest.fixture
def mock_agent_client():
    with patch("src.web_app.get_agent_client") as mock:
        mock_client = MagicMock()
        # Ensure async methods are AsyncMocks
        mock_client.async_stream_query = AsyncMock()
        mock_client.analyze_clearance = AsyncMock()
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

def test_analyze_success(mock_agent_client):
    mock_data = {
            "status": "CLEARED",
            "summary": {"total_usages": 1, "cleared": 1, "not_cleared": 0},
            "decisions": []
        }
    mock_agent_client.analyze_clearance.return_value = {
        "answer": "Explanation",
        "clearance_result": mock_data
    }
    response = client.post("/api/analyze")
    assert response.status_code == 200
    assert response.json()["overall_status"] == "CLEARED"
    assert response.json()["summary"] == mock_data["summary"]

def test_analyze_failure_malformed_status(mock_agent_client):
    # Missing status
    mock_agent_client.analyze_clearance.return_value = {
        "answer": "Explanation",
        "clearance_result": {
            "summary": {"total_usages": 1, "cleared": 1, "not_cleared": 0},
            "decisions": []
        }
    }
    response = client.post("/api/analyze")
    assert response.status_code == 500

def test_analyze_failure_malformed_summary(mock_agent_client):
    # Missing summary
    mock_agent_client.analyze_clearance.return_value = {
        "answer": "Explanation",
        "clearance_result": {
            "status": "CLEARED",
            "decisions": []
        }
    }
    response = client.post("/api/analyze")
    assert response.status_code == 500

def test_analyze_failure_malformed_decisions(mock_agent_client):
    # Missing decisions
    mock_agent_client.analyze_clearance.return_value = {
        "answer": "Explanation",
        "clearance_result": {
            "status": "CLEARED",
            "summary": {"total_usages": 1, "cleared": 1, "not_cleared": 0}
        }
    }
    response = client.post("/api/analyze")
    assert response.status_code == 500

def test_analyze_failure_malformed_summary_counts(mock_agent_client):
    # Missing summary count fields
    mock_agent_client.analyze_clearance.return_value = {
        "answer": "Explanation",
        "clearance_result": {
            "status": "CLEARED",
            "summary": {"total": 5},
            "decisions": []
        }
    }
    response = client.post("/api/analyze")
    assert response.status_code == 500
