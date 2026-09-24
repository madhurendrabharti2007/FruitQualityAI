"""Vendor batch scanning and export endpoints."""
import csv
import io
import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Cookie, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session
from app.authz import require_role
from app.database import BatchScan, BatchScanItem, Fruit, FruitNotebook, SessionLocal, User, get_db
from app.model.predict import predictor
from app.routers.auth import current_user
from app.routers.predict import _info
from app.schemas import BatchResponse

router = APIRouter(prefix="/api", tags=["batch"])
UPLOADS = Path(__file__).resolve().parents[2] / "uploads"
ALLOWED = {"image/jpeg", "image/png", "image/webp"}
MAX_FILES = 50
MAX_BYTES = 8 * 1024 * 1024


def _shelf(fruit: str | None, status: str) -> tuple[str, str]:
    stage = "not_recognized" if status == "not_recognized" else ("ripe" if status == "fresh" else "spoiled")
    if not fruit:
        return stage, "-"
    db = SessionLocal()
    notebook = db.get(FruitNotebook, fruit)
    db.close()
    shelf = json.loads(notebook.shelf_life_days) if notebook and notebook.shelf_life_days else {"ripe": "2-4 days", "spoiled": "0 days"}
    return stage, shelf.get(stage, "2-4 days")


def _serialize(batch: BatchScan, items: list[BatchScanItem]) -> dict:
    fresh = batch.fresh_count / batch.total * 100 if batch.total else 0
    rotten = batch.rotten_count / batch.total * 100 if batch.total else 0
    return {"batch_id": batch.batch_id, "created_at": batch.created_at.isoformat(), "total": batch.total, "fresh_count": batch.fresh_count, "rotten_count": batch.rotten_count, "not_recognized_count": batch.not_recognized_count, "fresh_percentage": round(fresh, 1), "rotten_percentage": round(rotten, 1), "items": [{"filename": item.filename, "fruit": item.fruit, "status": item.status, "confidence": item.confidence, "ripeness_stage": item.ripeness_stage, "shelf_life_estimate": item.shelf_life_estimate, "image_url": item.image_url} for item in items]}


@router.post("/batch-predict", response_model=BatchResponse)
async def batch_predict(files: list[UploadFile] = File(...), user: User = Depends(require_role("vendor")), db: Session = Depends(get_db)):
    if not files or len(files) > MAX_FILES:
        raise HTTPException(400, f"Upload between 1 and {MAX_FILES} images.")
    batch_id = str(uuid4())
    stored: list[BatchScanItem] = []
    for file in files:
        if file.content_type not in ALLOWED:
            raise HTTPException(415, f"{file.filename or 'A file'} is not a JPG, PNG, or WEBP image.")
        content = await file.read()
        if len(content) > MAX_BYTES:
            raise HTTPException(413, f"{file.filename or 'A file'} is larger than 8 MB.")
        target = UPLOADS / f"batch-{batch_id}-{uuid4().hex}.jpg"
        try:
            UPLOADS.mkdir(exist_ok=True)
            target.write_bytes(content)
            with Image.open(target) as image:
                image.verify()
            fruit, status, confidence, _demo, _message = predictor.predict(target)
        except (UnidentifiedImageError, OSError) as exc:
            target.unlink(missing_ok=True)
            raise HTTPException(400, f"{file.filename or 'A file'} is not a readable image.") from exc
        stage, shelf = _shelf(fruit, status)
        item = BatchScanItem(batch_id=batch_id, filename=file.filename or target.name, fruit=fruit, status=status, confidence=round(confidence, 1), ripeness_stage=stage, shelf_life_estimate=shelf, image_url=f"/uploads/{target.name}" if status != "not_recognized" else None)
        stored.append(item)
        if status == "not_recognized":
            target.unlink(missing_ok=True)
    batch = BatchScan(batch_id=batch_id, user_id=user.id, total=len(stored), fresh_count=sum(item.status == "fresh" for item in stored), rotten_count=sum(item.status == "rotten" for item in stored), not_recognized_count=sum(item.status == "not_recognized" for item in stored))
    db.add(batch); db.add_all(stored); db.commit(); db.refresh(batch)
    return _serialize(batch, stored)


@router.get("/reports", response_model=list[BatchResponse])
def reports(user: User = Depends(require_role("vendor")), db: Session = Depends(get_db)):
    batches = db.query(BatchScan).filter(BatchScan.user_id == user.id).order_by(BatchScan.created_at.desc()).all()
    return [_serialize(batch, db.query(BatchScanItem).filter(BatchScanItem.batch_id == batch.batch_id).all()) for batch in batches]


@router.get("/reports/{batch_id}", response_model=BatchResponse)
def report(batch_id: str, user: User = Depends(require_role("vendor")), db: Session = Depends(get_db)):
    batch = db.query(BatchScan).filter(BatchScan.batch_id == batch_id, BatchScan.user_id == user.id).first()
    if not batch:
        raise HTTPException(404, "Batch report not found.")
    return _serialize(batch, db.query(BatchScanItem).filter(BatchScanItem.batch_id == batch_id).all())


def _owned_report(batch_id: str, user: User, db: Session):
    batch = db.query(BatchScan).filter(BatchScan.batch_id == batch_id, BatchScan.user_id == user.id).first()
    if not batch:
        raise HTTPException(404, "Batch report not found.")
    return batch, db.query(BatchScanItem).filter(BatchScanItem.batch_id == batch_id).all()


@router.get("/reports/{batch_id}/csv")
def export_csv(batch_id: str, user: User = Depends(require_role("vendor")), db: Session = Depends(get_db)):
    batch, items = _owned_report(batch_id, user, db)
    output = io.StringIO(); writer = csv.writer(output); writer.writerow(["batch_id", "date", "filename", "fruit", "status", "ripeness_stage", "confidence", "shelf_life_estimate"])
    for item in items: writer.writerow([batch.batch_id, batch.created_at.isoformat(), item.filename, item.fruit or "", item.status, item.ripeness_stage, item.confidence, item.shelf_life_estimate])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={batch_id}.csv"})


@router.get("/reports/{batch_id}/pdf")
def export_pdf(batch_id: str, user: User = Depends(require_role("vendor")), db: Session = Depends(get_db)):
    batch, items = _owned_report(batch_id, user, db)
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise HTTPException(503, "PDF export is not installed on the server.") from exc
    output = io.BytesIO(); pdf = canvas.Canvas(output, pagesize=letter); pdf.setTitle(f"Ripewise report {batch_id}")
    pdf.drawString(42, 750, "Ripewise Batch Report"); pdf.drawString(42, 730, f"Batch: {batch_id}"); pdf.drawString(42, 712, f"Vendor: {user.name} | {batch.created_at:%Y-%m-%d %H:%M}"); pdf.drawString(42, 694, f"Total: {batch.total} | Fresh: {batch.fresh_count} | Rotten: {batch.rotten_count} | Not recognized: {batch.not_recognized_count}")
    y = 660
    for item in items[:30]:
        pdf.drawString(42, y, f"{item.filename[:28]} | {item.fruit or 'Not recognized'} | {item.status} | {item.confidence:.1f}% | {item.shelf_life_estimate}"); y -= 16
        if y < 45: pdf.showPage(); y = 750
    pdf.save(); output.seek(0)
    return StreamingResponse(output, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={batch_id}.pdf"})
