import pytest
from datetime import datetime, timezone
from backend.models.execution_log import ExecutionLog


def get_token(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    return r.json()["access_token"]


def test_get_logs_requires_auth(test_app):
    r = test_app.get("/api/logs/executions")
    assert r.status_code == 403


def test_get_logs_returns_list(test_app):
    token = get_token(test_app)
    r = test_app.get("/api/logs/executions", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_stats_returns_counts(test_app):
    token = get_token(test_app)
    r = test_app.get("/api/logs/executions/stats", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert "total" in data
    assert "success" in data
    assert "failed" in data
    assert "last_24h" in data


def test_get_logs_filters(test_app):
    from backend.main import app
    from backend.database import get_db
    db = next(app.dependency_overrides[get_db]())
    log = ExecutionLog(
        script_path="/home/user/test.py",
        username="admin",
        started_at=datetime.now(timezone.utc),
        exit_code=0,
        duration_seconds=1.5,
        output_summary="hello",
    )
    db.add(log)
    db.commit()
    db.close()

    token = get_token(test_app)
    headers = {"Authorization": f"Bearer {token}"}

    r = test_app.get("/api/logs/executions?script=test.py", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1

    r = test_app.get("/api/logs/executions?exit_code=0", headers=headers)
    assert r.status_code == 200
    assert all(e["exit_code"] == 0 for e in r.json())
