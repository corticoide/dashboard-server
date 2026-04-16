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
