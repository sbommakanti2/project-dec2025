"""Minimal regression test that ensures the health endpoint stays public."""

from fastapi.testclient import TestClient

from app.main import app


def test_health_check():
    """The ALB relies on this remaining stable, so lock its behavior."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
