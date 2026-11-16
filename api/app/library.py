"""Library services: the single place that reads and writes transcripts, folders, tags, jobs.

Both the REST routes and the MCP tools call these functions, so they always agree.
"""
from __future__ import annotations

import json
import re
import uuid

from . import captions, db, urls
from .errors import hint

# ---------- transcripts ----------


def find_cached(platform: str, video_id: str) -> int | None:
    with db.tx() as conn:
        row = conn.execute(
            "select t.id from transcripts t join videos v on v.id = t.video_id "
            "where v.platform = ? and v.platform_video_id = ?", (platform, video_id)).fetchone()
    return row["id"] if row else None


def _reindex(conn, transcript_id: int) -> None:
    row = conn.execute(
        "select t.full_text, v.title, v.author_handle from transcripts t join videos v on v.id = t.video_id "
        "where t.id = ?", (transcript_id,)).fetchone()
    conn.execute("delete from transcripts_fts where rowid = ?", (transcript_id,))
    if row:
        conn.execute("insert into transcripts_fts(rowid, full_text, title, author) values (?,?,?,?)",
                     (transcript_id, row["full_text"], row["title"] or "", row["author_handle"] or ""))


def save_transcript(platform: str, video_id: str, meta, segments: list[dict], language: str | None,
                    source: str, model: str | None, thumbnail_file: str | None) -> int:
    """Insert or replace the transcript for a video. Replacing clears user edits."""
    with db.tx() as conn:
        conn.execute(
            "insert into videos(platform, platform_video_id, canonical_url, title, description, author_handle, "
            "duration_s, thumbnail_file, stats_json) values (?,?,?,?,?,?,?,?,?) "
            "on conflict(platform, platform_video_id) do update set title=excluded.title, "
            "description=excluded.description, author_handle=excluded.author_handle, duration_s=excluded.duration_s, "
            "thumbnail_file=coalesce(excluded.thumbnail_file, videos.thumbnail_file), "
            "stats_json=excluded.stats_json, fetched_at=datetime('now')",
            (platform, video_id, urls.canonical(platform, video_id, meta.author), meta.title, meta.description,
             meta.author, meta.duration, thumbnail_file, json.dumps(meta.stats)))
        vid = conn.execute("select id from videos where platform = ? and platform_video_id = ?",
                           (platform, video_id)).fetchone()["id"]
        conn.execute(
            "insert into transcripts(video_id, source, language, segments_json, full_text, model) values (?,?,?,?,?,?) "
            "on conflict(video_id) do update set source=excluded.source, language=excluded.language, "
            "segments_json=excluded.segments_json, edited_segments_json=null, full_text=excluded.full_text, "
            "model=excluded.model, updated_at=datetime('now')",
            (vid, source, language, json.dumps(segments, ensure_ascii=False), captions.full_text(segments), model))
        tid = conn.execute("select id from transcripts where video_id = ?", (vid,)).fetchone()["id"]
        _reindex(conn, tid)
    return tid


_SELECT = (
    "select t.id, t.source, t.language, t.model, t.created_at, t.updated_at, t.folder_id, f.name as folder, "
    "t.edited_segments_json is not null as edited, length(t.full_text) as chars, "
    "v.platform, v.platform_video_id, v.canonical_url, v.title, v.description, v.author_handle, v.duration_s, "
    "v.thumbnail_file, v.stats_json, v.fetched_at "
    "from transcripts t join videos v on v.id = t.video_id left join folders f on f.id = t.folder_id ")


def _stats(raw: str) -> dict:
    stats = json.loads(raw or "{}")
    views = stats.get("view_count")
    if views:
        for key, label in (("like_count", "likes_per_view"), ("comment_count", "comments_per_view"),
                           ("repost_count", "shares_per_view")):
            if stats.get(key) is not None:
                stats[label] = round(stats[key] / views, 5)
    return stats


def _summary(row, tags: list[str]) -> dict:
    return {
        "id": row["id"], "platform": row["platform"], "url": row["canonical_url"], "title": row["title"],
        "author": row["author_handle"], "duration_s": row["duration_s"], "language": row["language"],
        "source": row["source"], "model": row["model"], "edited": bool(row["edited"]), "chars": row["chars"],
        "folder_id": row["folder_id"], "folder": row["folder"], "tags": tags,
        "thumbnail": f"/api/thumbs/{row['thumbnail_file']}" if row["thumbnail_file"] else None,
        "stats": _stats(row["stats_json"]), "created_at": row["created_at"], "updated_at": row["updated_at"],
    }


