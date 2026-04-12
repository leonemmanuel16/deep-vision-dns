"""Alert rules CRUD endpoints."""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.alert_rule import AlertRule
from schemas.alert_rule import AlertRuleCreate, AlertRuleUpdate, AlertRuleResponse
from services.auth import get_current_user

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/", response_model=list[AlertRuleResponse])
def list_alerts(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(AlertRule).order_by(AlertRule.created_at.desc()).all()


@router.post("/", response_model=AlertRuleResponse, status_code=201)
def create_alert(body: AlertRuleCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    rule = AlertRule(**body.model_dump(exclude_none=True))
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.put("/{alert_id}", response_model=AlertRuleResponse)
def update_alert(alert_id: uuid.UUID, body: AlertRuleUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    rule = db.query(AlertRule).filter(AlertRule.id == alert_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{alert_id}", status_code=204)
def delete_alert(alert_id: uuid.UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    rule = db.query(AlertRule).filter(AlertRule.id == alert_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    db.delete(rule)
    db.commit()


@router.post("/{alert_id}/test")
def test_alert(alert_id: uuid.UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Send a test notification for an alert rule."""
    rule = db.query(AlertRule).filter(AlertRule.id == alert_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    # TODO: trigger test notification via configured actions
    return {"status": "test_sent", "alert_id": str(alert_id), "actions": rule.actions}
