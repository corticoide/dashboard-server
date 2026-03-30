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


def test_stats_query_counts_correctly(test_app):
    from backend.main import app
    from backend.database import get_db
    from datetime import datetime, timezone

    db = next(app.dependency_overrides[get_db]())
    now = datetime.now(timezone.utc)
    db.add(ExecutionLog(script_path="/a.sh", username="admin", started_at=now, exit_code=0))
    db.add(ExecutionLog(script_path="/b.sh", username="admin", started_at=now, exit_code=0))
    db.add(ExecutionLog(script_path="/c.sh", username="admin", started_at=now, exit_code=1))
    db.commit()
    db.close()
    token = get_token(test_app)
    r = test_app.get("/api/logs/executions/stats", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
    assert data["success"] == 2
    assert data["failed"] == 1
    assert data["last_24h"] == 3


def test_pagination_offset_and_limit(test_app):
    from backend.main import app
    from backend.database import get_db
    from datetime import datetime, timezone

    db = next(app.dependency_overrides[get_db]())
    for i in range(10):
        db.add(ExecutionLog(
            script_path=f"/script_{i}.sh",
            username="admin",
            started_at=datetime.now(timezone.utc),
            exit_code=0,
        ))
    db.commit()
    db.close()
    token = get_token(test_app)
    headers = {"Authorization": f"Bearer {token}"}
    r = test_app.get("/api/logs/executions?limit=5&offset=0", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 5
    assert r.headers.get("x-total-count") == "10"
    r2 = test_app.get("/api/logs/executions?limit=5&offset=5", headers=headers)
    assert r2.status_code == 200
    assert len(r2.json()) == 5
    ids_p1 = {item["id"] for item in r.json()}
    ids_p2 = {item["id"] for item in r2.json()}
    assert ids_p1.isdisjoint(ids_p2)
