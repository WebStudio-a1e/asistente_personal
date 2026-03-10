"""Tests para src/main.py — T-003."""

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health_status_200():
    response = client.get("/health")
    assert response.status_code == 200


def test_health_body():
    response = client.get("/health")
    assert response.json() == {"status": "ok"}


def test_health_content_type():
    response = client.get("/health")
    assert "application/json" in response.headers["content-type"]
