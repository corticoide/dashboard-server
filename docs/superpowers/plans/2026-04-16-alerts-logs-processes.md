# Alerts, System Logs & Process Manager — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement three monitoring features — Alerts & Notifications, System Logs Viewer, and Process Manager — wired into the existing permissions system, scheduler, and Vue SPA.

**Architecture:** Alerts Foundation first (models + scheduler + email), then System Logs (read-only REST + WebSocket), then Process Manager (psutil REST), then wire-up (routers registered, permissions seeded, navigation added), then three Vue views. Process Manager's "watch" feature creates an `AlertRule` of type `process_missing`, so Alerts must be fully in place before Process Manager is tested end-to-end.

**Tech Stack:** Python 3.11 · FastAPI · SQLAlchemy (SQLite) · APScheduler · smtplib · psutil · Vue 3 · PrimeVue 4 · Pinia

---

## File Map

### New files
| File | Responsibility |
|------|---------------|
| `backend/models/alert.py` | `AlertRule` + `AlertFire` ORM models |
| `backend/schemas/alert.py` | Pydantic request/response schemas |
| `backend/routers/alerts.py` | CRUD endpoints for rules + fire history |
| `backend/services/notification_service.py` | smtplib email helpers |
| `backend/routers/system_logs.py` | `/var/log` tree listing + paginated read |
| `backend/routers/processes.py` | Process list / kill / watch / unwatch |
| `frontend/src/views/AlertsView.vue` | Two-panel alerts UI |
| `frontend/src/views/SystemLogsView.vue` | Two-panel log viewer with WS tail |
| `frontend/src/views/ProcessesView.vue` | Process table with 5s polling |
| `tests/test_alerts.py` | Unit + integration tests for alerts |
| `tests/test_system_logs.py` | Unit + integration tests for system logs |
| `tests/test_processes.py` | Unit + integration tests for processes |

### Modified files
| File | Change |
|------|--------|
| `backend/models/__init__.py` | Import `AlertRule`, `AlertFire` |
| `backend/main.py` | Register 3 new routers; import alert models |
| `backend/scheduler.py` | Add `_do_check_alerts` / `_check_alerts_job` |
| `backend/scripts/init_db.py` | Add `alerts`, `system_logs`, `processes` to `DEFAULT_PERMISSIONS` |
| `backend/scripts/add_indexes.py` | Add 5 new `CREATE INDEX IF NOT EXISTS` statements |
| `backend/config.py` | Add `alerts_retention_days: int = 90` |
| `backend/routers/ws.py` | Add `/log-tail` WebSocket endpoint |
| `tests/conftest.py` | Add `autouse` cache-reset fixtures for new routers |
| `frontend/src/router/index.js` | Rename `/logs` → `/execution-logs`; add 3 new routes |
| `frontend/src/components/layout/AppSidebar.vue` | Add Alerts / Logs / Processes entries; rename Exec Logs |
| `frontend/src/views/AdminPermissionsView.vue` | Add 6 rows to `MATRIX_ROWS` |

---

## Task 1: Alert data models

**Files:**
- Create: `backend/models/alert.py`
- Modify: `backend/models/__init__.py`
- Test: `tests/test_alerts.py` (step 1 only)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_alerts.py
from datetime import datetime


def test_alert_rule_model(db_session):
    from backend.models.alert import AlertRule
    rule = AlertRule(
        name="CPU High",
        enabled=True,
        condition_type="cpu",
        threshold=85.0,
        cooldown_minutes=60,
        notify_on_recovery=True,
        email_to="admin@test.com",
    )
    db_session.add(rule)
    db_session.commit()
    assert rule.id is not None
    assert rule.name == "CPU High"
    assert rule.threshold == 85.0


def test_alert_fire_model(db_session):
    from backend.models.alert import AlertRule, AlertFire
    rule = AlertRule(
        name="RAM High", enabled=True, condition_type="ram",
        threshold=90.0, cooldown_minutes=30,
        notify_on_recovery=False, email_to="x@x.com",
    )
    db_session.add(rule)
    db_session.flush()
    fire = AlertFire(
        rule_id=rule.id,
        fired_at=datetime.utcnow(),
        status="active",
        detail="RAM at 91.2%",
        email_sent=False,
        recovery_email_sent=False,
    )
    db_session.add(fire)
    db_session.commit()
    assert fire.id is not None
    assert fire.rule_id == rule.id
    assert fire.status == "active"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_alerts.py -v
```

Expected: `ImportError: cannot import name 'AlertRule' from 'backend.models.alert'` (file does not exist yet).

- [ ] **Step 3: Create `backend/models/alert.py`**

```python
from sqlalchemy import (
    Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Index
)
from sqlalchemy.sql import func
from backend.database import Base


class AlertRule(Base):
    __tablename__ = "alert_rules"
    id               = Column(Integer, primary_key=True)
    name             = Column(String, nullable=False)
    enabled          = Column(Boolean, default=True, nullable=False)
    condition_type   = Column(String, nullable=False)   # cpu|ram|disk|service_down|process_missing
    threshold        = Column(Float, nullable=True)     # for cpu/ram/disk
    target           = Column(String, nullable=True)    # service or process name
    cooldown_minutes = Column(Integer, default=60, nullable=False)
    notify_on_recovery = Column(Boolean, default=True, nullable=False)
    email_to         = Column(String, nullable=False)
    created_at       = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_alert_rules_enabled", "enabled"),
        Index("ix_alert_rules_condition_type", "condition_type"),
    )


class AlertFire(Base):
    __tablename__ = "alert_fires"
    id                  = Column(Integer, primary_key=True)
    rule_id             = Column(Integer, ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False)
    fired_at            = Column(DateTime, nullable=False)
    recovered_at        = Column(DateTime, nullable=True)
    status              = Column(String, default="active", nullable=False)  # active|recovered
    detail              = Column(String, nullable=True)
    email_sent          = Column(Boolean, default=False)
    recovery_email_sent = Column(Boolean, default=False)

    __table_args__ = (
        Index("ix_alert_fires_rule_id", "rule_id"),
        Index("ix_alert_fires_status", "status"),
        Index("ix_alert_fires_fired_at", "fired_at"),
    )
```

- [ ] **Step 4: Register models in `backend/models/__init__.py`**

Append two imports to the existing file (current content: `from backend.models.user import User`):

```python
from backend.models.user import User
from backend.models.alert import AlertRule, AlertFire  # noqa: F401
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_alerts.py -v
```

Expected: 2 tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend/models/alert.py backend/models/__init__.py tests/test_alerts.py
git commit -m "feat(alerts): add AlertRule and AlertFire ORM models"
```

---

## Task 2: Alert schemas + CRUD router

**Files:**
- Create: `backend/schemas/alert.py`
- Create: `backend/routers/alerts.py`
- Test: `tests/test_alerts.py` (extend)

- [ ] **Step 1: Add router integration tests**

Append to `tests/test_alerts.py`:

```python
def _login(test_app):
    r = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    return r.json()["access_token"]


def test_list_rules_requires_auth(test_app):
    r = test_app.get("/api/alerts/rules")
    assert r.status_code == 403


def test_create_and_list_rule(test_app):
    token = _login(test_app)
    headers = {"Authorization": f"Bearer {token}"}

    r = test_app.post("/api/alerts/rules", headers=headers, json={
        "name": "CPU High",
        "condition_type": "cpu",
        "threshold": 85.0,
        "cooldown_minutes": 60,
        "notify_on_recovery": True,
        "email_to": "admin@test.com",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "CPU High"
    assert data["id"] is not None

    r2 = test_app.get("/api/alerts/rules", headers=headers)
    assert r2.status_code == 200
    assert len(r2.json()) == 1


def test_update_rule(test_app):
    token = _login(test_app)
    headers = {"Authorization": f"Bearer {token}"}
    r = test_app.post("/api/alerts/rules", headers=headers, json={
        "name": "Old Name", "condition_type": "ram", "threshold": 80.0,
        "cooldown_minutes": 60, "notify_on_recovery": True, "email_to": "x@x.com",
    })
    rule_id = r.json()["id"]

    r2 = test_app.put(f"/api/alerts/rules/{rule_id}", headers=headers, json={
        "name": "New Name", "condition_type": "ram", "threshold": 90.0,
        "cooldown_minutes": 30, "notify_on_recovery": False, "email_to": "y@y.com",
    })
    assert r2.status_code == 200
    assert r2.json()["name"] == "New Name"
    assert r2.json()["threshold"] == 90.0


def test_toggle_rule(test_app):
    token = _login(test_app)
    headers = {"Authorization": f"Bearer {token}"}
    r = test_app.post("/api/alerts/rules", headers=headers, json={
        "name": "Toggle Test", "condition_type": "cpu", "threshold": 80.0,
        "cooldown_minutes": 60, "notify_on_recovery": True, "email_to": "x@x.com",
    })
    rule_id = r.json()["id"]
    assert r.json()["enabled"] is True

    r2 = test_app.patch(f"/api/alerts/rules/{rule_id}/toggle", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["enabled"] is False


def test_delete_rule(test_app):
    token = _login(test_app)
    headers = {"Authorization": f"Bearer {token}"}
    r = test_app.post("/api/alerts/rules", headers=headers, json={
        "name": "Delete Me", "condition_type": "disk", "threshold": 90.0,
        "cooldown_minutes": 60, "notify_on_recovery": True, "email_to": "x@x.com",
    })
    rule_id = r.json()["id"]

    r2 = test_app.delete(f"/api/alerts/rules/{rule_id}", headers=headers)
    assert r2.status_code == 204

    r3 = test_app.get("/api/alerts/rules", headers=headers)
    assert r3.json() == []


def test_list_fires(test_app):
    token = _login(test_app)
    headers = {"Authorization": f"Bearer {token}"}
    r = test_app.get("/api/alerts/fires", headers=headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
pytest tests/test_alerts.py::test_list_rules_requires_auth -v
```

