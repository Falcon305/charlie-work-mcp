from __future__ import annotations

import re

from ..models import SourceFile, ToilItem, ToilKind, make_id

_MARKER = re.compile(r"\b(TODO|FIXME|HACK|XXX|BUG|REFACTOR)\b[:\s-]*(.*)", re.IGNORECASE)

_SEVERITY = {
    "FIXME": 3,
    "BUG": 4,
    "HACK": 3,
    "XXX": 3,
    "TODO": 2,
    "REFACTOR": 2,
}


def scan(files: list[SourceFile]) -> list[ToilItem]:
    items: list[ToilItem] = []
    for file in files:
        for lineno, line in enumerate(file.text.splitlines(), start=1):
            match = _MARKER.search(line)
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
                )
            )
    return items
