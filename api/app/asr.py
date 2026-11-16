"""Speech-to-text through any OpenAI-compatible /audio/transcriptions endpoint."""
from __future__ import annotations

from pathlib import Path

import httpx

from . import config
from .errors import KnownFailure


def configured() -> bool:
    return bool(config.ASR_API_KEY)


def transcribe(audio: Path, prompt: str | None = None, language: str | None = None) -> tuple[list[dict], str | None]:
    """Return (segments, detected_language)."""
    if not configured():
        raise KnownFailure("ASR_NOT_CONFIGURED")
    data = {"model": config.ASR_MODEL, "response_format": "verbose_json",
            "timestamp_granularities[]": "segment", "temperature": "0"}
    if prompt:
        data["prompt"] = prompt[:400]  # biases spelling of names and slang
    if language:
        data["language"] = language
    try:
        with audio.open("rb") as handle, httpx.Client(timeout=300) as client:
            resp = client.post(f"{config.ASR_BASE_URL}/audio/transcriptions",
                               headers={"Authorization": f"Bearer {config.ASR_API_KEY}"},
                               data=data, files={"file": (audio.name, handle, "audio/ogg")})
    except httpx.HTTPError as exc:
        raise KnownFailure("ASR_FAILED", str(exc)[:200]) from exc
    if resp.status_code == 429:
        raise KnownFailure("RATE_LIMITED", "speech-to-text provider rate limit")
    if resp.status_code >= 400:
        raise KnownFailure("ASR_FAILED", f"HTTP {resp.status_code}: {resp.text[:200]}")
    body = resp.json()
    segments = [{"start": s.get("start", 0), "end": s.get("end", 0), "text": s.get("text", "")}
                for s in body.get("segments") or []]
    if not segments and (text := (body.get("text") or "").strip()):
        segments = [{"start": 0, "end": float(body.get("duration") or 0), "text": text}]
    return segments, body.get("language")


def self_test() -> dict:
    """Cheap credential check: list models on the provider."""
    if not configured():
        return {"ok": False, "message": "ASR_API_KEY is not set."}
    try:
        resp = httpx.get(f"{config.ASR_BASE_URL}/models",
                         headers={"Authorization": f"Bearer {config.ASR_API_KEY}"}, timeout=15)
    except httpx.HTTPError as exc:
        return {"ok": False, "message": f"Could not reach provider: {exc}"}
    if resp.status_code == 401:
        return {"ok": False, "message": "The provider rejected the API key."}
    if resp.status_code >= 400:
        return {"ok": False, "message": f"Provider returned HTTP {resp.status_code}."}
    ids = [m.get("id") for m in resp.json().get("data", [])]
    if ids and config.ASR_MODEL not in ids:
        return {"ok": False, "message": f"Key works, but model '{config.ASR_MODEL}' is not offered by this provider."}
    return {"ok": True, "message": f"Key accepted; model '{config.ASR_MODEL}' is available."}
