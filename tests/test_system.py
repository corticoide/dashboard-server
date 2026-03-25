from unittest.mock import patch
from backend.schemas.system import SystemMetrics


MOCK_METRICS = SystemMetrics(
    cpu_percent=25.0, ram_percent=50.0, ram_used_gb=4.0, ram_total_gb=8.0,
    disk_percent=40.0, disk_used_gb=40.0, disk_total_gb=100.0,
    uptime_seconds=3600, load_average=[1.0, 0.8, 0.5], os_name="Linux 6.6.87"
)


def test_metrics_endpoint_returns_data(test_app):
    login = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    token = login.json()["access_token"]
    with patch("backend.routers.system.get_metrics", return_value=MOCK_METRICS):
        response = test_app.get("/api/system/metrics", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["cpu_percent"] == 25.0
    assert data["load_average"] == [1.0, 0.8, 0.5]
    assert data["os_name"] == "Linux 6.6.87"


def test_metrics_endpoint_requires_auth(test_app):
    response = test_app.get("/api/system/metrics")
    assert response.status_code == 403
