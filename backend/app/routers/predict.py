"""Image prediction endpoint."""
from __future__ import annotations

import json
import hmac
import logging
import os
from pathlib import Path
from threading import Lock
from datetime import datetime, timezone
from typing import Literal, TypedDict
from uuid import uuid4
from starlette.concurrency import run_in_threadpool
from fastapi import APIRouter, Cookie, Depends, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, StrictBool
from sqlalchemy.orm import Session
from app.database import Fruit, FruitNotebook, Prediction, SessionLocal, get_db, User
from app.model.predict import predictor, BLURRY_MESSAGE, NOT_RECOGNIZED_MESSAGE
from app.model.fruit_scope import MIN_CONFIDENCE, FruitScopeUnavailable
from app.routers.image_uploads import save_validated_image
from app.schemas import NotRecognizedResponse, PredictionResponse, TopPrediction
from app.routers.auth import decode_token, current_user

router = APIRouter(prefix="/api", tags=["prediction"])
logger = logging.getLogger(__name__)
UPLOADS = Path(__file__).resolve().parents[2] / "uploads"


class HardwareCommand(TypedDict):
    id: int
    action: Literal["accept", "reject"]
    fruit_name: str
    quality: str
    confidence: float
    created_at: str


class HardwareIRUpdate(BaseModel):
    object_detected: StrictBool


hardware_state_lock = Lock()
last_command: HardwareCommand | None = None
last_ir: dict[str, bool | datetime | None] = {
    "object_detected": False,
    "updated_at": None,
}


def _authenticate_hardware_device(x_device_key: str | None) -> None:
    configured_key = os.environ.get("HARDWARE_DEVICE_KEY", "").strip()
    if not configured_key or configured_key.lower() in {
        "esp32-cam-default-key",
        "your-hardware-device-key",
        "change-me",
        "changeme",
    }:
        raise HTTPException(503, "Hardware device key is not configured.")
    if not x_device_key or not hmac.compare_digest(
        x_device_key.encode("utf-8"), configured_key.encode("utf-8")
    ):
        logger.warning("Hardware request rejected: invalid device key")
        raise HTTPException(401, "Invalid device key.")


def _publish_hardware_command(
    fruit: str | None, quality: str, confidence: float
) -> None:
    global last_command
    with hardware_state_lock:
        command_id = last_command["id"] + 1 if last_command is not None else 1
        last_command = {
            "id": command_id,
            "action": (
                "accept"
                if fruit and quality == "fresh" and confidence >= MIN_CONFIDENCE * 100
                else "reject"
            ),
            "fruit_name": fruit or "",
            "quality": quality if quality in {"fresh", "rotten", "unknown"} else "unknown",
            "confidence": float(confidence),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }


def _record_ir_status(object_detected: bool) -> None:
    with hardware_state_lock:
        last_ir["object_detected"] = object_detected
        last_ir["updated_at"] = datetime.now(timezone.utc)


def _hardware_command_payload() -> dict[str, int | str]:
    with hardware_state_lock:
        if last_command is None:
            return {"id": 0, "action": "none"}
        return {
            "id": last_command["id"],
            "action": last_command["action"],
            "fruit_name": last_command["fruit_name"],
            "quality": last_command["quality"],
        }


def _info(fruit: str, status: str):
    if status == "unknown":
        return {"title": f"{fruit} quality unclear", "points": [], "disposal_tip": None}
    db = SessionLocal()
    try:
        record = db.get(Fruit, fruit)
        if record is None:
            return {"title": f"{status.title()} {fruit}", "points": [], "disposal_tip": None}
        return {
            "title": f"{status.title()} {fruit}",
            "points": json.loads(record.benefits if status == "fresh" else record.harms),
            "disposal_tip": record.disposal_tip if status == "rotten" else None,
        }
    finally:
        db.close()


def _ripeness(fruit: str, status: str) -> tuple[str, str]:
    if status == "unknown":
        return "unknown", "-"
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


def _top_prediction_payload(scores: list[tuple[str, float]]) -> list[TopPrediction]:
    return [TopPrediction(fruit=f, score=float(s)) for f, s in scores[:5] if f]


