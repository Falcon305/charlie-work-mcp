from __future__ import annotations

import re

from ..models import HEURISTIC, SourceFile, ToilItem, ToilKind, make_id
from . import py_ast, treesitter_scan

_FALLBACK_DEBUG = [
    (re.compile(r"\bbinding\.pry\b"), "binding.pry left in the code"),
    (re.compile(r"\bbyebug\b"), "byebug left in the code"),
    (re.compile(r"\bdebugger\b"), "debugger left in the code"),
]
_FALLBACK_EXT = (".rb", ".php", ".java", ".rs")

_FLAG_READ = re.compile(
    r"""(?:is_enabled|isEnabled|feature_enabled|get_flag|flag|variation)\(\s*['"]([A-Za-z0-9_.-]+)['"]"""
)
_FLAG_DEF = re.compile(r"""(?:register_flag|define_flag|add_flag|set_flag)\(\s*['"]([A-Za-z0-9_.-]+)['"]""")
_FLAG_DEF_ASSIGN = re.compile(r"""['"]([A-Za-z0-9_.-]+)['"]\s*[:=]\s*(?:true|false|True|False)""")


def _fallback_debug(file: SourceFile) -> list[ToilItem]:
    if not file.path.lower().endswith(_FALLBACK_EXT):
        return []
    items: list[ToilItem] = []
    for lineno, line in enumerate(file.text.splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith("#") or stripped.startswith("//"):
            continue
        for pattern, title in _FALLBACK_DEBUG:
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
                        confidence=HEURISTIC,
                    )
                )
                break
    return items


def _regex_flags(file: SourceFile) -> tuple[dict[str, tuple[str, int, str]], set[str]]:
    reads: dict[str, tuple[str, int, str]] = {}
    defs: set[str] = set()
    for lineno, line in enumerate(file.text.splitlines(), start=1):
        for name in _FLAG_READ.findall(line):
            reads.setdefault(name, (file.path, lineno, line.strip()[:200]))
        for name in _FLAG_DEF.findall(line):
            defs.add(name)
        for name in _FLAG_DEF_ASSIGN.findall(line):
            defs.add(name)
    return reads, defs


def scan(files: list[SourceFile]) -> list[ToilItem]:
    items: list[ToilItem] = []
    reads: dict[str, tuple[str, int, str]] = {}
    defs: set[str] = set()

    for file in files:
        lowered = file.path.lower()
        if lowered.endswith(".py"):
            items.extend(py_ast.scan_python(file))
            file_reads, file_defs = py_ast.collect_flags(file)
        elif treesitter_scan.language_for(file.path):
            items.extend(treesitter_scan.scan_file(file))
            file_reads, file_defs = _regex_flags(file)
        else:
            items.extend(_fallback_debug(file))
            file_reads, file_defs = _regex_flags(file)
        for name, payload in file_reads.items():
            reads.setdefault(name, payload)
        defs |= file_defs

    for name, (path, lineno, evidence) in sorted(reads.items()):
        if name in defs:
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
                confidence=HEURISTIC,
            )
        )
    return items
