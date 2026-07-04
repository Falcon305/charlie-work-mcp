from __future__ import annotations

import re

from .gitmeta import _run
from .models import ToilItem

_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def merge_base(root: str, base: str) -> str | None:
    output = _run(root, ["merge-base", base, "HEAD"])
    if output is None:
        return None
    result = output.strip()
    return result or None


def added_lines(root: str, base: str) -> dict[str, set[int]]:
    anchor = merge_base(root, base) or base
    output = _run(root, ["diff", "--unified=0", f"{anchor}...HEAD"])
    if output is None:
        output = _run(root, ["diff", "--unified=0", anchor])
    if output is None:
        return {}
    added: dict[str, set[int]] = {}
    current: str | None = None
    for line in output.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:].strip()
            added.setdefault(current, set())
            continue
        if line.startswith("+++ ") and "/dev/null" in line:
            current = None
            continue
        match = _HUNK.match(line)
        if match and current is not None:
            start = int(match.group(1))
            count = int(match.group(2)) if match.group(2) is not None else 1
            for offset in range(count):
                added[current].add(start + offset)
    return added


def filter_to_diff(items: list[ToilItem], added: dict[str, set[int]]) -> list[ToilItem]:
    kept: list[ToilItem] = []
    for item in items:
        lines = added.get(item.path)
        if lines is None:
            continue
        if item.line is None or item.line in lines:
            kept.append(item)
    return kept
