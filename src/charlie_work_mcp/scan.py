from __future__ import annotations

from datetime import UTC, datetime

from . import hotspots, owners, scoring
from .config import Config, load_config
from .constants import CERT_WARN_DAYS
from .fs import walk_repo
from .gitmeta import blame_line_times, is_git_repo
from .models import SourceFile, ToilItem, ToilKind
from .scanners import dep_health, run_all
from .suppress import apply_suppressions

_BLAME_ENRICHED = {ToilKind.todo_rot, ToilKind.debug_leftover}
_MAX_BLAME_FILES = 300


def _urgency(item: ToilItem) -> float:
    if item.kind == ToilKind.expiring_cert and item.staleness_days is not None:
        base = max(0, CERT_WARN_DAYS - item.staleness_days)
        if item.staleness_days < 0:
            base += 40
        return float(base)
    if item.kind in _BLAME_ENRICHED and item.staleness_days is not None:
        return min(max(item.staleness_days, 0), 730) / 730 * 10
    return 0.0


def compute_priority(item: ToilItem) -> float:
    base = item.severity * 10 + (6 - item.effort) * 2 + _urgency(item)
    if item.security_severity:
        base += item.security_severity * 2
    return round(base * item.hotspot_multiplier, 3)


def _enrich_staleness(root: str, items: list[ToilItem], now: datetime) -> None:
    if not is_git_repo(root):
        return
    by_path: dict[str, list[ToilItem]] = {}
    for item in items:
        if item.kind in _BLAME_ENRICHED and item.line is not None:
            by_path.setdefault(item.path, []).append(item)
    for path in list(by_path)[:_MAX_BLAME_FILES]:
        times = blame_line_times(root, path)
        if not times:
            continue
        for item in by_path[path]:
            epoch = times.get(item.line or 0)
            if epoch is None:
                continue
            committed = datetime.fromtimestamp(epoch, tz=UTC)
            item.staleness_days = max(0, (now - committed).days)


def scan_detailed(
    root: str,
    kinds: list[str] | None = None,
    extra_items: list[ToilItem] | None = None,
    now: datetime | None = None,
    online: bool = True,
    config: Config | None = None,
) -> tuple[list[ToilItem], list[SourceFile]]:
    reference = now or datetime.now(UTC)
    resolved_config = config or load_config(root)
    files = walk_repo(root)
    items = run_all(files)
    if online:
        items.extend(dep_health.scan(files, online=True))
    if extra_items:
        items.extend(extra_items)
    items = apply_suppressions(items, files, resolved_config, root)
    _enrich_staleness(root, items, reference)
    hotspots.apply_multipliers(items, hotspots.compute_multipliers(root, files))
    owners.annotate(items, owners.load_owners(root))
    scoring.annotate(items)
    for item in items:
        item.priority = compute_priority(item)
    if kinds:
        wanted = set(kinds)
        items = [item for item in items if item.kind.value in wanted]
    items.sort(key=lambda i: (-i.priority, i.path, i.line or 0))
    return items, files


def scan_repo(
    root: str,
    kinds: list[str] | None = None,
    extra_items: list[ToilItem] | None = None,
    now: datetime | None = None,
    online: bool = True,
    config: Config | None = None,
) -> list[ToilItem]:
    items, _ = scan_detailed(root, kinds, extra_items, now, online, config)
    return items


def summarize_repo(root: str, online: bool = False) -> tuple[list[ToilItem], dict]:
    items, files = scan_detailed(root, online=online)
    return items, scoring.summarize(items, files)
