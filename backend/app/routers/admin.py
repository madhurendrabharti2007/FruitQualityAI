"""Admin analytics endpoints."""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.authz import require_role
from app.database import BatchScan, BatchScanItem, Prediction, User, get_db

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/analytics")
def analytics(user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    prediction_total = db.query(func.count(Prediction.id)).scalar() or 0
    batch_total = db.query(func.coalesce(func.sum(BatchScan.total), 0)).scalar() or 0
    fresh = (db.query(func.count(Prediction.id)).filter(Prediction.status == "fresh").scalar() or 0) + (db.query(func.coalesce(func.sum(BatchScan.fresh_count), 0)).scalar() or 0)
    rotten = (db.query(func.count(Prediction.id)).filter(Prediction.status == "rotten").scalar() or 0) + (db.query(func.coalesce(func.sum(BatchScan.rotten_count), 0)).scalar() or 0)
    since = datetime.utcnow() - timedelta(days=30)
    volume = {day: 0 for day in [(since + timedelta(days=index)).date().isoformat() for index in range(31)]}
    for created_at, count in db.query(func.date(Prediction.created_at), func.count(Prediction.id)).filter(Prediction.created_at >= since).group_by(func.date(Prediction.created_at)).all(): volume[str(created_at)] = volume.get(str(created_at), 0) + count
    for created_at, count in db.query(func.date(BatchScan.created_at), func.sum(BatchScan.total)).filter(BatchScan.created_at >= since).group_by(func.date(BatchScan.created_at)).all(): volume[str(created_at)] = volume.get(str(created_at), 0) + int(count or 0)
    spoilage = {}
    for fruit, status in db.query(Prediction.fruit, Prediction.status).all():
        bucket = spoilage.setdefault(fruit, {"total": 0, "rotten": 0}); bucket["total"] += 1; bucket["rotten"] += status == "rotten"
    for fruit, status in db.query(BatchScanItem.fruit, BatchScanItem.status).filter(BatchScanItem.fruit.isnot(None)).all():
        bucket = spoilage.setdefault(fruit, {"total": 0, "rotten": 0}); bucket["total"] += 1; bucket["rotten"] += status == "rotten"
    spoilage = [{"fruit": fruit, "total": values["total"], "rotten": values["rotten"], "rate": round(values["rotten"] / values["total"] * 100, 1)} for fruit, values in spoilage.items()]
    users = []
    for account in db.query(User).order_by(User.created_at.desc()).all(): users.append({"id": account.id, "name": account.name, "email": account.email, "role": account.role, "scan_count": db.query(func.count(Prediction.id)).filter(Prediction.user_id == account.id).scalar() or 0})
    return {"total_scans": prediction_total + batch_total, "fresh_count": fresh, "rotten_count": rotten, "volume_over_time": [{"date": date, "count": count} for date, count in volume.items()], "spoilage_by_fruit": spoilage, "users": users}
