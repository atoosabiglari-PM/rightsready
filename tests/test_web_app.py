import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch
from src.web_app import app

client = TestClient(app)

@pytest.fixture
def mock_agent_client():
    with patch("src.web_app.get_agent_client") as mock:
        mock_client = MagicMock()
        mock_client.async_stream_query = AsyncMock()
        mock_client.ask_with_evidence = AsyncMock()
        mock_client.analyze_clearance = AsyncMock()
        mock.return_value = mock_client
        yield mock_client

def test_health():
    response = client.get("/health")
    assert response.status_code == 200

def test_ask_empty_question():
    response = client.post("/api/ask", json={"question": ""})
    assert response.status_code == 400

def test_ask_whitespace_only():
    response = client.post("/api/ask", json={"question": "   "})
    assert response.status_code == 400

def test_ask_success(mock_agent_client):
    mock_agent_client.ask_with_evidence.return_value = {"answer": "Mocked answer"}
    response = client.post("/api/ask", json={"question": "Test question"})
    assert response.status_code == 200
    assert response.json() == {"answer": "Mocked answer"}

# L, M, N: Evidence parsing and returning
def test_ask_with_evidence_success(mock_agent_client):
    mock_data = {
        "source": "ClickHouse via MCP",
        "tool": "agent_query_warehouse",
        "columns": ["asset_count"],
        "rows": [[5]]
    }
    mock_agent_client.ask_with_evidence.return_value = {
        "answer": "There are 5 assets.",
        "warehouse_evidence": mock_data
    }
    response = client.post("/api/ask", json={"question": "How many assets?"})
    assert response.status_code == 200
    assert response.json()["warehouse_evidence"] == mock_data

# P: Agent/MCP failure returns safe generic HTTP 500 message
def test_ask_failure_generic_error(mock_agent_client):
    mock_agent_client.ask_with_evidence.side_effect = Exception("Hidden system error")
    response = client.post("/api/ask", json={"question": "Question?"})
    assert response.status_code == 500
    assert response.json()["detail"] == "RightsReady could not complete this query."

# Q: Analyze tests remain intact
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
