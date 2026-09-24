"""Fruit gallery and token-protected admin CRUD."""
import json
import os
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.database import Fruit, get_db
from app.schemas import FruitCreate, FruitResponse

router = APIRouter(prefix="/api/fruits", tags=["fruits"])
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "fruit-admin")

def serialize(item: Fruit) -> FruitResponse:
    return FruitResponse(name=item.name, benefits=json.loads(item.benefits), harms=json.loads(item.harms), disposal_tip=item.disposal_tip, sample_image=item.sample_image)

def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(401, "A valid admin token is required.")

@router.get("", response_model=list[FruitResponse])
def list_fruits(db: Session = Depends(get_db)):
    return [serialize(item) for item in db.query(Fruit).order_by(Fruit.name).all()]

@router.post("", response_model=FruitResponse, dependencies=[Depends(require_admin)])
def create_fruit(payload: FruitCreate, db: Session = Depends(get_db)):
    if db.get(Fruit, payload.name):
        raise HTTPException(409, "That fruit already exists.")
    item = Fruit(name=payload.name, benefits=json.dumps(payload.benefits), harms=json.dumps(payload.harms), disposal_tip=payload.disposal_tip, sample_image=payload.sample_image)
    db.add(item); db.commit(); db.refresh(item)
    return serialize(item)

@router.put("/{name}", response_model=FruitResponse, dependencies=[Depends(require_admin)])
def update_fruit(name: str, payload: FruitCreate, db: Session = Depends(get_db)):
    item = db.get(Fruit, name)
    if item is None:
        raise HTTPException(404, "Fruit not found.")
    item.name = payload.name; item.benefits = json.dumps(payload.benefits); item.harms = json.dumps(payload.harms); item.disposal_tip = payload.disposal_tip; item.sample_image = payload.sample_image
    db.commit(); db.refresh(item)
    return serialize(item)

@router.delete("/{name}", dependencies=[Depends(require_admin)])
def delete_fruit(name: str, db: Session = Depends(get_db)):
    item = db.get(Fruit, name)
    if item is None:
        raise HTTPException(404, "Fruit not found.")
    db.delete(item); db.commit()
    return {"deleted": name}
