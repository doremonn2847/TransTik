"""Live smoke test: can this install still fetch each platform?

Probes known public videos directly (no database writes, no speech-to-text cost) and reports,
per platform, whether metadata and captions came back. Run it when something stops working:

    docker compose exec api python -m app.smoke          # in Docker
    uv run python -m app.smoke                           # local dev, from api/
"""
from __future__ import annotations

import sys
import time

from .acquire import acquirer, pick_caption_track
from .errors import KnownFailure

CASES = [
    ("youtube", "https://www.youtube.com/watch?v=jNQXAC9IVRw"),
    ("tiktok", "https://www.tiktok.com/@scout2015/video/6718335390845095173"),
    ("instagram", "https://www.instagram.com/reel/Chunk8-jurw/"),
    ("instagram", "https://www.instagram.com/reel/CDUMkliABpa/"),
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # titles contain emoji
    results: dict[str, list[bool]] = {}
    for platform, url in CASES:
        start = time.monotonic()
        try:
            try:
                meta = acquirer.probe(url)
            except KnownFailure as first:
                if first.code not in ("NETWORK", "RATE_LIMITED", "FORBIDDEN"):
                    raise
                time.sleep(3)
                meta = acquirer.probe(url)  # one retry: platforms fail intermittently
            track = pick_caption_track(meta)
            line = f"ok    {meta.title!r:.50}  captions={'yes (' + track['lang'] + ')' if track else 'no -> speech-to-text'}"
            ok = True
        except KnownFailure as exc:
            line, ok = f"FAIL  {exc.code}  {exc.detail[:90]}", False
        results.setdefault(platform, []).append(ok)
        print(f"{platform:<10} {time.monotonic() - start:5.1f}s  {line}")
    print()
    for platform, oks in results.items():
        print(f"{platform:<10} {sum(oks)}/{len(oks)} reachable")
    # One success per platform is enough; individual test videos get deleted over time.
    return 0 if all(any(oks) for oks in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
