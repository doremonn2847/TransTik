"""Acquisition: URL -> metadata, captions, audio. The only module that knows about yt-dlp.

Everything else talks to the `Acquirer` protocol, so a broken platform can be swapped
for an official API or another provider without touching the pipeline.
"""
from __future__ import annotations

import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import yt_dlp
from yt_dlp.utils import DownloadError

from . import config, urls
from .errors import KnownFailure, classify_message

CAPTION_EXTS = ("json3", "vtt", "srt")


@dataclass
class VideoMeta:
    id: str
    platform: str | None
    url: str
    title: str | None = None
    description: str | None = None
    author: str | None = None
    duration: int | None = None
    thumbnail: str | None = None
    language: str | None = None
    stats: dict = field(default_factory=dict)
    subtitles: dict = field(default_factory=dict)
    auto_captions: dict = field(default_factory=dict)


class Acquirer(Protocol):
    def probe(self, url: str) -> VideoMeta: ...
    def fetch_caption(self, track: dict) -> str: ...
    def audio(self, url: str, out_dir: Path) -> Path: ...
    def expand(self, url: str, limit: int) -> list[str]: ...


def pick_caption_track(meta: VideoMeta) -> dict | None:
    """Creator-uploaded subtitles first, then auto-captions in the video's own language.

    YouTube lists auto-translations into 100+ languages under automatic_captions, so the
    original track ("xx-orig", or the video's declared language) must be chosen explicitly.
    """
    def usable(bucket: dict, lang: str) -> dict | None:
        formats = bucket.get(lang) or []
        for ext in CAPTION_EXTS:
            for fmt in formats:
                if fmt.get("ext") == ext and fmt.get("url"):
                    return {"lang": lang.removesuffix("-orig"), "ext": ext, "url": fmt["url"]}
        return None

    manual = {k: v for k, v in meta.subtitles.items() if k != "live_chat"}
    prefer = [meta.language] if meta.language else []
    for lang in [*prefer, *[k for k in manual if k.startswith("en")], *manual]:
        if lang and (track := usable(manual, lang)):
            return {**track, "kind": "manual"}

    auto = meta.auto_captions
    originals = [k for k in auto if k.endswith("-orig")]
    for lang in [*originals, *prefer, "en"]:
        if lang and (track := usable(auto, lang)):
            return {**track, "kind": "auto"}
    return None


class _QuietLogger:
    """yt-dlp prints errors to stderr even in quiet mode; we report them ourselves."""

    def debug(self, msg: str) -> None: ...
    def info(self, msg: str) -> None: ...
    def warning(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...


class _Throttle:
    """At most one request per platform every `gap` seconds."""

    def __init__(self, gap: float = 1.5):
        self.gap = gap
        self._lock = threading.Lock()
        self._last: dict[str, float] = {}

    def wait(self, key: str) -> None:
        with self._lock:
            delay = self._last.get(key, 0) + self.gap - time.monotonic()
            self._last[key] = time.monotonic() + max(delay, 0)
        if delay > 0:
            time.sleep(delay)


class YtDlpAcquirer:
    def __init__(self) -> None:
        self._throttle = _Throttle()

    def _opts(self, **extra) -> dict:
        opts = {"quiet": True, "no_warnings": True, "noplaylist": True, "socket_timeout": 20,
                "retries": 2, "noprogress": True, "logger": _QuietLogger(), "cachedir": str(config.DATA_DIR / "ytdlp-cache")}
        if config.COOKIES_PATH.exists():
            opts["cookiefile"] = str(config.COOKIES_PATH)
        return {**opts, **extra}

    def _host_key(self, url: str) -> str:
        return next((p for p in ("tiktok", "instagram", "youtu") if p in url), "other")

    def _extract(self, url: str, download: bool, **extra) -> dict:
        self._throttle.wait(self._host_key(url))
        try:
            with yt_dlp.YoutubeDL(self._opts(**extra)) as ydl:
                info = ydl.extract_info(url, download=download)
        except DownloadError as exc:
            raise KnownFailure(classify_message(str(exc)), str(exc)[:300]) from exc
        if not info:
            raise KnownFailure("DELETED")
        return info

    def probe(self, url: str) -> VideoMeta:
        info = self._extract(url, download=False, skip_download=True)
        if info.get("_type") == "playlist":
            entries = [e for e in info.get("entries") or [] if e]
            if not entries:
                raise KnownFailure("UNSUPPORTED", "link points to a collection with no videos")
            info = entries[0]
        key = (info.get("extractor_key") or info.get("extractor") or "").lower()
        platform = next((p for p in ("tiktok", "instagram", "youtube") if p in key), None)
        stats = {k: info.get(k) for k in ("view_count", "like_count", "comment_count", "repost_count",
                                           "save_count", "channel_follower_count", "timestamp")}
        return VideoMeta(
            id=str(info.get("id") or ""), platform=platform, url=info.get("webpage_url") or url,
            title=info.get("title") or info.get("fulltitle"), description=info.get("description"),
            author=(info.get("uploader_id") or info.get("channel") or info.get("uploader") or "").lstrip("@") or None,
            duration=int(info["duration"]) if info.get("duration") else None,
            thumbnail=info.get("thumbnail"), language=info.get("language"),
            stats={k: v for k, v in stats.items() if v is not None},
            subtitles=info.get("subtitles") or {}, auto_captions=info.get("automatic_captions") or {},
        )

    def fetch_caption(self, track: dict) -> str:
        self._throttle.wait(self._host_key(track["url"]))
        with yt_dlp.YoutubeDL(self._opts()) as ydl:
            return ydl.urlopen(track["url"]).read().decode("utf-8", errors="replace")

    def audio(self, url: str, out_dir: Path) -> Path:
        """Download audio only and convert to small 16 kHz mono Opus for upload."""
        if not shutil.which("ffmpeg"):
            raise KnownFailure("FAILED", "ffmpeg is not installed")
        info = self._extract(url, download=True, format="bestaudio/best", outtmpl=str(out_dir / "src.%(ext)s"))
        if info.get("_type") == "playlist":
            info = next(e for e in info["entries"] if e)
        source = next((p for p in out_dir.glob("src.*")), None)
        if source is None:
            raise KnownFailure("EXTRACTOR_BROKEN", "audio download produced no file")
        target = out_dir / "audio.ogg"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000",
               "-c:a", "libopus", "-b:a", "24k", str(target)]
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if done.returncode != 0 or not target.exists():
            if "does not contain any stream" in done.stderr or "matches no streams" in done.stderr:
                raise KnownFailure("NO_SPEECH", "video has no audio track")
            raise KnownFailure("FAILED", f"ffmpeg: {done.stderr[-300:]}")
        return target

    def expand(self, url: str, limit: int) -> list[str]:
        info = self._extract(url, download=False, extract_flat="in_playlist", noplaylist=False,
                             playlistend=limit, skip_download=True)
        out: list[str] = []

        def walk(node: dict) -> None:
            for entry in node.get("entries") or []:
                if not entry or len(out) >= limit:
                    continue
                if entry.get("entries"):
                    walk(entry)
                    continue
                link = entry.get("url") or entry.get("webpage_url")
                if link and urls.classify(link) and link not in out:
                    out.append(link)

        walk(info)
        return out


acquirer: Acquirer = YtDlpAcquirer()
