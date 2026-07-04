from __future__ import annotations

import re

from ..models import SourceFile, ToilItem, ToilKind, make_id

_SKIP_PATTERNS = [
    re.compile(r"@pytest\.mark\.skip\b"),
    re.compile(r"@pytest\.mark\.xfail\b"),
    re.compile(r"@unittest\.skip\b"),
    re.compile(r"\bpytest\.skip\("),
    re.compile(r"\b(it|test|describe|context)\.skip\("),
    re.compile(r"\bx(it|describe|test)\("),
    re.compile(r"\.skip\.each\b"),
]

_FOCUS_PATTERNS = [
    re.compile(r"\b(it|test|describe|context)\.only\("),
    re.compile(r"\bf(it|describe|test)\("),
]

_FLAKY_PATTERNS = [
    re.compile(r"@pytest\.mark\.flaky\b"),
    re.compile(r"@flaky\b"),
    re.compile(r"\bflaky\s*\("),
    re.compile(r"\bretries\s*[:=]\s*[1-9]"),
    re.compile(r"\bretry\s*\(\s*[1-9]"),
]


def _emit(file: SourceFile, kind: ToilKind, lineno: int, line: str, severity: int) -> ToilItem:
    evidence = line.strip()[:200]
    titles = {
        ToilKind.skipped_test: "Skipped test quietly rotting in the suite",
        ToilKind.focused_test: "Focused test left in — the rest of the suite isn't running",
        ToilKind.flaky_test: "Flaky test papered over with retries",
    }
    return ToilItem(
        id=make_id(kind, file.path, lineno, evidence),
        kind=kind,
        path=file.path,
        line=lineno,
        title=titles[kind],
        evidence=evidence,
        severity=severity,
        effort=2,
    )


def scan(files: list[SourceFile]) -> list[ToilItem]:
    items: list[ToilItem] = []
    for file in files:
        for lineno, line in enumerate(file.text.splitlines(), start=1):
            if any(p.search(line) for p in _FOCUS_PATTERNS):
                items.append(_emit(file, ToilKind.focused_test, lineno, line, 4))
                continue
            if any(p.search(line) for p in _SKIP_PATTERNS):
                items.append(_emit(file, ToilKind.skipped_test, lineno, line, 3))
                continue
            if any(p.search(line) for p in _FLAKY_PATTERNS):
                items.append(_emit(file, ToilKind.flaky_test, lineno, line, 4))
    return items
