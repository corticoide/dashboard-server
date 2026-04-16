from unittest.mock import patch, MagicMock


def _login(test_app):
    r = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    return r.json()["access_token"]


MOCK_PROCS = [
    MagicMock(info={
        "pid": 1234, "name": "nginx", "cpu_percent": 0.2,
        "memory_info": MagicMock(rss=47_185_920),
        "username": "www-data", "status": "sleeping",
    }),
    MagicMock(info={
        "pid": 5678, "name": "python3", "cpu_percent": 12.4,
        "memory_info": MagicMock(rss=293_601_280),
        "username": "crt", "status": "running",
    }),
]


def test_list_processes_requires_auth(test_app):
    r = test_app.get("/api/processes/")
    assert r.status_code == 403


def test_list_processes_returns_sorted_by_cpu(test_app):
    token = _login(test_app)
    headers = {"Authorization": f"Bearer {token}"}

    with patch("backend.routers.processes.psutil.process_iter", return_value=iter(MOCK_PROCS)):
        r = test_app.get("/api/processes/", headers=headers)

    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert data[0]["name"] == "python3"   # higher CPU first
    assert data[0]["cpu_percent"] == 12.4
    assert data[1]["name"] == "nginx"


def test_list_processes_includes_watched_flag(test_app):
    token = _login(test_app)
    headers = {"Authorization": f"Bearer {token}"}

    # Create a watch rule for nginx
    test_app.post("/api/alerts/rules", headers=headers, json={
        "name": "Watch: nginx", "condition_type": "process_missing",
        "target": "nginx", "cooldown_minutes": 15,
        "notify_on_recovery": True, "email_to": "x@x.com",
    })

    with patch("backend.routers.processes.psutil.process_iter", return_value=iter(MOCK_PROCS)):
        r = test_app.get("/api/processes/", headers=headers)

    data = r.json()
    nginx = next(p for p in data if p["name"] == "nginx")
    assert nginx["watched"] is True
    python3 = next(p for p in data if p["name"] == "python3")
    assert python3["watched"] is False


def test_kill_process_not_found(test_app):
    token = _login(test_app)
    headers = {"Authorization": f"Bearer {token}"}

    import psutil as _psutil
    with patch("backend.routers.processes.psutil.Process", side_effect=_psutil.NoSuchProcess(99999)):
        r = test_app.post("/api/processes/99999/kill", headers=headers)

    assert r.status_code == 404


def test_watch_creates_alert_rule(test_app):
    token = _login(test_app)
    headers = {"Authorization": f"Bearer {token}"}

    r = test_app.post("/api/processes/watch", headers=headers, json={
        "name": "postgres",
        "email_to": "ops@test.com",
        "cooldown_minutes": 15,
    })
    assert r.status_code == 201

    rules = test_app.get("/api/alerts/rules", headers=headers).json()
    assert any(
        r["condition_type"] == "process_missing" and r["target"] == "postgres"
        for r in rules
    )


def test_unwatch_removes_alert_rule(test_app):
    token = _login(test_app)
    headers = {"Authorization": f"Bearer {token}"}

    test_app.post("/api/processes/watch", headers=headers, json={
        "name": "redis",
        "email_to": "ops@test.com",
        "cooldown_minutes": 15,
    })

    r = test_app.delete("/api/processes/watch/redis", headers=headers)
    assert r.status_code == 204

    rules = test_app.get("/api/alerts/rules", headers=headers).json()
    assert not any(r["target"] == "redis" for r in rules)
