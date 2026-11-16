"""Fixed failure codes shared by the web UI and the MCP tools."""
from __future__ import annotations

HINTS = {
    "PRIVATE": "The video is private. Only public videos can be transcribed.",
    "DELETED": "The video no longer exists or the link is wrong.",
    "GEO_BLOCKED": "The video is not available from this network's region.",
    "LOGIN_REQUIRED": "The platform asked for a login. Add data/cookies.txt (see README) and retry.",
    "RATE_LIMITED": "The platform is rate limiting this network. Wait a few minutes and retry.",
    "NO_SPEECH": "No speech was found (music-only or silent video).",
    "UNSUPPORTED": "Not a TikTok, Instagram Reel or YouTube video link.",
    "TOO_LONG": "The video is longer than the configured limit (MAX_DURATION_S).",
    "ASR_NOT_CONFIGURED": "This video has no captions, so it needs speech-to-text. Add an API key on the Settings page.",
    "ASR_FAILED": "The speech-to-text provider returned an error. Check the key on the Settings page (Test key).",
    "NETWORK": "Could not reach the platform (connection problem). It will be retried automatically.",
    "FORBIDDEN": "The platform refused this request. The video may be private or removed; if every link fails, wait a while or update yt-dlp.",
    "EXTRACTOR_BROKEN": "The platform changed something. Update yt-dlp from Settings and retry.",
    "FAILED": "Unexpected error. Check the api container logs.",
}


class KnownFailure(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def hint(code: str | None) -> str | None:
    return HINTS.get(code or "")


_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("NETWORK", ("httpsconnection", "timed out", "connection reset", "connection aborted", "name resolution",
                 "getaddrinfo", "remote end closed", "network is unreachable")),
    ("RATE_LIMITED", ("429", "too many requests", "rate limit", "rate-limit")),
    ("LOGIN_REQUIRED", ("login required", "log in", "sign in", "cookies", "requires authentication", "empty media response")),
    ("PRIVATE", ("private video", "is private", "private account")),
    ("GEO_BLOCKED", ("ip address is blocked", "in your country", "from your location", "geo restrict", "geo-restrict", "your region")),
    ("DELETED", ("video unavailable", "has been removed", "404", "not found", "does not exist", "no longer available", "unavailable")),
    ("FORBIDDEN", ("http error 403", "forbidden")),
    ("UNSUPPORTED", ("unsupported url", "no video formats", "no video could be found")),
]


def classify_message(message: str) -> str:
    """Map a yt-dlp error message to one of the fixed codes."""
    low = message.lower()
    for code, needles in _RULES:
        if any(n in low for n in needles):
            return code
    return "EXTRACTOR_BROKEN"
