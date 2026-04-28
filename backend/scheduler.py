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
    from backend.services.settings_service import get_setting
    db = SessionLocal()
    try:
        retention_days = int(get_setting(db, "log_retention_days", "30"))
        _do_cleanup(db, retention_days)
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
    from backend.services.settings_service import get_setting
    db = SessionLocal()
    try:
        retention_days = int(get_setting(db, "metrics_retention_days", "30"))
        _do_metrics_cleanup(db, retention_days)
    except Exception:
        logger.exception("Metrics cleanup job failed")
    finally:
        db.close()


def _do_network_sample(db: Session) -> int:
    """Capture current network interface stats as snapshots. Returns count inserted."""
    from backend.models.network_snapshot import NetworkSnapshot
    from backend.services.network_service import get_interfaces

    ifaces = get_interfaces()
    now = datetime.utcnow()
    count = 0
    for iface in ifaces:
        db.add(NetworkSnapshot(
            timestamp=now,
            interface=iface["name"],
            bytes_sent=iface["bytes_sent"],
            bytes_recv=iface["bytes_recv"],
            packets_sent=iface["packets_sent"],
            packets_recv=iface["packets_recv"],
            errin=iface["errin"],
            errout=iface["errout"],
            dropin=iface["dropin"],
            dropout=iface["dropout"],
        ))
        count += 1
    db.commit()
    logger.info("Network sample: inserted %d interface snapshot(s)", count)
    return count


def _do_network_cleanup(db: Session, retention_days: int) -> int:
    """Delete network snapshots older than retention_days. Returns count deleted."""
    from backend.models.network_snapshot import NetworkSnapshot

    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    deleted = db.query(NetworkSnapshot).filter(
        NetworkSnapshot.timestamp < cutoff
    ).delete(synchronize_session=False)
    db.commit()
    logger.info("Network cleanup: deleted %d snapshot(s) older than %d days", deleted, retention_days)
    return deleted


def _network_sample_job() -> None:
    """APScheduler job: sample network stats every 60 seconds."""
    from backend.database import SessionLocal
    db = SessionLocal()
    try:
        _do_network_sample(db)
    except Exception:
        logger.exception("Network sample job failed")
    finally:
        db.close()


def _network_cleanup_job() -> None:
    """APScheduler job: daily network snapshot retention cleanup."""
    from backend.database import SessionLocal
    from backend.services.settings_service import get_setting
    db = SessionLocal()
    try:
        retention_days = int(get_setting(db, "network_retention_days", "30"))
        _do_network_cleanup(db, retention_days)
    except Exception:
        logger.exception("Network cleanup job failed")
    finally:
        db.close()


def _do_alerts_cleanup(db: Session, retention_days: int) -> int:
    """Delete resolved/recovered alert fires older than retention_days. Returns count deleted."""
    from backend.models.alert import AlertFire
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    deleted = db.query(AlertFire).filter(
        AlertFire.fired_at < cutoff,
        AlertFire.status != "active",
    ).delete(synchronize_session=False)
    db.commit()
    logger.info("Alerts cleanup: deleted %d fire record(s) older than %d days", deleted, retention_days)
    return deleted


def _alerts_cleanup_job() -> None:
    """APScheduler job: daily alert fire history cleanup at 2:45 AM."""
    from backend.database import SessionLocal
    from backend.services.settings_service import get_setting
    db = SessionLocal()
    try:
        retention_days = int(get_setting(db, "alerts_retention_days", "90"))
        _do_alerts_cleanup(db, retention_days)
    except Exception:
        logger.exception("Alerts cleanup job failed")
    finally:
        db.close()