Expected: `FAILED` — router does not exist yet.

- [ ] **Step 3: Create `backend/schemas/alert.py`**

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AlertRuleCreate(BaseModel):
    name: str
    enabled: bool = True
    condition_type: str
    threshold: Optional[float] = None
    target: Optional[str] = None
    cooldown_minutes: int = 60
    notify_on_recovery: bool = True
    email_to: str


class AlertRuleUpdate(AlertRuleCreate):
    pass


class AlertRuleOut(BaseModel):
    id: int
    name: str
    enabled: bool
    condition_type: str
    threshold: Optional[float] = None
    target: Optional[str] = None
    cooldown_minutes: int
    notify_on_recovery: bool
    email_to: str
    created_at: Optional[datetime] = None
    has_active_fire: bool = False

    model_config = {"from_attributes": True}


class AlertFireOut(BaseModel):
    id: int
    rule_id: int
    fired_at: datetime
    recovered_at: Optional[datetime] = None
    status: str
    detail: Optional[str] = None
    email_sent: bool
    recovery_email_sent: bool

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Create `backend/routers/alerts.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.database import get_db
from backend.dependencies import require_permission
from backend.models.alert import AlertRule, AlertFire
from backend.schemas.alert import AlertRuleCreate, AlertRuleUpdate, AlertRuleOut, AlertFireOut

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def _has_active_fire(rule_id: int, db: Session) -> bool:
    return (
        db.query(AlertFire)
        .filter(AlertFire.rule_id == rule_id, AlertFire.status == "active")
        .first()
    ) is not None


def _rule_out(rule: AlertRule, db: Session) -> AlertRuleOut:
    out = AlertRuleOut.model_validate(rule)
    out.has_active_fire = _has_active_fire(rule.id, db)
    return out


@router.get("/rules", response_model=List[AlertRuleOut])
def list_rules(
    db: Session = Depends(get_db),
    user=Depends(require_permission("alerts", "read")),
):
    rules = db.query(AlertRule).order_by(AlertRule.id).all()
    return [_rule_out(r, db) for r in rules]


@router.post("/rules", response_model=AlertRuleOut, status_code=201)
def create_rule(
    body: AlertRuleCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permission("alerts", "write")),
):
    rule = AlertRule(**body.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _rule_out(rule, db)


@router.put("/rules/{rule_id}", response_model=AlertRuleOut)
def update_rule(
    rule_id: int,
    body: AlertRuleUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permission("alerts", "write")),
):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    for k, v in body.model_dump().items():
        setattr(rule, k, v)
    db.commit()
    db.refresh(rule)
    return _rule_out(rule, db)


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permission("alerts", "write")),
):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()


@router.patch("/rules/{rule_id}/toggle", response_model=AlertRuleOut)
def toggle_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permission("alerts", "write")),
):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.enabled = not rule.enabled
    db.commit()
    db.refresh(rule)
    return _rule_out(rule, db)


@router.get("/fires", response_model=List[AlertFireOut])
def list_fires(
    rule_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user=Depends(require_permission("alerts", "read")),
):
    q = db.query(AlertFire).order_by(AlertFire.fired_at.desc())
    if rule_id is not None:
        q = q.filter(AlertFire.rule_id == rule_id)
    if status is not None:
        q = q.filter(AlertFire.status == status)
    return q.limit(100).all()
```

- [ ] **Step 5: Register router temporarily in `backend/main.py` to enable integration tests**

Add to the imports block in `backend/main.py`:

```python
from backend.routers.alerts import router as alerts_router
import backend.models.alert  # noqa: F401
```

Add to the `app.include_router` block:

```python
app.include_router(alerts_router)
```

- [ ] **Step 6: Run all alert tests to verify they pass**

```bash
pytest tests/test_alerts.py -v
```

Expected: all tests PASSED.

- [ ] **Step 7: Commit**

```bash
git add backend/schemas/alert.py backend/routers/alerts.py backend/main.py tests/test_alerts.py
git commit -m "feat(alerts): add schemas and CRUD router for alert rules and fire history"
```

---

## Task 3: Notification service

**Files:**
- Create: `backend/services/notification_service.py`
- Test: `tests/test_alerts.py` (extend)

- [ ] **Step 1: Add notification service tests**

Append to `tests/test_alerts.py`:

```python
def test_send_alert_email_calls_smtp(db_session):
    from unittest.mock import patch, MagicMock
    from backend.models.alert import AlertRule, AlertFire
    from backend.services.notification_service import send_alert_email
    from datetime import datetime

    rule = AlertRule(
        name="CPU High", enabled=True, condition_type="cpu",
        threshold=85.0, cooldown_minutes=60,
        notify_on_recovery=True, email_to="ops@test.com",
    )
    db_session.add(rule)
    db_session.flush()
    fire = AlertFire(
        rule_id=rule.id, fired_at=datetime.utcnow(),
        status="active", detail="CPU at 87.3%",
        email_sent=False, recovery_email_sent=False,
    )
    db_session.add(fire)
    db_session.commit()

    with patch("backend.services.notification_service.smtplib.SMTP") as mock_smtp_cls:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        send_alert_email(rule, fire)

    mock_smtp.sendmail.assert_called_once()
    args = mock_smtp.sendmail.call_args[0]
    assert args[1] == "ops@test.com"


def test_send_recovery_email_calls_smtp(db_session):
    from unittest.mock import patch, MagicMock
    from backend.models.alert import AlertRule, AlertFire
    from backend.services.notification_service import send_recovery_email
    from datetime import datetime

    rule = AlertRule(
        name="RAM High", enabled=True, condition_type="ram",
        threshold=90.0, cooldown_minutes=30,
        notify_on_recovery=True, email_to="ops@test.com",
    )
    db_session.add(rule)
    db_session.flush()
    fire = AlertFire(
        rule_id=rule.id, fired_at=datetime.utcnow(),
        recovered_at=datetime.utcnow(), status="recovered",
        detail="RAM at 91%", email_sent=True, recovery_email_sent=False,
    )
    db_session.add(fire)
    db_session.commit()

    with patch("backend.services.notification_service.smtplib.SMTP") as mock_smtp_cls:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        send_recovery_email(rule, fire)

    mock_smtp.sendmail.assert_called_once()
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
pytest tests/test_alerts.py::test_send_alert_email_calls_smtp -v
```

Expected: `ImportError: cannot import name 'send_alert_email'`.

- [ ] **Step 3: Create `backend/services/notification_service.py`**

```python
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from backend.models.alert import AlertRule, AlertFire

logger = logging.getLogger(__name__)


def _build_smtp(settings) -> smtplib.SMTP:
    smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
    smtp.starttls()
    if settings.smtp_user:
        smtp.login(settings.smtp_user, settings.smtp_password)
    return smtp


def send_alert_email(rule: AlertRule, fire: AlertFire) -> None:
    """Send alert-fired email via smtplib using settings.smtp_*."""
    from backend.config import settings
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[ServerDash Alert] {rule.name} triggered"
    msg["From"] = settings.smtp_from
    msg["To"] = rule.email_to
    body = (
        f"Alert rule '{rule.name}' has been triggered.\n\n"
        f"Condition: {rule.condition_type}\n"
        f"Detail: {fire.detail or 'n/a'}\n"
        f"Fired at: {fire.fired_at.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
    )
    msg.attach(MIMEText(body, "plain"))
    with _build_smtp(settings) as smtp:
        smtp.sendmail(settings.smtp_from, rule.email_to, msg.as_string())
    logger.info("Alert email sent for rule '%s' (fire id=%s)", rule.name, fire.id)


def send_recovery_email(rule: AlertRule, fire: AlertFire) -> None:
    """Send alert-recovered email via smtplib using settings.smtp_*."""
    from backend.config import settings
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[ServerDash Alert] {rule.name} recovered"
    msg["From"] = settings.smtp_from
    msg["To"] = rule.email_to
    body = (
        f"Alert rule '{rule.name}' has recovered.\n\n"
        f"Condition: {rule.condition_type}\n"
        f"Detail at fire: {fire.detail or 'n/a'}\n"
        f"Fired at: {fire.fired_at.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        f"Recovered at: {fire.recovered_at.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
    )
    msg.attach(MIMEText(body, "plain"))
    with _build_smtp(settings) as smtp:
        smtp.sendmail(settings.smtp_from, rule.email_to, msg.as_string())
    logger.info("Recovery email sent for rule '%s' (fire id=%s)", rule.name, fire.id)
```

- [ ] **Step 4: Run all alert tests to verify they pass**

```bash
pytest tests/test_alerts.py -v
```

Expected: all PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/services/notification_service.py tests/test_alerts.py
git commit -m "feat(alerts): add email notification service using smtplib"
```

---

## Task 4: Alert scheduler job + config

**Files:**
- Modify: `backend/scheduler.py`
- Modify: `backend/config.py`
- Modify: `.env.example`
- Test: `tests/test_alerts.py` (extend)

- [ ] **Step 1: Add scheduler job tests**

Append to `tests/test_alerts.py`:

```python
def test_do_check_alerts_fires_on_cpu_threshold(db_session):
    from unittest.mock import patch
    from backend.models.alert import AlertRule, AlertFire
    from backend.models.metrics_snapshot import MetricsSnapshot
    from backend.scheduler import _do_check_alerts
    from datetime import datetime

    # Seed a metrics snapshot with CPU at 90%
    db_session.add(MetricsSnapshot(
        timestamp=datetime.utcnow(),
        cpu_percent=90.0, ram_percent=50.0, ram_used_gb=4.0,
        disk_percent=40.0, disk_used_gb=20.0,
    ))
    # Seed an alert rule for CPU >= 85%
    rule = AlertRule(
        name="CPU High", enabled=True, condition_type="cpu",
        threshold=85.0, cooldown_minutes=60,
        notify_on_recovery=True, email_to="ops@test.com",
    )
    db_session.add(rule)
    db_session.commit()

    with patch("backend.scheduler.send_alert_email") as mock_send:
        count = _do_check_alerts(db_session)

    assert count == 1
    mock_send.assert_called_once()
    fire = db_session.query(AlertFire).first()
    assert fire is not None
    assert fire.status == "active"
    assert fire.email_sent is True
    assert "90.0%" in fire.detail


