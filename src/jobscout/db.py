"""SQLite-backed job store: the data layer behind the MCP tools.

Kept free of any MCP / LLM code so it can be unit-tested in isolation.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEED = PACKAGE_ROOT / "data" / "jobs_sample.json"
DEFAULT_DB = PACKAGE_ROOT / "data" / "jobscout.db"

# Map common spellings to one canonical skill name so counts and matching are fair.
SKILL_ALIASES = {
    "genai": "llm",
    "large language models": "llm",
    "llms": "llm",
    "lang chain": "langchain",
    "lang graph": "langgraph",
    "model context protocol": "mcp",
    "huggingface": "hugging face",
    "sklearn": "scikit-learn",
    "k8s": "kubernetes",
    "openai": "openai api",
    "vector db": "vector database",
    "ml": "machine learning",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT NOT NULL,
    remote INTEGER NOT NULL DEFAULT 0,
    min_exp INTEGER NOT NULL,
    max_exp INTEGER NOT NULL,
    salary_min_lpa REAL,
    salary_max_lpa REAL,
    skills TEXT NOT NULL,
    description TEXT,
    posted_date TEXT
);
CREATE TABLE IF NOT EXISTS shortlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL UNIQUE REFERENCES jobs(id),
    note TEXT,
    created_at TEXT NOT NULL
);
"""


def normalize_skill(skill: str) -> str:
    s = " ".join(skill.strip().lower().split())
    return SKILL_ALIASES.get(s, s)


def connect(db_path: str | Path | None = None, seed_path: str | Path | None = None) -> sqlite3.Connection:
    """Open the database, creating and seeding it on first use."""
    db_path = Path(db_path or os.environ.get("JOBSCOUT_DB", DEFAULT_DB))
    seed_path = Path(seed_path or os.environ.get("JOBSCOUT_SEED", DEFAULT_SEED))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0 and seed_path.exists():
        load_jobs(conn, json.loads(seed_path.read_text()))
    return conn


def load_jobs(conn: sqlite3.Connection, jobs: list[dict[str, Any]]) -> int:
    rows = [
        (
            j["id"], j["title"], j["company"], j["location"], int(bool(j.get("remote"))),
            int(j["min_exp"]), int(j["max_exp"]), j.get("salary_min_lpa"), j.get("salary_max_lpa"),
            json.dumps(sorted({normalize_skill(s) for s in j.get("skills", [])})),
            j.get("description", ""), j.get("posted_date"),
        )
        for j in jobs
    ]
    conn.executemany("INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    return len(rows)


def _row_to_job(row: sqlite3.Row) -> dict[str, Any]:
    job = dict(row)
    job["remote"] = bool(job["remote"])
    job["skills"] = json.loads(job["skills"])
    return job


def search_jobs(
    conn: sqlite3.Connection,
    query: str | None = None,
    location: str | None = None,
    years_experience: float | None = None,
    remote_only: bool = False,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Filter jobs by keyword (title/skills/description), location and experience fit."""
    sql = "SELECT * FROM jobs WHERE 1=1"
    params: list[Any] = []
    if query:
        for term in query.lower().split():
            sql += " AND (lower(title) LIKE ? OR lower(skills) LIKE ? OR lower(description) LIKE ?)"
            like = f"%{normalize_skill(term)}%"
            params += [like, like, like]
    if location:
        sql += " AND lower(location) = ?"
        params.append(location.strip().lower())
    if years_experience is not None:
        sql += " AND min_exp <= ? AND max_exp >= ?"
        params += [years_experience, years_experience]
    if remote_only:
        sql += " AND remote = 1"
    sql += " ORDER BY posted_date DESC LIMIT ?"
    params.append(max(1, min(int(limit), 50)))
    return [_row_to_job(r) for r in conn.execute(sql, params)]


def get_job(conn: sqlite3.Connection, job_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_job(row) if row else None


def skill_demand(
    conn: sqlite3.Connection,
    query: str | None = None,
    location: str | None = None,
    top_n: int = 10,
) -> dict[str, Any]:
    """Count how often each skill appears across matching jobs."""
    jobs = search_jobs(conn, query=query, location=location, limit=50)
    counts = Counter(skill for job in jobs for skill in job["skills"])
    total = len(jobs)
    return {
        "jobs_analysed": total,
        "top_skills": [
            {"skill": s, "jobs": c, "share": round(c / total, 2)} for s, c in counts.most_common(top_n)
        ],
    }


def skill_gap(conn: sqlite3.Connection, job_id: str, my_skills: list[str]) -> dict[str, Any] | None:
    """Compare a candidate's skills with what a job asks for."""
    job = get_job(conn, job_id)
    if job is None:
        return None
    mine = {normalize_skill(s) for s in my_skills}
    required = set(job["skills"])
    matched = sorted(required & mine)
    missing = sorted(required - mine)
    return {
        "job_id": job_id,
        "title": job["title"],
        "company": job["company"],
        "match_score": round(len(matched) / len(required), 2) if required else 0.0,
        "matched": matched,
        "missing": missing,
    }


def add_to_shortlist(conn: sqlite3.Connection, job_id: str, note: str = "") -> dict[str, Any]:
    if get_job(conn, job_id) is None:
        raise ValueError(f"Unknown job id: {job_id}")
    conn.execute(
        "INSERT INTO shortlist (job_id, note, created_at) VALUES (?, ?, ?) "
        "ON CONFLICT(job_id) DO UPDATE SET note = excluded.note",
        (job_id, note, datetime.now(timezone.utc).isoformat(timespec="seconds")),
    )
    conn.commit()
    return {"job_id": job_id, "note": note, "status": "saved"}


def list_shortlist(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT s.job_id, s.note, s.created_at, j.title, j.company, j.location "
        "FROM shortlist s JOIN jobs j ON j.id = s.job_id ORDER BY s.created_at DESC"
    )
    return [dict(r) for r in rows]


def market_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    by_loc = conn.execute(
        "SELECT location, COUNT(*) AS n FROM jobs GROUP BY location ORDER BY n DESC"
    ).fetchall()
    by_title = conn.execute(
        "SELECT title, COUNT(*) AS n, ROUND(AVG(salary_max_lpa), 1) AS avg_max_lpa "
        "FROM jobs GROUP BY title ORDER BY n DESC"
    ).fetchall()
    return {
        "total_jobs": total,
        "by_location": {r["location"]: r["n"] for r in by_loc},
        "by_title": [dict(r) for r in by_title],
    }