def _evaluate_condition(rule, db) -> tuple[bool, str]:
    """Evaluate one alert rule. Returns (condition_met, detail_string)."""
    if rule.condition_type in ("cpu", "ram", "disk"):
        from backend.models.metrics_snapshot import MetricsSnapshot
        snap = (
            db.query(MetricsSnapshot)
            .order_by(MetricsSnapshot.timestamp.desc())
            .first()
        )
        if snap is None:
            return False, ""
        val = getattr(snap, f"{rule.condition_type}_percent")
        met = val >= rule.threshold
        detail = f"{rule.condition_type.upper()} at {val:.1f}%"
        return met, detail
    elif rule.condition_type == "service_down":
        from backend.services.services_service import list_services
        services = list_services()
        svc = next(
            (s for s in services
             if s.name == rule.target or s.name == f"{rule.target}.service"),
            None,
        )
        if svc is None:
            return True, f"Service '{rule.target}' not found"
        met = svc.active_state != "active"
        detail = f"Service '{rule.target}' is {svc.active_state}"
        return met, detail
    elif rule.condition_type == "process_missing":
        import psutil
        names = {p.info["name"] for p in psutil.process_iter(["name"])}
        met = rule.target not in names
        detail = (
            f"Process '{rule.target}' not running"
            if met
            else f"Process '{rule.target}' running"
        )
        return met, detail
    return False, ""


def _do_check_alerts(db: Session) -> int:
    """Check all enabled alert rules; fire/recover as needed. Returns count of actions taken."""
    from backend.models.alert import AlertRule, AlertFire
    from backend.services.notification_service import send_alert_email, send_recovery_email

    rules = db.query(AlertRule).filter(AlertRule.enabled == True).all()  # noqa: E712
    actions = 0

    for rule in rules:
        try:
            condition_met, detail = _evaluate_condition(rule, db)
        except Exception:
            logger.exception("Alert evaluation failed for rule id=%s name='%s'", rule.id, rule.name)
            continue

        active_fire = (
            db.query(AlertFire)
            .filter(AlertFire.rule_id == rule.id, AlertFire.status == "active")
            .order_by(AlertFire.fired_at.desc())
            .first()
        )

        if condition_met:
            if active_fire is None:
                fire = AlertFire(
                    rule_id=rule.id,
                    fired_at=datetime.utcnow(),
                    status="active",
                    detail=detail,
                    email_sent=False,
                )
                db.add(fire)
                db.flush()
                try:
                    send_alert_email(rule, fire)
                    fire.email_sent = True
                except Exception:
                    logger.exception("Failed to send alert email for rule id=%s", rule.id)
                db.commit()
                actions += 1
            else:
                cooldown_secs = rule.cooldown_minutes * 60
                elapsed = (datetime.utcnow() - active_fire.fired_at).total_seconds()
                if elapsed >= cooldown_secs:
                    active_fire.fired_at = datetime.utcnow()
                    active_fire.detail = detail
                    try:
                        send_alert_email(rule, active_fire)
                    except Exception:
                        logger.exception("Failed to send cooldown email for rule id=%s", rule.id)
                    db.commit()
                    actions += 1
        else:
            if active_fire is not None:
                active_fire.status = "recovered"
                active_fire.recovered_at = datetime.utcnow()
                if rule.notify_on_recovery and not active_fire.recovery_email_sent:
                    try:
                        send_recovery_email(rule, active_fire)
                        active_fire.recovery_email_sent = True
                    except Exception:
                        logger.exception("Failed to send recovery email for rule id=%s", rule.id)
                db.commit()
                actions += 1

    return actions


def _check_alerts_job() -> None:
    """APScheduler job: evaluate alert rules every 60 seconds."""
    from backend.database import SessionLocal
    db = SessionLocal()
    try:
        _do_check_alerts(db)
    except Exception:
        logger.exception("Alert check job failed")
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
    _scheduler.add_job(_network_sample_job, IntervalTrigger(seconds=60), id="network_sample")
    _scheduler.add_job(_network_cleanup_job, CronTrigger(hour=2, minute=30), id="network_cleanup")
    _scheduler.add_job(_check_alerts_job, IntervalTrigger(seconds=60), id="check_alerts")
    _scheduler.add_job(_alerts_cleanup_job, CronTrigger(hour=2, minute=45), id="alerts_cleanup")
    _scheduler.start()
    logger.info("Background scheduler started")


def shutdown_scheduler():
    """Stop the background scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped")
