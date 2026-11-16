"""REST API for the web app. No logic here: every handler calls a service function."""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
from typing import Literal
from urllib.parse import quote

import httpx
import yt_dlp
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import asr, config, exports, library, settings_store, worker

router = APIRouter(prefix="/api")
Format = Literal["txt", "srt", "vtt", "json", "csv", "md"]


def _need(value, what: str = "Not found"):
    if value is None or value is False:
        raise HTTPException(404, what)
    return value


# ---------- jobs ----------

class Submit(BaseModel):
    text: str
    force_asr: bool = False


@router.post("/jobs")
async def submit(body: Submit) -> dict:
    return await worker.submit_text(body.text, body.force_asr)


@router.get("/jobs")
def jobs(limit: int = 100) -> list[dict]:
    return library.list_jobs(limit=min(limit, 500))


@router.get("/jobs/{job_id}")
def job(job_id: int) -> dict:
    return _need(library.get_job(job_id))


@router.post("/jobs/{job_id}/retry")
def retry(job_id: int) -> dict:
    current = _need(library.get_job(job_id))
    if current["status"] != "failed":
        raise HTTPException(409, "Only failed jobs can be retried")
    worker.requeue(job_id)
    return library.get_job(job_id)


@router.delete("/jobs/finished")
def clear_finished() -> dict:
    return {"deleted": library.clear_finished_jobs()}


@router.get("/batches/{batch_id}")
def batch(batch_id: str) -> dict:
    return _need(library.batch_summary(batch_id))


# ---------- library ----------

@router.get("/library")
def list_library(q: str | None = None, platform: str | None = None, folder_id: int | None = None,
                 tag: str | None = None, source: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    return library.list_library(q=q, platform=platform, folder_id=folder_id, tag=tag, source=source,
                                limit=limit, offset=offset)


@router.get("/transcripts/{transcript_id}")
def transcript(transcript_id: int) -> dict:
    return _need(library.get_transcript(transcript_id))


class Segment(BaseModel):
    start: float
    end: float
    text: str


class Patch(BaseModel):
    segments: list[Segment] | None = None
    restore_original: bool = False
    folder_id: int | None = None
    clear_folder: bool = False
    tags: list[str] | None = None


@router.patch("/transcripts/{transcript_id}")
def patch(transcript_id: int, body: Patch) -> dict:
    _need(library.get_transcript(transcript_id))
    if body.restore_original:
        library.update_segments(transcript_id, None)
    elif body.segments is not None:
        library.update_segments(transcript_id, [s.model_dump() for s in body.segments])
    if body.folder_id is not None or body.clear_folder or body.tags is not None:
        library.organize(transcript_id, folder_id=body.folder_id, tags=body.tags, clear_folder=body.clear_folder)
    return library.get_transcript(transcript_id)


@router.delete("/transcripts/{transcript_id}")
def delete(transcript_id: int) -> dict:
    return {"deleted": library.delete_transcripts([transcript_id])}


@router.post("/transcripts/{transcript_id}/retranscribe")
def retranscribe(transcript_id: int) -> dict:
    item = _need(library.get_transcript(transcript_id))
    batch_id, ids = worker.enqueue([item["url"]], force_asr=True)
    return {"batch_id": batch_id, "job_id": ids[0]}


def _download(content: str | bytes, name: str, media: str) -> Response:
    ascii_name = name.encode("ascii", "ignore").decode() or "export"
    disposition = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}"
    return Response(content, media_type=media, headers={"Content-Disposition": disposition})


@router.get("/transcripts/{transcript_id}/export")
def export(transcript_id: int, format: Format = "txt", timestamps: bool = False, download: bool = True) -> Response:
    item = _need(library.get_transcript(transcript_id))
    body = exports.render(item, format, timestamps)
    if not download:
        return Response(body, media_type="text/plain; charset=utf-8")
    return _download(body, exports.filename(item, format), exports.FORMATS[format] + "; charset=utf-8")


class Bulk(BaseModel):
    ids: list[int]
    format: Format = "txt"
    timestamps: bool = False


