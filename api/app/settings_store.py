"""Settings saved from the web app (data/settings.json). Values saved here win over .env.

Only the speech-to-text provider lives here, so a non-technical user can paste an API key
on the Settings page instead of editing a hidden file. The key never leaves the server:
the API only ever returns a masked form.
"""
from __future__ import annotations

import json
import os
import threading

from . import config

PROVIDERS = {
    "openai": {"label": "OpenAI", "base_url": "https://api.openai.com/v1", "model": "whisper-1"},
    "groq": {"label": "Groq", "base_url": "https://api.groq.com/openai/v1", "model": "whisper-large-v3-turbo"},
}

_lock = threading.Lock()


def _path():
    return config.DATA_DIR / "settings.json"


def _load() -> dict:
    try:
        return json.loads(_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def asr() -> dict:
    """The speech-to-text settings in effect: {base_url, api_key, model, source}."""
    saved = _load().get("asr") or {}
    if saved.get("api_key"):
        return {"base_url": saved["base_url"].rstrip("/"), "api_key": saved["api_key"],
                "model": saved["model"], "source": "settings"}
    return {"base_url": config.ASR_BASE_URL, "api_key": config.ASR_API_KEY, "model": config.ASR_MODEL,
            "source": "env" if config.ASR_API_KEY else "none"}


def provider_of(base_url: str) -> str:
    return next((k for k, p in PROVIDERS.items() if p["base_url"] == base_url.rstrip("/")), "custom")


def save_asr(provider: str, api_key: str, base_url: str | None = None, model: str | None = None) -> None:
    if provider in PROVIDERS:
        base_url = base_url or PROVIDERS[provider]["base_url"]
        model = model or PROVIDERS[provider]["model"]
    if not (base_url and model and api_key.strip()):
        raise ValueError("Provider address, model and API key are all required.")
    with _lock:
        data = _load()
        data["asr"] = {"base_url": base_url.strip().rstrip("/"), "model": model.strip(), "api_key": api_key.strip()}
        _write(data)


def clear_asr() -> None:
    with _lock:
        data = _load()
        data.pop("asr", None)
        _write(data)


def _write(data: dict) -> None:
    config.ensure_dirs()
    tmp = _path().with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)  # readable only by the app's user
    except OSError:
        pass
    tmp.replace(_path())


def masked(key: str) -> str | None:
    if not key:
        return None
    return f"{key[:3]}…{key[-4:]}" if len(key) > 10 else "…"
