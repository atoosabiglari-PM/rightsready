import pytest
from fastapi.testclient import TestClient
from src.web_app import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_homepage():
    response = client.get("/")
    assert response.status_code == 200
    assert "RightsReady" in response.text
    assert "Project Aurora" in response.text
