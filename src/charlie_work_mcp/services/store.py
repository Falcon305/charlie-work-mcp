from __future__ import annotations

import json
import os
import tempfile

from ..constants import LEDGER_FILENAME, STATE_DIRNAME
from ..models import LedgerEntry


def _state_dir(root: str) -> str:
    return os.path.join(os.path.abspath(root), STATE_DIRNAME)


def _ledger_path(root: str) -> str:
    return os.path.join(_state_dir(root), LEDGER_FILENAME)


def load_entries(root: str) -> list[LedgerEntry]:
    path = _ledger_path(root)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    entries: list[LedgerEntry] = []
    for row in raw.get("entries", []):
        try:
            entries.append(LedgerEntry(**row))
        except (TypeError, ValueError):
            continue
    return entries


def append_entry(root: str, entry: LedgerEntry) -> list[LedgerEntry]:
    entries = load_entries(root)
    entries.append(entry)
    _write(root, entries)
    return entries


def _write(root: str, entries: list[LedgerEntry]) -> None:
    directory = _state_dir(root)
    os.makedirs(directory, exist_ok=True)
    payload = {"entries": [entry.model_dump() for entry in entries]}
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=directory, delete=False, suffix=".tmp"
    )
    try:
        json.dump(payload, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    finally:
        handle.close()
    os.replace(handle.name, _ledger_path(root))


def credit_counts(entries: list[LedgerEntry]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry.who] = counts.get(entry.who, 0) + 1
    return counts


def champion(counts: dict[str, int]) -> str | None:
    if not counts:
        return None
    return max(sorted(counts), key=lambda who: counts[who])
