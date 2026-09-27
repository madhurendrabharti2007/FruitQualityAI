"""Image prediction endpoint."""
import json
import logging
import os
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Cookie, Depends, File, Header, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session
from app.database import Fruit, FruitNotebook, Prediction, SessionLocal, get_db, User
from app.model.predict import predictor, BLURRY_MESSAGE, NOT_RECOGNIZED_MESSAGE
from app.schemas import NotRecognizedResponse, PredictionResponse
from app.routers.auth import decode_token, current_user

router = APIRouter(prefix="/api", tags=["prediction"])
logger = logging.getLogger(__name__)
UPLOADS = Path(__file__).resolve().parents[2] / "uploads"
ALLOWED = {"image/jpeg", "image/png", "image/webp"}
MAX_BYTES = 8 * 1024 * 1024
HARDWARE_DEVICE_KEY = os.getenv("HARDWARE_DEVICE_KEY", "esp32-cam-default-key")

def _info(fruit: str, status: str):
    db = SessionLocal()
    try:
        record = db.get(Fruit, fruit)
        if record is None:
            return {"title": f"{status.title()} {fruit}", "points": [], "disposal_tip": None}
        return {"title": f"{status.title()} {fruit}", "points": json.loads(record.benefits if status == "fresh" else record.harms), "disposal_tip": record.disposal_tip if status == "rotten" else None}
    finally:
        db.close()

def _ripeness(fruit: str, status: str) -> tuple[str, str]:
    stage = "ripe" if status == "fresh" else "spoiled"
    db = SessionLocal()
    try:
        record = db.get(FruitNotebook, fruit)
        if record is None or not record.shelf_life_days:
            return stage, ("2-4 days" if status == "fresh" else "0 days")
        shelf = json.loads(record.shelf_life_days)
        return stage, shelf.get(stage, "2-4 days" if status == "fresh" else "0 days")
    finally:
        db.close()

@router.post("/predict", response_model=PredictionResponse | NotRecognizedResponse)
async def predict(file: UploadFile = File(...), access_token: str | None = Cookie(default=None), authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    from app.routers.auth import _bearer_token
    token = access_token or _bearer_token(authorization)
    user = current_user(token, authorization, db)
    target = None
    try:
        if file.content_type not in ALLOWED:
            raise HTTPException(415, "Please upload a JPG, PNG, or WEBP image.")
        content = await file.read()
        if len(content) > MAX_BYTES:
            raise HTTPException(413, "Images must be smaller than 8 MB.")
        UPLOADS.mkdir(exist_ok=True)
        target = UPLOADS / f"{uuid4().hex}.jpg"
        target.write_bytes(content)
        with Image.open(target) as image:
            image.verify()
        
        logger.info("Starting prediction for file: %s by user: %s", file.filename, user.id)
        fruit, status, confidence, demo, message = predictor.predict(target)
        logger.info("Prediction result - fruit: %s, status: %s, confidence: %.1f, demo: %s, message: %s", 
                   fruit, status, confidence, demo, message)
        
    except (UnidentifiedImageError, OSError) as exc:
        if target:
            target.unlink(missing_ok=True)
        raise HTTPException(400, "That file is not a readable image.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        if target:
            target.unlink(missing_ok=True)
        logger.exception("Prediction failed: exception_type=%s, message=%s", type(exc).__name__, str(exc))
        raise HTTPException(500, "The detector could not process that image. Please try a clear JPG, PNG, or WEBP photo.") from exc
    
    if status == "not_recognized":
        target.unlink(missing_ok=True)
        return {"status": status, "message": message or NOT_RECOGNIZED_MESSAGE}
    
    rounded_confidence = round(confidence, 1)
    ripeness_stage, shelf_life_estimate = _ripeness(fruit, status)
    
    # Always save prediction for authenticated users
    db.add(Prediction(user_id=user.id, fruit=fruit, status=status, confidence=rounded_confidence, ripeness_stage=ripeness_stage, shelf_life_estimate=shelf_life_estimate, image_url=f"/uploads/{target.name}"))
    db.commit()
    
    return {"fruit": fruit, "status": status, "confidence": rounded_confidence, "info": _info(fruit, status), "demo": demo, "ripeness_stage": ripeness_stage, "shelf_life_estimate": shelf_life_estimate}


@router.post("/hardware-predict")
async def hardware_predict(file: UploadFile = File(...), x_device_key: str | None = Header(default=None)):
    """Prediction endpoint for ESP32-CAM hardware devices. Authenticates via X-Device-Key header."""
    if x_device_key != HARDWARE_DEVICE_KEY:
        logger.warning("Hardware predict rejected: invalid device key")
        raise HTTPException(401, "Invalid device key.")
    target = None
    try:
        if file.content_type not in ALLOWED and (file.content_type is None or file.content_type not in ALLOWED):
            raise HTTPException(415, "Please upload a JPG, PNG, or WEBP image.")
        content = await file.read()
        if len(content) > MAX_BYTES:
            raise HTTPException(413, "Images must be smaller than 8 MB.")
        UPLOADS.mkdir(exist_ok=True)
        target = UPLOADS / f"hw-{uuid4().hex}.jpg"
        target.write_bytes(content)
        with Image.open(target) as image:
            image.verify()

        logger.info("Hardware prediction starting for file: %s", file.filename)
        fruit, status, confidence, demo, message = predictor.predict(target)
        logger.info("Hardware prediction result - fruit: %s, status: %s, confidence: %.1f", fruit, status, confidence)

    except (UnidentifiedImageError, OSError) as exc:
        if target:
            target.unlink(missing_ok=True)
        raise HTTPException(400, "Not a readable image.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        if target:
            target.unlink(missing_ok=True)
        logger.exception("Hardware prediction failed: %s", str(exc), exc_info=True)
        raise HTTPException(500, "Prediction failed.") from exc

    if status == "not_recognized":
        target.unlink(missing_ok=True)
        return {"status": status, "message": message or NOT_RECOGNIZED_MESSAGE}

    rounded_confidence = round(confidence, 1)
    ripeness_stage, shelf_life_estimate = _ripeness(fruit, status)
    target.unlink(missing_ok=True)
    return {
        "fruit": fruit,
        "status": status,
        "confidence": rounded_confidence,
        "ripeness_stage": ripeness_stage,
        "shelf_life_estimate": shelf_life_estimate,
        "demo": demo,
    }
