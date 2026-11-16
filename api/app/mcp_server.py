"""MCP server: thin wrappers over the same services the web app uses."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from mcp.server.mcpserver import MCPServer

from . import exports, library, originality, urls, worker
from .acquire import acquirer
from .errors import KnownFailure, hint

PLAYBOOKS = Path(__file__).parent / "playbooks"
Kind = Literal["hooks", "remix", "virality"]
Format = Literal["txt", "srt", "vtt", "json", "csv", "md"]

INSTRUCTIONS = """\
TransTik turns TikTok, Instagram Reel and YouTube (Shorts) links into transcripts and keeps
them in a searchable personal library.

Typical flow: transcribe_url (one link) or transcribe_batch (many) -> get_transcript / search_library.
For a profile or playlist link, call expand_collection first and choose which videos to transcribe.

Before writing hooks, writing a script based on a video, or explaining why a video performed well,
call get_playbook with kind "hooks", "remix" or "virality" and follow it. After drafting anything
derived from a transcript, call check_originality.

Failures come back with an error_code and a hint; relay the hint to the user rather than guessing.
"""

mcp = MCPServer("transtik", title="TransTik", instructions=INSTRUCTIONS, version="0.1.0")


def _payload(transcript_id: int, timestamps: bool = False, include_stats: bool = True) -> dict:
    item = library.get_transcript(transcript_id)
    if item is None:
        return {"error_code": "NOT_FOUND", "hint": f"No transcript with id {transcript_id}."}
    out = {k: item[k] for k in ("id", "title", "author", "platform", "url", "duration_s", "language",
                                 "source", "edited", "folder", "tags")}
    out["word_count"] = len(item["text"].split())
    if include_stats:
        out["stats"] = item["stats"]
        out["description"] = item["description"]
    out["text"] = exports.to_txt(item["segments"], timestamps)
    return out


def _job_view(job: dict) -> dict:
    out = {"job_id": job["id"], "status": job["status"], "url": job.get("input_url")}
    if job.get("transcript_id"):
        out["transcript_id"] = job["transcript_id"]
        out["title"] = job.get("title")
    if job.get("error_code"):
        out["error_code"] = job["error_code"]
        out["hint"] = job.get("hint")
    return out


@mcp.tool()
async def transcribe_url(url: str, timestamps: bool = False, force_speech_to_text: bool = False) -> dict:
    """Get the transcript of one TikTok, Instagram Reel or YouTube video and save it to the library.

    Uses the platform's own captions when they exist, otherwise speech-to-text. Already-saved videos
    return instantly. Waits up to about 45 seconds; if the job is still running it returns a job_id
    to check with get_job. Set force_speech_to_text to redo a poor caption-based transcript.
    """
    found = urls.extract_urls(url)
    if not found:
        return {"error_code": "UNSUPPORTED", "hint": hint("UNSUPPORTED")}
    if urls.is_collection(found[0]):
        return {"error_code": "IS_COLLECTION",
                "hint": "This is a profile or playlist link. Use expand_collection, then transcribe_batch."}
    _, ids = worker.enqueue([found[0]], force_asr=force_speech_to_text)
    job = await worker.wait_for(ids[0], timeout=45)
    if job["status"] == "done" and job.get("transcript_id"):
        return _payload(job["transcript_id"], timestamps)
    return _job_view(job)


@mcp.tool()
async def transcribe_batch(urls_or_text: str) -> dict:
    """Queue many videos at once. Pass links separated by spaces or new lines (any pasted text works).

    Profile and playlist links are expanded automatically (up to 50 videos each). Returns a batch_id;
    poll get_batch until finished is true.
    """
    result = await worker.submit_text(urls_or_text)
    return {**result, "queued": len(result["job_ids"])}


@mcp.tool()
async def expand_collection(url: str, limit: int = 25) -> dict:
    """List the video links inside a TikTok profile, YouTube channel/playlist or similar, without transcribing."""
    import asyncio
    try:
        links = await asyncio.to_thread(acquirer.expand, url, max(1, min(limit, 50)))
    except KnownFailure as exc:
        return {"error_code": exc.code, "hint": hint(exc.code)}
    return {"count": len(links), "urls": links}


@mcp.tool()
def get_job(job_id: int, timestamps: bool = False) -> dict:
    """Check one transcription job. When it is done, the transcript is included."""
    job = library.get_job(job_id)
    if job is None:
        return {"error_code": "NOT_FOUND", "hint": f"No job with id {job_id}."}
    if job["status"] == "done" and job.get("transcript_id"):
        return {"job_id": job_id, "status": "done", **_payload(job["transcript_id"], timestamps)}
    return _job_view(job)


@mcp.tool()
def get_batch(batch_id: str) -> dict:
    """Progress of a batch: counts per status and, per job, the transcript_id or the error."""
    summary = library.batch_summary(batch_id)
    if summary is None:
        return {"error_code": "NOT_FOUND", "hint": f"No batch with id {batch_id}."}
    return {**{k: summary[k] for k in ("batch_id", "total", "pending", "finished", "counts")},
            "jobs": [_job_view(j) for j in summary["jobs"]]}


@mcp.tool()
def search_library(query: str, platform: Literal["tiktok", "instagram", "youtube"] | None = None,
                   author: str | None = None, limit: int = 10) -> dict:
    """Full-text search across saved transcripts, titles and authors. Returns matches with a snippet."""
    found = library.list_library(q=query, platform=platform, author=author, limit=max(1, min(limit, 50)))
    return {"total": found["total"], "results": [_brief(i) for i in found["items"]]}


@mcp.tool()
def list_library(folder: str | None = None, tag: str | None = None,
                 platform: Literal["tiktok", "instagram", "youtube"] | None = None,
                 limit: int = 20, offset: int = 0) -> dict:
    """Browse saved transcripts, newest first, optionally by folder name, tag or platform."""
    folder_id = None
    if folder:
        match = next((f for f in library.list_folders() if f["name"].lower() == folder.lower()), None)
        if match is None:
            return {"total": 0, "results": [], "folders": [f["name"] for f in library.list_folders()]}
        folder_id = match["id"]
    found = library.list_library(folder_id=folder_id, tag=tag, platform=platform,
                                 limit=max(1, min(limit, 100)), offset=offset)
    return {"total": found["total"], "results": [_brief(i) for i in found["items"]],
            "folders": [f["name"] for f in library.list_folders()], "tags": [t["tag"] for t in library.list_tags()]}


def _brief(item: dict) -> dict:
    out = {k: item[k] for k in ("id", "title", "author", "platform", "url", "duration_s", "language", "folder", "tags")}
    out["views"] = item["stats"].get("view_count")
    if item.get("snippet"):
        out["snippet"] = item["snippet"]
    return out


@mcp.tool()
def get_transcript(transcript_id: int, timestamps: bool = False, include_stats: bool = True) -> dict:
    """Read a saved transcript. With include_stats you also get views, likes, comments and per-view ratios."""
    return _payload(transcript_id, timestamps, include_stats)


@mcp.tool()
def export_transcript(transcript_id: int, format: Format = "srt", timestamps: bool = False) -> dict:
    """Render a transcript as txt, srt, vtt, json, csv or md and return the file content."""
    item = library.get_transcript(transcript_id)
    if item is None:
        return {"error_code": "NOT_FOUND", "hint": f"No transcript with id {transcript_id}."}
    return {"filename": exports.filename(item, format), "content": exports.render(item, format, timestamps)}


@mcp.tool()
def organize(transcript_id: int, folder: str | None = None, tags: list[str] | None = None) -> dict:
    """File a transcript into a folder (created if new) and/or replace its tags."""
    if not library.organize(transcript_id, folder=folder, tags=tags):
        return {"error_code": "NOT_FOUND", "hint": f"No transcript with id {transcript_id}."}
    item = library.get_transcript(transcript_id)
    return {"id": transcript_id, "folder": item["folder"], "tags": item["tags"]}


@mcp.tool()
def get_playbook(kind: Kind) -> str:
    """Instructions for a writing task. Call this BEFORE generating hooks ("hooks"), writing a script
    modelled on a video ("remix"), or explaining a video's performance ("virality"), then follow it."""
    return (PLAYBOOKS / f"{kind}.md").read_text(encoding="utf-8")


