from __future__ import annotations

import json

from charlie_work_mcp import cli, server
from charlie_work_mcp.models import LedgerEntry


def _repo(tmp_path) -> str:
    (tmp_path / "app.py").write_text("def f():\n    breakpoint()\n")
    (tmp_path / "b.test.js").write_text("it.only('x', () => {})\n")
    return str(tmp_path)


def test_cli_scan_json(tmp_path, capsys):
    code = cli.main(["scan", "--offline", "--json", _repo(tmp_path)])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert any(i["kind"] == "focused_test" for i in payload)


def test_cli_summary_and_sarif(tmp_path, capsys):
    root = _repo(tmp_path)
    assert cli.main(["summary", "--offline", root]) == 0
    assert "Grade" in capsys.readouterr().out
    out_file = tmp_path / "out.sarif"
    assert cli.main(["sarif", "--offline", "-o", str(out_file), root]) == 0
    doc = json.loads(out_file.read_text())
    assert doc["version"] == "2.1.0"


def test_cli_gate_blocks_high_severity(tmp_path):
    root = _repo(tmp_path)
    assert cli.main(["gate", "--offline", "--severity", "4", root]) == 1
    assert cli.main(["gate", "--offline", "--severity", "6", root]) == 0


def test_server_summary_explain_triage(tmp_path):
    root = _repo(tmp_path)
    summary = server.charlie_summary(repo=root, online=False)
    assert summary.grade in {"A", "B", "C", "D", "E"}
    triage = server.charlie_triage(repo=root, top_n=3, online=False)
    assert triage.items
    top_id = triage.items[0].id
    explanation = server.charlie_explain(finding_id=top_id, repo=root, online=False)
    assert explanation.found
    missing = server.charlie_explain(finding_id="nope", repo=root, online=False)
    assert not missing.found


def test_server_ledger_reclaimed_minutes():
    entries = [LedgerEntry(toil_id="a", kind="secret_leak", title="t", who="dee", at="2026-01-01T00:00:00+00:00")]
    minutes = server._reclaimed_minutes(entries)
    assert minutes["dee"] == 30
