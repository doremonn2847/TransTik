"""URL recognition: which platform, which video id, single video or collection."""
from __future__ import annotations

import re

import httpx

PATTERNS = {
    "tiktok": re.compile(r"tiktok\.com/(?:@[^/?#]+/video/|v/|embed/(?:v2/)?|player/v1/)(\d+)"),
    "instagram": re.compile(r"instagram\.com/(?:[^/?#]+/)?(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)"),
    "youtube": re.compile(
        r"(?:youtube(?:-nocookie)?\.com/(?:shorts/|live/|embed/|v/|watch\?(?:[^#\s]*&)?v=)|youtu\.be/)"
        r"([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])"
    ),
}

SHORT_LINK = re.compile(r"^https?://(?:vm\.tiktok\.com|vt\.tiktok\.com|(?:www\.)?tiktok\.com/t)/", re.I)

COLLECTION = [
    re.compile(r"tiktok\.com/@[^/?#]+/?(?:[?#].*)?$"),
    re.compile(r"tiktok\.com/@[^/?#]+/(?:collection|playlist)/"),
    re.compile(r"youtube\.com/playlist\?"),
    re.compile(r"youtube\.com/(?:@[^/?#]+|channel/[^/?#]+|c/[^/?#]+|user/[^/?#]+)(?:/(?:shorts|videos|streams)?)?/?(?:[?#].*)?$"),
    re.compile(r"instagram\.com/(?!reel/|reels/|p/|tv/|explore/|stories/)[A-Za-z0-9_.]+/?(?:reels/?)?(?:[?#].*)?$"),
]

_URL = re.compile(r"https?://[^\s<>\"'`,]+", re.I)
_BARE = re.compile(r"(?<![\w/.])(?:www\.|m\.|vm\.|vt\.)?(?:tiktok\.com|instagram\.com|youtube\.com|youtu\.be)/[^\s<>\"'`,]+", re.I)


def classify(url: str) -> tuple[str, str] | None:
    """Return (platform, video_id) for a single-video URL, else None."""
    for platform, pattern in PATTERNS.items():
        if m := pattern.search(url):
            return platform, m.group(1)
    return None


def is_short_link(url: str) -> bool:
    return bool(SHORT_LINK.match(url))


def is_collection(url: str) -> bool:
    return classify(url) is None and any(p.search(url) for p in COLLECTION)


def canonical(platform: str, video_id: str, author: str | None = None) -> str:
    if platform == "youtube":
        return f"https://www.youtube.com/watch?v={video_id}"
    if platform == "instagram":
        return f"https://www.instagram.com/reel/{video_id}/"
    handle = (author or "_").lstrip("@")
    return f"https://www.tiktok.com/@{handle}/video/{video_id}"


def extract_urls(text: str) -> list[str]:
    """Pull every link out of pasted text, in order, without duplicates."""
    found: list[tuple[int, str]] = [(m.start(), m.group(0)) for m in _URL.finditer(text)]
    taken = [(pos, pos + len(u)) for pos, u in found]
    for m in _BARE.finditer(text):
        if not any(a <= m.start() < b for a, b in taken):
            found.append((m.start(), "https://" + m.group(0)))
    out: list[str] = []
    seen: set[str] = set()
    for _, url in sorted(found):
        url = url.rstrip(".;)]}>")
        key = "|".join(classify(url) or ("", url))
        if key not in seen:
            seen.add(key)
            out.append(url)
    return out


def resolve_redirect(url: str) -> str:
    """Follow a share short link to its final URL. Returns the input on failure."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}
    try:
        with httpx.Client(follow_redirects=True, timeout=15, headers=headers) as client:
            return str(client.get(url).url)
    except httpx.HTTPError:
        return url
