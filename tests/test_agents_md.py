from __future__ import annotations

import asyncio

from charlie_work_mcp import rules, server


def test_block_has_markers_and_guidance():
    block = rules.agents_block()
    assert block.startswith(rules.START)
    assert block.rstrip().endswith(rules.END)
    assert "charlie_next" in block
    assert "patch-first" in block


def test_upsert_creates_file(tmp_path):
    _path, action = rules.upsert(str(tmp_path))
    assert action == "created"
    assert rules.START in (tmp_path / "AGENTS.md").read_text()


def test_upsert_appends_and_preserves_existing(tmp_path):
    (tmp_path / "AGENTS.md").write_text("# My Project\n\nExisting rules.\n")
    _, action = rules.upsert(str(tmp_path))
    content = (tmp_path / "AGENTS.md").read_text()
    assert action == "appended"
    assert "Existing rules." in content
    assert rules.START in content


def test_upsert_is_idempotent(tmp_path):
    rules.upsert(str(tmp_path))
    rules.upsert(str(tmp_path))
    _, action = rules.upsert(str(tmp_path))
    content = (tmp_path / "AGENTS.md").read_text()
    assert action == "updated"
    assert content.count(rules.START) == 1
    assert content.count(rules.END) == 1


def test_charlie_rules_prompt_is_registered():
    prompts = asyncio.run(server.mcp.list_prompts())
    names = {p.name for p in prompts}
    assert "charlie_rules" in names
    assert "triage_toil" in names