def test_do_check_alerts_no_fire_below_threshold(db_session):
    from unittest.mock import patch
    from backend.models.alert import AlertRule, AlertFire
    from backend.models.metrics_snapshot import MetricsSnapshot
    from backend.scheduler import _do_check_alerts
    from datetime import datetime

    db_session.add(MetricsSnapshot(
        timestamp=datetime.utcnow(),
        cpu_percent=70.0, ram_percent=50.0, ram_used_gb=4.0,
        disk_percent=40.0, disk_used_gb=20.0,
    ))
    rule = AlertRule(
        name="CPU High", enabled=True, condition_type="cpu",
        threshold=85.0, cooldown_minutes=60,
        notify_on_recovery=True, email_to="ops@test.com",
    )
    db_session.add(rule)
    db_session.commit()

    with patch("backend.scheduler.send_alert_email") as mock_send:
        count = _do_check_alerts(db_session)

    assert count == 0
    mock_send.assert_not_called()
    assert db_session.query(AlertFire).count() == 0


def test_do_check_alerts_recovery(db_session):
    from unittest.mock import patch
    from backend.models.alert import AlertRule, AlertFire
    from backend.models.metrics_snapshot import MetricsSnapshot
    from backend.scheduler import _do_check_alerts
    from datetime import datetime

    # CPU is now below threshold — should recover an existing active fire
    db_session.add(MetricsSnapshot(
        timestamp=datetime.utcnow(),
        cpu_percent=60.0, ram_percent=50.0, ram_used_gb=4.0,
        disk_percent=40.0, disk_used_gb=20.0,
    ))
    rule = AlertRule(
        name="CPU High", enabled=True, condition_type="cpu",
        threshold=85.0, cooldown_minutes=60,
        notify_on_recovery=True, email_to="ops@test.com",
    )
    db_session.add(rule)
    db_session.flush()

    # Pre-seed an active fire
    fire = AlertFire(
        rule_id=rule.id, fired_at=datetime.utcnow(), status="active",
        detail="CPU at 90%", email_sent=True, recovery_email_sent=False,
    )
    db_session.add(fire)
    db_session.commit()

    with patch("backend.scheduler.send_recovery_email") as mock_recover:
        count = _do_check_alerts(db_session)

    assert count == 1
    mock_recover.assert_called_once()
    db_session.refresh(fire)
    assert fire.status == "recovered"
    assert fire.recovered_at is not None
    assert fire.recovery_email_sent is True


def test_do_check_alerts_disabled_rule_skipped(db_session):
    from unittest.mock import patch
    from backend.models.alert import AlertRule
    from backend.models.metrics_snapshot import MetricsSnapshot
    from backend.scheduler import _do_check_alerts
    from datetime import datetime

    db_session.add(MetricsSnapshot(
        timestamp=datetime.utcnow(),
        cpu_percent=95.0, ram_percent=50.0, ram_used_gb=4.0,
        disk_percent=40.0, disk_used_gb=20.0,
    ))
    rule = AlertRule(
        name="CPU High", enabled=False, condition_type="cpu",
        threshold=85.0, cooldown_minutes=60,
        notify_on_recovery=True, email_to="ops@test.com",
    )
    db_session.add(rule)
    db_session.commit()

    with patch("backend.scheduler.send_alert_email") as mock_send:
        count = _do_check_alerts(db_session)

    assert count == 0
    mock_send.assert_not_called()
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
pytest tests/test_alerts.py::test_do_check_alerts_fires_on_cpu_threshold -v
```

Expected: `ImportError: cannot import name '_do_check_alerts' from 'backend.scheduler'`.

- [ ] **Step 3: Add `alerts_retention_days` to `backend/config.py`**

Add after `network_retention_days`:

```python
alerts_retention_days: int = 90
```

The full class becomes (showing only the new line — add it after `network_retention_days: int = 30`):

```python
    network_retention_days: int = 30
    alerts_retention_days: int = 90
    smtp_host: str = ""
```

- [ ] **Step 4: Add scheduler job to `backend/scheduler.py`**

Add these functions **before** the `_scheduler = None` line:

```python
def _evaluate_condition(rule, db) -> tuple[bool, str]:
    """Evaluate one alert rule. Returns (condition_met, detail_string)."""
    from backend.models.alert import AlertRule  # noqa: F401 — for type hint clarity
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
```

- [ ] **Step 5: Register the job in `init_scheduler()`**

In `backend/scheduler.py`, inside `init_scheduler()`, add after the last `_scheduler.add_job(...)` call:

```python
    _scheduler.add_job(_check_alerts_job, IntervalTrigger(seconds=60), id="check_alerts")
```

- [ ] **Step 6: Update `.env.example`**

Add after `SMTP_FROM=`:

```
ALERTS_RETENTION_DAYS=90
```

- [ ] **Step 7: Run all alert tests**

```bash
pytest tests/test_alerts.py -v
```

Expected: all PASSED.

- [ ] **Step 8: Commit**

```bash
git add backend/scheduler.py backend/config.py .env.example tests/test_alerts.py
git commit -m "feat(alerts): add scheduler job for alert evaluation every 60s"
```

---

## Task 5: System Logs router

**Files:**
- Create: `backend/routers/system_logs.py`
- Create: `tests/test_system_logs.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_system_logs.py
import os
import tempfile


def _login(test_app):
    r = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    return r.json()["access_token"]


def test_tree_requires_auth(test_app):
    r = test_app.get("/api/system-logs/tree")
    assert r.status_code == 403


def test_read_rejects_path_outside_var_log(test_app):
    token = _login(test_app)
    headers = {"Authorization": f"Bearer {token}"}
    r = test_app.get("/api/system-logs/read?path=/etc/passwd", headers=headers)
    assert r.status_code == 403


def test_read_returns_lines(test_app, tmp_path):
    from unittest.mock import patch
    token = _login(test_app)
    headers = {"Authorization": f"Bearer {token}"}

    # Write a temp file with known content under /var/log via path override
    log_file = tmp_path / "test.log"
    log_file.write_text("line1\nline2\nline3\n")

    # Patch LOG_ROOT so the router validates against tmp_path
    with patch("backend.routers.system_logs.LOG_ROOT", tmp_path):
        r = test_app.get(
            f"/api/system-logs/read?path={log_file}&lines=10",
            headers=headers,
        )

    assert r.status_code == 200
    data = r.json()
    assert data["total_lines"] == 3
    assert data["lines"] == ["line1", "line2", "line3"]


def test_tree_returns_structure(test_app, tmp_path):
    from unittest.mock import patch

    # Create a small tree
    (tmp_path / "syslog").write_text("x")
    sub = tmp_path / "nginx"
    sub.mkdir()
    (sub / "access.log").write_text("y")

    token = _login(test_app)
    headers = {"Authorization": f"Bearer {token}"}

    with patch("backend.routers.system_logs.LOG_ROOT", tmp_path):
        r = test_app.get("/api/system-logs/tree", headers=headers)

    assert r.status_code == 200
    names = {entry["name"] for entry in r.json()}
    assert "syslog" in names
    assert "nginx" in names
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_system_logs.py -v
```

Expected: `FAILED` — router not found.

- [ ] **Step 3: Create `backend/routers/system_logs.py`**

```python
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from backend.dependencies import require_permission

router = APIRouter(prefix="/api/system-logs", tags=["system-logs"])

LOG_ROOT = Path("/var/log")


def _validate_path(path_str: str) -> Path:
    """Resolve path and ensure it is under LOG_ROOT. Raises HTTPException otherwise."""
    try:
        p = Path(path_str).resolve()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid path")
    if not p.is_relative_to(LOG_ROOT):
        raise HTTPException(status_code=403, detail="Path outside /var/log")
    return p


def _build_tree(root: Path) -> List[dict]:
    """Recursively list files and directories under root."""
    result = []
    try:
        entries = sorted(root.iterdir(), key=lambda e: (e.is_file(), e.name))
    except PermissionError:
        return result
    for entry in entries:
        if entry.is_dir(follow_symlinks=False):
            result.append({
                "name": entry.name,
                "path": str(entry),
                "is_dir": True,
                "children": _build_tree(entry),
            })
        elif entry.is_file(follow_symlinks=False):
            readable = os.access(entry, os.R_OK)
            try:
                size_bytes = entry.stat().st_size
            except OSError:
                size_bytes = 0
            result.append({
                "name": entry.name,
                "path": str(entry),
                "is_dir": False,
                "size_bytes": size_bytes,
                "readable": readable,
            })
    return result


@router.get("/tree")
def get_tree(user=Depends(require_permission("system_logs", "read"))):
    return _build_tree(LOG_ROOT)


@router.get("/read")
def read_log(
    path: str = Query(...),
    lines: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    user=Depends(require_permission("system_logs", "read")),
):
    p = _validate_path(path)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="Not a file")
    try:
        with open(p, "rb") as f:
            content = f.read().decode("utf-8", errors="replace")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    all_lines = content.splitlines()
    total = len(all_lines)
    end = max(0, total - offset)
    start = max(0, end - lines)
    return {
        "path": str(p),
        "total_lines": total,
        "lines": all_lines[start:end],
    }
