"""
db.py — SQLite persistence layer.

Stores job URLs, scores, and verdicts so the agent never re-alerts the same job.
"""
import json
import os
import sqlite3
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_DB_PATH: str = os.getenv("DB_PATH", "data/jobs.db")


def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(_DB_PATH) or ".", exist_ok=True)
    c = sqlite3.connect(_DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                url         TEXT    UNIQUE NOT NULL,
                title       TEXT,
                company     TEXT,
                location    TEXT,
                description TEXT,
                fit_score   INTEGER,
                verdict     TEXT,
                reasons     TEXT,   -- JSON array
                concerns    TEXT,   -- JSON array
                notified    INTEGER DEFAULT 0,
                seen_at     TEXT    DEFAULT (datetime('now'))
            )
        """)
        c.commit()
    logger.info("DB ready: %s", _DB_PATH)


def is_seen(url: str) -> bool:
    """Return True if this job URL is already in the database."""
    with _conn() as c:
        row = c.execute("SELECT id FROM jobs WHERE url = ?", (url,)).fetchone()
        return row is not None


def save_job(job: Dict, score: Optional[Dict] = None) -> None:
    """Insert a job record (ignores duplicates via UNIQUE constraint)."""
    with _conn() as c:
        c.execute("""
            INSERT OR IGNORE INTO jobs
                (url, title, company, location, description,
                 fit_score, verdict, reasons, concerns)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job.get("url", ""),
            job.get("title", ""),
            job.get("company", ""),
            job.get("location", ""),
            (job.get("description") or "")[:2000],
            score.get("fit_score")               if score else None,
            score.get("verdict")                 if score else None,
            json.dumps(score.get("reasons",  [])) if score else None,
            json.dumps(score.get("concerns", [])) if score else None,
        ))
        c.commit()


def mark_notified(url: str) -> None:
    with _conn() as c:
        c.execute("UPDATE jobs SET notified = 1 WHERE url = ?", (url,))
        c.commit()


def recent_jobs(days: int = 7) -> List[Dict]:
    """Return all jobs seen in the last N days, ordered by fit_score desc."""
    with _conn() as c:
        rows = c.execute("""
            SELECT * FROM jobs
            WHERE seen_at >= datetime('now', ?)
            ORDER BY fit_score DESC NULLS LAST
        """, (f"-{days} days",)).fetchall()
        return [dict(r) for r in rows]
