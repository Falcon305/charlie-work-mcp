from __future__ import annotations

from .models import SourceFile, ToilItem, ToilKind

_EST_MINUTES = {
    ToilKind.secret_leak: 30,
    ToilKind.vulnerable_dep: 30,
    ToilKind.expiring_cert: 20,
    ToilKind.flaky_test: 30,
    ToilKind.skipped_test: 10,
    ToilKind.focused_test: 5,
    ToilKind.dead_flag: 15,
    ToilKind.todo_rot: 10,
    ToilKind.dependency_risk: 5,
    ToilKind.outdated_dep: 15,
    ToilKind.unowned_runbook: 20,
    ToilKind.debug_leftover: 2,
}

_MINUTES_PER_LINE = 0.5


def annotate(items: list[ToilItem]) -> None:
    for item in items:
        if not item.est_minutes:
            item.est_minutes = _EST_MINUTES.get(item.kind, 10)


def total_minutes(items: list[ToilItem]) -> int:
    return sum(item.est_minutes for item in items)


def toil_score(items: list[ToilItem]) -> float:
    return round(sum(item.severity * item.est_minutes * item.hotspot_multiplier for item in items), 1)


def debt_ratio(items: list[ToilItem], loc: int) -> float:
    if loc <= 0:
        return 0.0
    return round(total_minutes(items) / (loc * _MINUTES_PER_LINE), 4)


def grade(ratio: float) -> str:
    if ratio < 0.05:
        return "A"
    if ratio < 0.10:
        return "B"
    if ratio < 0.20:
        return "C"
    if ratio < 0.50:
        return "D"
    return "E"


def loc_of(files: list[SourceFile]) -> int:
    return sum(file.text.count("\n") + 1 for file in files)


def summarize(items: list[ToilItem], files: list[SourceFile]) -> dict:
    loc = loc_of(files)
    ratio = debt_ratio(items, loc)
    counts: dict[str, int] = {}
    for item in items:
        counts[item.kind.value] = counts.get(item.kind.value, 0) + 1
    return {
        "toil_score": toil_score(items),
        "total_minutes": total_minutes(items),
        "loc": loc,
        "debt_ratio": ratio,
        "grade": grade(ratio),
        "count": len(items),
        "counts": counts,
    }