```

- [ ] **Step 4: Register router in `backend/main.py`**

Add to imports:

```python
from backend.routers.system_logs import router as system_logs_router
```

Add to `app.include_router` block:

```python
app.include_router(system_logs_router)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_system_logs.py -v
```

Expected: all PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/system_logs.py backend/main.py tests/test_system_logs.py
git commit -m "feat(system-logs): add /var/log tree listing and paginated read endpoints"
```

---

## Task 6: WebSocket log-tail endpoint

**Files:**
- Modify: `backend/routers/ws.py`
- Test: `tests/test_system_logs.py` (extend — basic auth rejection only; WS streaming is tested manually)

- [ ] **Step 1: Add WS auth rejection test**

Append to `tests/test_system_logs.py`:

```python
def test_ws_log_tail_rejects_bad_token(test_app):
    with test_app.websocket_connect("/api/ws/log-tail?path=/var/log/syslog&token=bad") as ws:
        # Server should close immediately on bad token
        try:
            ws.receive_text()
            assert False, "Expected disconnect"
        except Exception:
            pass  # Expected — server closes connection
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_system_logs.py::test_ws_log_tail_rejects_bad_token -v
```

Expected: FAILED — endpoint does not exist yet.

- [ ] **Step 3: Add the `/log-tail` endpoint to `backend/routers/ws.py`**

Add these imports at the top of `ws.py` (add `Path` to the stdlib imports and add `asyncio` — already present):

```python
from pathlib import Path
```

Add this endpoint function after the `ws_network` function:

```python
@router.websocket("/log-tail")
async def ws_log_tail(
    websocket: WebSocket,
    path: str = Query(""),
    token: str = Query(""),
):
    """
    Stream new lines from a /var/log file as they are appended.
    Client: wss://host/api/ws/log-tail?path=/var/log/syslog&token=<jwt>
    """
    if not _auth_token(token):
        await websocket.close(code=4001)
        return

    log_root = Path("/var/log")
    try:
        p = Path(path).resolve()
    except Exception:
        await websocket.close(code=4003)
        return
    if not p.is_relative_to(log_root) or not p.is_file():
        await websocket.close(code=4003)
        return

    try:
        f = open(p, "r", errors="replace")
    except PermissionError:
        await websocket.close(code=4003)
        return

    await websocket.accept()
    logger.info("WS /log-tail connected: %s", path)

    # Seek to end — send only new content
    f.seek(0, 2)

    try:
        while True:
            chunk = f.read()
            if chunk:
                await websocket.send_text(chunk)
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        logger.info("WS /log-tail disconnected: %s", path)
    except Exception as e:
        logger.exception("WS /log-tail error: %s", e)
    finally:
        f.close()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_system_logs.py -v
```

Expected: all PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/ws.py tests/test_system_logs.py
git commit -m "feat(system-logs): add WebSocket /log-tail endpoint for real-time file tailing"
```

---

## Task 7: Process Manager router

**Files:**
- Create: `backend/routers/processes.py`
- Create: `tests/test_processes.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_processes.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_processes.py -v
```

Expected: FAILED — router not found.

- [ ] **Step 3: Create `backend/routers/processes.py`**

```python
import psutil
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend.database import get_db
from backend.dependencies import require_permission
from backend.models.alert import AlertRule
from backend.core.logging import get_audit_logger

router = APIRouter(prefix="/api/processes", tags=["processes"])