@router.post("/export/zip")
def export_zip(body: Bulk) -> Response:
    items = [it for it in (library.get_transcript(i) for i in body.ids) if it]
    if not items:
        raise HTTPException(404, "No transcripts selected")
    return _download(exports.to_zip(items, body.format, body.timestamps), f"transcripts-{len(items)}.zip", "application/zip")


@router.post("/library/delete")
def bulk_delete(body: Bulk) -> dict:
    return {"deleted": library.delete_transcripts(body.ids)}


class Name(BaseModel):
    name: str


@router.get("/folders")
def folders() -> list[dict]:
    return library.list_folders()


@router.post("/folders")
def create_folder(body: Name) -> dict:
    if not body.name.strip():
        raise HTTPException(422, "Folder name is empty")
    return library.create_folder(body.name)


@router.delete("/folders/{folder_id}")
def delete_folder(folder_id: int) -> dict:
    library.delete_folder(folder_id)
    return {"ok": True}


@router.get("/tags")
def tags() -> list[dict]:
    return library.list_tags()


@router.get("/thumbs/{name}")
def thumb(name: str) -> FileResponse:
    path = (config.THUMBS_DIR / name).resolve()
    if path.parent != config.THUMBS_DIR.resolve() or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=604800"})


# ---------- settings ----------

async def _tunnel_url() -> str | None:
    if not config.TUNNEL_METRICS_URL:
        return None
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            host = (await client.get(f"{config.TUNNEL_METRICS_URL}/quicktunnel")).json().get("hostname")
    except Exception:
        return None
    return f"https://{host}/mcp/{config.mcp_secret()}" if host else None


@router.get("/settings/status")
async def status() -> dict:
    return {
        "asr": _asr_view(),
        "ytdlp_version": yt_dlp.version.__version__,
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "js_runtime": bool(shutil.which("deno")),
        "cookies": config.COOKIES_PATH.exists(),
        "mcp": {"local_url": f"http://localhost:{config.PORT}/mcp", "tunnel_url": await _tunnel_url()},
        "library_count": library.list_library(limit=1)["total"],
        "in_docker": config.IN_DOCKER,
    }


def _asr_view() -> dict:
    cfg = settings_store.asr()
    return {"configured": bool(cfg["api_key"]), "base_url": cfg["base_url"], "model": cfg["model"],
            "provider": settings_store.provider_of(cfg["base_url"]), "source": cfg["source"],
            "key_hint": settings_store.masked(cfg["api_key"]),
            "providers": settings_store.PROVIDERS}


class AsrSettings(BaseModel):
    provider: str
    api_key: str
    base_url: str | None = None
    model: str | None = None


@router.put("/settings/asr")
async def save_asr(body: AsrSettings) -> dict:
    try:
        settings_store.save_asr(body.provider, body.api_key, body.base_url, body.model)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    result = await asyncio.to_thread(asr.self_test)
    return {**_asr_view(), "test": result}


@router.delete("/settings/asr")
def clear_asr() -> dict:
    settings_store.clear_asr()
    return _asr_view()


@router.post("/settings/asr-test")
async def asr_test() -> dict:
    return await asyncio.to_thread(asr.self_test)


@router.post("/settings/ytdlp-update")
async def ytdlp_update() -> dict:
    """Upgrade yt-dlp in place. In Docker the api then restarts itself to load the new version."""
    uv = shutil.which("uv")
    cmd = [uv, "pip", "install", "--python", sys.executable, "-U", "yt-dlp"] if uv else \
          [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"]
    done = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True, timeout=300)
    if done.returncode != 0:
        return {"ok": False, "message": (done.stderr or done.stdout)[-400:]}
    version = await asyncio.to_thread(
        subprocess.run, [sys.executable, "-c", "import yt_dlp;print(yt_dlp.version.__version__)"],
        capture_output=True, text=True)
    new = version.stdout.strip()
    changed = new != yt_dlp.version.__version__
    if changed and config.IN_DOCKER:
        asyncio.get_running_loop().call_later(1.0, os._exit, 0)  # compose restarts the container
    message = ("Already up to date." if not changed else
               f"Updated to {new}. Restarting…" if config.IN_DOCKER else f"Updated to {new}. Restart the api to load it.")
    return {"ok": True, "version": new, "changed": changed, "message": message}


@router.get("/health")
def health() -> dict:
    return {"ok": True}
