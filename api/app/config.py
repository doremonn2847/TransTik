"""Runtime settings, read from environment variables once at import."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data")).resolve()
DB_PATH = DATA_DIR / "app.db"
THUMBS_DIR = DATA_DIR / "thumbs"
COOKIES_PATH = DATA_DIR / "cookies.txt"

ASR_BASE_URL = os.environ.get("ASR_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
ASR_API_KEY = os.environ.get("ASR_API_KEY", "").strip()
ASR_MODEL = os.environ.get("ASR_MODEL", "whisper-large-v3-turbo")

PORT = int(os.environ.get("PORT", "8765"))
PUBLIC_PORT = int(os.environ.get("PUBLIC_PORT", "8766"))  # tunnel-facing, MCP only
HOST = os.environ.get("HOST", "127.0.0.1")

WORKER_CONCURRENCY = int(os.environ.get("WORKER_CONCURRENCY", "2"))
MAX_DURATION_S = int(os.environ.get("MAX_DURATION_S", "1800"))
COLLECTION_LIMIT = int(os.environ.get("COLLECTION_LIMIT", "50"))
TUNNEL_METRICS_URL = os.environ.get("TUNNEL_METRICS_URL", "")
IN_DOCKER = os.environ.get("IN_DOCKER", "") == "1"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)


def mcp_secret() -> str:
    """Secret path segment that guards the tunnel-facing MCP endpoint."""
    if env := os.environ.get("MCP_SECRET", "").strip():
        return env
    ensure_dirs()
    path = DATA_DIR / "mcp_secret.txt"
    if path.exists() and (value := path.read_text().strip()):
        return value
    value = secrets.token_urlsafe(32)
    path.write_text(value)
    return value