def _tags_for(conn, ids: list[int]) -> dict[int, list[str]]:
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    out: dict[int, list[str]] = {i: [] for i in ids}
    for row in conn.execute(f"select transcript_id, tag from tags where transcript_id in ({marks}) order by tag", ids):
        out[row["transcript_id"]].append(row["tag"])
    return out


def get_transcript(transcript_id: int) -> dict | None:
    with db.tx() as conn:
        row = conn.execute(_SELECT + "where t.id = ?", (transcript_id,)).fetchone()
        if not row:
            return None
        raw = conn.execute("select segments_json, edited_segments_json from transcripts where id = ?",
                           (transcript_id,)).fetchone()
        tags = _tags_for(conn, [transcript_id])[transcript_id]
    original = json.loads(raw["segments_json"])
    segments = json.loads(raw["edited_segments_json"]) if raw["edited_segments_json"] else original
    return {**_summary(row, tags), "description": row["description"], "segments": segments,
            "text": captions.full_text(segments)}


def fts_query(text: str) -> str | None:
    """Turn free text into a safe FTS5 query: every word must match, last word is a prefix."""
    tokens = re.findall(r"\w+", text, flags=re.UNICODE)
    if not tokens:
        return None
    quoted = [f'"{t}"' for t in tokens]
    quoted[-1] += "*"
    return " ".join(quoted)


def list_library(q: str | None = None, platform: str | None = None, folder_id: int | None = None,
                 tag: str | None = None, source: str | None = None, author: str | None = None,
                 limit: int = 50, offset: int = 0) -> dict:
    where, params = [], []
    match = fts_query(q) if q else None
    base = _SELECT
    snippet = "null as snippet"
    if match:
        base = base.replace("from transcripts t", "from transcripts_fts join transcripts t on t.id = transcripts_fts.rowid", 1)
        snippet = "snippet(transcripts_fts, 0, '[', ']', ' … ', 18) as snippet"
        where.append("transcripts_fts match ?")
        params.append(match)
    for clause, value in (("v.platform = ?", platform), ("t.folder_id = ?", folder_id), ("t.source = ?", source),
                          ("v.author_handle = ? collate nocase", author.lstrip("@") if author else None),
                          ("exists (select 1 from tags g where g.transcript_id = t.id and g.tag = ?)", tag)):
        if value not in (None, ""):
            where.append(clause)
            params.append(value)
    cond = ("where " + " and ".join(where)) if where else ""
    order = "order by transcripts_fts.rank" if match else "order by t.created_at desc, t.id desc"
    sql = base.replace("select ", f"select {snippet}, ", 1) + cond
    count_sql = "select count(*) " + base[base.index("from "):] + cond
    with db.tx() as conn:
        total = conn.execute(count_sql, params).fetchone()[0]
        rows = conn.execute(f"{sql} {order} limit ? offset ?", [*params, min(limit, 200), offset]).fetchall()
        tags = _tags_for(conn, [r["id"] for r in rows])
    return {"total": total, "items": [{**_summary(r, tags[r["id"]]), "snippet": r["snippet"]} for r in rows]}


def update_segments(transcript_id: int, segments: list[dict] | None) -> bool:
    """Store user corrections (None restores the original)."""
    with db.tx() as conn:
        row = conn.execute("select segments_json from transcripts where id = ?", (transcript_id,)).fetchone()
        if not row:
            return False
        clean = captions.normalize(segments) if segments is not None else None
        effective = clean if clean is not None else json.loads(row["segments_json"])
        conn.execute("update transcripts set edited_segments_json = ?, full_text = ?, updated_at = datetime('now') "
                     "where id = ?", (json.dumps(clean, ensure_ascii=False) if clean is not None else None,
                                      captions.full_text(effective), transcript_id))
        _reindex(conn, transcript_id)
    return True


def organize(transcript_id: int, folder: str | None = None, folder_id: int | None = None,
             tags: list[str] | None = None, clear_folder: bool = False) -> bool:
    with db.tx() as conn:
        if not conn.execute("select 1 from transcripts where id = ?", (transcript_id,)).fetchone():
            return False
        if folder:
            conn.execute("insert or ignore into folders(name) values (?)", (folder.strip(),))
            folder_id = conn.execute("select id from folders where name = ?", (folder.strip(),)).fetchone()["id"]
        if folder_id is not None or clear_folder:
            conn.execute("update transcripts set folder_id = ? where id = ?", (folder_id, transcript_id))
        if tags is not None:
            conn.execute("delete from tags where transcript_id = ?", (transcript_id,))
            for tag in {t.strip().lstrip("#").lower() for t in tags if t.strip()}:
                conn.execute("insert or ignore into tags(transcript_id, tag) values (?,?)", (transcript_id, tag))
    return True


