"""Backend configuration loading."""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_backend_env() -> None:
    load_dotenv(BACKEND_ENV_PATH)


load_backend_env()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip() or "gemini-3.6-flash"
