"""JobScout MCP server.

Exposes job-market tools, a stats resource and a prompt over the Model Context
Protocol. Works with any MCP client (Cursor, VS Code, the bundled
LangGraph agent, ...).

Run:
    python -m jobscout.server                              # stdio (default)
    python -m jobscout.server --transport streamable-http  # HTTP on :8000/mcp
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from jobscout import db

mcp = FastMCP(
    "jobscout",
    instructions=(
        "Tools for exploring AI/ML job postings: search jobs, measure skill demand, "
        "compute a candidate's skill gap for a job, and keep a shortlist."
    ),
)

_conn = None


def conn():
    """Lazily open one connection per server process."""
    global _conn
    if _conn is None:
        _conn = db.connect()
    return _conn


@mcp.tool()
def search_jobs(
    query: str | None = None,
    location: str | None = None,
    years_experience: float | None = None,
    remote_only: bool = False,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Search job postings.

    Args:
        query: Keywords matched against title, skills and description (e.g. "genai rag").
        location: Exact city, e.g. "Pune", "Bengaluru" or "Remote".
        years_experience: Only return jobs whose experience range includes this value.
        remote_only: Only return remote-friendly jobs.
        limit: Maximum number of results (1-50).
    """
    jobs = db.search_jobs(conn(), query, location, years_experience, remote_only, limit)
    # Keep tool output compact for the LLM context window.
    return [
        {k: j[k] for k in ("id", "title", "company", "location", "remote", "min_exp", "max_exp",
                           "salary_min_lpa", "salary_max_lpa", "skills")}
        for j in jobs
    ]


@mcp.tool()
def get_job(job_id: str) -> dict[str, Any]:
    """Get full details (including description) for one job by its id, e.g. "JS-1004"."""
    job = db.get_job(conn(), job_id)
    if job is None:
        raise ValueError(f"No job with id {job_id}")
    return job


@mcp.tool()
def skill_demand(query: str | None = None, location: str | None = None, top_n: int = 10) -> dict[str, Any]:
    """Rank the most requested skills across jobs matching an optional keyword and location."""
    return db.skill_demand(conn(), query, location, top_n)


@mcp.tool()
def skill_gap(job_id: str, my_skills: list[str]) -> dict[str, Any]:
    """Compare a candidate's skills with a job's requirements.

    Returns a match score (0-1), the matched skills and the missing skills.
    """
    result = db.skill_gap(conn(), job_id, my_skills)
    if result is None:
        raise ValueError(f"No job with id {job_id}")
    return result


@mcp.tool()
def add_to_shortlist(job_id: str, note: str = "") -> dict[str, Any]:
    """Save a job to the shortlist with an optional note (updates the note if already saved)."""
    return db.add_to_shortlist(conn(), job_id, note)


@mcp.tool()
def list_shortlist() -> list[dict[str, Any]]:
    """List all shortlisted jobs, newest first."""
    return db.list_shortlist(conn())


@mcp.resource("jobscout://stats")
def stats() -> str:
    """Aggregate market statistics: job counts by location and title, average max salary."""
    return json.dumps(db.market_stats(conn()), indent=2)


@mcp.prompt()
def career_advisor(my_skills: str, years_experience: str, location: str = "Pune") -> str:
    """Prompt template: find best-fit jobs and a learning plan for a candidate."""
    return (
        f"I have {years_experience} years of experience and these skills: {my_skills}. "
        f"Find the best matching jobs in {location} (and remote), compute my skill gap for the "
        "top 3, shortlist the best one, and suggest the 3 skills I should learn next."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="JobScout MCP server")
    parser.add_argument("--transport", default="stdio", choices=["stdio", "sse", "streamable-http"])
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
