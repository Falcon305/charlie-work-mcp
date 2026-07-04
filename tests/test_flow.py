from __future__ import annotations

import os

from charlie_work_mcp.models import ToilKind
from charlie_work_mcp.scan import compute_priority, scan_repo
from charlie_work_mcp.services import store
from charlie_work_mcp.models import ToilItem


def _write(root: str, rel: str, text: str) -> None:
    full = os.path.join(root, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as handle:
        handle.write(text)


def test_scan_repo_ranks_and_filters(tmp_path):
    root = str(tmp_path)
    _write(root, "app.py", "def f():\n    breakpoint()  # TODO fix\n")
    _write(root, "test_x.py", "@pytest.mark.skip\ndef test_x():\n    pass\n")
    items = scan_repo(root, online=False)
    assert items
    priorities = [i.priority for i in items]
    assert priorities == sorted(priorities, reverse=True)
    only_todo = scan_repo(root, kinds=[ToilKind.todo_rot.value], online=False)
    assert only_todo and all(i.kind == ToilKind.todo_rot for i in only_todo)


def test_priority_prefers_high_severity_low_effort():
    high = ToilItem(id="a", kind=ToilKind.focused_test, path="p", title="t", evidence="e", severity=4, effort=2)
    low = ToilItem(id="b", kind=ToilKind.todo_rot, path="p", title="t", evidence="e", severity=2, effort=2)
    assert compute_priority(high) > compute_priority(low)


def test_ledger_persists_across_reload(tmp_path):
    root = str(tmp_path)
    from charlie_work_mcp.models import LedgerEntry

    entry = LedgerEntry(toil_id="abc", kind="todo_rot", title="did a thing", who="dee", at="2026-07-04T00:00:00+00:00")
    store.append_entry(root, entry)
    reloaded = store.load_entries(root)
    assert len(reloaded) == 1
    assert reloaded[0].who == "dee"
    counts = store.credit_counts(reloaded)
    assert store.champion(counts) == "dee"
