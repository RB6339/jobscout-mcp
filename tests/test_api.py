from fastapi.testclient import TestClient

from jobscout import agent, api


def test_health_tools_and_ask(db_path, monkeypatch):
    async def fake_ask(question, tools=None, **_):
        return agent.AgentResult(answer=f"echo: {question}", tool_calls=[
            {"tool": "search_jobs", "args": {"query": "rag"}, "result_preview": "[...]"}])

    monkeypatch.setattr(agent, "ask", fake_ask)
    with TestClient(api.app) as client:
        assert client.get("/health").json()["tools_loaded"] >= 6
        assert {t["name"] for t in client.get("/tools").json()} >= {"search_jobs", "skill_gap"}
        r = client.post("/ask", json={"question": "Which RAG jobs fit me?"})
        assert r.status_code == 200
        assert r.json()["answer"] == "echo: Which RAG jobs fit me?"
        assert r.json()["tool_calls"][0]["tool"] == "search_jobs"
