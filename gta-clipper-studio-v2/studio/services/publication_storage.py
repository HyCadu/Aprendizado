"""Histórico transacional local de publicações YouTube em SQLite."""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from ..integrations.models import DuplicatePublication
from ..storage import DATA_DIR

PUBLICATION_DB = DATA_DIR / "publications.sqlite3"
ALLOWED_FIELDS = {"channel_name", "title", "description", "video_id", "url", "uploaded_at", "publish_at",
                  "visibility", "status", "error", "file_path"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class PublicationStorage:
    def __init__(self, path: str | Path = PUBLICATION_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        return db

    @contextmanager
    def _database(self):
        db = self._connect()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _initialize(self):
        with self._database() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS publications (
                id TEXT PRIMARY KEY, clip_id TEXT NOT NULL, file_hash TEXT NOT NULL,
                platform TEXT NOT NULL, channel_id TEXT NOT NULL, channel_name TEXT NOT NULL,
                title TEXT NOT NULL, description TEXT NOT NULL, video_id TEXT, url TEXT,
                uploaded_at TEXT, publish_at TEXT, visibility TEXT NOT NULL, status TEXT NOT NULL,
                error TEXT, file_path TEXT NOT NULL, created_at TEXT NOT NULL
            )""")
            db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS uq_publication_file_channel
                ON publications(file_hash, channel_id)
                WHERE status NOT IN ('failed', 'cancelled')""")
            db.execute("CREATE INDEX IF NOT EXISTS ix_publication_created ON publications(created_at DESC)")

    def create(self, *, clip_id: str, file_hash: str, platform: str, channel_id: str, channel_name: str,
               title: str, description: str, publish_at: str | None, visibility: str, status: str,
               file_path: str) -> dict:
        record_id = str(uuid.uuid4())
        created = utc_now()
        try:
            with self._database() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("""INSERT INTO publications
                    (id, clip_id, file_hash, platform, channel_id, channel_name, title, description,
                     publish_at, visibility, status, file_path, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                           (record_id, clip_id, file_hash, platform, channel_id, channel_name, title,
                            description, publish_at, visibility, status, file_path, created))
        except sqlite3.IntegrityError:
            raise DuplicatePublication() from None
        return self.get(record_id)

    def update(self, record_id: str, **values) -> dict | None:
        values = {key: value for key, value in values.items() if key in ALLOWED_FIELDS}
        if not values:
            return self.get(record_id)
        columns = ", ".join(f"{key} = ?" for key in values)
        with self._database() as db:
            db.execute(f"UPDATE publications SET {columns} WHERE id = ?", (*values.values(), record_id))
        return self.get(record_id)

    def get(self, record_id: str) -> dict | None:
        with self._database() as db:
            row = db.execute("SELECT * FROM publications WHERE id = ?", (record_id,)).fetchone()
        return dict(row) if row else None

    def list_recent(self, limit: int = 100) -> list[dict]:
        with self._database() as db:
            rows = db.execute("SELECT * FROM publications ORDER BY created_at DESC LIMIT ?",
                              (max(1, min(limit, 500)),)).fetchall()
        return [dict(row) for row in rows]

    def pending_reconciliation(self) -> list[dict]:
        with self._database() as db:
            rows = db.execute("""SELECT * FROM publications WHERE video_id IS NOT NULL
                AND status IN ('processing', 'unknown') ORDER BY created_at ASC LIMIT 50""").fetchall()
        return [dict(row) for row in rows]
