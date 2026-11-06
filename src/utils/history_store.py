"""Local, transactional translation history. Images and API keys are never stored."""
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import uuid


class HistoryStore:
    def __init__(self, directory):
        self.path = Path(directory) / "history.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS translations (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, original TEXT NOT NULL,
                translated TEXT NOT NULL, source_lang TEXT NOT NULL, target_lang TEXT NOT NULL,
                provider TEXT NOT NULL, model TEXT NOT NULL, kind TEXT NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS translations_time ON translations(created_at DESC)")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def add(self, result, target_lang, provider, kind, limit=500):
        record_id = uuid.uuid4().hex
        with self._connect() as db:
            db.execute("INSERT INTO translations VALUES (?,?,?,?,?,?,?,?,?)", (
                record_id, datetime.now().astimezone().isoformat(timespec="seconds"),
                result.get("extracted_text", ""), result["translated_text"],
                result.get("source_language") or "auto", target_lang, provider,
                result.get("last_used_model") or "", kind))
            db.execute("DELETE FROM translations WHERE id NOT IN (SELECT id FROM translations ORDER BY created_at DESC, rowid DESC LIMIT ?)", (limit,))
        return record_id

    def search(self, query="", limit=500):
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        with self._connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT id,created_at,substr(original,1,80) AS original,substr(translated,1,80) AS translated,"
                "source_lang,target_lang,provider,model,kind FROM translations "
                "WHERE original LIKE ? ESCAPE '\\' OR translated LIKE ? ESCAPE '\\' "
                "ORDER BY created_at DESC,rowid DESC LIMIT ?", (f"%{escaped}%", f"%{escaped}%", limit))]

    def get(self, record_id):
        with self._connect() as db:
            row = db.execute("SELECT * FROM translations WHERE id=?", (record_id,)).fetchone()
            return dict(row) if row else None

    def delete(self, record_id):
        with self._connect() as db:
            db.execute("DELETE FROM translations WHERE id=?", (record_id,))

    def clear(self):
        with self._connect() as db:
            db.execute("DELETE FROM translations")

    def trim(self, limit):
        with self._connect() as db:
            db.execute("DELETE FROM translations WHERE id NOT IN (SELECT id FROM translations ORDER BY created_at DESC,rowid DESC LIMIT ?)", (limit,))
