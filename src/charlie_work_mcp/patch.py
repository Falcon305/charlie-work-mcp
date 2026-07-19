from __future__ import annotations

import difflib


def unified_diff(path: str, original: str, patched: str) -> str:
    if original == patched:
        return ""
    original_lines = original.splitlines(keepends=True)
    patched_lines = patched.splitlines(keepends=True)
    if original_lines and not original_lines[-1].endswith("\n"):
        original_lines[-1] += "\n"
    if patched_lines and not patched_lines[-1].endswith("\n"):
        patched_lines[-1] += "\n"
    diff = difflib.unified_diff(
        original_lines,
        patched_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        n=3,
    )
    return "".join(diff)
