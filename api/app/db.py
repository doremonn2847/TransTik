"""SQLite storage. One file, WAL mode, FTS5 for full-text search."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from . import config

SCHEMA = """
create table if not exists videos (
  id integer primary key,
  platform text not null,
  platform_video_id text not null,
  canonical_url text not null,
  title text, description text, author_handle text, duration_s integer,
  thumbnail_file text,
  stats_json text not null default '{}',
  fetched_at text not null default (datetime('now')),
  unique (platform, platform_video_id)
);
create table if not exists folders (
  id integer primary key,
  name text not null unique collate nocase
);
create table if not exists transcripts (
  id integer primary key,
  video_id integer not null unique references videos(id) on delete cascade,
  source text not null,
  language text,
  segments_json text not null,
  edited_segments_json text,
  full_text text not null,
  model text,
  folder_id integer references folders(id) on delete set null,
  created_at text not null default (datetime('now')),
  updated_at text not null default (datetime('now'))
);
create table if not exists tags (
  transcript_id integer not null references transcripts(id) on delete cascade,
  tag text not null collate nocase,
  primary key (transcript_id, tag)
);
create table if not exists jobs (
  id integer primary key,
  batch_id text,
  input_url text not null,
  status text not null default 'queued',
  error_code text, error_detail text,
  force_asr integer not null default 0,
  attempts integer not null default 0,
  transcript_id integer references transcripts(id) on delete set null,
  created_at text not null default (datetime('now')),
  finished_at text
);
create index if not exists jobs_batch on jobs(batch_id);
create virtual table if not exists transcripts_fts using fts5(
  full_text, title, author, tokenize = "unicode61 remove_diacritics 2"
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    return conn


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    config.ensure_dirs()
    with tx() as conn:
        conn.execute("pragma journal_mode = wal")
        conn.executescript(SCHEMA)
