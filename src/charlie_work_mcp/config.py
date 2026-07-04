from __future__ import annotations

import os
import tomllib

from pydantic import BaseModel, Field

_CONFIDENCE_RANK = {"heuristic": 0, "high": 1, "verified": 2}


class Config(BaseModel):
    exclude: list[str] = Field(default_factory=list)
    disable: list[str] = Field(default_factory=list)
    per_file_ignores: dict[str, list[str]] = Field(default_factory=dict)
    min_confidence: str = "heuristic"
    gate_min_severity: int = 4
    gate_min_confidence: str = "high"

    def confidence_rank(self, value: str) -> int:
        return _CONFIDENCE_RANK.get(value, 0)


def _from_table(table: dict) -> Config:
    return Config(
        exclude=list(table.get("exclude", [])),
        disable=list(table.get("disable", [])),
        per_file_ignores={k: list(v) for k, v in table.get("per-file-ignores", {}).items()},
        min_confidence=str(table.get("min_confidence", "heuristic")),
        gate_min_severity=int(table.get("gate_min_severity", 4)),
        gate_min_confidence=str(table.get("gate_min_confidence", "high")),
    )


def _read(path: str) -> dict | None:
    try:
        with open(path, "rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return None


def load_config(root: str) -> Config:
    charlie_toml = os.path.join(root, "charlie.toml")
    if os.path.exists(charlie_toml):
        data = _read(charlie_toml)
        if data is not None:
            table = data.get("tool", {}).get("charlie", data)
            return _from_table(table)
    pyproject = os.path.join(root, "pyproject.toml")
    if os.path.exists(pyproject):
        data = _read(pyproject)
        if data is not None:
            table = data.get("tool", {}).get("charlie")
            if isinstance(table, dict):
                return _from_table(table)
    return Config()