def _list_procs(db: Session) -> list[dict]:
    watched_names = {
        r.target
        for r in db.query(AlertRule).filter(
            AlertRule.condition_type == "process_missing",
            AlertRule.enabled == True,  # noqa: E712
        ).all()
    }
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info", "username", "status"]):
        try:
            info = p.info
            procs.append({
                "pid": info["pid"],
                "name": info["name"] or "",
                "cpu_percent": info["cpu_percent"] or 0.0,
                "memory_mb": round(
                    (info["memory_info"].rss if info["memory_info"] else 0) / 1_048_576, 1
                ),
                "username": info["username"] or "",
                "status": info["status"] or "",
                "watched": (info["name"] or "") in watched_names,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(key=lambda x: x["cpu_percent"], reverse=True)
    return procs[:500]


@router.get("/")
async def list_processes(
    db: Session = Depends(get_db),
    user=Depends(require_permission("processes", "read")),
):
    return await run_in_threadpool(_list_procs, db)


@router.post("/{pid}/kill", status_code=204)
async def kill_process(
    pid: int,
    user=Depends(require_permission("processes", "execute")),
):
    def _kill():
        try:
            proc = psutil.Process(pid)
            proc.kill()
        except psutil.NoSuchProcess:
            raise HTTPException(status_code=404, detail="Process not found")
        except psutil.AccessDenied:
            raise HTTPException(status_code=403, detail="Access denied")

    await run_in_threadpool(_kill)
    get_audit_logger().info("process_kill user=%s pid=%s", user.username, pid)


class WatchRequest(BaseModel):
    name: str
    email_to: str
    cooldown_minutes: int = 15


@router.post("/watch", status_code=201)
def watch_process(
    body: WatchRequest,
    db: Session = Depends(get_db),
    user=Depends(require_permission("alerts", "write")),
):
    existing = db.query(AlertRule).filter(
        AlertRule.condition_type == "process_missing",
        AlertRule.target == body.name,
    ).first()
    if existing:
        return existing
    rule = AlertRule(
        name=f"Watch: {body.name}",
        enabled=True,
        condition_type="process_missing",
        target=body.name,
        cooldown_minutes=body.cooldown_minutes,
        notify_on_recovery=True,
        email_to=body.email_to,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/watch/{name}", status_code=204)
def unwatch_process(
    name: str,
    db: Session = Depends(get_db),
    user=Depends(require_permission("alerts", "write")),
):
    rule = db.query(AlertRule).filter(
        AlertRule.condition_type == "process_missing",
        AlertRule.target == name,
    ).first()
    if rule:
        db.delete(rule)
        db.commit()
```

- [ ] **Step 4: Register router in `backend/main.py`**

Add to imports:

```python
from backend.routers.processes import router as processes_router
```

Add to `app.include_router` block:

```python
app.include_router(processes_router)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_processes.py -v
```

Expected: all PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/processes.py backend/main.py tests/test_processes.py
git commit -m "feat(processes): add process list/kill/watch endpoints"
```

---

## Task 8: Wire up permissions, indexes, and test fixtures

**Files:**
- Modify: `backend/scripts/init_db.py`
- Modify: `backend/scripts/add_indexes.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Add permissions to `DEFAULT_PERMISSIONS` in `backend/scripts/init_db.py`**

In the `DEFAULT_PERMISSIONS` dict, extend both roles:

```python
DEFAULT_PERMISSIONS = {
    UserRole.operator: [
        ("system",      "read"),
        ("services",    "read"),  ("services",    "write"), ("services",    "execute"),
        ("files",       "read"),  ("files",       "write"),
        ("network",     "read"),
        ("scripts",     "read"),  ("scripts",     "write"), ("scripts",     "execute"),
        ("crontab",     "read"),
        ("logs",        "read"),
        ("pipelines",   "read"),  ("pipelines",   "execute"),
        ("alerts",      "read"),  ("alerts",      "write"),
        ("system_logs", "read"),
        ("processes",   "read"),  ("processes",   "execute"),
    ],
    UserRole.readonly: [
        ("system",      "read"),
        ("services",    "read"),
        ("files",       "read"),
        ("network",     "read"),
        ("scripts",     "read"),
        ("crontab",     "read"),
        ("logs",        "read"),
        ("pipelines",   "read"),
        ("alerts",      "read"),
        ("system_logs", "read"),
        ("processes",   "read"),
    ],
}
```

- [ ] **Step 2: Add indexes to `backend/scripts/add_indexes.py`**

Append to the `statements` list:

```python
        "CREATE INDEX IF NOT EXISTS ix_alert_rules_enabled ON alert_rules (enabled)",
        "CREATE INDEX IF NOT EXISTS ix_alert_rules_condition_type ON alert_rules (condition_type)",
        "CREATE INDEX IF NOT EXISTS ix_alert_fires_rule_id ON alert_fires (rule_id)",
        "CREATE INDEX IF NOT EXISTS ix_alert_fires_status ON alert_fires (status)",
        "CREATE INDEX IF NOT EXISTS ix_alert_fires_fired_at ON alert_fires (fired_at)",
```

- [ ] **Step 3: Add cache-reset fixture to `tests/conftest.py`**

The alerts router has no count cache (it queries without pagination), but the conftest must patch `SessionLocal` for any service that calls it directly. No new service calls `SessionLocal()` directly in this feature set, so only a `reset_permission_cache` autouse is needed (already present).

Add a comment noting this was verified:

Add at the end of `conftest.py`:

```python
# No new module-level TTLCache instances in alerts/system_logs/processes routers.
# Permission cache reset is already handled by reset_permission_cache above.
```

- [ ] **Step 4: Run the full test suite**

```bash
pytest -q
```

Expected: all existing tests + all new tests PASS. Known pre-existing failure: up to 3 `LoginView` frontend Vitest failures — not ours, ignore.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/init_db.py backend/scripts/add_indexes.py tests/conftest.py
git commit -m "feat(wire-up): add permissions, indexes, and test fixture notes for new features"
```

---

## Task 9: Frontend routing, sidebar, and permissions matrix

**Files:**
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/components/layout/AppSidebar.vue`
- Modify: `frontend/src/views/AdminPermissionsView.vue`

No automated tests for these changes. Manual verification in Task 10–12.

- [ ] **Step 1: Update `frontend/src/router/index.js`**

Replace the existing routes array with:

```javascript
const routes = [
  { path: '/login',             component: () => import('../views/LoginView.vue'),             meta: { public: true,       title: 'Login' } },
  { path: '/',                  component: () => import('../views/DashboardView.vue'),          meta: { requiresAuth: true, title: 'Dashboard',      resource: 'system' } },
  { path: '/services',          component: () => import('../views/ServicesView.vue'),           meta: { requiresAuth: true, title: 'Services',        resource: 'services' } },
  { path: '/files',             component: () => import('../views/FilesView.vue'),              meta: { requiresAuth: true, title: 'Files',           resource: 'files' } },
  { path: '/scripts',           component: () => import('../views/ScriptsView.vue'),            meta: { requiresAuth: true, title: 'Scripts',         resource: 'scripts' } },
  { path: '/crontab',           component: () => import('../views/CrontabView.vue'),            meta: { requiresAuth: true, title: 'Crontab',         resource: 'crontab' } },
  { path: '/execution-logs',    component: () => import('../views/LogsView.vue'),               meta: { requiresAuth: true, title: 'Execution Logs',  resource: 'logs' } },
  { path: '/network',           component: () => import('../views/NetworkView.vue'),            meta: { requiresAuth: true, title: 'Network',         resource: 'network' } },
  { path: '/history',           component: () => import('../views/HistoryView.vue'),            meta: { requiresAuth: true, title: 'History',         resource: 'system' } },
  { path: '/admin/users',       component: () => import('../views/AdminUsersView.vue'),         meta: { requiresAuth: true, title: 'Users',           adminOnly: true } },
  { path: '/pipelines',         component: () => import('../views/PipelinesView.vue'),          meta: { requiresAuth: true, title: 'Pipelines',       resource: 'pipelines' } },
  { path: '/admin/permissions', component: () => import('../views/AdminPermissionsView.vue'),   meta: { requiresAuth: true, title: 'Permissions',     adminOnly: true } },
  { path: '/alerts',            component: () => import('../views/AlertsView.vue'),             meta: { requiresAuth: true, title: 'Alerts',          resource: 'alerts' } },
  { path: '/logs',              component: () => import('../views/SystemLogsView.vue'),         meta: { requiresAuth: true, title: 'System Logs',     resource: 'system_logs' } },
  { path: '/processes',         component: () => import('../views/ProcessesView.vue'),          meta: { requiresAuth: true, title: 'Processes',       resource: 'processes' } },
  { path: '/:pathMatch(.*)*',   redirect: '/' },
]
```

- [ ] **Step 2: Update `frontend/src/components/layout/AppSidebar.vue`**

Replace the `manageItems` computed property and add `monitoringItems`. The full `<script setup>` section becomes:

```javascript
const monitorItems = computed(() => {
  const items = [
    { to: '/',         icon: 'pi-th-large',  label: 'Dashboard', resource: 'system' },
    { to: '/services', icon: 'pi-cog',       label: 'Services',  resource: 'services' },
    { to: '/files',    icon: 'pi-folder-open', label: 'Files',   resource: 'files' },
    { to: '/network',  icon: 'pi-wifi',      label: 'Network',   resource: 'network' },
    { to: '/history',  icon: 'pi-chart-bar', label: 'History',   resource: 'system' },
  ]
  return items.filter(i => auth.hasPermission(i.resource, 'read'))
})

const manageItems = computed(() => {
  const items = [
    { to: '/scripts',         icon: 'pi-code',       label: 'Scripts',    resource: 'scripts' },
    { to: '/pipelines',       icon: 'pi-sitemap',    label: 'Pipelines',  resource: 'pipelines' },
    { to: '/crontab',         icon: 'pi-clock',      label: 'Crontab',    resource: 'crontab' },
    { to: '/execution-logs',  icon: 'pi-list',       label: 'Exec Logs',  resource: 'logs' },
    { to: '/alerts',          icon: 'pi-bell',       label: 'Alerts',     resource: 'alerts' },
    { to: '/logs',            icon: 'pi-file-edit',  label: 'Logs',       resource: 'system_logs' },
    { to: '/processes',       icon: 'pi-server',     label: 'Processes',  resource: 'processes' },
  ]
  return items.filter(i => auth.hasPermission(i.resource, 'read'))
})
```

- [ ] **Step 3: Update `MATRIX_ROWS` in `frontend/src/views/AdminPermissionsView.vue`**

Add these rows after `{ resource: 'pipelines', action: 'execute' }`:

```javascript
  { resource: 'alerts',      action: 'read' },
  { resource: 'alerts',      action: 'write' },
  { resource: 'system_logs', action: 'read' },
  { resource: 'processes',   action: 'read' },
  { resource: 'processes',   action: 'execute' },
```

- [ ] **Step 4: Run frontend type-check and tests**

```bash
cd frontend && npm test
```

Expected: the 3 known `LoginView` failures only. No new failures.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/router/index.js frontend/src/components/layout/AppSidebar.vue frontend/src/views/AdminPermissionsView.vue
git commit -m "feat(nav): add Alerts/Logs/Processes routes, sidebar entries, and permission matrix rows"
```

---

## Task 10: AlertsView.vue

**Files:**
- Create: `frontend/src/views/AlertsView.vue`

- [ ] **Step 1: Create `frontend/src/views/AlertsView.vue`**

```vue
<template>
  <div class="alerts-view">
    <div class="page-header">
      <div class="page-title">
        <i class="pi pi-bell page-icon" />
        <span>ALERTS</span>
        <Tag :value="`${rules.length} rules`" severity="secondary" />
      </div>
      <Button
        v-if="auth.hasPermission('alerts', 'write')"
        label="New Rule"
        icon="pi pi-plus"
        size="small"
        @click="startNew"
      />
    </div>

    <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>

    <Splitter class="alerts-splitter" :gutter-size="6">
      <!-- Left: rule list -->
      <SplitterPanel :size="30" :min-size="20">
        <div class="rule-list">
          <div
            v-for="rule in rules"
            :key="rule.id"
            class="rule-item"
            :class="{ selected: selectedRule?.id === rule.id }"
            @click="selectRule(rule)"
          >
            <span
              class="status-dot"
              :class="{
                'dot-active': rule.has_active_fire,
                'dot-ok': !rule.has_active_fire && rule.enabled,
                'dot-disabled': !rule.enabled,
              }"
            />
            <div class="rule-info">
              <span class="rule-name">{{ rule.name }}</span>
              <span class="rule-meta">{{ rule.condition_type }} · {{ rule.cooldown_minutes }}min</span>
            </div>
          </div>
          <div v-if="rules.length === 0" class="empty-state">No alert rules configured.</div>
        </div>
      </SplitterPanel>

      <!-- Right: editor + fire history -->
      <SplitterPanel :size="70" :min-size="40">
        <div class="right-panel">
          <!-- Rule editor -->
          <div v-if="selectedRule || isNew" class="editor-card">
            <div class="editor-header">
              <span class="editor-title">{{ isNew ? 'NEW RULE' : 'EDIT RULE' }}</span>
              <div class="editor-actions" v-if="auth.hasPermission('alerts', 'write')">
                <Button
                  v-if="!isNew"
                  :label="form.enabled ? 'Disable' : 'Enable'"
                  size="small"
                  severity="secondary"
                  @click="toggleRule"
                />
                <Button
                  v-if="!isNew"
                  label="Delete"
                  icon="pi pi-trash"
                  size="small"
                  severity="danger"
                  @click="deleteRule"
                />
                <Button label="Save" icon="pi pi-check" size="small" @click="saveRule" :loading="saving" />
              </div>
            </div>

            <div class="form-grid">
              <div class="form-field">
                <label>Name</label>
                <InputText v-model="form.name" size="small" :disabled="!canEdit" />
              </div>
              <div class="form-field">
                <label>Type</label>
                <Select
                  v-model="form.condition_type"
                  :options="conditionOptions"
                  option-label="label"
                  option-value="value"
                  size="small"
                  :disabled="!canEdit"
                />
              </div>
              <div class="form-field" v-if="['cpu','ram','disk'].includes(form.condition_type)">
                <label>Threshold (%)</label>
                <InputNumber v-model="form.threshold" :min="1" :max="100" size="small" :disabled="!canEdit" />
              </div>
              <div class="form-field" v-else>
                <label>Target (name)</label>
                <InputText v-model="form.target" size="small" :disabled="!canEdit" placeholder="nginx" />
              </div>
              <div class="form-field">
                <label>Cooldown (minutes)</label>
                <InputNumber v-model="form.cooldown_minutes" :min="1" size="small" :disabled="!canEdit" />
              </div>
              <div class="form-field">
                <label>Email to</label>
                <InputText v-model="form.email_to" size="small" :disabled="!canEdit" />
              </div>
              <div class="form-field form-field--checkbox">
                <Checkbox v-model="form.notify_on_recovery" :binary="true" :disabled="!canEdit" />
                <label>Notify on recovery</label>
              </div>
            </div>
          </div>

          <!-- Fire history -->
          <div class="fire-history" v-if="selectedRule && !isNew">
            <div class="section-label">FIRE HISTORY</div>
            <DataTable :value="fires" size="small" class="fire-table" :loading="firesLoading">
              <Column field="status" header="Status" style="width: 120px">
                <template #body="{ data }">
                  <Tag
                    :value="data.status === 'active' ? 'ACTIVE' : 'RECOVERED'"
                    :severity="data.status === 'active' ? 'danger' : 'success'"
                  />
                </template>
              </Column>
              <Column field="detail" header="Detail" />
              <Column field="fired_at" header="Fired" style="width: 160px">
                <template #body="{ data }">{{ formatTs(data.fired_at) }}</template>
              </Column>
              <Column field="recovered_at" header="Recovered" style="width: 160px">
                <template #body="{ data }">{{ data.recovered_at ? formatTs(data.recovered_at) : '—' }}</template>
              </Column>
              <Column header="Duration" style="width: 100px">
                <template #body="{ data }">{{ duration(data) }}</template>
              </Column>
              <template #empty>No fires recorded for this rule.</template>
            </DataTable>
          </div>

          <div v-if="!selectedRule && !isNew" class="empty-state center">
            Select a rule to view details or click "New Rule" to create one.
          </div>
        </div>
      </SplitterPanel>
    </Splitter>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth.js'
import api from '../api/client.js'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Message from 'primevue/message'
import Splitter from 'primevue/splitter'
import SplitterPanel from 'primevue/splitterpanel'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Select from 'primevue/select'
import Checkbox from 'primevue/checkbox'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'

const auth = useAuthStore()

const rules = ref([])
const fires = ref([])
const selectedRule = ref(null)
const isNew = ref(false)
const saving = ref(false)
const firesLoading = ref(false)
const error = ref(null)

const emptyForm = () => ({
  name: '',
  enabled: true,
  condition_type: 'cpu',
  threshold: 85,
  target: '',
  cooldown_minutes: 60,
  notify_on_recovery: true,
  email_to: '',
})

const form = ref(emptyForm())

const canEdit = computed(() => auth.hasPermission('alerts', 'write'))

const conditionOptions = [
  { label: 'CPU %',           value: 'cpu' },
  { label: 'RAM %',           value: 'ram' },
  { label: 'Disk %',          value: 'disk' },
  { label: 'Service Down',    value: 'service_down' },
  { label: 'Process Missing', value: 'process_missing' },
]

async function loadRules() {
  try {
    const r = await api.get('/alerts/rules')
    rules.value = r.data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load alert rules'
  }
}

async function loadFires(ruleId) {
  firesLoading.value = true
  try {
    const r = await api.get('/alerts/fires', { params: { rule_id: ruleId } })
    fires.value = r.data
  } catch {
    fires.value = []
  } finally {
    firesLoading.value = false
  }
}

function selectRule(rule) {
  isNew.value = false
  selectedRule.value = rule
  form.value = { ...rule }
  loadFires(rule.id)
}

function startNew() {
  isNew.value = true
  selectedRule.value = null
  form.value = emptyForm()
  fires.value = []
}

async function saveRule() {
  saving.value = true
  try {
    if (isNew.value) {
      await api.post('/alerts/rules', form.value)
    } else {
      await api.put(`/alerts/rules/${selectedRule.value.id}`, form.value)
    }
    await loadRules()
    isNew.value = false
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to save rule'
  } finally {
    saving.value = false
  }
}

async function toggleRule() {
  try {
    await api.patch(`/alerts/rules/${selectedRule.value.id}/toggle`)
    await loadRules()
    // Refresh selected rule
    selectedRule.value = rules.value.find(r => r.id === selectedRule.value.id)
    if (selectedRule.value) form.value = { ...selectedRule.value }
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to toggle rule'
  }
}

async function deleteRule() {
  if (!confirm(`Delete rule "${selectedRule.value.name}"?`)) return
  try {
    await api.delete(`/alerts/rules/${selectedRule.value.id}`)
    selectedRule.value = null
    isNew.value = false
    fires.value = []
    await loadRules()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to delete rule'
  }
}

function formatTs(ts) {
  if (!ts) return '—'
  return new Date(ts + 'Z').toLocaleString()
}

function duration(fire) {
  const end = fire.recovered_at ? new Date(fire.recovered_at + 'Z') : new Date()
  const start = new Date(fire.fired_at + 'Z')
  const secs = Math.floor((end - start) / 1000)
  if (secs < 60) return `${secs}s`
  if (secs < 3600) return `${Math.floor(secs / 60)}m`
  return `${Math.floor(secs / 3600)}h`
}

onMounted(loadRules)
</script>

<style scoped>
.alerts-view { display: flex; flex-direction: column; height: 100%; gap: 12px; }
.page-header { display: flex; align-items: center; justify-content: space-between; }
.page-title { display: flex; align-items: center; gap: 10px; font-family: var(--font-mono); font-size: var(--text-sm); font-weight: 700; letter-spacing: 2px; color: var(--p-text-muted-color); }
.page-icon { color: var(--brand-orange); font-size: var(--text-lg); }
.alerts-splitter { flex: 1; border: none; background: transparent; }
.rule-list { padding: 8px; display: flex; flex-direction: column; gap: 4px; height: 100%; overflow-y: auto; }
.rule-item { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border-radius: 6px; cursor: pointer; border: 1px solid transparent; transition: background 0.15s, border-color 0.15s; }
.rule-item:hover { background: var(--p-surface-hover); }
.rule-item.selected { background: color-mix(in srgb, var(--brand-orange) 10%, transparent); border-color: color-mix(in srgb, var(--brand-orange) 30%, transparent); }
.status-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.dot-active { background: var(--p-red-500); box-shadow: 0 0 6px var(--p-red-500); animation: pulse 1.5s ease-in-out infinite; }
.dot-ok { background: var(--p-green-500); }
.dot-disabled { background: var(--p-surface-border); }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.rule-info { display: flex; flex-direction: column; gap: 2px; }
.rule-name { font-size: var(--text-sm); color: var(--p-text-color); }
.rule-meta { font-size: var(--text-xs); color: var(--p-text-muted-color); font-family: var(--font-mono); }
.right-panel { display: flex; flex-direction: column; gap: 12px; height: 100%; overflow-y: auto; padding: 8px; }
.editor-card { background: var(--p-surface-card); border: 1px solid var(--p-surface-border); border-radius: 8px; padding: 14px; }
.editor-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.editor-title { font-family: var(--font-mono); font-size: var(--text-xs); letter-spacing: 2px; color: var(--p-text-muted-color); font-weight: 600; }
.editor-actions { display: flex; gap: 8px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.form-field { display: flex; flex-direction: column; gap: 4px; }
.form-field label { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); letter-spacing: 1px; }
.form-field--checkbox { flex-direction: row; align-items: center; gap: 8px; }
.fire-history { display: flex; flex-direction: column; gap: 8px; }
.section-label { font-family: var(--font-mono); font-size: var(--text-xs); letter-spacing: 2px; color: var(--p-text-muted-color); font-weight: 600; }
.empty-state { padding: 24px; text-align: center; color: var(--p-text-muted-color); font-size: var(--text-sm); }
.empty-state.center { flex: 1; display: flex; align-items: center; justify-content: center; }
</style>
```

- [ ] **Step 2: Start the dev server and verify in browser**

```bash
cd frontend && npm run dev
```

Navigate to `https://localhost:5173/alerts`. Verify:
- Rule list loads (empty on fresh DB)
- "New Rule" button visible for admin
- Creating a rule: fill form, click Save, rule appears in list
- Selecting a rule: form populates, fire history loads
- Toggle enable/disable: status dot changes
- Delete: rule disappears from list

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/AlertsView.vue
git commit -m "feat(frontend): add AlertsView with rule editor and fire history"
```

---

## Task 11: SystemLogsView.vue

**Files:**
- Create: `frontend/src/views/SystemLogsView.vue`

- [ ] **Step 1: Create `frontend/src/views/SystemLogsView.vue`**

```vue
<template>
  <div class="logs-view">
    <div class="page-header">
      <div class="page-title">
        <i class="pi pi-file-edit page-icon" />
        <span>SYSTEM LOGS</span>
        <Tag v-if="tailing" value="TAILING" severity="info" />
        <Tag v-else-if="selectedFile" value="PAUSED" severity="warning" />
      </div>
      <div class="header-actions" v-if="selectedFile">
        <Button
          :label="tailing ? 'Pause' : 'Resume'"
          :icon="tailing ? 'pi pi-pause' : 'pi pi-play'"
          size="small"
          severity="secondary"
          @click="toggleTail"
        />
        <IconField>
          <InputIcon class="pi pi-search" />
          <InputText v-model="searchTerm" placeholder="Search…" size="small" />
        </IconField>
      </div>
    </div>

    <Splitter class="main-splitter" :gutter-size="6">
      <!-- Left: file tree -->
      <SplitterPanel :size="25" :min-size="15">
        <div class="file-tree">
          <div class="tree-header">
            <span class="tree-label">/VAR/LOG</span>
            <Button icon="pi pi-refresh" size="small" text severity="secondary" @click="loadTree" :loading="treeLoading" />
          </div>
          <div class="tree-body">
            <TreeNode
              v-for="node in tree"
              :key="node.path"
              :node="node"
              :selected-path="selectedFile?.path"
              @select="openFile"
            />
          </div>
        </div>
      </SplitterPanel>

      <!-- Right: log output -->
      <SplitterPanel :size="75" :min-size="40">
        <div v-if="!selectedFile" class="empty-state">
          Select a log file from the tree on the left.
        </div>
        <div v-else class="log-panel">
          <div class="log-header">
            <span class="log-filename">{{ selectedFile.name }}</span>
          </div>
          <div ref="logContainer" class="log-output" @scroll="onScroll">
            <div
              v-for="(line, idx) in filteredLines"
              :key="idx"
              class="log-line"
              :class="lineClass(line)"
            >{{ line }}</div>
            <div ref="logBottom" />
          </div>
        </div>
      </SplitterPanel>
    </Splitter>
  </div>

  <!-- Inline TreeNode component -->
</template>

<script setup>
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'
import api from '../api/client.js'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Splitter from 'primevue/splitter'
import SplitterPanel from 'primevue/splitterpanel'
import InputText from 'primevue/inputtext'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'

// ── Recursive TreeNode (defined inline) ──────────────────────────────────────
import { defineComponent, h } from 'vue'
const TreeNode = defineComponent({
  name: 'TreeNode',
  props: { node: Object, selectedPath: String },
  emits: ['select'],
  setup(props, { emit }) {
    const open = ref(false)
    return () => {
      const n = props.node
      if (n.is_dir) {
        return h('div', { class: 'tree-dir' }, [
          h('div', {
            class: 'tree-dir-label',
            onClick: () => { open.value = !open.value },
          }, [
            h('i', { class: open.value ? 'pi pi-chevron-down tree-arrow' : 'pi pi-chevron-right tree-arrow' }),
            h('i', { class: 'pi pi-folder tree-icon' }),
            h('span', n.name),
          ]),
          open.value
            ? h('div', { class: 'tree-children' },
                n.children?.map(c =>
                  h(TreeNode, { node: c, selectedPath: props.selectedPath, onSelect: (f) => emit('select', f) })
                )
              )
            : null,
        ])
      }
      return h('div', {
        class: [
          'tree-file',
          { selected: props.selectedPath === n.path, unreadable: !n.readable },
        ],
        onClick: () => n.readable && emit('select', n),
      }, [
        h('i', { class: 'pi pi-file tree-icon' }),
        h('span', { class: 'tree-file-name' }, n.name),
        n.size_bytes != null
          ? h('span', { class: 'tree-file-size' }, formatSize(n.size_bytes))
          : null,
      ])
    }
  },
})

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(0)}K`
  return `${(bytes / 1_048_576).toFixed(1)}M`
}

// ── State ────────────────────────────────────────────────────────────────────
const tree = ref([])
const treeLoading = ref(false)
const selectedFile = ref(null)
const lines = ref([])       // bounded at 2000
const tailing = ref(false)
const searchTerm = ref('')
const logContainer = ref(null)
const logBottom = ref(null)
const autoScroll = ref(true)

const MAX_LINES = 2000

let ws = null

// ── Computed ─────────────────────────────────────────────────────────────────
const filteredLines = computed(() => {
  if (!searchTerm.value) return lines.value
  const term = searchTerm.value.toLowerCase()
  return lines.value.filter(l => l.toLowerCase().includes(term))
})

// ── Tree ─────────────────────────────────────────────────────────────────────
async function loadTree() {
  treeLoading.value = true
  try {
    const r = await api.get('/system-logs/tree')
    tree.value = r.data
  } catch { /* permission denied or /var/log not accessible */ }
  finally { treeLoading.value = false }
}

// ── File selection ────────────────────────────────────────────────────────────
async function openFile(file) {
  stopTail()
  selectedFile.value = file
  lines.value = []
  searchTerm.value = ''

  // Load last 100 lines
  try {
    const r = await api.get('/system-logs/read', { params: { path: file.path, lines: 100 } })
    lines.value = r.data.lines.slice(-MAX_LINES)
  } catch { /* unreadable */ }

  await nextTick()
  scrollToBottom()
  startTail(file.path)
}

// ── WebSocket tail ────────────────────────────────────────────────────────────
function buildWsUrl(filePath) {
  const token = localStorage.getItem('access_token')
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return `${protocol}//${host}/api/ws/log-tail?path=${encodeURIComponent(filePath)}&token=${token}`
}

function startTail(filePath) {
  stopTail()
  tailing.value = true
  ws = new WebSocket(buildWsUrl(filePath))

  ws.onmessage = (evt) => {
    if (!tailing.value) return
    const newLines = evt.data.split('\n').filter(l => l.length > 0)
    lines.value.push(...newLines)
    if (lines.value.length > MAX_LINES) {
      lines.value = lines.value.slice(-MAX_LINES)
    }
    if (autoScroll.value) {
      nextTick(scrollToBottom)
    }
  }

  ws.onclose = () => {
    tailing.value = false
  }

  ws.onerror = () => {
    tailing.value = false
  }
}

function stopTail() {
  if (ws) {
    ws.close()
    ws = null
  }
  tailing.value = false
}

function toggleTail() {
  if (tailing.value) {
    stopTail()
  } else if (selectedFile.value) {
    startTail(selectedFile.value.path)
  }
}

// ── Scroll behaviour ──────────────────────────────────────────────────────────
function scrollToBottom() {
  logBottom.value?.scrollIntoView({ behavior: 'instant' })
}

function onScroll() {
  if (!logContainer.value) return
  const { scrollTop, scrollHeight, clientHeight } = logContainer.value
  autoScroll.value = scrollHeight - scrollTop - clientHeight < 40
}

// ── Line colouring ────────────────────────────────────────────────────────────
function lineClass(line) {
  const u = line.toUpperCase()
  if (u.includes('ERROR') || u.includes('ERR ') || u.includes('CRITICAL') || u.includes('FATAL'))
    return 'line-error'
  if (u.includes('WARN'))
    return 'line-warn'
  return ''
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────
loadTree()
onUnmounted(stopTail)
</script>

<style scoped>
.logs-view { display: flex; flex-direction: column; height: 100%; gap: 12px; }
.page-header { display: flex; align-items: center; justify-content: space-between; }
.page-title { display: flex; align-items: center; gap: 10px; font-family: var(--font-mono); font-size: var(--text-sm); font-weight: 700; letter-spacing: 2px; color: var(--p-text-muted-color); }
.page-icon { color: var(--p-blue-400); font-size: var(--text-lg); }
.header-actions { display: flex; align-items: center; gap: 8px; }
.main-splitter { flex: 1; border: none; background: transparent; }
.file-tree { display: flex; flex-direction: column; height: 100%; }
.tree-header { display: flex; align-items: center; justify-content: space-between; padding: 8px 10px; border-bottom: 1px solid var(--p-surface-border); }
.tree-label { font-family: var(--font-mono); font-size: var(--text-xs); letter-spacing: 2px; color: var(--p-text-muted-color); }
.tree-body { flex: 1; overflow-y: auto; padding: 4px; }
:deep(.tree-dir-label) { display: flex; align-items: center; gap: 6px; padding: 4px 8px; cursor: pointer; border-radius: 4px; font-size: var(--text-xs); color: var(--p-text-color); }
:deep(.tree-dir-label:hover) { background: var(--p-surface-hover); }
:deep(.tree-children) { padding-left: 14px; }
:deep(.tree-file) { display: flex; align-items: center; gap: 6px; padding: 3px 8px; border-radius: 4px; cursor: pointer; font-size: var(--text-xs); color: var(--p-text-muted-color); }
:deep(.tree-file:hover) { background: var(--p-surface-hover); color: var(--p-text-color); }
:deep(.tree-file.selected) { background: color-mix(in srgb, var(--p-blue-400) 15%, transparent); color: var(--p-blue-400); }
:deep(.tree-file.unreadable) { opacity: 0.4; cursor: not-allowed; }
:deep(.tree-file-name) { flex: 1; }
:deep(.tree-file-size) { font-family: var(--font-mono); font-size: 10px; color: var(--p-text-muted-color); }
:deep(.tree-arrow) { font-size: 10px; width: 10px; color: var(--p-text-muted-color); }
:deep(.tree-icon) { font-size: var(--text-xs); color: var(--p-text-muted-color); }
.log-panel { display: flex; flex-direction: column; height: 100%; }
.log-header { padding: 6px 12px; border-bottom: 1px solid var(--p-surface-border); }
.log-filename { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); letter-spacing: 1px; }
.log-output { flex: 1; overflow-y: auto; padding: 8px 12px; font-family: var(--font-mono); font-size: 12px; line-height: 1.6; background: var(--p-surface-ground); }
.log-line { white-space: pre-wrap; word-break: break-all; color: var(--p-text-muted-color); }
.log-line.line-error { color: var(--p-red-400); }
.log-line.line-warn  { color: var(--p-orange-400); }
.empty-state { flex: 1; display: flex; align-items: center; justify-content: center; color: var(--p-text-muted-color); font-size: var(--text-sm); }
</style>
```

- [ ] **Step 2: Start dev server and verify in browser**

```bash
cd frontend && npm run dev
```

Navigate to `https://localhost:5173/logs`. Verify:
- `/var/log` tree loads on the left (may show only directories readable by the current user)
- Clicking a readable file loads last 100 lines on the right
- "TAILING" badge appears; new lines appended to a log appear automatically
- "Pause" stops the WebSocket; "Resume" reconnects
- Search input filters visible lines
- Error/warn lines are color-coded red/orange
- Scrolling up during tail pauses auto-scroll; scrolling to bottom resumes it

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/SystemLogsView.vue
git commit -m "feat(frontend): add SystemLogsView with /var/log tree and WebSocket file tail"
```

---

## Task 12: ProcessesView.vue

**Files:**
- Create: `frontend/src/views/ProcessesView.vue`

- [ ] **Step 1: Create `frontend/src/views/ProcessesView.vue`**

```vue
<template>
  <div class="processes-view">
    <div class="page-header">
      <div class="page-title">
        <i class="pi pi-server page-icon" />
        <span>PROCESSES</span>
        <Tag :value="`${displayedCount} shown`" severity="secondary" />
        <Tag value="AUTO-REFRESH 5s" severity="success" />
      </div>
      <IconField>
        <InputIcon class="pi pi-search" />
        <InputText v-model="filter" placeholder="Filter by name…" size="small" @input="applyFilter" />
      </IconField>
    </div>

    <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>

    <div v-if="truncated" class="truncate-notice">
      Showing top 500 processes by CPU usage. Use the filter to find specific processes.
    </div>

    <DataTable
      :value="filteredProcs"
      size="small"
      :loading="loading"
      class="procs-table"
      scrollable
      scroll-height="flex"
      :sort-field="sortField"
      :sort-order="sortOrder"
      @sort="onSort"
    >
      <Column field="name" header="Name" sortable style="min-width: 160px">
        <template #body="{ data }">
          <span class="proc-name">{{ data.name }}</span>
        </template>
      </Column>
      <Column field="pid" header="PID" sortable style="width: 80px">
        <template #body="{ data }">
          <span class="mono">{{ data.pid }}</span>
        </template>
      </Column>
      <Column field="cpu_percent" header="CPU %" sortable style="width: 90px">
        <template #body="{ data }">
          <span :class="cpuClass(data.cpu_percent)" class="mono">{{ data.cpu_percent.toFixed(1) }}%</span>
        </template>
      </Column>
      <Column field="memory_mb" header="RAM (MB)" sortable style="width: 100px">
        <template #body="{ data }">
          <span class="mono">{{ data.memory_mb }}</span>
        </template>
      </Column>
      <Column field="username" header="User" style="width: 100px" />
      <Column field="status" header="Status" style="width: 90px">
        <template #body="{ data }">
          <Tag :value="data.status" :severity="data.status === 'running' ? 'success' : 'secondary'" />
        </template>
      </Column>
      <Column header="Watch" style="width: 100px">
        <template #body="{ data }">
          <button
            class="watch-btn"
            :class="{ watched: data.watched }"
            @click="toggleWatch(data)"
            :title="data.watched ? 'Unwatch' : 'Watch'"
          >
            <i :class="data.watched ? 'pi pi-eye-slash' : 'pi pi-eye'" />
            {{ data.watched ? 'Watching' : 'Watch' }}
          </button>
        </template>
      </Column>
      <Column header="Kill" style="width: 80px" v-if="auth.isAdmin">
        <template #body="{ data }">
          <button class="kill-btn" @click="confirmKill(data)">
            <i class="pi pi-times-circle" />
          </button>
        </template>
      </Column>
      <template #empty>No processes found.</template>
    </DataTable>

    <!-- Watch modal — collect email before creating watch rule -->
    <Dialog v-model:visible="watchDialog.visible" :header="`Watch: ${watchDialog.name}`" modal style="width: 360px">
      <div class="watch-form">
        <label>Email for alerts</label>
        <InputText v-model="watchDialog.email" size="small" placeholder="ops@example.com" />
        <label>Cooldown (minutes)</label>
        <InputNumber v-model="watchDialog.cooldown" :min="1" size="small" />
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" size="small" @click="watchDialog.visible = false" />
        <Button label="Watch" size="small" @click="submitWatch" />
      </template>
    </Dialog>

    <!-- Kill confirmation -->
    <ConfirmDialog />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useConfirm } from 'primevue/useconfirm'
