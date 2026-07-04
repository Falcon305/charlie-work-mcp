from __future__ import annotations

import os
from fnmatch import fnmatch

from .models import ToilItem

_LOCATIONS = ("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS")


def _translate(pattern: str) -> str:
    if pattern.startswith("/"):
        pattern = pattern[1:]
    if pattern.endswith("/"):
        pattern = pattern + "**"
    return pattern


def load_owners(root: str) -> list[tuple[str, list[str]]]:
    for location in _LOCATIONS:
        path = os.path.join(root, location)
        if not os.path.exists(path):
            continue
        rules: list[tuple[str, list[str]]] = []
        try:
            with open(path, encoding="utf-8") as handle:
                for raw in handle:
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split()
                    rules.append((_translate(parts[0]), parts[1:]))
        except OSError:
            return []
        return rules
    return []


def owner_for(path: str, rules: list[tuple[str, list[str]]]) -> str | None:
    match: list[str] | None = None
    for pattern, owners in rules:
        if fnmatch(path, pattern) or fnmatch(path, f"{pattern}/*") or fnmatch(os.path.basename(path), pattern):
            match = owners
    return " ".join(match) if match else None


def annotate(items: list[ToilItem], rules: list[tuple[str, list[str]]]) -> None:
    if not rules:
        return
    for item in items:
        item.owner = owner_for(item.path, rules)
