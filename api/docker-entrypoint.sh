#!/bin/sh
set -e

# Platforms change often and old yt-dlp versions stop working, so refresh it on start.
# A failed update (offline, PyPI down) never blocks startup.
if [ "${YTDLP_AUTO_UPDATE:-1}" = "1" ]; then
  echo "Checking for a newer yt-dlp..."
  timeout 90 uv pip install --python /opt/venv/bin/python -q -U "yt-dlp[default,deno]" \
    || echo "yt-dlp update skipped (no network?). Continuing with the installed version."
fi

exec python -m app.main