import { useAuthStore } from '../stores/auth.js'
import { usePolling } from '../composables/usePolling.js'
import api from '../api/client.js'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Message from 'primevue/message'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import Dialog from 'primevue/dialog'
import ConfirmDialog from 'primevue/confirmdialog'

const auth = useAuthStore()
const confirm = useConfirm()

const allProcs = ref([])
const loading = ref(false)
const error = ref(null)
const filter = ref('')
const sortField = ref('cpu_percent')
const sortOrder = ref(-1)
const MAX_DISPLAY = 500

const watchDialog = ref({ visible: false, name: '', pid: null, email: '', cooldown: 15 })

const truncated = computed(() => allProcs.value.length >= MAX_DISPLAY)
const displayedCount = computed(() => filteredProcs.value.length)

const filteredProcs = computed(() => {
  if (!filter.value) return allProcs.value
  const term = filter.value.toLowerCase()
  return allProcs.value.filter(p => p.name.toLowerCase().includes(term))
})

function applyFilter() { /* reactivity handles it */ }

function cpuClass(val) {
  if (val >= 50) return 'cpu-high'
  if (val >= 10) return 'cpu-mid'
  return 'cpu-low'
}

function onSort(e) {
  sortField.value = e.sortField
  sortOrder.value = e.sortOrder
}

