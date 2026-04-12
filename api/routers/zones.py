"""Zone CRUD endpoints."""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.zone import Zone
from schemas.zone import ZoneCreate, ZoneUpdate, ZoneResponse
from services.auth import get_current_user

router = APIRouter(prefix="/zones", tags=["zones"])


@router.get("/", response_model=list[ZoneResponse])
def list_zones(
    camera_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = db.query(Zone)
    if camera_id:
        query = query.filter(Zone.camera_id == camera_id)
    return query.all()


@router.post("/", response_model=ZoneResponse, status_code=201)
def create_zone(body: ZoneCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    zone = Zone(**body.model_dump(exclude_none=True))
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone


@router.put("/{zone_id}", response_model=ZoneResponse)
def update_zone(zone_id: uuid.UUID, body: ZoneUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(zone, field, value)
    db.commit()
    db.refresh(zone)
    return zone


@router.delete("/{zone_id}", status_code=204)
def delete_zone(zone_id: uuid.UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    db.delete(zone)
    db.commit()
