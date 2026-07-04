from __future__ import annotations

from ..models import SourceFile, ToilItem
from . import certs, code, deps, runbooks, secrets, todos

ALL_SCANNERS = [
    code.scan,
    todos.scan,
    certs.scan,
    deps.scan,
    runbooks.scan,
    secrets.scan,
]


def run_all(files: list[SourceFile]) -> list[ToilItem]:
    found: list[ToilItem] = []
    for scanner in ALL_SCANNERS:
        found.extend(scanner(files))
    return found
