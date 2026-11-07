"""End-to-end: start the real MCP server over stdio and call it like any MCP client would."""

import json

from langchain_mcp_adapters.client import MultiServerMCPClient

from jobscout.agent import mcp_connections

EXPECTED_TOOLS = {"search_jobs", "get_job", "skill_demand", "skill_gap", "add_to_shortlist", "list_shortlist"}


async def test_tools_discovered(db_path):
    tools = await MultiServerMCPClient(mcp_connections(db_path)).get_tools()
    assert EXPECTED_TOOLS <= {t.name for t in tools}


async def test_call_search_and_gap(db_path):
    client = MultiServerMCPClient(mcp_connections(db_path))
    async with client.session("jobscout") as session:
        res = await session.call_tool("search_jobs", {"query": "rag", "limit": 3})
        jobs = [json.loads(c.text) for c in res.content]
        assert jobs and all("id" in j for j in jobs)

        gap = await session.call_tool("skill_gap", {"job_id": jobs[0]["id"], "my_skills": ["python", "rag"]})
        payload = json.loads(gap.content[0].text)
        assert "match_score" in payload and "missing" in payload


async def test_stats_resource(db_path):
    client = MultiServerMCPClient(mcp_connections(db_path))
    async with client.session("jobscout") as session:
        res = await session.read_resource("jobscout://stats")
        assert json.loads(res.contents[0].text)["total_jobs"] == 60
