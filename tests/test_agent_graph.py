"""Run the full LangGraph loop against the real MCP server with a scripted (offline) model."""

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from jobscout import agent


class ScriptedModel(GenericFakeChatModel):
    """Fake chat model that replays fixed messages; bind_tools is a no-op."""

    def bind_tools(self, tools, **kwargs):
        return self


async def test_agent_calls_mcp_tool_then_answers(db_path):
    model = ScriptedModel(messages=iter([
        AIMessage(content="", tool_calls=[{
            "name": "search_jobs", "args": {"query": "genai", "years_experience": 2}, "id": "call_1",
        }]),
        AIMessage(content="Here are the best GenAI roles for 2 years of experience."),
    ]))
    tools = await agent.load_tools(db_path)
    result = await agent.ask("Find GenAI jobs for 2 years experience", model=model, tools=tools)

    assert result.answer.startswith("Here are")
    assert [c["tool"] for c in result.tool_calls] == ["search_jobs"]
    assert "JS-" in result.tool_calls[0]["result_preview"]
