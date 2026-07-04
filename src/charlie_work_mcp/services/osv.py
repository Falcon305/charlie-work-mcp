from __future__ import annotations

import httpx

from .lockfiles import ResolvedPackage

_BATCH_URL = "https://api.osv.dev/v1/querybatch"
_VULN_URL = "https://api.osv.dev/v1/vulns/"
_BATCH_SIZE = 500


class Vulnerability:
    def __init__(self, vuln_id: str, summary: str, fixed: str | None, severity: float | None) -> None:
        self.id = vuln_id
        self.summary = summary
        self.fixed = fixed
        self.severity = severity


def _fixed_version(record: dict, name: str) -> str | None:
    for affected in record.get("affected", []):
        pkg = affected.get("package", {})
        if pkg.get("name", "").lower() != name.lower():
            continue
        for rng in affected.get("ranges", []):
            for event in rng.get("events", []):
                if "fixed" in event:
                    return event["fixed"]
    return None


def _severity_score(record: dict) -> float | None:
    for entry in record.get("severity", []):
        score = entry.get("score", "")
        match = score.split("/")[0]
        try:
            return float(match)
        except ValueError:
            continue
    database = record.get("database_specific", {})
    label = str(database.get("severity", "")).upper()
    return {"CRITICAL": 9.5, "HIGH": 8.0, "MODERATE": 5.5, "MEDIUM": 5.5, "LOW": 3.0}.get(label)


def query_vulns(
    packages: list[ResolvedPackage], timeout: float = 15.0
) -> dict[tuple[str, str, str], list[Vulnerability]]:
    if not packages:
        return {}
    results: dict[tuple[str, str, str], list[Vulnerability]] = {}
    try:
        with httpx.Client(timeout=timeout, headers={"User-Agent": "charlie-work-mcp"}) as client:
            for start in range(0, len(packages), _BATCH_SIZE):
                chunk = packages[start : start + _BATCH_SIZE]
                queries = [
                    {"package": {"ecosystem": p.ecosystem, "name": p.name}, "version": p.version}
                    for p in chunk
                ]
                response = client.post(_BATCH_URL, json={"queries": queries})
                if response.status_code != 200:
                    continue
                rows = response.json().get("results", [])
                for pkg, row in zip(chunk, rows):
                    ids = [v["id"] for v in (row.get("vulns") or [])]
                    if not ids:
                        continue
                    vulns: list[Vulnerability] = []
                    for vuln_id in ids[:5]:
                        detail = client.get(f"{_VULN_URL}{vuln_id}")
                        if detail.status_code != 200:
                            vulns.append(Vulnerability(vuln_id, "", None, None))
                            continue
                        record = detail.json()
                        vulns.append(
                            Vulnerability(
                                vuln_id,
                                record.get("summary", "") or record.get("details", "")[:140],
                                _fixed_version(record, pkg.name),
                                _severity_score(record),
                            )
                        )
                    if vulns:
                        results[pkg.key()] = vulns
    except httpx.HTTPError:
        return results
    return results
