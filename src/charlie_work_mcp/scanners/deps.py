from __future__ import annotations

import json
import re

from ..models import SourceFile, ToilItem, ToilKind, make_id

_LOOSE_NPM = re.compile(r"^[\^~]?\s*(\*|latest|x)\s*$", re.IGNORECASE)


def _npm(file: SourceFile) -> list[ToilItem]:
    try:
        data = json.loads(file.text)
    except (json.JSONDecodeError, ValueError):
        return []
    items: list[ToilItem] = []
    for section in ("dependencies", "devDependencies"):
        deps = data.get(section)
        if not isinstance(deps, dict):
            continue
        for name, spec in deps.items():
            if not isinstance(spec, str):
                continue
            if _LOOSE_NPM.match(spec.strip()) or spec.strip() in {"", "*"}:
                items.append(
                    ToilItem(
                        id=make_id(ToilKind.dependency_risk, file.path, None, name),
                        kind=ToilKind.dependency_risk,
                        path=file.path,
                        line=None,
                        title=f"Dependency '{name}' is pinned to '{spec}' — a rug that will pull itself",
                        evidence=f"{name}: {spec}",
                        severity=3,
                        effort=2,
                    )
                )
    return items


def _requirements(file: SourceFile) -> list[ToilItem]:
    items: list[ToilItem] = []
    for lineno, raw in enumerate(file.text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        if re.search(r"[<>=!~]", line):
            continue
        name = re.split(r"[\[;]", line, maxsplit=1)[0].strip()
        if not name:
            continue
        items.append(
            ToilItem(
                id=make_id(ToilKind.dependency_risk, file.path, lineno, name),
                kind=ToilKind.dependency_risk,
                path=file.path,
                line=lineno,
                title=f"Dependency '{name}' has no version pin — whatever ships, ships",
                evidence=line[:200],
                severity=3,
                effort=2,
            )
        )
    return items


def scan(files: list[SourceFile]) -> list[ToilItem]:
    items: list[ToilItem] = []
    for file in files:
        base = file.path.rsplit("/", 1)[-1].lower()
        if base == "package.json":
            items.extend(_npm(file))
        elif base == "requirements.txt":
            items.extend(_requirements(file))
    return items
