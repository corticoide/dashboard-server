import pytest


def _auth(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_create_and_list_pipeline(test_app):
    h = _auth(test_app)
    r = test_app.post("/api/pipelines", json={
        "name": "test-pipe",
        "description": "desc",
        "steps": [
            {"name": "step1", "step_type": "shell", "config": {"command": "echo hi"},
             "on_success": "continue", "on_failure": "stop", "order": 0}
        ]
    }, headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "test-pipe"
    assert data["step_count"] == 1

    r2 = test_app.get("/api/pipelines", headers=h)
    assert r2.status_code == 200
    assert len(r2.json()) == 1


def test_get_pipeline_detail(test_app):
    h = _auth(test_app)
    r = test_app.post("/api/pipelines", json={"name": "detail-pipe", "steps": []}, headers=h)
    pid = r.json()["id"]
    r2 = test_app.get(f"/api/pipelines/{pid}", headers=h)
    assert r2.status_code == 200
    assert r2.json()["id"] == pid


def test_update_pipeline(test_app):
    h = _auth(test_app)
    r = test_app.post("/api/pipelines", json={"name": "update-me", "steps": []}, headers=h)
    pid = r.json()["id"]
    r2 = test_app.put(f"/api/pipelines/{pid}", json={
        "name": "updated-name",
        "description": "new desc",
        "steps": []
    }, headers=h)
    assert r2.status_code == 200
    assert r2.json()["name"] == "updated-name"


def test_delete_pipeline(test_app):
    h = _auth(test_app)
    r = test_app.post("/api/pipelines", json={"name": "delete-me", "steps": []}, headers=h)
    pid = r.json()["id"]
    r2 = test_app.delete(f"/api/pipelines/{pid}", headers=h)
    assert r2.status_code == 200
    r3 = test_app.get(f"/api/pipelines/{pid}", headers=h)
    assert r3.status_code == 404


def test_manual_run(test_app):
    h = _auth(test_app)
    r = test_app.post("/api/pipelines", json={
        "name": "runnable",
        "steps": [{"name": "s1", "step_type": "shell", "config": {"command": "echo test"},
                   "on_success": "continue", "on_failure": "stop", "order": 0}]
    }, headers=h)
    pid = r.json()["id"]
    r2 = test_app.post(f"/api/pipelines/{pid}/run", headers=h)
    assert r2.status_code == 200
    assert "run_id" in r2.json()


def test_run_history(test_app):
    h = _auth(test_app)
    r = test_app.post("/api/pipelines", json={"name": "hist-pipe", "steps": []}, headers=h)
    pid = r.json()["id"]
    test_app.post(f"/api/pipelines/{pid}/run", headers=h)
    import time; time.sleep(0.3)  # esperar que el ThreadPoolExecutor termine
    r2 = test_app.get(f"/api/pipelines/{pid}/runs", headers=h)
    assert r2.status_code == 200