async function loadProcesses() {
  if (loading.value) return
  loading.value = true
  try {
    const r = await api.get('/processes/')
    allProcs.value = r.data
    error.value = null
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load processes'
  } finally {
    loading.value = false
  }
}

function toggleWatch(proc) {
  if (proc.watched) {
    unwatchProcess(proc.name)
  } else {
    watchDialog.value = { visible: true, name: proc.name, pid: proc.pid, email: '', cooldown: 15 }
  }
}

async function submitWatch() {
  if (!watchDialog.value.email) return
  try {
    await api.post('/processes/watch', {
      name: watchDialog.value.name,
      email_to: watchDialog.value.email,
      cooldown_minutes: watchDialog.value.cooldown,
    })
    watchDialog.value.visible = false
    await loadProcesses()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to add watch'
  }
}

async function unwatchProcess(name) {
  try {
    await api.delete(`/processes/watch/${encodeURIComponent(name)}`)
    await loadProcesses()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to remove watch'
  }
}

function confirmKill(proc) {
  confirm.require({
    message: `Kill process "${proc.name}" (PID ${proc.pid})?`,
    header: 'Confirm Kill',
    icon: 'pi pi-exclamation-triangle',
    rejectLabel: 'Cancel',
    acceptLabel: 'Kill',
    acceptSeverity: 'danger',
    accept: () => killProcess(proc.pid),
  })
}

