"""Command line entry point: `jobscout "your question"`."""

from __future__ import annotations

import argparse
import asyncio
import json

from jobscout import agent


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the JobScout agent a question.")
    parser.add_argument("question", help="e.g. 'Top skills for GenAI jobs in Pune?'")
    parser.add_argument("--trace", action="store_true", help="print every MCP tool call")
    args = parser.parse_args()

    result = asyncio.run(agent.ask(args.question))
    if args.trace:
        for i, call in enumerate(result.tool_calls, 1):
            print(f"[{i}] {call['tool']}({json.dumps(call['args'])})")
        print()
    print(result.answer)


if __name__ == "__main__":
    main()
