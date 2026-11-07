"""LangGraph agent that reasons over the JobScout MCP tools.

Graph:  START -> agent --(tool calls?)--> tools -> agent ... -> END

The agent never imports the data layer directly: every capability comes from
the MCP server, discovered at runtime via langchain-mcp-adapters. Swap the
server for any other MCP server and the same graph keeps working.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

SYSTEM_PROMPT = """You are JobScout, a career assistant for AI/ML engineers in India.
Use the tools to ground every answer in the job data. Rules:
- Search before you recommend; never invent job ids, companies or salaries.
- When the user shares their skills, use skill_gap to quantify fit.
- Salaries are in LPA (lakh rupees per annum).
- Finish with a short, practical summary and concrete next steps."""


def mcp_connections(db_path: str | None = None) -> dict[str, dict[str, Any]]:
    """Launch the JobScout MCP server as a stdio subprocess."""
    env = dict(os.environ)
    src_dir = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [src_dir, env.get("PYTHONPATH")]))
    if db_path:
        env["JOBSCOUT_DB"] = db_path
    return {
        "jobscout": {
            "command": sys.executable,
            "args": ["-m", "jobscout.server"],
            "transport": "stdio",
            "env": env,
        }
    }


def default_model() -> BaseChatModel:
    """OpenAI by default; any OpenAI-compatible endpoint works via OPENAI_BASE_URL."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=os.environ.get("JOBSCOUT_MODEL", "gpt-4o-mini"), temperature=0)


def build_graph(model: BaseChatModel, tools: list[BaseTool]):
    """Compile the agent <-> tools loop."""
    llm = model.bind_tools(tools)

    def agent(state: MessagesState) -> dict[str, list]:
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(SYSTEM_PROMPT), *messages]
        return {"messages": [llm.invoke(messages)]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile()


@dataclass
class AgentResult:
    answer: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


def summarize(messages: list) -> AgentResult:
    """Extract the final answer plus a trace of every tool call (useful for demos/debugging)."""
    calls: list[dict[str, Any]] = []
    results = {m.tool_call_id: m.content for m in messages if isinstance(m, ToolMessage)}
    for m in messages:
        if isinstance(m, AIMessage):
            for tc in m.tool_calls:
                out = results.get(tc["id"], "")
                calls.append({
                    "tool": tc["name"],
                    "args": tc["args"],
                    "result_preview": str(out)[:300],
                })
    final = next((m for m in reversed(messages) if isinstance(m, AIMessage) and not m.tool_calls), None)
    return AgentResult(answer=str(final.content) if final else "", tool_calls=calls)


async def load_tools(db_path: str | None = None) -> list[BaseTool]:
    client = MultiServerMCPClient(mcp_connections(db_path))
    return await client.get_tools()


async def ask(
    question: str,
    model: BaseChatModel | None = None,
    tools: list[BaseTool] | None = None,
    max_steps: int = 12,
) -> AgentResult:
    tools = tools if tools is not None else await load_tools()
    graph = build_graph(model or default_model(), tools)
    state = await graph.ainvoke(
        {"messages": [HumanMessage(question)]},
        config={"recursion_limit": max_steps * 2},
    )
    return summarize(state["messages"])
