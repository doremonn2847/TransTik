# TransTik

Turn TikTok, Instagram Reels and YouTube Shorts links into transcripts. Keep them in a private, searchable library, and let **Claude** (or ChatGPT) read them for you to write hooks and scripts or explain why a video worked.

- Paste one link, many links, or a whole profile or playlist.
- Uses the video's own captions when it has them (free and instant). Otherwise it listens to the audio with speech-to-text.
- Search every word you've saved, sort transcripts into folders and tags, and fix mistakes by clicking a line.
- Download as TXT, SRT, VTT, Markdown, CSV or JSON, or many at once as a ZIP.

TransTik runs on **your own computer**. Your library stays on your computer and isn't shared with anyone, including other people who use TransTik.

---

## Set up on a Mac (about 20 minutes, once)

### What you need

- A Mac with an up-to-date macOS (Docker Desktop supports the three most recent versions). Apple chip or Intel both work.
- About 4 GB of free disk space
- An **API key** for speech-to-text, from OpenAI or Groq (step 4 explains)

### Step 1: Install Docker Desktop

TransTik runs inside Docker, a free app that keeps it self-contained.

1. Find out which chip your Mac has: the **Apple menu → About This Mac**. Look at **Chip** (says "Apple M…") or **Processor** (says "Intel").
2. Go to **https://www.docker.com/products/docker-desktop/** and download Docker Desktop for that chip.
3. Open the downloaded `.dmg` and drag **Docker** into **Applications**.
4. Open **Docker** from Applications. Accept the terms, and skip signing in (you don't need an account).
5. Wait until the whale icon in the menu bar at the top of the screen stops animating. Docker is now running.

> Tip: in Docker Desktop's **Settings → General**, turn on **Start Docker Desktop when you sign in to your computer**. Then TransTik is always ready after a restart.

### Step 2: Download TransTik

1. Open **https://github.com/doremonn2847/TransTik**.
2. Click the green **Code** button, then **Download ZIP**.
3. Open your **Downloads** folder and double-click `TransTik-main.zip` to unzip it.
4. Move the `TransTik-main` folder into your **Documents** folder.

### Step 3: Start TransTik

1. Open **Terminal**: press **⌘ + Space**, type `Terminal`, and press **Return**.
2. Copy this line, paste it into Terminal, and press **Return**:

   ```bash
   cd ~/Documents/TransTik-main
   ```

3. Then copy, paste and press **Return** again:

   ```bash
   docker compose up -d --build
   ```

The first time takes **5 to 15 minutes**: Docker downloads and builds everything. You'll see a lot of text scroll by. It's finished when you get your prompt back and see lines ending in **Started**.

You can close Terminal afterwards. TransTik keeps running in the background.

### Step 4: Add your speech-to-text key

1. Open **http://localhost:3000** in Safari or Chrome. Bookmark it.
2. Click **Settings** at the top.
3. Under **Speech-to-text**, choose a provider:
   - **OpenAI**: create a key at **https://platform.openai.com/api-keys** (it starts with `sk-`). Your account needs a little credit; $5 lasts a very long time.
   - **Groq**: cheaper, with a free tier. Create a key at **https://console.groq.com/keys**.
4. Paste the key and click **Save and test**. A green message means it worked.

The key is saved only on your Mac. With OpenAI it costs about 0.6 cents per minute of audio, so a typical 30-second TikTok costs about a third of a cent. Videos that already have captions cost nothing.

**Done.** Go to **Inbox**, paste a link, and click **Transcribe**.

---

## Using TransTik

**Inbox:** paste links (one per line, or mixed into any text) and press **Transcribe** (or **⌘ + Return**). Paste a profile or playlist link to bring in up to 50 of its videos. Each link shows its progress; click a finished one to open it.

**Library:** everything you've transcribed. Type in the search box (press **/** to jump there) to find any word said in any video. Tick several to download them together as a ZIP, or delete them.

**Transcript page:**
- **Copy text** copies it all (or press **C**). Untick **Timestamps** for plain text.
- **Click any line to fix a mistake.** Press Return to save, Esc to cancel. Your fixes are used in every download.
- Click a timestamp to open the video at that moment (YouTube only).
- On the right: views, likes and comments, downloads, folders and tags.
- **Re-transcribe from audio** helps when a video's own captions are poor.

---

## Connect TransTik to Claude

With this connected, you can ask Claude things like:

> Transcribe https://www.tiktok.com/@someone/video/123 and give me 10 hooks for my skincare channel based on it.

> Search my TransTik library for "morning routine", pick the most-viewed video, and explain why it worked.

> Write a 45-second script about meal prep that follows the structure of transcript 12, and check that it's original.

Claude does the writing; TransTik gives it the transcripts, the numbers, and step-by-step writing guides. It also checks how much of a new script copies the original, so you don't accidentally post a near-copy.

### Claude Desktop app (Mac)

1. Install **Node.js**: download the **LTS** version from **https://nodejs.org** and run the installer.
2. Open the **Claude** app. In the menu bar choose **Claude → Settings… → Developer → Edit Config**. A Finder window opens with the file `claude_desktop_config.json` selected.
3. Open that file with **TextEdit** (right-click → **Open With → TextEdit**).
4. Replace everything in it with the text below. If the file already has other servers listed under `"mcpServers"`, add the `"transtik"` part next to them instead.

   ```json
   {
     "mcpServers": {
       "transtik": {
         "command": "npx",
         "args": ["-y", "mcp-remote", "http://localhost:8765/mcp"]
       }
     }
   }
   ```

5. Save (**⌘ + S**), then **quit Claude completely (⌘ + Q)** and open it again.
6. In a new chat, open the tools menu and check that **transtik** is listed. If you're asked to allow a TransTik tool, choose **Allow**.

The same text, with a copy button, is on TransTik's **Settings** page.

### Claude Code

Run this once in Terminal:

```bash
claude mcp add --transport http transtik http://localhost:8765/mcp
```

### ChatGPT, or claude.ai in a web browser

These run in the cloud and can't reach your Mac directly, so they need a temporary public address:

```bash
cd ~/Documents/TransTik-main
docker compose --profile tunnel up -d
```

After about 10 seconds, TransTik's **Settings** page shows an address like `https://something.trycloudflare.com/mcp/…`. Add it as a custom connector (MCP server, no authentication) in ChatGPT or claude.ai.

- The address works only while your Mac is awake, and changes each time the tunnel restarts.
- **Keep it private.** Anyone with the address can use your library.
- Turn it off: `docker compose --profile tunnel down` (this stops TransTik too; start it again with `docker compose up -d`).

---

## Everyday care

TransTik runs whenever Docker Desktop is running. To use these commands, open Terminal and first run `cd ~/Documents/TransTik-main`.

| To… | Run |
|---|---|
| Stop TransTik | `docker compose down` |
| Start it again | `docker compose up -d` |
| See what it's doing (when something seems stuck) | `docker compose logs --tail 50 api` |
| Check that TikTok, Instagram and YouTube still work | `docker compose exec api python -m app.smoke` |

### Updating to a new version

Your library lives in the `data` folder inside `TransTik-main`. Keep that folder.

1. Stop TransTik: `docker compose down`
2. Download the new ZIP (Step 2) and unzip it.
3. Move the **`data`** folder from your old `TransTik-main` into the new one (replace the empty one).
4. Put the new folder where the old one was (delete or rename the old one first).
5. In Terminal: `cd ~/Documents/TransTik-main` then `docker compose up -d --build`

### Back up your library

Copy the `data` folder somewhere safe. It holds every transcript, your settings and your saved key. To move TransTik to another Mac, set it up there, then replace its `data` folder with your copy.

---

## When something goes wrong

**Problems starting it**

| You see | Do this |
|---|---|
| `command not found: docker` | Docker Desktop isn't installed or hasn't been opened yet. Open it from Applications and try again. |
| `Cannot connect to the Docker daemon` | Docker Desktop isn't running. Open it, wait for the whale icon to settle, and try again. |
| `no such file or directory` after `cd` | The folder is somewhere else or has a different name. Type `cd ` (with a space), drag the TransTik folder from Finder into Terminal, and press Return. |
| `port is already allocated` | Another app uses port 3000. In the TransTik folder, create a file named `.env` containing `WEB_PORT=3001`, run `docker compose up -d`, and open http://localhost:3001 instead. |
| The page at localhost:3000 won't load | Wait a minute after starting; it may still be booting. Then check Docker Desktop: both `transtik` containers should show as running. |
| The first build stopped with a network error | Your connection dropped. Run `docker compose up -d --build` again; it continues where it stopped. |

**A link fails.** Each failed link shows a short explanation and a **Retry** button.

| Error | What it means |
|---|---|
| ASR NOT CONFIGURED | The video has no captions and no speech-to-text key is saved. Add one in Settings. |
| ASR FAILED | The key was rejected or has run out of credit. Settings → **Test key**. |
| EXTRACTOR BROKEN | TikTok or Instagram changed their website. Settings → **Update now**, then Retry. |
| LOGIN REQUIRED | Instagram wants a login (see "Instagram keeps failing" below). |
| FORBIDDEN | The platform refused that video; it's probably private or removed. |
| RATE LIMITED / NETWORK | Too many requests, or a connection hiccup. TransTik retries by itself; wait a bit. |
| NO SPEECH | The video is music only, or silent. |
| GEO BLOCKED | The video isn't available in your country. |

**Instagram keeps failing.** Instagram sometimes needs a logged-in account. Install a browser extension that exports cookies in "Netscape cookies.txt" format, log in to instagram.com, export the cookies for instagram.com, and save the file as `cookies.txt` inside the `data` folder. Requests then go out as that account, so use one you don't mind, and never share the file.

**Claude doesn't show TransTik.** Check that TransTik is running (http://localhost:3000 opens), that Node.js is installed, and that the config file is valid JSON (every `{` has a matching `}`; quotes are straight `"`, not curly). Then quit Claude with ⌘ + Q and reopen it.

---

## Privacy and fair use

- Your library, settings and key stay in the `data` folder on your Mac. There are no accounts and no tracking.
- TransTik is reachable only from your own Mac, not from other devices on your Wi-Fi.
- Audio from videos without captions is sent to your speech-to-text provider (OpenAI or Groq), then deleted from your Mac.
- TransTik reads public videos the way a browser does; it doesn't download or keep the videos. Keep it for personal research, don't publish other people's transcripts, and make sure scripts you post are your own work. The originality check helps with that.

---

## For developers

```
api/    Python 3.12 · FastAPI · MCP server · job worker · SQLite (uv)
web/    Next.js app
data/   your library (not in git)
```

How a link is processed (`api/app/pipeline.py`): work out the platform and video id → reuse the saved transcript if the video was done before → fetch metadata with yt-dlp → use creator subtitles, then auto-captions in the video's own language → otherwise download audio only, shrink it to 16 kHz mono Opus, send it to speech-to-text, delete it → drop repeated hallucinated lines → save and index for search.

The web API (`routes.py`) and the MCP tools (`mcp_server.py`) are thin wrappers over the same functions in `library.py`, so the app and Claude always behave the same. All platform access goes through `acquire.py`.

Run without Docker (needs `uv`, Node 22+, and `ffmpeg` for speech-to-text):

```bash
cd api && uv sync && DATA_DIR=../data uv run python -m app.main     # API + MCP on :8765
cd web && npm install && npm run dev -- -p 3210                      # app on :3210
cd api && uv run pytest                                              # tests
```

Settings come from the Settings page (`data/settings.json`) or `.env` (see `.env.example`); the Settings page wins.
