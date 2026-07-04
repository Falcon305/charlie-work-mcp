from __future__ import annotations

import os

from .constants import MAX_FILE_BYTES, SKIP_DIRS, TEXT_EXTENSIONS
from .models import SourceFile


def _looks_textual(name: str) -> bool:
    lowered = name.lower()
    _, ext = os.path.splitext(lowered)
    if ext in TEXT_EXTENSIONS:
        return True
    special = {
        "makefile",
        "dockerfile",
        "codeowners",
        "requirements.txt",
        "pipfile",
        "gemfile",
    }
    return lowered in special


def walk_repo(root: str) -> list[SourceFile]:
    root = os.path.abspath(root)
    collected: list[SourceFile] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".egg")]
        for name in filenames:
            if not _looks_textual(name):
                continue
            full = os.path.join(dirpath, name)
            try:
                if os.path.getsize(full) > MAX_FILE_BYTES:
                    continue
                with open(full, encoding="utf-8", errors="ignore") as handle:
                    text = handle.read()
            except OSError:
                continue
            rel = os.path.relpath(full, root)
            collected.append(SourceFile(path=rel.replace(os.sep, "/"), text=text))
    collected.sort(key=lambda f: f.path)
    return collected


def is_test_file(path: str) -> bool:
    lowered = path.lower()
    base = lowered.rsplit("/", 1)[-1]
    return (
        base.startswith("test_")
        or base.endswith("_test.py")
        or ".test." in base
        or ".spec." in base
        or "/tests/" in f"/{lowered}"
        or "/test/" in f"/{lowered}"
        or "__tests__" in lowered
    )
