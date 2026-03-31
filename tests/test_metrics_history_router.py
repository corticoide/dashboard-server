from datetime import datetime, timedelta
from backend.models.metrics_snapshot import MetricsSnapshot


def get_token(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    return r.json()["access_token"]


def _seed_snapshots(test_app):
    from backend.main import app
    from backend.database import get_db
    db = next(app.dependency_overrides[get_db]())
    now = datetime.utcnow()
    for i in range(5):
        db.add(MetricsSnapshot(
            timestamp=now - timedelta(hours=i),
            cpu_percent=50.0 + i,
            ram_percent=60.0 + i,
            ram_used_gb=4.0,
            disk_percent=70.0,
            disk_used_gb=100.0
        ))
    db.commit()
    db.close()


def test_get_history(test_app):
    _seed_snapshots(test_app)
    token = get_token(test_app)
    r = test_app.get("/api/metrics/history?hours=24", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 5
    # Check first and last timestamps
    assert data[0]["cpu_percent"] == 54.0  # Most recent (i=4)
    assert data[-1]["cpu_percent"] == 50.0  # Oldest (i=0)


def test_get_history_empty(test_app):
    token = get_token(test_app)
    r = test_app.get("/api/metrics/history?hours=1", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == []


def test_get_history_downsampling(test_app):
    """Test that large result sets are downsampled to 1440 points."""
    from backend.main import app
    from backend.database import get_db
    db = next(app.dependency_overrides[get_db]())
    now = datetime.utcnow()
    # Create 2000 snapshots
    for i in range(2000):
        db.add(MetricsSnapshot(
            timestamp=now - timedelta(seconds=i),
            cpu_percent=50.0,
            ram_percent=60.0,
            ram_used_gb=4.0,
            disk_percent=70.0,
            disk_used_gb=100.0
        ))
    db.commit()
    db.close()

    token = get_token(test_app)
    r = test_app.get("/api/metrics/history?hours=120", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert len(data) <= 1440


def test_unauthenticated_returns_403(test_app):
    r = test_app.get("/api/metrics/history")
    assert r.status_code == 403


def test_invalid_hours_param(test_app):
    token = get_token(test_app)
    # hours=0 should fail (ge=1)
    r = test_app.get("/api/metrics/history?hours=0", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 422
    # hours=1000 should fail (le=720)
    r = test_app.get("/api/metrics/history?hours=1000", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 422
