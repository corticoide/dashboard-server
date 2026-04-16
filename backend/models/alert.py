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
