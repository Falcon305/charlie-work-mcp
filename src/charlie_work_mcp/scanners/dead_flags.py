from __future__ import annotations

import re

from ..models import SourceFile, ToilItem, ToilKind, make_id

_READ_PATTERNS = [
    re.compile(r"""is_enabled\(\s*['"]([A-Za-z0-9_.-]+)['"]"""),
    re.compile(r"""isEnabled\(\s*['"]([A-Za-z0-9_.-]+)['"]"""),
    re.compile(r"""feature_enabled\(\s*['"]([A-Za-z0-9_.-]+)['"]"""),
    re.compile(r"""flags?\.is_?on\(\s*['"]([A-Za-z0-9_.-]+)['"]"""),
    re.compile(r"""get_flag\(\s*['"]([A-Za-z0-9_.-]+)['"]"""),
    re.compile(r"""feature_flags?\[\s*['"]([A-Za-z0-9_.-]+)['"]\s*\]"""),
    re.compile(r"""flag\(\s*['"]([A-Za-z0-9_.-]+)['"]"""),
]

_DEF_PATTERNS = [
    re.compile(r"""['"]([A-Za-z0-9_.-]+)['"]\s*[:=]\s*(?:true|false|True|False|0|1)"""),
    re.compile(r"""register_flag\(\s*['"]([A-Za-z0-9_.-]+)['"]"""),
    re.compile(r"""define_flag\(\s*['"]([A-Za-z0-9_.-]+)['"]"""),
    re.compile(r"""add_flag\(\s*['"]([A-Za-z0-9_.-]+)['"]"""),
    re.compile(r"""set_flag\(\s*['"]([A-Za-z0-9_.-]+)['"]"""),
]


def scan(files: list[SourceFile]) -> list[ToilItem]:
    reads: dict[str, tuple[str, int, str]] = {}
    defined: set[str] = set()

    for file in files:
        for lineno, line in enumerate(file.text.splitlines(), start=1):
            for pattern in _READ_PATTERNS:
                for name in pattern.findall(line):
                    reads.setdefault(name, (file.path, lineno, line.strip()[:200]))
            for pattern in _DEF_PATTERNS:
                for name in pattern.findall(line):
                    defined.add(name)

    items: list[ToilItem] = []
    for name, (path, lineno, evidence) in sorted(reads.items()):
        if name in defined:
            continue
        items.append(
            ToilItem(
                id=make_id(ToilKind.dead_flag, path, lineno, name),
                kind=ToilKind.dead_flag,
                path=path,
                line=lineno,
                title=f"Feature flag '{name}' is read but never set anywhere",
                evidence=evidence,
                severity=3,
                effort=2,
            )
        )
    return items
