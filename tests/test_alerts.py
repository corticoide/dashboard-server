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


def test_send_alert_email_calls_smtp(db_session):
    from unittest.mock import patch, MagicMock
    from backend.models.alert import AlertRule, AlertFire
    from backend.services.notification_service import send_alert_email

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
