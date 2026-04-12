"""Camera CRUD endpoints."""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.camera import Camera
from schemas.camera import CameraCreate, CameraUpdate, CameraResponse
from services.auth import get_current_user

router = APIRouter(prefix="/cameras", tags=["cameras"])


@router.get("/", response_model=list[CameraResponse])
def list_cameras(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(Camera).order_by(Camera.name).all()


@router.get("/{camera_id}", response_model=CameraResponse)
def get_camera(camera_id: uuid.UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


@router.post("/", response_model=CameraResponse, status_code=201)
def create_camera(body: CameraCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    camera = Camera(**body.model_dump(exclude_none=True))
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


@router.put("/{camera_id}", response_model=CameraResponse)
def update_camera(camera_id: uuid.UUID, body: CameraUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(camera, field, value)

    db.commit()
    db.refresh(camera)
    return camera


@router.delete("/{camera_id}", status_code=204)
def delete_camera(camera_id: uuid.UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    db.delete(camera)
    db.commit()
