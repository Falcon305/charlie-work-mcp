from __future__ import annotations

import os
import subprocess

from charlie_work_mcp.baseline import filter_new, load_baseline, write_baseline
from charlie_work_mcp.config import Config, load_config
from charlie_work_mcp.diff import added_lines, filter_to_diff
from charlie_work_mcp.models import SourceFile, ToilItem, ToilKind
from charlie_work_mcp.sarif import to_sarif
from charlie_work_mcp.suppress import apply_suppressions


def _item(path: str, line: int, kind: ToilKind, confidence: str = "high") -> ToilItem:
    return ToilItem(
        id=f"{path}:{line}",
        kind=kind,
        path=path,
        line=line,
        title="t",
        evidence="e",
        severity=4,
        effort=2,
        confidence=confidence,
    )


def test_config_loads_from_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[tool.charlie]\nexclude = ["vendor/**"]\ndisable = ["charlie/todo-rot"]\n'
        'min_confidence = "high"\n[tool.charlie.per-file-ignores]\n"tests/**" = ["secret_leak"]\n'
    )
    config = load_config(str(tmp_path))
    assert "vendor/**" in config.exclude
    assert "charlie/todo-rot" in config.disable
    assert config.min_confidence == "high"
    assert config.per_file_ignores["tests/**"] == ["secret_leak"]


def test_suppression_excludes_disables_and_confidence(tmp_path):
    files = [SourceFile(path="a.py", text="x = 1\n")]
    items = [
        _item("vendor/lib.py", 1, ToilKind.todo_rot),
        _item("a.py", 1, ToilKind.todo_rot),
        _item("b.py", 1, ToilKind.secret_leak, confidence="heuristic"),
    ]
    config = Config(exclude=["vendor/**"], disable=["charlie/todo-rot"], min_confidence="high")
    kept = apply_suppressions(items, files, config, str(tmp_path))
    assert kept == []


def test_inline_ignore(tmp_path):
    files = [SourceFile(path="a.py", text="risky()  # charlie: ignore\nother()  # charlie: ignore[charlie/todo-rot]\n")]
    items = [
        _item("a.py", 1, ToilKind.debug_leftover),
        _item("a.py", 2, ToilKind.todo_rot),
        _item("a.py", 2, ToilKind.flaky_test),
    ]
    kept = apply_suppressions(items, files, Config(), str(tmp_path))
    kept_lines = {(i.line, i.kind) for i in kept}
    assert (1, ToilKind.debug_leftover) not in kept_lines
    assert (2, ToilKind.todo_rot) not in kept_lines
    assert (2, ToilKind.flaky_test) in kept_lines


def test_baseline_roundtrip(tmp_path):
    items = [_item("a.py", 1, ToilKind.todo_rot), _item("b.py", 2, ToilKind.flaky_test)]
    written = write_baseline(str(tmp_path), items)
    assert written == 2
    loaded = load_baseline(str(tmp_path))
    new_item = _item("c.py", 3, ToilKind.secret_leak)
    fresh = filter_new(items + [new_item], loaded)
    assert [i.path for i in fresh] == ["c.py"]


def _git(root: str, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def test_diff_added_lines(tmp_path):
    root = str(tmp_path)
    _git(root, "init")
    _git(root, "config", "user.email", "t@t.com")
    _git(root, "config", "user.name", "t")
    (tmp_path / "app.py").write_text("a = 1\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "base")
    _git(root, "checkout", "-b", "feature")
    (tmp_path / "new.py").write_text("b = 2\nc = 3\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "feature")
    added = added_lines(root, "master")
    assert added.get("new.py") == {1, 2}
    items = [_item("new.py", 2, ToilKind.todo_rot), _item("app.py", 1, ToilKind.todo_rot)]
    kept = filter_to_diff(items, added)
    assert [i.path for i in kept] == ["new.py"]


def test_sarif_structure():
    items = [_item("a.py", 5, ToilKind.secret_leak)]
    items[0].security_severity = 9.5
    doc = to_sarif(items)
    assert doc["version"] == "2.1.0"
    run = doc["runs"][0]
    assert run["tool"]["driver"]["name"] == "charlie-work"
    result = run["results"][0]
    assert result["locations"][0]["physicalLocation"]["region"]["startLine"] == 5
    assert result["partialFingerprints"]["primaryLocationLineHash"]
    assert result["properties"]["security-severity"] == "9.5"
