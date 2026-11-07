from jobscout import db


def test_seed_loaded(conn):
    assert db.market_stats(conn)["total_jobs"] == 60


def test_normalize_skill_aliases():
    assert db.normalize_skill("  Model Context Protocol ") == "mcp"
    assert db.normalize_skill("K8s") == "kubernetes"


def test_search_by_experience_and_location(conn):
    jobs = db.search_jobs(conn, location="Pune", years_experience=2, limit=50)
    assert jobs, "expected at least one Pune job for 2 years"
    for j in jobs:
        assert j["location"] == "Pune"
        assert j["min_exp"] <= 2 <= j["max_exp"]


def test_search_keyword_matches_skills(conn):
    jobs = db.search_jobs(conn, query="langgraph", limit=50)
    assert jobs and all(
        "langgraph" in j["skills"] or "langgraph" in j["description"].lower() for j in jobs
    )


def test_skill_demand_shares(conn):
    out = db.skill_demand(conn, query="engineer", top_n=5)
    assert out["jobs_analysed"] > 0
    assert len(out["top_skills"]) == 5
    assert all(0 < s["share"] <= 1 for s in out["top_skills"])


def test_skill_gap(conn):
    job = db.search_jobs(conn, limit=1)[0]
    gap = db.skill_gap(conn, job["id"], job["skills"][:2])
    assert set(gap["matched"]) == set(job["skills"][:2])
    assert set(gap["missing"]) == set(job["skills"][2:])
    assert 0 < gap["match_score"] < 1


def test_skill_gap_unknown_job(conn):
    assert db.skill_gap(conn, "NOPE", ["python"]) is None


def test_shortlist_upsert(conn):
    job_id = db.search_jobs(conn, limit=1)[0]["id"]
    db.add_to_shortlist(conn, job_id, "first")
    db.add_to_shortlist(conn, job_id, "updated")
    items = db.list_shortlist(conn)
    assert len(items) == 1 and items[0]["note"] == "updated"