@mcp.tool()
def check_originality(draft: str, transcript_id: int) -> dict:
    """Measure how much of a draft is copied word-for-word from a saved transcript.

    Returns overlap (0-1, share of the draft's 5-word sequences found in the source), a verdict
    (original / borrowed / too_similar) and the longest copied phrases to rewrite.
    """
    item = library.get_transcript(transcript_id)
    if item is None:
        return {"error_code": "NOT_FOUND", "hint": f"No transcript with id {transcript_id}."}
    return originality.check(draft, item["text"])


# Prompts: shown as ready-made commands in hosts that support MCP prompts (Claude).
# Hosts that only support tools (ChatGPT) reach the same text through get_playbook.

def _prompt(kind: str, lead: str) -> str:
    return f"{lead}\n\nFollow this playbook exactly:\n\n{(PLAYBOOKS / f'{kind}.md').read_text(encoding='utf-8')}"


@mcp.prompt(title="Generate hooks")
def generate_hooks(topic_or_transcript_id: str, niche: str = "", tone: str = "") -> str:
    """Ten opening hooks for a topic, or inspired by a saved transcript."""
    return _prompt("hooks", f"Write hooks. Topic or reference transcript id: {topic_or_transcript_id}. "
                            f"Niche: {niche or 'ask me'}. Tone: {tone or 'match my usual voice'}.")


@mcp.prompt(title="Remix a script")
def remix_script(transcript_id: str, my_topic: str = "") -> str:
    """A new script on your topic that follows the structure of a saved video."""
    return _prompt("remix", f"Reference transcript id: {transcript_id}. My topic: {my_topic or 'ask me'}.")


@mcp.prompt(title="Explain virality")
def explain_virality(transcript_id: str) -> str:
    """Why a saved video may have performed the way it did."""
    return _prompt("virality", f"Explain the performance of transcript id {transcript_id}.")
