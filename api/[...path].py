"""Vercel catch-all serverless function wrapper for the Ripewise FastAPI backend.

This file (with the [...path] filesystem route token) handles EVERY request
under /api/* — /api/health, /api/auth/login, /api/predict, etc. — so the
FastAPI application (not Vercel's filesystem router) decides which handler
to invoke based on the incoming URL path.

See api/index.py for the actual implementation and docstring; this file is
intentionally a thin re-export so both the index entry-point and the
catch-all wildcard stay in sync and use the exact same Mangum adapter.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SQLITE_DB_DIR", "/tmp")
os.environ.setdefault("UPLOAD_DIR", "/tmp/uploads")

try:
    from mangum import Mangum
except Exception:
    raise RuntimeError(
        "The 'mangum' package is required to run FastAPI on Vercel. "
        "Add it to requirements.txt and redeploy."
    )

from app.main import app as fastapi_app

handler = Mangum(fastapi_app, lifespan="on", api_gateway_base_path="/")
