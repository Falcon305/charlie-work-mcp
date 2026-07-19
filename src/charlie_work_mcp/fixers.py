from __future__ import annotations

import os

from .models import ToilItem, ToilKind
from .patch import unified_diff

AUTO_SAFE = "auto-safe"
NEEDS_REVIEW = "needs-review"
MANUAL = "manual"

_MANUAL_NOTES: dict[ToilKind, str] = {
    ToilKind.secret_leak: "Rotate the leaked credential and purge it from history — never patch it in place.",
    ToilKind.expiring_cert: "Renew or rotate the certificate; this is an ops task, not a code edit.",
    ToilKind.vulnerable_dep: "Bump the pinned version to the fixed release and regenerate the lockfile.",
    ToilKind.outdated_dep: "Bump the dependency and run the tests; check the changelog for breaking changes.",
    ToilKind.dependency_risk: "Pin the dependency to an exact version.",
    ToilKind.dead_flag: "Remove the flag and the dead branch it guards, or wire the flag up.",
    ToilKind.unowned_runbook: "Give it an owner — a CODEOWNERS entry or a header comment.",
}

_PY_DECORATORS = (
    "@pytest.mark.skip",
    "@pytest.mark.skipif",
    "@pytest.mark.xfail",
    "@unittest.skip",
    "@mark.skip",
)
_PY_CALLS = ("pytest.skip(", "self.skipTest(", "unittest.skip(")
_JS_MARKERS = (
    (".only", ""),
    (".skip", ""),
    ("xdescribe", "describe"),
    ("fdescribe", "describe"),
    ("xit(", "it("),
    ("fit(", "it("),
)


def _read(root: str, rel: str) -> str | None:
    try:
        with open(os.path.join(root, rel), encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return None


def _delete_line(content: str, line: int) -> str | None:
    lines = content.splitlines(keepends=True)
    if line < 1 or line > len(lines):
        return None
    del lines[line - 1]
    return "".join(lines)


def _unskip(content: str, line: int) -> str | None:
    lines = content.splitlines(keepends=True)
    if line < 1 or line > len(lines):
        return None
    original = lines[line - 1]
    stripped = original.strip()
    if any(stripped.startswith(dec) for dec in _PY_DECORATORS) or any(call in original for call in _PY_CALLS):
        del lines[line - 1]
        return "".join(lines)
    replaced = original
    for needle, repl in _JS_MARKERS:
        replaced = replaced.replace(needle, repl)
    if replaced == original:
        return None
    lines[line - 1] = replaced
    return "".join(lines)


def _attach(item: ToilItem, content: str, patched: str | None) -> bool:
    if patched is None or patched == content:
        return False
    item.patch = unified_diff(item.path, content, patched)
    return bool(item.patch)


def build_fix(item: ToilItem, root: str = ".") -> ToilItem:
    if item.kind in _MANUAL_NOTES:
        item.fixability = MANUAL
        item.patch = None
        if not item.fix:
            item.fix = _MANUAL_NOTES[item.kind]
        return item
    content = _read(root, item.path) if item.line else None
    if content is None or item.line is None:
        item.fixability = MANUAL
        return item
    if item.kind is ToilKind.debug_leftover and _attach(item, content, _delete_line(content, item.line)):
        item.fixability = AUTO_SAFE
        return item
    if item.kind is ToilKind.todo_rot and _attach(item, content, _delete_line(content, item.line)):
        item.fixability = NEEDS_REVIEW
        return item
    if item.kind in (ToilKind.skipped_test, ToilKind.focused_test) and _attach(
        item, content, _unskip(content, item.line)
    ):
        item.fixability = NEEDS_REVIEW
        return item
    item.fixability = MANUAL
    return item
