from __future__ import annotations

import subprocess

from charlie_work_mcp.actions import fix_findings, next_action
from charlie_work_mcp.fixers import build_fix
from charlie_work_mcp.models import ToilItem, ToilKind
from charlie_work_mcp.patch import unified_diff
from charlie_work_mcp.scan import scan_repo


def _git_repo(tmp_path):
    subprocess.run(["git", "-C", str(tmp_path), "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t.co"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True, capture_output=True)
    (tmp_path / "app.py").write_text("def f():\n    x = 1\n    breakpoint()\n    return x\n")
    (tmp_path / "test_a.py").write_text("import pytest\n\n\n@pytest.mark.skip\ndef test_a():\n    assert True\n")
    (tmp_path / "keys.txt").write_text("aws_key = AKIAIOSFODNN7EXAMPLE1234\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "base"], check=True, capture_output=True)
    return str(tmp_path)


def _item(tmp_path, kind):
    return next(i for i in scan_repo(_git_repo(tmp_path), online=False) if i.kind is kind)


def test_unified_diff_is_well_formed():
    diff = unified_diff("a.py", "one\ntwo\n", "one\n")
    assert diff.startswith("--- a/a.py")
    assert "+++ b/a.py" in diff
    assert "-two" in diff


def test_debug_leftover_is_auto_safe_and_applies(tmp_path):
    root = _git_repo(tmp_path)
    item = next(i for i in scan_repo(root, online=False) if i.kind is ToilKind.debug_leftover)
    build_fix(item, root)
    assert item.fixability == "auto-safe"
    (tmp_path / "charlie.patch").write_text(item.patch)
    check = subprocess.run(
        ["git", "-C", root, "apply", "--check", "charlie.patch"], capture_output=True, text=True
    )
    assert check.returncode == 0, check.stderr


def test_skipped_test_removes_decorator(tmp_path):
    item = _item(tmp_path, ToilKind.skipped_test)
    build_fix(item, str(tmp_path))
    assert item.fixability == "needs-review"
    assert "-@pytest.mark.skip" in item.patch


def test_secret_and_cert_are_never_patched(tmp_path):
    for kind in (ToilKind.secret_leak, ToilKind.expiring_cert):
        item = ToilItem(id="x", kind=kind, path="f.txt", line=1, title="t", evidence="e", severity=5, effort=2)
        build_fix(item, str(tmp_path))
        assert item.fixability == "manual"
        assert item.patch is None
        assert item.fix


def test_next_action_surfaces_top_item_with_patch(tmp_path):
    result = next_action(_git_repo(tmp_path), online=False)
    assert result.found
    assert result.item is not None
    assert result.next_actions


def test_fix_findings_splits_patchable_from_manual(tmp_path):
    result = fix_findings(_git_repo(tmp_path), top_n=20, online=False)
    kinds_with_patch = {i.kind for i in result.patches}
    assert ToilKind.debug_leftover in kinds_with_patch
    assert all(i.patch for i in result.patches)
    assert all(i.patch is None for i in result.manual)


def test_cli_next_prints_patch(tmp_path, capsys):
    from charlie_work_mcp import cli

    code = cli.main(["next", "--offline", _git_repo(tmp_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "--- a/" in out and "@@" in out
    assert any(tag in out for tag in ("[auto-safe]", "[needs-review]"))


def test_cli_fix_by_id(tmp_path, capsys):
    root = _git_repo(tmp_path)
    item = next(i for i in scan_repo(root, online=False) if i.kind is ToilKind.debug_leftover)
    from charlie_work_mcp import cli

    code = cli.main(["fix", "--offline", "--id", item.id, root])
    out = capsys.readouterr().out
    assert code == 0
    assert "-    breakpoint()" in out


def test_charlie_next_and_fix_tools(tmp_path):
    from charlie_work_mcp import server

    root = _git_repo(tmp_path)
    nxt = server.charlie_next(repo=root, online=False)
    assert nxt.found and nxt.item is not None
    fixed = server.charlie_fix(repo=root, top_n=20, online=False)
    assert any(i.kind is ToilKind.debug_leftover for i in fixed.patches)


def test_manual_note_does_not_clobber_existing_fix():
    item = ToilItem(
        id="x",
        kind=ToilKind.vulnerable_dep,
        path="req.txt",
        title="t",
        evidence="e",
        severity=4,
        effort=2,
        fix="upgrade foo to 2.0",
    )
    build_fix(item, ".")
    assert item.fix == "upgrade foo to 2.0"
    assert item.fixability == "manual"
