from unittest.mock import patch
from backend.schemas.system import SystemMetrics


MOCK_METRICS = SystemMetrics(
    cpu_percent=25.0, ram_percent=50.0, ram_used_gb=4.0, ram_total_gb=8.0,
    disk_percent=40.0, disk_used_gb=40.0, disk_total_gb=100.0,
    uptime_seconds=3600, load_average=[1.0, 0.8, 0.5], os_name="Linux 6.6.87",
    hostname="srv-test", cpu_count=4, cpu_arch="x86_64"
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


def test_metrics_endpoint_uses_cache(test_app, monkeypatch):
    import backend.services.system_service as sys_svc
    import backend.routers.system as sys_router
    from backend.services.cache import TTLCache

    call_count = {"n": 0}
    original = sys_svc.get_metrics
    def counting_get_metrics():
        call_count["n"] += 1
        return original()
    # Patch the name as seen by the router module (imported reference)
    monkeypatch.setattr(sys_router, "get_metrics", counting_get_metrics)
    # Reset the module-level cache so previous test runs don't interfere
    sys_router._metrics_cache = TTLCache()

    token = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    test_app.get("/api/system/metrics", headers=headers)
    test_app.get("/api/system/metrics", headers=headers)
    assert call_count["n"] == 1, f"get_metrics() called {call_count['n']} times, expected 1"
