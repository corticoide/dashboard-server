from unittest.mock import patch
from backend.schemas.services import ServiceInfo, ServiceLog

MOCK_SERVICES = [
    ServiceInfo(name="ssh.service", load_state="loaded", active_state="active",
                sub_state="running", description="SSH Server", enabled="enabled"),
    ServiceInfo(name="cron.service", load_state="loaded", active_state="inactive",
                sub_state="dead", description="Cron daemon", enabled="enabled"),
]

def test_list_services_requires_auth(test_app):
    r = test_app.get("/api/services/")
    assert r.status_code == 403

def test_list_services_returns_list(test_app):
    login = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    token = login.json()["access_token"]
    with patch("backend.routers.services.list_services", return_value=MOCK_SERVICES):
        r = test_app.get("/api/services/", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert data[0]["name"] == "ssh.service"

def test_get_logs_returns_data(test_app):
    login = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    token = login.json()["access_token"]
    mock_log = ServiceLog(service="ssh.service", lines=["Mar 25 10:00:00 srv sshd: started"])
    with patch("backend.routers.services.get_service_logs", return_value=mock_log):
        r = test_app.get("/api/services/ssh.service/logs",
                         headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["service"] == "ssh.service"

def test_control_invalid_action_returns_400(test_app):
    login = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    token = login.json()["access_token"]
    with patch("backend.routers.services.control_service", side_effect=ValueError("Invalid action")):
        r = test_app.post("/api/services/ssh.service/delete",
                          headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400