@router.post("/predict", response_model=PredictionResponse | NotRecognizedResponse)
async def predict(
    file: UploadFile = File(...),
    access_token: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    from app.routers.auth import _bearer_token
    token = access_token or _bearer_token(authorization)
    user = current_user(token, authorization, db)
    target = None
    try:
        target = UPLOADS / f"{uuid4().hex}.jpg"
        await save_validated_image(file, target)

        logger.info("Starting prediction for file: %s by user: %s", file.filename, user.id)
        result = await run_in_threadpool(predictor.predict, target)
        fruit, status, confidence, demo, message, top_scores = result
        logger.info(
            "Prediction result - fruit=%s status=%s confidence=%.1f demo=%s message=%s top=%s",
            fruit, status, confidence, demo, message, top_scores[:3],
        )
    except HTTPException:
        if target:
            target.unlink(missing_ok=True)
        raise
    except FruitScopeUnavailable as exc:
        if target:
            target.unlink(missing_ok=True)
        raise HTTPException(exc.status_code, str(exc)) from exc
    except Exception as exc:
        if target:
            target.unlink(missing_ok=True)
        logger.exception(
            "Prediction failed: exception_type=%s message=%s",
            type(exc).__name__, str(exc),
        )
        raise HTTPException(
            500,
            "The detector could not process that image. Please try a clear JPG, PNG, or WEBP photo.",
        ) from exc

    top_payload = _top_prediction_payload(top_scores or [])
    if status == "not_recognized" or fruit is None:
        target.unlink(missing_ok=True)
        _publish_hardware_command(fruit, status, confidence)
        return {
            "status": "not_recognized",
            "message": message or NOT_RECOGNIZED_MESSAGE,
            "top_predictions": top_payload,
        }

    rounded_confidence = round(confidence, 1)
    ripeness_stage, shelf_life_estimate = _ripeness(fruit, status)

    db.add(Prediction(
        user_id=user.id,
        fruit=fruit,
        status=status,
        confidence=rounded_confidence,
        ripeness_stage=ripeness_stage,
        shelf_life_estimate=shelf_life_estimate,
        image_url=f"/uploads/{target.name}",
    ))
    db.commit()

    response = {
        "fruit": fruit,
        "status": status,
        "confidence": rounded_confidence,
        "info": _info(fruit, status),
        "demo": demo,
        "ripeness_stage": ripeness_stage,
        "shelf_life_estimate": shelf_life_estimate,
        "top_predictions": top_payload,
    }
    _publish_hardware_command(fruit, status, confidence)
    return response


@router.post("/hardware-predict")
async def hardware_predict(
    file: UploadFile = File(...),
    x_device_key: str | None = Header(default=None),
):
    """Prediction endpoint for ESP32-CAM hardware devices. Authenticates via X-Device-Key header."""
    _authenticate_hardware_device(x_device_key)
    target = None
    try:
        target = UPLOADS / f"hw-{uuid4().hex}.jpg"
        await save_validated_image(file, target)

        logger.info("Hardware prediction starting for file: %s", file.filename)
        fruit, status, confidence, demo, message, top_scores = await run_in_threadpool(
            predictor.predict, target
        )
        logger.info(
            "Hardware prediction result - fruit=%s status=%s confidence=%.1f top=%s",
            fruit, status, confidence, top_scores[:3],
        )
    except HTTPException:
        if target:
            target.unlink(missing_ok=True)
        raise
    except FruitScopeUnavailable as exc:
        if target:
            target.unlink(missing_ok=True)
        raise HTTPException(exc.status_code, str(exc)) from exc
    except Exception as exc:
        if target:
            target.unlink(missing_ok=True)
        logger.exception("Hardware prediction failed: %s", str(exc), exc_info=True)
        raise HTTPException(500, "Prediction failed.") from exc

    top_payload = _top_prediction_payload(top_scores or [])
    if status == "not_recognized" or fruit is None:
        target.unlink(missing_ok=True)
        _publish_hardware_command(fruit, status, confidence)
        return {
            "status": "not_recognized",
            "message": message or NOT_RECOGNIZED_MESSAGE,
            "top_predictions": top_payload,
        }

    rounded_confidence = round(confidence, 1)
    ripeness_stage, shelf_life_estimate = _ripeness(fruit, status)
    target.unlink(missing_ok=True)
    response = {
        "fruit": fruit,
        "status": status,
        "confidence": rounded_confidence,
        "ripeness_stage": ripeness_stage,
        "shelf_life_estimate": shelf_life_estimate,
        "demo": demo,
        "top_predictions": top_payload,
    }
    _publish_hardware_command(fruit, status, confidence)
    return response


@router.get("/hardware/command")
def hardware_command(x_device_key: str | None = Header(default=None)):
    _authenticate_hardware_device(x_device_key)
    return _hardware_command_payload()


@router.post("/hardware/ir")
def hardware_ir(payload: HardwareIRUpdate, x_device_key: str | None = Header(default=None)):
    _authenticate_hardware_device(x_device_key)
    _record_ir_status(payload.object_detected)
    return {"status": "ok"}


@router.get("/hardware/ir-status")
def hardware_ir_status(_: User = Depends(current_user)):
    with hardware_state_lock:
        object_detected = bool(last_ir["object_detected"])
        updated_at = last_ir["updated_at"]
    seconds_since_update = (
        round(max(0.0, (datetime.now(timezone.utc) - updated_at).total_seconds()), 3)
        if isinstance(updated_at, datetime)
        else None
    )
    return {
        "object_detected": object_detected,
        "seconds_since_update": seconds_since_update,
    }
