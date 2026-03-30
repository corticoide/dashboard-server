import pytest
from datetime import datetime, timezone, timedelta
from backend.models.execution_log import ExecutionLog


def make_log(db, script, days_ago, exit_code=0):
    started = datetime.utcnow() - timedelta(days=days_ago)
    log = ExecutionLog(
        script_path=script,
        username="admin",
        started_at=started,
        exit_code=exit_code,
    )
    db.add(log)
    db.commit()
    return log


def test_cleanup_deletes_old_logs(db_session):
    from backend.scheduler import _do_cleanup
    make_log(db_session, "/old.sh", days_ago=31)
    make_log(db_session, "/recent.sh", days_ago=1)

    deleted = _do_cleanup(db_session, retention_days=30)

    assert deleted == 1
    remaining = db_session.query(ExecutionLog).all()
    assert len(remaining) == 1
    assert remaining[0].script_path == "/recent.sh"


def test_cleanup_returns_zero_when_nothing_to_delete(db_session):
    from backend.scheduler import _do_cleanup
    make_log(db_session, "/fresh.sh", days_ago=5)

    deleted = _do_cleanup(db_session, retention_days=30)

    assert deleted == 0
    assert db_session.query(ExecutionLog).count() == 1


def test_cleanup_deletes_all_when_all_are_old(db_session):
    from backend.scheduler import _do_cleanup
    for i in range(3):
        make_log(db_session, f"/old_{i}.sh", days_ago=60)

    deleted = _do_cleanup(db_session, retention_days=30)

    assert deleted == 3
    assert db_session.query(ExecutionLog).count() == 0
