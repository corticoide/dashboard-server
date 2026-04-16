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
