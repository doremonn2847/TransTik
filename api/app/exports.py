"""Export formats. Input is the dict returned by library.get_transcript()."""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile

FORMATS = {"txt": "text/plain", "srt": "application/x-subrip", "vtt": "text/vtt",
           "json": "application/json", "csv": "text/csv", "md": "text/markdown"}


def ts(t: float, sep: str = ".") -> str:
    h, rem = divmod(int(round(t * 1000)), 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02}:{m:02}:{s:02}{sep}{ms:03}"


def short_ts(t: float) -> str:
    total = int(t)
    h, rem = divmod(total, 3600)
    return f"{h}:{rem // 60:02}:{rem % 60:02}" if h else f"{rem // 60:02}:{rem % 60:02}"


def to_srt(segs: list[dict]) -> str:
    return "\n".join(f"{i}\n{ts(s['start'], ',')} --> {ts(s['end'], ',')}\n{s['text']}\n"
                     for i, s in enumerate(segs, 1))


def to_vtt(segs: list[dict]) -> str:
    return "WEBVTT\n\n" + "\n".join(f"{ts(s['start'])} --> {ts(s['end'])}\n{s['text']}\n" for s in segs)


def to_txt(segs: list[dict], timestamps: bool = False) -> str:
    if timestamps:
        return "\n".join(f"[{short_ts(s['start'])}] {s['text']}" for s in segs)
    return " ".join(s["text"] for s in segs)


def to_csv(segs: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["start", "end", "text"])
    for s in segs:
        writer.writerow([s["start"], s["end"], s["text"]])
    return buf.getvalue()


def to_md(item: dict, timestamps: bool = True) -> str:
    stats = item.get("stats") or {}
    facts = [f"**Source:** <{item['url']}>", f"**Author:** @{item['author']}" if item.get("author") else None,
             f"**Platform:** {item['platform']}", f"**Language:** {item['language']}" if item.get("language") else None,
             f"**Views:** {stats['view_count']:,}" if stats.get("view_count") else None,
             f"**Likes:** {stats['like_count']:,}" if stats.get("like_count") else None]
    head = f"# {item.get('title') or 'Untitled'}\n\n" + "  \n".join(f for f in facts if f)
    return f"{head}\n\n## Transcript\n\n{to_txt(item['segments'], timestamps)}\n"


def to_json(item: dict) -> str:
    keep = ("url", "platform", "title", "author", "duration_s", "stats")
    payload = {"video": {k: item.get(k) for k in keep}, "language": item.get("language"),
               "source": item.get("source"), "segments": item["segments"]}
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render(item: dict, fmt: str, timestamps: bool = False) -> str:
    segs = item["segments"]
    match fmt:
        case "txt":
            return to_txt(segs, timestamps)
        case "srt":
            return to_srt(segs)
        case "vtt":
            return to_vtt(segs)
        case "csv":
            return to_csv(segs)
        case "md":
            return to_md(item, timestamps)
        case "json":
            return to_json(item)
    raise ValueError(f"unknown format: {fmt}")


def filename(item: dict, fmt: str) -> str:
    stem = re.sub(r"[^\w\- ]+", "", (item.get("title") or "transcript"), flags=re.UNICODE).strip()[:60] or "transcript"
    author = re.sub(r"[^\w\-.]+", "", item.get("author") or "", flags=re.UNICODE)
    return f"{author + ' - ' if author else ''}{stem} [{item['id']}].{fmt}"


def bulk_csv(items: list[dict]) -> str:
    """One row per video: what agencies want in a spreadsheet."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["url", "platform", "author", "title", "duration_s", "views", "likes", "comments", "language", "transcript"])
    for it in items:
        st = it.get("stats") or {}
        writer.writerow([it["url"], it["platform"], it.get("author"), it.get("title"), it.get("duration_s"),
                         st.get("view_count"), st.get("like_count"), st.get("comment_count"), it.get("language"),
                         it["text"]])
    return buf.getvalue()


def to_zip(items: list[dict], fmt: str, timestamps: bool = False) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for it in items:
            zf.writestr(filename(it, fmt), render(it, fmt, timestamps))
        zf.writestr("_all_transcripts.csv", "﻿" + bulk_csv(items))
    return buf.getvalue()
