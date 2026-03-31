import logging
import sqlite3
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.models.execution_log import ExecutionLog

logger = logging.getLogger(__name__)


def _do_cleanup(db: Session, retention_days: int) -> int:
    """Delete execution logs older than retention_days. Returns count deleted."""
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    deleted = db.query(ExecutionLog).filter(
        ExecutionLog.started_at < cutoff
    ).delete(synchronize_session=False)
    db.commit()
    logger.info("Retention cleanup: deleted %d log(s) older than %d days", deleted, retention_days)
    return deleted


def _do_vacuum(db_path: str) -> None:
    """Run SQLite VACUUM using a raw sqlite3 connection (cannot run inside a transaction)."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("VACUUM")
        logger.info("SQLite VACUUM completed on %s", db_path)
    finally:
        conn.close()


def _cleanup_job() -> None:
    """APScheduler job: daily log retention cleanup."""
    from backend.database import SessionLocal
    from backend.config import settings
    db = SessionLocal()
    try:
        _do_cleanup(db, settings.log_retention_days)
    except Exception:
        logger.exception("Log retention cleanup failed")
    finally:
        db.close()


def _vacuum_job() -> None:
    """APScheduler job: weekly VACUUM."""
    from backend.config import settings
    try:
        _do_vacuum(settings.db_path)
    except Exception:
        logger.exception("SQLite VACUUM failed")


def _do_metrics_sample(db: Session) -> None:
    """Sample current system metrics and record to DB."""
    from backend.models.metrics_snapshot import MetricsSnapshot
    from backend.services.system_service import get_metrics
    m = get_metrics()
    db.add(MetricsSnapshot(
        timestamp=datetime.utcnow(),
        cpu_percent=m.cpu_percent,
        ram_percent=m.ram_percent,
        ram_used_gb=m.ram_used_gb,
        disk_percent=m.disk_percent,
        disk_used_gb=m.disk_used_gb
    ))
    db.commit()
    logger.info("Metrics sample recorded")


def _do_metrics_cleanup(db: Session, retention_days: int) -> int:
    """Delete metrics snapshots older than retention_days. Returns count deleted."""
    from backend.models.metrics_snapshot import MetricsSnapshot
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    deleted = db.query(MetricsSnapshot).filter(
        MetricsSnapshot.timestamp < cutoff
    ).delete(synchronize_session=False)
    db.commit()
    logger.info("Metrics cleanup: deleted %d snapshot(s) older than %d days", deleted, retention_days)
    return deleted


def _metrics_sample_job() -> None:
    """APScheduler job: sample system metrics every 60 seconds."""
    from backend.database import SessionLocal
    db = SessionLocal()
    try:
        _do_metrics_sample(db)
    except Exception:
        logger.exception("Metrics sample job failed")
    finally:
        db.close()


def _metrics_cleanup_job() -> None:
    """APScheduler job: daily metrics retention cleanup at 2:15 AM."""
    from backend.database import SessionLocal
    from backend.config import settings
    db = SessionLocal()
    try:
        _do_metrics_cleanup(db, settings.metrics_retention_days)
    except Exception:
        logger.exception("Metrics cleanup job failed")
    finally:
        db.close()


_scheduler = None


def init_scheduler():
    """Initialize and start the background scheduler."""
    global _scheduler
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(_cleanup_job, CronTrigger(hour=2, minute=0), id="log_cleanup")
    _scheduler.add_job(_vacuum_job, CronTrigger(day_of_week="sun", hour=3), id="db_vacuum")
    _scheduler.add_job(_metrics_sample_job, IntervalTrigger(seconds=60), id="metrics_sample")
    _scheduler.add_job(_metrics_cleanup_job, CronTrigger(hour=2, minute=15), id="metrics_cleanup")
    _scheduler.start()
    logger.info("Background scheduler started")


def shutdown_scheduler():
    """Stop the background scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped")
