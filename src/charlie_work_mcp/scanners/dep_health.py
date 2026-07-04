from __future__ import annotations

from ..models import HEURISTIC, VERIFIED, SourceFile, ToilItem, ToilKind, make_id
from ..services import registries
from ..services.lockfiles import ResolvedPackage, parse_lockfiles
from ..services.osv import Vulnerability, query_vulns

_MAX_OUTDATED_LOOKUPS = 80


def _vulnerable_items(
    packages: list[ResolvedPackage], vulns: dict[tuple[str, str, str], list[Vulnerability]]
) -> list[ToilItem]:
    items: list[ToilItem] = []
    for pkg in packages:
        hits = vulns.get(pkg.key())
        if not hits:
            continue
        top = max(hits, key=lambda v: v.severity or 0.0)
        ids = ", ".join(v.id for v in hits[:3])
        fix = None
        if top.fixed:
            fix = f"Upgrade {pkg.name} {pkg.version} -> {top.fixed}."
        items.append(
            ToilItem(
                id=make_id(ToilKind.vulnerable_dep, pkg.path, None, f"{pkg.name}@{pkg.version}:{ids}"),
                kind=ToilKind.vulnerable_dep,
                path=pkg.path,
                title=f"{pkg.name} {pkg.version} has known vulnerabilities ({ids})",
                evidence=top.summary or ids,
                severity=5,
                effort=2,
                confidence=VERIFIED,
                rule_id="charlie/vulnerable-dep",
                security_severity=top.severity or 8.0,
                fix=fix,
            )
        )
    return items


def _outdated_items(packages: list[ResolvedPackage]) -> list[ToilItem]:
    items: list[ToilItem] = []
    by_ecosystem: dict[str, list] = {}
    for pkg in packages:
        by_ecosystem.setdefault(pkg.ecosystem, []).append(pkg)
    checked = 0
    for ecosystem, pkgs in by_ecosystem.items():
        if ecosystem not in registries._FETCHERS or checked >= _MAX_OUTDATED_LOOKUPS:
            continue
        names = sorted({p.name for p in pkgs})[: _MAX_OUTDATED_LOOKUPS - checked]
        checked += len(names)
        latest = registries.latest_versions(ecosystem, names)
        for pkg in pkgs:
            newest = latest.get(pkg.name)
            if not newest:
                continue
            behind = registries.majors_behind(pkg.version, newest)
            if not behind:
                continue
            items.append(
                ToilItem(
                    id=make_id(ToilKind.outdated_dep, pkg.path, None, f"{pkg.name}:{newest}"),
                    kind=ToilKind.outdated_dep,
                    path=pkg.path,
                    title=f"{pkg.name} is {behind} major version(s) behind ({pkg.version} -> {newest})",
                    evidence=f"{pkg.name} {pkg.version}, latest {newest}",
                    severity=3 if behind >= 2 else 2,
                    effort=3,
                    confidence=HEURISTIC,
                    rule_id="charlie/outdated-dep",
                    fix=f"Upgrade {pkg.name} to {newest}.",
                )
            )
    return items


def scan(files: list[SourceFile], online: bool = True, check_outdated: bool = True) -> list[ToilItem]:
    packages = parse_lockfiles(files)
    if not packages or not online:
        return []
    items = _vulnerable_items(packages, query_vulns(packages))
    if check_outdated:
        items.extend(_outdated_items(packages))
    return items