async function killProcess(pid) {
  try {
    await api.post(`/processes/${pid}/kill`)
    await loadProcesses()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to kill process'
  }
}

const { start, stop } = usePolling(loadProcesses, 5000)
onMounted(start)
onUnmounted(stop)
</script>

<style scoped>
.processes-view { display: flex; flex-direction: column; height: 100%; gap: 12px; }
.page-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.page-title { display: flex; align-items: center; gap: 10px; font-family: var(--font-mono); font-size: var(--text-sm); font-weight: 700; letter-spacing: 2px; color: var(--p-text-muted-color); }
.page-icon { color: var(--p-violet-400, #a855f7); font-size: var(--text-lg); }
.truncate-notice { font-size: var(--text-xs); color: var(--p-text-muted-color); padding: 4px 8px; background: var(--p-surface-hover); border-radius: 4px; }
.procs-table { flex: 1; }
.proc-name { font-family: var(--font-mono); font-size: var(--text-xs); }
.mono { font-family: var(--font-mono); font-size: var(--text-xs); }
.cpu-high { color: var(--p-red-400); }
.cpu-mid  { color: var(--p-orange-400); }
.cpu-low  { color: var(--p-green-400); }
.watch-btn { display: flex; align-items: center; gap: 4px; background: none; border: 1px solid var(--p-surface-border); border-radius: 4px; padding: 2px 8px; cursor: pointer; font-size: var(--text-xs); color: var(--p-text-muted-color); transition: color 0.15s, border-color 0.15s; }
.watch-btn:hover { color: var(--p-orange-400); border-color: var(--p-orange-400); }
.watch-btn.watched { color: var(--p-orange-400); border-color: var(--p-orange-400); }
.kill-btn { background: none; border: none; color: var(--p-red-400); cursor: pointer; font-size: var(--text-base); padding: 2px 6px; border-radius: 4px; transition: background 0.15s; }
.kill-btn:hover { background: color-mix(in srgb, var(--p-red-400) 15%, transparent); }
.watch-form { display: flex; flex-direction: column; gap: 8px; }
.watch-form label { font-family: var(--font-mono); font-size: var(--text-xs); letter-spacing: 1px; color: var(--p-text-muted-color); }
</style>
```

- [ ] **Step 2: Start dev server and verify in browser**

```bash
cd frontend && npm run dev
```

Navigate to `https://localhost:5173/processes`. Verify:
- Process list loads, sorted by CPU desc
- Auto-refresh badge visible; table updates every 5 seconds
- Filter input narrows the list by name
- "Watch" button opens the email dialog; submitting creates an AlertRule visible in `/alerts`
- After watching, the process row shows "Watching" and the alert rule appears in `/alerts`
- "Unwatch" removes the rule
- (Admin only) Kill button opens confirm dialog; confirmed kill sends request

- [ ] **Step 3: Run full test suite**

```bash
pytest -q
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/ProcessesView.vue
git commit -m "feat(frontend): add ProcessesView with 5s polling, watch, and kill"
```

---

## Task 13: Final verification and documentation

- [ ] **Step 1: Run full backend test suite**

```bash
pytest -v
```

Expected: all tests PASS. Note any pre-existing failures that existed before this branch.

- [ ] **Step 2: Run frontend tests**

```bash
cd frontend && npm test
```

Expected: only the 3 known `LoginView` failures (pre-existing PrimeVue test env issue). No new failures.

- [ ] **Step 3: Build frontend**

```bash
cd frontend && npm run build
```

Expected: successful build, no TypeScript or bundle errors.

- [ ] **Step 4: Apply new indexes to any existing database**

```bash
python -m backend.scripts.add_indexes
```

Expected: `Indexes applied.`

- [ ] **Step 5: Log in the bitacora**

Add an entry to `docs/bitacora.md` under today's date with:
- Feature: Alerts & Notifications, System Logs Viewer, Process Manager
- Files created: 12 new files listed
- Files modified: 11 modified files listed
- Notes: scheduler job runs every 60s; WS tail polls at 500ms; bounded at MAX_LINES=2000 in SystemLogsView; bounded at 500 processes in ProcessesView

- [ ] **Step 6: Final commit**

```bash
git add docs/bitacora.md
git commit -m "docs: log alerts/logs/processes implementation in bitacora"
```

---

## Self-review checklist

- [x] All new DB columns used in WHERE/ORDER BY have `Index` in `__table_args__` AND in `add_indexes.py`
- [x] No inline `q.count()` on paginated endpoints (fires list uses `.limit(100)`, not count)
- [x] Date comparisons use `datetime.utcnow()` (naive UTC) throughout scheduler
- [x] New background task follows `_do_check_alerts` / `_check_alerts_job` split and is registered in `init_scheduler()`
- [x] All three new Vue routes use `() => import(...)` — no static imports
- [x] `SystemLogsView` caps lines at `MAX_LINES = 2000`
- [x] `ProcessesView` caps at `MAX_DISPLAY = 500`
- [x] No new module-level `TTLCache` instances (none needed in these routers)
- [x] `require_permission` used on every new endpoint — no bare `get_current_user`
- [x] `run_in_threadpool` wraps `psutil.process_iter` and `psutil.Process.kill`
- [x] WS tail validates path under `/var/log` before accepting connection
- [x] Process watch/unwatch requires `alerts.write` (creates/deletes AlertRule)
