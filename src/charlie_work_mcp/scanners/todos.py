from __future__ import annotations

import re

from ..models import HIGH, SourceFile, ToilItem, ToilKind, make_id

_COMMENT_LEAD = re.compile(r"(#|//|/\*|<!--)")
_MARKER = re.compile(r"\b(TODO|FIXME|HACK|XXX|BUG|REFACTOR)\b[:\s-]*(.*)")

_SEVERITY = {
    "FIXME": 3,
    "BUG": 4,
    "HACK": 3,
    "XXX": 3,
    "TODO": 2,
    "REFACTOR": 2,
}

_SKIP_EXT = (".json", ".lock", ".csv", ".svg", ".map", ".md", ".rst", ".txt")


def scan(files: list[SourceFile]) -> list[ToilItem]:
    items: list[ToilItem] = []
    for file in files:
        if file.path.lower().endswith(_SKIP_EXT):
            continue
        for lineno, line in enumerate(file.text.splitlines(), start=1):
            comment = _COMMENT_LEAD.search(line)
            if not comment:
                continue
            match = _MARKER.search(line, comment.end())
            if not match:
                continue
            marker = match.group(1).upper()
            note = match.group(2).strip()
            evidence = (f"{marker}: {note}" if note else marker)[:200]
            items.append(
                ToilItem(
                    id=make_id(ToilKind.todo_rot, file.path, lineno, evidence),
                    kind=ToilKind.todo_rot,
                    path=file.path,
                    line=lineno,
                    title=f"{marker} left in the code",
                    evidence=evidence,
                    severity=_SEVERITY.get(marker, 2),
                    effort=2,
                    confidence=HIGH,
                )
            )
    return items
