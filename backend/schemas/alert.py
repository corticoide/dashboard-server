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
