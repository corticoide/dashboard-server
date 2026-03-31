from datetime import datetime, timedelta
from backend.models.metrics_snapshot import MetricsSnapshot


def test_do_metrics_sample(db_session):
    from backend.scheduler import _do_metrics_sample
    _do_metrics_sample(db_session)
    snapshots = db_session.query(MetricsSnapshot).all()
    assert len(snapshots) == 1
    snap = snapshots[0]
    assert snap.cpu_percent >= 0
    assert snap.ram_percent >= 0
    assert snap.ram_used_gb >= 0
    assert snap.disk_percent >= 0
    assert snap.disk_used_gb >= 0
    assert snap.timestamp is not None


def test_do_metrics_cleanup(db_session):
    from backend.scheduler import _do_metrics_cleanup
    old = MetricsSnapshot(
        timestamp=datetime.utcnow() - timedelta(days=40),
        cpu_percent=50.0,
        ram_percent=60.0,
        ram_used_gb=4.0,
        disk_percent=70.0,
        disk_used_gb=100.0
    )
    recent = MetricsSnapshot(
        timestamp=datetime.utcnow() - timedelta(hours=1),
        cpu_percent=55.0,
        ram_percent=65.0,
        ram_used_gb=4.5,
        disk_percent=72.0,
        disk_used_gb=102.0
    )
    db_session.add_all([old, recent])
    db_session.commit()
    deleted = _do_metrics_cleanup(db_session, retention_days=30)
    assert deleted == 1
    assert db_session.query(MetricsSnapshot).count() == 1
    remaining = db_session.query(MetricsSnapshot).first()
    assert remaining.cpu_percent == 55.0
