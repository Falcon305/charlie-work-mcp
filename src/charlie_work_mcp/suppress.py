from __future__ import annotations

import os
import re
from fnmatch import fnmatch

from .config import Config
from .models import SourceFile, ToilItem

_INLINE = re.compile(r"charlie:\s*ignore(?:\[([^\]]+)\])?", re.IGNORECASE)
_FILE_MARKER = re.compile(r"charlie:\s*ignore-file", re.IGNORECASE)


class Suppressions:
    def __init__(self) -> None:
        self.whole_file: set[str] = set()
        self.by_line: dict[str, dict[int, set[str]]] = {}


def _rule_matches(item: ToilItem, token: str) -> bool:
    token = token.strip()
    return fnmatch(item.rule_id, token) or fnmatch(item.kind.value, token) or token == "all"


def collect_inline(files: list[SourceFile]) -> Suppressions:
    result = Suppressions()
    for file in files:
        for lineno, line in enumerate(file.text.splitlines(), start=1):
            if _FILE_MARKER.search(line):
                result.whole_file.add(file.path)
            match = _INLINE.search(line)
            if match and not _FILE_MARKER.search(line):
                rules = match.group(1)
                tokens = {t.strip() for t in rules.split(",")} if rules else {"all"}
                result.by_line.setdefault(file.path, {}).setdefault(lineno, set()).update(tokens)
    return result


def _load_charlieignore(root: str) -> list[str]:
    path = os.path.join(root, ".charlieignore")
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            return [ln.strip() for ln in handle if ln.strip() and not ln.startswith("#")]
    except OSError:
        return []


def _excluded(path: str, patterns: list[str]) -> bool:
    return any(fnmatch(path, pattern) or fnmatch(path, f"{pattern}/*") for pattern in patterns)


def _line_suppressed(item: ToilItem, supp: Suppressions) -> bool:
    if item.path in supp.whole_file:
        return True
    lines = supp.by_line.get(item.path, {})
    for candidate in {item.line, item.line_end}:
        if candidate is None:
            continue
        for token in lines.get(candidate, set()):
            if token == "all" or _rule_matches(item, token):
                return True
    return False


def apply_suppressions(
    items: list[ToilItem], files: list[SourceFile], config: Config, root: str
) -> list[ToilItem]:
    inline = collect_inline(files)
    exclude = config.exclude + _load_charlieignore(root)
    min_rank = config.confidence_rank(config.min_confidence)
    kept: list[ToilItem] = []
    for item in items:
        if _excluded(item.path, exclude):
            continue
        if any(_rule_matches(item, token) for token in config.disable):
            continue
        if config.confidence_rank(item.confidence) < min_rank:
            continue
        per_file = [
            token
            for glob, tokens in config.per_file_ignores.items()
            if fnmatch(item.path, glob) or fnmatch(item.path, f"{glob}/*")
            for token in tokens
        ]
        if any(_rule_matches(item, token) for token in per_file):
            continue
        if _line_suppressed(item, inline):
            continue
        kept.append(item)
    return kept
