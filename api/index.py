"""Vercel Serverless Function wrapper for the Ripewise FastAPI backend.

Exposed at `/api/*` on a Vercel deployment, this uses Mangum to adapt the
FastAPI ASGI application to the AWS Lambda-style event/context interface
that Vercel Python serverless functions expect.

Environment variables:
  DATABASE_URL / SQLITE_DB_PATH / SQLITE_DB_DIR  – where to put the SQLite file
      (defaults to /tmp/fruit_quality.db in serverless environments so writes
      succeed for the function's ephemeral filesystem lifetime).
  CORS_ALLOW_ORIGINS  – comma-separated list of allowed origins for CORS.
  CORS_ALLOW_ALL  – set to "true" to permit every origin (disables credentials).
  JWT_SECRET  – signing secret for HttpOnly access tokens.
  GEMINI_API_KEY  – optional, used by the notebook-grounded assistant.
  ADMIN_TOKEN  – header token required for direct admin CRUD on /fruits.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure the `backend/` source folder is importable regardless of where
# Vercel actually runs this file from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Make writes land in /tmp so the serverless read-only filesystem constraint
# doesn't break SQLite / uploads.  In production you should use a managed
# Postgres + object storage instead of the ephemeral /tmp directory.
os.environ.setdefault("SQLITE_DB_DIR", "/tmp")
os.environ.setdefault("UPLOAD_DIR", "/tmp/uploads")

try:
    from mangum import Mangum
except Exception:  # pragma: no cover - Mangum is a runtime dependency on Vercel
    raise RuntimeError(
        "The 'mangum' package is required to run FastAPI on Vercel. "
        "Add it to requirements.txt and redeploy."
    )

from app.main import app as fastapi_app

handler = Mangum(fastapi_app, lifespan="on", api_gateway_base_path="/")
