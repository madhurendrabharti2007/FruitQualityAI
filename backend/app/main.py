"""Fruit Freshness Detector API."""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.database import init_db
from app.routers import admin, auth, batch, chat, fruits, notebook, predict
from app.seed_data import seed

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ripewise")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Ripewise API - initializing database and seed data")
    init_db()
    seed()
    logger.info("Ripewise API startup complete")
    yield

def _parse_origins() -> list[str]:
    raw = os.environ.get("ALLOWED_ORIGINS") or os.environ.get("CORS_ALLOW_ORIGINS")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:5176",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
    "http://127.0.0.1:5176",
    "https://fruit-quality-ai-n41u.vercel.app",
]

def _allow_all_origins() -> bool:
    return (os.environ.get("CORS_ALLOW_ALL", "").lower() in {"1", "true", "yes", "on"})

app = FastAPI(title="Ripewise API", version="1.0.0", lifespan=lifespan)

if _allow_all_origins():
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
else:
    app.add_middleware(CORSMiddleware, allow_origins=_parse_origins(), allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(predict.router)
app.include_router(fruits.router)
app.include_router(auth.router)
app.include_router(notebook.router)
app.include_router(chat.router)
app.include_router(batch.router)
app.include_router(admin.router)

def _upload_dir() -> str:
    p = os.environ.get("UPLOAD_DIR") or os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    try:
        os.makedirs(p, exist_ok=True)
    except Exception:
        p = "/tmp/uploads"
        os.makedirs(p, exist_ok=True)
    return p

app.mount("/uploads", StaticFiles(directory=_upload_dir(), check_dir=False), name="uploads")

@app.get("/api/health")
def health():
    return {"status": "ok"}
