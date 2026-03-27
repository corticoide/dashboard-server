def test_poll_execution_reads_is_running_from_db(test_app):
    """poll_execution must use is_running from DB when exec not in _running dict."""
    token = test_app.post(
        "/api/auth/login", json={"username": "admin", "password": "adminpass"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create a ScriptExecution directly in DB (simulating another worker started it)
    from backend.database import SessionLocal
    from backend.models.script import ScriptExecution, ScriptFavorite

    db = SessionLocal()
    fav = ScriptFavorite(path="/usr/bin/true")
    db.add(fav)
    db.flush()
    exe = ScriptExecution(
        script_path="/usr/bin/true",
        run_as_root=False,
        triggered_by="admin",
        is_running=True,
        output="line1\nline2",
    )
    db.add(exe)
    db.commit()
    exec_id = exe.id
    db.close()

    # Confirm NOT in _running (simulates different worker)
    from backend.services import scripts_service
    assert exec_id not in scripts_service._running

    r = test_app.get(f"/api/scripts/executions/{exec_id}", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["running"] is True
    assert "line1" in data["lines"]
    assert "line2" in data["lines"]


def test_poll_execution_completed_shows_not_running(test_app):
    """Completed execution must show running=False from DB."""
    token = test_app.post(
        "/api/auth/login", json={"username": "admin", "password": "adminpass"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    from backend.database import SessionLocal
    from backend.models.script import ScriptExecution, ScriptFavorite
    from datetime import datetime, timezone

    db = SessionLocal()
    fav = ScriptFavorite(path="/usr/bin/true")
    db.add(fav)
    db.flush()
    exe = ScriptExecution(
        script_path="/usr/bin/true",
        run_as_root=False,
        triggered_by="admin",
        is_running=False,
        output="done",
        exit_code=0,
        ended_at=datetime.now(timezone.utc),
    )
    db.add(exe)
    db.commit()
    exec_id = exe.id
    db.close()

    r = test_app.get(f"/api/scripts/executions/{exec_id}", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["running"] is False
    assert data["exit_code"] == 0
