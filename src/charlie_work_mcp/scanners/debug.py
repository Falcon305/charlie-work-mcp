from __future__ import annotations

import re

from ..fs import is_test_file
from ..models import SourceFile, ToilItem, ToilKind, make_id

_PATTERNS = [
    (re.compile(r"\bconsole\.log\("), "console.log left in the code"),
    (re.compile(r"\bdebugger;"), "debugger statement left in the code"),
    (re.compile(r"\bpdb\.set_trace\("), "pdb.set_trace left in the code"),
    (re.compile(r"\bbreakpoint\(\s*\)"), "breakpoint() left in the code"),
    (re.compile(r"\bbinding\.pry\b"), "binding.pry left in the code"),
    (re.compile(r"\bdd\(\s*\)"), "dd() debug dump left in the code"),
]

_SUFFIXES = (".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".rb")


def scan(files: list[SourceFile]) -> list[ToilItem]:
    items: list[ToilItem] = []
    for file in files:
        if not file.path.lower().endswith(_SUFFIXES):
            continue
        if is_test_file(file.path):
            continue
        for lineno, line in enumerate(file.text.splitlines(), start=1):
            stripped = line.lstrip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue
            for pattern, title in _PATTERNS:
                if pattern.search(line):
                    items.append(
                        ToilItem(
                            id=make_id(ToilKind.debug_leftover, file.path, lineno, line.strip()),
                            kind=ToilKind.debug_leftover,
                            path=file.path,
                            line=lineno,
                            title=title,
                            evidence=line.strip()[:200],
                            severity=2,
                            effort=1,
                        )
                    )
                    break
    return items
