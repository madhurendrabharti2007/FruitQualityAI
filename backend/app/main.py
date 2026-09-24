"""Fruit Freshness Detector API."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.database import init_db
from app.routers import admin, auth, batch, chat, fruits, notebook, predict
from app.seed_data import seed

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ripewise")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Ripewise API - initializing database and seed data")
    init_db()
    seed()
    logger.info("Ripewise API startup complete")
    yield

app = FastAPI(title="Ripewise API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://127.0.0.1:5175", "http://127.0.0.1:5176"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(predict.router)
app.include_router(fruits.router)
app.include_router(auth.router)
app.include_router(notebook.router)
app.include_router(chat.router)
app.include_router(batch.router)
app.include_router(admin.router)
app.mount("/uploads", StaticFiles(directory="uploads", check_dir=False), name="uploads")

@app.get("/api/health")
def health():
    return {"status": "ok"}
