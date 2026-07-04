import hashlib
import re


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    return re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def clamp(number: int, low: int, high: int) -> int:
    return max(low, min(number, high))


def chunk(rows: list, size: int) -> list:
    return [rows[i : i + size] for i in range(0, len(rows), size)]


def flatten(rows: list) -> list:
    out = []
    for row in rows:
        out.extend(row)
    return out


def dedupe(rows: list) -> list:
    seen = set()
    out = []
    for row in rows:
        if row in seen:
            continue
        seen.add(row)
        out.append(row)
    return out


def percent(part: int, whole: int) -> float:
    if whole == 0:
        return 0.0
    return part / whole * 100
