from __future__ import annotations

import re

from ..models import SourceFile, ToilItem, ToilKind, make_id

_SCRIPT_SUFFIXES = (".sh", ".bash")
_OPS_HINTS = ("deploy", "release", "provision", "migrate", "backup", "rotate", "restore")
_OWNER_HINT = re.compile(r"\b(owner|maintainer|maintained by|contact)\b", re.IGNORECASE)


def _looks_operational(path: str) -> bool:
    lowered = path.lower()
    if lowered.endswith(_SCRIPT_SUFFIXES):
        return True
    base = lowered.rsplit("/", 1)[-1]
    return any(hint in base for hint in _OPS_HINTS)


def _codeowned_paths(files: list[SourceFile]) -> bool:
    for file in files:
        base = file.path.rsplit("/", 1)[-1].upper()
        if base == "CODEOWNERS":
            return True
    return False


def scan(files: list[SourceFile]) -> list[ToilItem]:
    has_codeowners = _codeowned_paths(files)
    items: list[ToilItem] = []
    for file in files:
        if not _looks_operational(file.path):
            continue
        head = "\n".join(file.text.splitlines()[:15])
        if _OWNER_HINT.search(head):
            continue
        if has_codeowners:
            continue
        items.append(
            ToilItem(
                id=make_id(ToilKind.unowned_runbook, file.path, None, "no-owner"),
                kind=ToilKind.unowned_runbook,
                path=file.path,
                line=None,
                title="Operational script with no owner — nobody's cleaning this grease trap",
                evidence=file.path,
                severity=2,
                effort=1,
            )
        )
    return items
