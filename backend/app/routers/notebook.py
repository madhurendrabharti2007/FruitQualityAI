"""Fruit knowledge notebook endpoints."""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import Fruit, FruitNotebook, get_db

router = APIRouter(prefix="/api/notebook", tags=["notebook"])
DISCLAIMER = "This information is for general educational purposes and is not medical advice. Nutrition values are approximate for 100 g raw edible portion; actual values vary by cultivar, ripeness, and preparation."


def _json(value: str) -> list | dict:
    return json.loads(value or "[]")


def serialize(item: FruitNotebook, fruit: Fruit) -> dict:
    return {
        "fruit_id": fruit.name,
        "name": fruit.name,
        "highlight": item.highlight,
        "sample_image": fruit.sample_image,
        "benefits": _json(item.benefits),
        "good_combinations": _json(item.good_combinations),
        "bad_combinations": _json(item.bad_combinations),
        "overconsumption_risk": item.overconsumption_risk,
        "rotten_fruit_harms": _json(item.rotten_fruit_harms),
        "safe_disposal_tip": item.safe_disposal_tip,
        "storage_tip": item.storage_tip,
        "shelf_life_days": _json(item.shelf_life_days),
        "nutrition_facts": _json(item.nutrition_facts) or {},
        "disclaimer": DISCLAIMER,
    }


@router.get("")
def list_notebook(db: Session = Depends(get_db)):
    entries = db.query(FruitNotebook, Fruit).join(Fruit, Fruit.name == FruitNotebook.fruit_name).order_by(Fruit.name).all()
    return [{"fruit_id": fruit.name, "name": fruit.name, "highlight": notebook.highlight, "sample_image": fruit.sample_image, "disclaimer": DISCLAIMER} for notebook, fruit in entries]


@router.get("/{fruit_id}")
def get_notebook_entry(fruit_id: str, db: Session = Depends(get_db)):
    fruit = db.get(Fruit, fruit_id)
    entry = db.get(FruitNotebook, fruit_id)
    if fruit is None or entry is None:
        raise HTTPException(404, "Notebook entry not found.")
    return serialize(entry, fruit)
