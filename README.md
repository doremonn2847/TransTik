# Transcript Desk

A private tool for one or two people. It turns TikTok, Instagram Reel and YouTube (Shorts) links into transcripts, keeps them in a searchable library, and lets **Claude or ChatGPT** use all of it through an MCP server.

- Paste one link, many links, or a profile/playlist link.
- Uses the platform's own captions when they exist (free, instant), and falls back to speech-to-text when they don't.
- Library with full-text search, folders, tags and inline corrections.
- Exports TXT, SRT, VTT, Markdown, CSV and JSON, or a ZIP of many.
- MCP tools for transcribing, searching and exporting, plus playbooks for hooks, scripts and "why did this go viral", and an originality check.

Everything runs on your own laptop in Docker. Each install has its own library.

---

## 1. Install

You need **Docker Desktop** ([Windows / Mac](https://www.docker.com/products/docker-desktop/)) running.

```bash
git clone <this repo> transcript-desk
cd transcript-desk
cp .env.example .env
```

Open `.env` and set `ASR_API_KEY` (see below). Then start it:

```bash
docker compose up -d --build
```

Open **http://localhost:3000**. The first build takes a few minutes; later starts take seconds.

### Speech-to-text key

Only needed for videos **without** captions. That covers most TikToks and Reels, so set it.

- **Groq** (default, very cheap): create a key at console.groq.com → API Keys, paste it into `ASR_API_KEY`.
- **OpenAI**: set `ASR_BASE_URL=https://api.openai.com/v1`, `ASR_MODEL=whisper-1`, and your key.

After changing `.env`, run `docker compose up -d` again. **Settings → Test key** confirms it works.

Audio is sent to that provider and deleted locally right after. Caption-based transcripts never leave your machine.

### Everyday commands

| Do this | Command |
|---|---|
| Start | `docker compose up -d` |
| Stop | `docker compose down` |
| Update the app after pulling new code | `docker compose up -d --build` |
| See what the backend is doing | `docker compose logs -f api` |
| Check every platform still works | `docker compose exec api python -m app.smoke` |

---

## 2. Connect an assistant

The MCP endpoint is **http://localhost:8765/mcp**. Settings shows the same instructions with copy buttons.

### Claude Code

```bash
claude mcp add --transport http transcript-desk http://localhost:8765/mcp
```

### Claude Desktop

Claude Desktop needs a small bridge (`mcp-remote`) to reach a local HTTP server. Install [Node.js](https://nodejs.org), then in Claude Desktop open **Settings → Developer → Edit config** and add:

```json
{
  "mcpServers": {
    "transcript-desk": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:8765/mcp"]
    }
  }
}
```

Restart Claude Desktop. The tools appear under the tools menu in a new chat.

### ChatGPT, or claude.ai in a browser

These run in the cloud and cannot see `localhost`, so they need a public HTTPS address. Start the optional tunnel:

```bash
docker compose --profile tunnel up -d
```

After about 10 seconds, **Settings** shows an address like `https://something.trycloudflare.com/mcp/<secret>`. Add it as a custom connector (MCP server, no authentication) in ChatGPT or claude.ai. Connector menus move around, so look for "Connectors" or "Custom connector" in each app's settings.

What to know:
- Only the MCP endpoint goes through the tunnel. The web app and REST API stay on your laptop.
- The secret in the address is the only protection. Don't share it. To change it, set a new `MCP_SECRET` in `.env` (or delete `data/mcp_secret.txt`) and restart.
- The address changes every time the tunnel restarts, and it works only while your laptop is on and awake.
- Stop it with `docker compose --profile tunnel down`.

### What to ask

> Transcribe https://www.tiktok.com/@someone/video/123 and give me 10 hooks for my fitness channel based on it.

> Search my library for "morning routine", pick the most-viewed one, and explain why it worked.

> Write me a 45-second script about meal prep that follows the structure of transcript 12. Check it for originality.

Writing happens in the assistant you already use; the server supplies transcripts, numbers and playbooks. Prompts called **Generate hooks**, **Remix a script** and **Explain virality** also show up in Claude.

---

## 3. When something breaks

Platforms change often, and most failures fix themselves with a newer yt-dlp. The app updates yt-dlp on every start (`YTDLP_AUTO_UPDATE=1`), and **Settings → Update now** does it on demand.

| Error | What it means | What to do |
|---|---|---|
| `ASR_NOT_CONFIGURED` | No captions and no speech-to-text key | Set `ASR_API_KEY` |
| `LOGIN_REQUIRED` | The platform wants a login (common on Instagram) | Add a cookies file, see below |
| `RATE_LIMITED` / `NETWORK` | Too many requests, or a connection hiccup | Retried automatically; wait if it keeps happening |
| `FORBIDDEN` | The platform refused this video | Probably private or removed; if every link fails, update yt-dlp |
| `EXTRACTOR_BROKEN` | The platform changed its site | Settings → Update now, then Retry |
| `NO_SPEECH` | Music only, or silent | Nothing to transcribe |
| `GEO_BLOCKED` | Not available from your country | Can't fix from here |

Run `docker compose exec api python -m app.smoke` to see which platforms work right now.

**Cookies (optional).** If Instagram keeps asking for a login, export cookies for instagram.com from your browser in Netscape format (a "Get cookies.txt" style extension does this) and save the file as `data/cookies.txt`. Requests then go out as that account, so use one you're comfortable with and never share the file.

---

## 4. Your data

Everything lives in the `data/` folder next to `docker-compose.yml`:

- `app.db`: the library (SQLite). Copy `data/` to back it up or move it to another machine.
- `thumbs/`: thumbnail images.
- `mcp_secret.txt`: the tunnel secret, if you didn't set one.

No accounts, no analytics. Every port is bound to `127.0.0.1`, so other devices on your network can't reach the app.

### Fair use

This tool reads public videos the way a browser would; it doesn't download or keep the videos. Platform terms generally don't allow automated access, so keep it personal, transcribe only public videos, and don't publish other people's transcripts. Scripts you write with it must be your own work; the originality check helps you avoid copying.

---

## 5. Development

```
api/   FastAPI + MCP server + job worker (Python 3.12, uv)
web/   Next.js app
data/  local library (git-ignored)
```

Run without Docker. You need `uv`, Node 22+, and `ffmpeg` on your PATH for speech-to-text:

```bash
cd api && uv sync && DATA_DIR=../data uv run python -m app.main     # http://localhost:8765
cd web && npm install && npm run dev -- -p 3210                      # http://localhost:3210
cd api && uv run pytest                                              # unit tests
```

How a link is processed (`api/app/pipeline.py`): find the platform and video id → reuse the saved transcript if the video was done before → fetch metadata → use creator subtitles, then platform auto-captions in the video's own language → otherwise download audio only, shrink it to 16 kHz mono Opus, send it to speech-to-text, delete it → remove repeated hallucinated lines → save and index.

The REST routes (`routes.py`) and MCP tools (`mcp_server.py`) are thin wrappers over the same services in `library.py`, so the web app and the assistant always behave the same. All platform access goes through `acquire.py`; to swap yt-dlp for an official API, replace `YtDlpAcquirer`.
