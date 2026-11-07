"""FastAPI wrapper so the agent can be called over HTTP (and deployed in Docker)."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from jobscout import agent


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000,
                          examples=[("I know Python, RAG and LangChain with 2 years experience. "
                                     "Which Pune or remote GenAI jobs fit me best?")])


class ToolCall(BaseModel):
    tool: str
    args: dict
    result_preview: str


class AskResponse(BaseModel):
    answer: str
    tool_calls: list[ToolCall]


STATE: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    STATE["tools"] = await agent.load_tools()  # discover MCP tools once at startup
    yield
    STATE.clear()


app = FastAPI(title="JobScout MCP Agent", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "tools_loaded": len(STATE.get("tools", []))}


@app.get("/tools")
async def tools() -> list[dict]:
    return [{"name": t.name, "description": t.description} for t in STATE.get("tools", [])]


@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest) -> AskResponse:
    try:
        result = await agent.ask(req.question, tools=STATE["tools"])
    except Exception as exc:  # surface model/provider errors cleanly
        raise HTTPException(status_code=502, detail=f"Agent error: {exc}") from exc
    return AskResponse(answer=result.answer, tool_calls=result.tool_calls)
