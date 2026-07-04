from __future__ import annotations

from ..models import SourceFile, ToilItem
from . import certs, dead_flags, debug, deps, runbooks, tests, todos

ALL_SCANNERS = [
    tests.scan,
    todos.scan,
    certs.scan,
    dead_flags.scan,
    deps.scan,
    runbooks.scan,
    debug.scan,
]


def run_all(files: list[SourceFile]) -> list[ToilItem]:
    found: list[ToilItem] = []
    for scanner in ALL_SCANNERS:
        found.extend(scanner(files))
    return found
