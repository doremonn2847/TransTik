"""In-process job worker. Jobs live in SQLite, so a restart picks up where it stopped."""
from __future__ import annotations

import asyncio
import logging

from . import config, library, pipeline, urls
from .acquire import acquirer
from .errors import KnownFailure

log = logging.getLogger("worker")
MAX_ATTEMPTS = 3
RETRYABLE = {"RATE_LIMITED", "NETWORK"}

_queue: asyncio.Queue[int] | None = None
_tasks: list[asyncio.Task] = []


async def _run(job_id: int) -> None:
    try:
        transcript_id = await asyncio.to_thread(pipeline.run_job, job_id)
        library.set_job(job_id, "done", transcript_id=transcript_id)
    except KnownFailure as exc:
        attempts = library.bump_attempts(job_id)
        if exc.code in RETRYABLE and attempts < MAX_ATTEMPTS:
            delay = (30 if exc.code == "RATE_LIMITED" else 5) * 2 ** (attempts - 1)
            log.info("job %s hit %s, retry in %ss", job_id, exc.code, delay)
            library.set_job(job_id, "queued", error_code=exc.code, error_detail=f"retrying in {delay}s")
            asyncio.get_running_loop().call_later(delay, _queue.put_nowait, job_id)
        else:
            library.set_job(job_id, "failed", error_code=exc.code, error_detail=exc.detail or None)
    except Exception as exc:
        log.exception("job %s crashed", job_id)
        library.set_job(job_id, "failed", error_code="FAILED", error_detail=str(exc)[:300])


async def _loop() -> None:
    assert _queue is not None
    while True:
        job_id = await _queue.get()
        try:
            await _run(job_id)
        finally:
            _queue.task_done()


async def start() -> None:
    global _queue
    _queue = asyncio.Queue()
    for job_id in library.unfinished_job_ids():
        _queue.put_nowait(job_id)
    _tasks.extend(asyncio.create_task(_loop()) for _ in range(config.WORKER_CONCURRENCY))


async def stop() -> None:
    for task in _tasks:
        task.cancel()
    _tasks.clear()


def enqueue(url_list: list[str], force_asr: bool = False) -> tuple[str, list[int]]:
    assert _queue is not None, "worker not started"
    batch_id, ids = library.create_jobs(url_list, force_asr)
    for job_id in ids:
        _queue.put_nowait(job_id)
    return batch_id, ids


def requeue(job_id: int) -> None:
    assert _queue is not None
    library.set_job(job_id, "queued")
    _queue.put_nowait(job_id)


async def submit_text(text: str, force_asr: bool = False) -> dict:
    """Queue every link found in pasted text. Profile/playlist links are expanded first."""
    found = urls.extract_urls(text)
    final: list[str] = []
    notes: list[str] = []
    for url in found:
        if urls.is_collection(url):
            try:
                entries = await asyncio.to_thread(acquirer.expand, url, config.COLLECTION_LIMIT)
            except KnownFailure as exc:
                notes.append(f"Could not expand {url}: {exc.code}")
                continue
            notes.append(f"Expanded {url} into {len(entries)} videos")
            final.extend(entries)
        else:
            final.append(url)
    seen: set[str] = set()
    unique = []
    for url in final:
        key = "|".join(urls.classify(url) or ("", url))
        if key not in seen:
            seen.add(key)
            unique.append(url)
    if not unique:
        return {"batch_id": None, "job_ids": [], "notes": notes or ["No video links found."]}
    batch_id, ids = enqueue(unique, force_asr)
    return {"batch_id": batch_id, "job_ids": ids, "notes": notes}


async def wait_for(job_id: int, timeout: float) -> dict:
    """Poll until the job finishes or the timeout passes; returns the job either way."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        job = library.get_job(job_id)
        if job is None or job["status"] in ("done", "failed") or loop.time() >= deadline:
            return job or {"id": job_id, "status": "failed", "error_code": "FAILED"}
        await asyncio.sleep(0.4)
