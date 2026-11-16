"""One job, start to finish: captions first, speech-to-text as the fallback. Blocking code."""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import httpx

from . import asr, captions, config, library, settings_store, urls
from .acquire import VideoMeta, acquirer, pick_caption_track
from .errors import KnownFailure

log = logging.getLogger("pipeline")


def _save_thumbnail(meta: VideoMeta, platform: str, video_id: str) -> str | None:
    """Keep a local copy: TikTok and Instagram thumbnail links expire within hours."""
    if not meta.thumbnail:
        return None
    name = f"{platform}_{video_id}.jpg"
    try:
        resp = httpx.get(meta.thumbnail, timeout=15, follow_redirects=True)
        if resp.status_code == 200 and resp.content:
            (config.THUMBS_DIR / name).write_bytes(resp.content)
            return name
    except httpx.HTTPError:
        pass
    return None


def _from_captions(meta: VideoMeta) -> tuple[list[dict], str | None] | None:
    track = pick_caption_track(meta)
    if not track:
        return None
    try:
        segs = captions.normalize(captions.parse_caption(track["ext"], acquirer.fetch_caption(track)))
    except Exception as exc:  # a broken caption track should fall through to ASR, not fail the job
        log.warning("caption fetch failed, falling back to ASR: %s", exc)
        return None
    return (segs, track["lang"]) if captions.has_speech(segs) else None


def _from_asr(job_id: int, url: str, meta: VideoMeta) -> tuple[list[dict], str | None]:
    if not asr.configured():
        raise KnownFailure("ASR_NOT_CONFIGURED")
    if meta.duration and meta.duration > config.MAX_DURATION_S:
        raise KnownFailure("TOO_LONG", f"{meta.duration}s")
    library.set_job(job_id, "transcribing")
    with tempfile.TemporaryDirectory(prefix="transtik_") as tmp:  # audio is deleted as soon as this block ends
        audio = acquirer.audio(url, Path(tmp))
        segs, lang = asr.transcribe(audio, prompt=meta.title)
    segs = captions.drop_repeats(captions.normalize(segs))
    if not captions.has_speech(segs):
        raise KnownFailure("NO_SPEECH")
    return segs, lang


def run_job(job_id: int) -> int:
    """Process one job and return the transcript id. Raises KnownFailure on a classified error."""
    job = library.get_job(job_id)
    if job is None:
        raise KnownFailure("FAILED", "job vanished")
    url, force_asr = job["input_url"], job["force_asr"]

    library.set_job(job_id, "resolving")
    ident = urls.classify(url)
    if ident is None and urls.is_short_link(url):
        url = urls.resolve_redirect(url)
        ident = urls.classify(url)
    if ident and not force_asr and (cached := library.find_cached(*ident)):
        return cached
    if ident is None and not any(h in url for h in ("tiktok.com", "instagram.com", "youtube.com", "youtu.be")):
        raise KnownFailure("UNSUPPORTED")

    library.set_job(job_id, "fetching")
    meta = acquirer.probe(url)
    platform, video_id = ident or (meta.platform, meta.id)
    if not platform or not video_id:
        raise KnownFailure("UNSUPPORTED")
    if not force_asr and (cached := library.find_cached(platform, video_id)):
        return cached

    result = None if force_asr else _from_captions(meta)
    if result:
        segs, lang = result
        source, model = "platform_captions", None
    else:
        segs, lang = _from_asr(job_id, url, meta)
        source, model = "asr", settings_store.asr()["model"]

    thumb = _save_thumbnail(meta, platform, video_id)
    return library.save_transcript(platform, video_id, meta, segs, lang or meta.language, source, model, thumb)
