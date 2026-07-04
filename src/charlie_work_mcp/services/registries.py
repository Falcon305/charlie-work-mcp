from __future__ import annotations

import httpx
from packaging.version import InvalidVersion, Version


def _pypi_latest(client: httpx.Client, name: str) -> str | None:
    response = client.get(f"https://pypi.org/pypi/{name}/json")
    if response.status_code != 200:
        return None
    releases = response.json().get("releases", {})
    best: Version | None = None
    for raw in releases:
        try:
            candidate = Version(raw)
        except InvalidVersion:
            continue
        if candidate.is_prerelease:
            continue
        if best is None or candidate > best:
            best = candidate
    return str(best) if best else None


def _npm_latest(client: httpx.Client, name: str) -> str | None:
    response = client.get(
        f"https://registry.npmjs.org/{name}",
        headers={"Accept": "application/vnd.npm.install-v1+json"},
    )
    if response.status_code != 200:
        return None
    return response.json().get("dist-tags", {}).get("latest")


def _crates_latest(client: httpx.Client, name: str) -> str | None:
    response = client.get(f"https://crates.io/api/v1/crates/{name}")
    if response.status_code != 200:
        return None
    return response.json().get("crate", {}).get("max_stable_version")


def _go_latest(client: httpx.Client, name: str) -> str | None:
    response = client.get(f"https://proxy.golang.org/{name}/@latest")
    if response.status_code != 200:
        return None
    return str(response.json().get("Version", "")).lstrip("v") or None


_FETCHERS = {
    "PyPI": _pypi_latest,
    "npm": _npm_latest,
    "crates.io": _crates_latest,
    "Go": _go_latest,
}


def majors_behind(current: str, latest: str) -> int | None:
    try:
        cur = Version(current)
        new = Version(latest)
    except InvalidVersion:
        return None
    return max(0, new.major - cur.major)


def latest_versions(
    ecosystem: str, names: list[str], timeout: float = 12.0
) -> dict[str, str]:
    fetcher = _FETCHERS.get(ecosystem)
    if not fetcher:
        return {}
    out: dict[str, str] = {}
    try:
        with httpx.Client(timeout=timeout, headers={"User-Agent": "charlie-work-mcp"}) as client:
            for name in names:
                try:
                    latest = fetcher(client, name)
                except httpx.HTTPError:
                    continue
                if latest:
                    out[name] = latest
    except httpx.HTTPError:
        return out
    return out
