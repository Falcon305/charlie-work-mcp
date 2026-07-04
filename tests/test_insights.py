from __future__ import annotations

import subprocess

from charlie_work_mcp import history, hotspots, owners, scoring
from charlie_work_mcp.models import SourceFile, ToilItem, ToilKind


def _item(path: str, kind: ToilKind, severity: int = 3) -> ToilItem:
    return ToilItem(id=path, kind=kind, path=path, title="t", evidence="e", severity=severity, effort=2)


def test_scoring_annotate_and_grade():
    items = [_item("a.py", ToilKind.secret_leak, 5), _item("b.py", ToilKind.todo_rot, 2)]
    scoring.annotate(items)
    assert items[0].est_minutes == 30
    assert scoring.total_minutes(items) == 40
    files = [SourceFile(path="a.py", text="x = 1\n" * 100)]
    summary = scoring.summarize(items, files)
    assert summary["grade"] in {"A", "B", "C", "D", "E"}
    assert summary["toil_score"] > 0


def test_grade_thresholds():
    assert scoring.grade(0.01) == "A"
    assert scoring.grade(0.30) == "D"
    assert scoring.grade(0.80) == "E"


def test_owners_parsing_and_matching(tmp_path):
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "CODEOWNERS").write_text("*.py @py-team\n/ops/ @ops-team\n")
    rules = owners.load_owners(str(tmp_path))
    assert owners.owner_for("src/app.py", rules) == "@py-team"
    assert owners.owner_for("ops/deploy.sh", rules) == "@ops-team"
    items = [_item("ops/run.sh", ToilKind.unowned_runbook)]
    owners.annotate(items, rules)
    assert items[0].owner == "@ops-team"


def _git(root: str, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def test_hotspot_multiplier_favors_churned_file(tmp_path):
    root = str(tmp_path)
    _git(root, "init")
    _git(root, "config", "user.email", "t@t.com")
    _git(root, "config", "user.name", "t")
    body = "def f(x):\n    if x:\n        return 1\n    return 0\n"
    for i in range(4):
        (tmp_path / "hot.py").write_text(body + f"# rev {i}\n")
        _git(root, "add", "-A")
        _git(root, "commit", "-m", f"c{i}")
    (tmp_path / "cold.py").write_text(body)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "cold")
    files = [SourceFile(path="hot.py", text=body), SourceFile(path="cold.py", text=body)]
    multipliers = hotspots.compute_multipliers(root, files)
    assert multipliers.get("hot.py", 1.0) > multipliers.get("cold.py", 1.0)


def test_history_record_and_delta(tmp_path):
    root = str(tmp_path)
    history.record(root, {"toil_score": 100.0, "total_minutes": 200, "debt_ratio": 0.1, "grade": "C", "count": 5})
    history.record(root, {"toil_score": 80.0, "total_minutes": 160, "debt_ratio": 0.08, "grade": "B", "count": 4})
    delta = history.delta(root)
    assert delta is not None
    assert delta["toil_score_delta"] == -20.0
    assert delta["count_delta"] == -1
