"""Caption parsing and transcript clean-up. Everything becomes {start, end, text}."""
from __future__ import annotations

import html
import json
import re

Segment = dict  # {"start": float, "end": float, "text": str}

_TAG = re.compile(r"<[^>]+>")
_TIME = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})")
_SPACE = re.compile(r"\s+")


def _seconds(stamp: str) -> float | None:
    m = _TIME.search(stamp)
    if not m:
        return None
    h, mnt, s, ms = m.groups()
    return int(h or 0) * 3600 + int(mnt) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def _clean(text: str) -> str:
    return _SPACE.sub(" ", html.unescape(_TAG.sub("", text))).strip()


def parse_vtt(body: str) -> list[Segment]:
    """Parse WebVTT or SRT. Handles YouTube's rolling auto-captions."""
    lines = body.replace("\ufeff", "").splitlines()
    raw: list[tuple[float, float, list[str]]] = []
    current: list[str] | None = None
    blank_since_timing = False
    for i, line in enumerate(lines):
        if "-->" in line:
            left, right = line.split("-->", 1)
            start, end = _seconds(left), _seconds(right)
            current = None
            if start is not None and end is not None:
                current = []
                raw.append((start, end, current))
            blank_since_timing = False
            continue
        if not line.strip():
            blank_since_timing = True
            continue
        if current is None:
            continue  # header, NOTE or STYLE text before the first cue
        if line.strip().isdigit() and "-->" in next((x for x in lines[i + 1:i + 4] if x.strip()), ""):
            continue  # SRT cue number
        # YouTube puts a whitespace-only line between the timing and the text, so accept
        # text after a blank line only while the cue is still empty.
        if blank_since_timing and current:
            continue
        if text := _clean(line):
            current.append(text)

    cues: list[Segment] = []
    prev_lines: list[str] = []
    for start, end, text_lines in raw:
        fresh = [line for line in text_lines if line not in prev_lines]
        prev_lines = text_lines or prev_lines
        if fresh:
            cues.append({"start": start, "end": end, "text": " ".join(fresh)})
    return drop_rolling(cues)


def parse_json3(body: str) -> list[Segment]:
    """Parse YouTube's json3 caption format."""
    out: list[Segment] = []
    for event in json.loads(body).get("events", []):
        text = _clean("".join(seg.get("utf8", "") for seg in event.get("segs") or []))
        if not text:
            continue
        start = event.get("tStartMs", 0) / 1000
        out.append({"start": start, "end": start + event.get("dDurationMs", 0) / 1000, "text": text})
    # Auto-caption events overlap; end each one where the next begins.
    for cur, nxt in zip(out, out[1:]):
        if cur["end"] > nxt["start"] > cur["start"]:
            cur["end"] = nxt["start"]
    return drop_rolling(out)


def parse_caption(ext: str, body: str) -> list[Segment]:
    if ext == "json3" or body.lstrip().startswith("{"):
        return parse_json3(body)
    return parse_vtt(body)


def drop_rolling(segs: list[Segment]) -> list[Segment]:
    """Drop a segment whose text is just the beginning of the next one."""
    out: list[Segment] = []
    for i, seg in enumerate(segs):
        nxt = segs[i + 1]["text"] if i + 1 < len(segs) else None
        if nxt is not None and nxt != seg["text"] and nxt.startswith(seg["text"]):
            continue
        out.append(seg)
    return out


def drop_repeats(segs: list[Segment], max_run: int = 3) -> list[Segment]:
    """Remove runs of the same line repeated more than max_run times (ASR hallucination)."""
    out: list[Segment] = []
    i = 0
    while i < len(segs):
        j = i
        key = segs[i]["text"].strip().lower()
        while j < len(segs) and segs[j]["text"].strip().lower() == key:
            j += 1
        if j - i <= max_run:
            out.extend(segs[i:j])
        i = j
    return out


def normalize(segs: list[Segment]) -> list[Segment]:
    out = []
    for seg in segs:
        text = _SPACE.sub(" ", str(seg.get("text", ""))).strip()
        if text:
            start = max(0.0, float(seg.get("start", 0)))
            out.append({"start": round(start, 3), "end": round(max(start, float(seg.get("end", start))), 3), "text": text})
    return out


def full_text(segs: list[Segment]) -> str:
    return " ".join(s["text"] for s in segs)


def has_speech(segs: list[Segment]) -> bool:
    return len(re.findall(r"\w", full_text(segs))) >= 3
