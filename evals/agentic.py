from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from charlie_work_mcp.server import mcp

_CASES = [
    ("Find the tech debt and toil in this repository.", "charlie_scan_toil"),
    ("What's my repo's toil budget and maintainability grade?", "charlie_summary"),
    ("Give me the top 3 things to fix first as an action plan.", "charlie_triage"),
    ("Why is finding abc123 considered debt?", "charlie_explain"),
    ("Record that dee cleared the flaky login test.", "charlie_did_it"),
]


async def _tool_schemas() -> list[dict]:
    tools = await mcp.list_tools()
    return [{"name": t.name, "description": t.description or "", "input_schema": t.inputSchema} for t in tools]


def _selected_tool(client, model: str, prompt: str, tools: list[dict]) -> str | None:
    message = client.messages.create(
        model=model,
        max_tokens=512,
        tools=tools,
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": prompt}],
    )
    for block in message.content:
        if getattr(block, "type", None) == "tool_use":
            return block.name
    return None


def main() -> int:
    tools = asyncio.run(_tool_schemas())
    print(f"Agentic tool-selection eval — {len(tools)} tools exposed.")
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("SKIPPED: set ANTHROPIC_API_KEY to run the model-graded tool-selection eval.")
        return 0
    try:
        import anthropic
    except ImportError:
        print("SKIPPED: `pip install anthropic` to run this eval.")
        return 0

    client = anthropic.Anthropic(api_key=key)
    model = os.environ.get("CHARLIE_EVAL_MODEL", "claude-sonnet-5")
    correct = 0
    for prompt, expected in _CASES:
        chosen = _selected_tool(client, model, prompt, tools)
        ok = chosen == expected
        correct += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] want {expected:18} got {chosen}")
    accuracy = correct / len(_CASES)
    print(f"tool-selection accuracy: {accuracy:.0%} ({correct}/{len(_CASES)}) on {model}")
    return 0 if accuracy >= 0.8 else 1


if __name__ == "__main__":
    raise SystemExit(main())