def delete_transcripts(ids: list[int]) -> int:
    if not ids:
        return 0
    marks = ",".join("?" * len(ids))
    with db.tx() as conn:
        conn.execute(f"delete from transcripts_fts where rowid in ({marks})", ids)
        cur = conn.execute(
            f"delete from videos where id in (select video_id from transcripts where id in ({marks}))", ids)
    return cur.rowcount


def list_folders() -> list[dict]:
    with db.tx() as conn:
        rows = conn.execute("select f.id, f.name, count(t.id) as count from folders f "
                            "left join transcripts t on t.folder_id = f.id group by f.id order by f.name").fetchall()
    return [dict(r) for r in rows]


def create_folder(name: str) -> dict:
    with db.tx() as conn:
        conn.execute("insert or ignore into folders(name) values (?)", (name.strip(),))
        row = conn.execute("select id, name from folders where name = ?", (name.strip(),)).fetchone()
    return dict(row)


def delete_folder(folder_id: int) -> None:
    with db.tx() as conn:
        conn.execute("delete from folders where id = ?", (folder_id,))


def list_tags() -> list[dict]:
    with db.tx() as conn:
        rows = conn.execute("select tag, count(*) as count from tags group by tag order by count desc, tag").fetchall()
    return [dict(r) for r in rows]


# ---------- jobs ----------

ACTIVE = ("queued", "resolving", "fetching", "transcribing")


def _job(row) -> dict:
    out = dict(row)
    out["force_asr"] = bool(out["force_asr"])
    out["hint"] = hint(out["error_code"])
    return out


_JOB_SELECT = ("select j.*, v.title, v.author_handle as author, v.platform from jobs j "
               "left join transcripts t on t.id = j.transcript_id left join videos v on v.id = t.video_id ")


def create_jobs(url_list: list[str], force_asr: bool = False) -> tuple[str, list[int]]:
    batch_id = uuid.uuid4().hex[:12]
    ids = []
    with db.tx() as conn:
        for url in url_list:
            cur = conn.execute("insert into jobs(batch_id, input_url, force_asr) values (?,?,?)",
                               (batch_id, url, int(force_asr)))
            ids.append(cur.lastrowid)
    return batch_id, ids


def get_job(job_id: int) -> dict | None:
    with db.tx() as conn:
        row = conn.execute(_JOB_SELECT + "where j.id = ?", (job_id,)).fetchone()
    return _job(row) if row else None


def list_jobs(batch_id: str | None = None, limit: int = 100) -> list[dict]:
    with db.tx() as conn:
        if batch_id:
            rows = conn.execute(_JOB_SELECT + "where j.batch_id = ? order by j.id", (batch_id,)).fetchall()
        else:
            rows = conn.execute(_JOB_SELECT + "order by j.id desc limit ?", (limit,)).fetchall()
    return [_job(r) for r in rows]


def set_job(job_id: int, status: str, error_code: str | None = None, error_detail: str | None = None,
            transcript_id: int | None = None) -> None:
    finished = status in ("done", "failed")
    with db.tx() as conn:
        conn.execute(
            "update jobs set status = ?, error_code = ?, error_detail = ?, "
            "transcript_id = coalesce(?, transcript_id), "
            "finished_at = case when ? then datetime('now') else null end where id = ?",
            (status, error_code, error_detail, transcript_id, finished, job_id))


def bump_attempts(job_id: int) -> int:
    with db.tx() as conn:
        conn.execute("update jobs set attempts = attempts + 1 where id = ?", (job_id,))
        return conn.execute("select attempts from jobs where id = ?", (job_id,)).fetchone()["attempts"]


def unfinished_job_ids() -> list[int]:
    marks = ",".join("?" * len(ACTIVE))
    with db.tx() as conn:
        conn.execute(f"update jobs set status = 'queued' where status in ({marks})", ACTIVE)
        return [r["id"] for r in conn.execute("select id from jobs where status = 'queued' order by id")]


def clear_finished_jobs() -> int:
    with db.tx() as conn:
        return conn.execute("delete from jobs where status in ('done', 'failed')").rowcount


def batch_summary(batch_id: str) -> dict | None:
    jobs = list_jobs(batch_id=batch_id)
    if not jobs:
        return None
    counts: dict[str, int] = {}
    for job in jobs:
        counts[job["status"]] = counts.get(job["status"], 0) + 1
    pending = sum(counts.get(s, 0) for s in ACTIVE)
    return {"batch_id": batch_id, "total": len(jobs), "pending": pending, "finished": pending == 0,
            "counts": counts, "jobs": jobs}
