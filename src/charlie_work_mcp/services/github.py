from __future__ import annotations

import os

import httpx

from ..models import ToilItem, ToilKind, make_id

_LABELS = {"chore", "tech-debt", "techdebt", "maintenance", "good-first-issue", "good first issue"}
_API = "https://api.github.com"


class GithubUnavailable(Exception):
    pass


def _token() -> str | None:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def _severity_for_labels(labels: set[str]) -> int:
    if "tech-debt" in labels or "techdebt" in labels:
        return 3
    if "chore" in labels or "maintenance" in labels:
        return 2
    return 2


def fetch_labeled_issues(repo: str, limit: int = 50) -> list[ToilItem]:
    token = _token()
    if not token:
        raise GithubUnavailable("no GITHUB_TOKEN in environment")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"{_API}/repos/{repo}/issues"
    params = {"state": "open", "per_page": str(min(limit, 100)), "sort": "updated"}
    try:
        response = httpx.get(url, headers=headers, params=params, timeout=20)
    except httpx.HTTPError as exc:
        raise GithubUnavailable(f"request failed: {exc}") from exc
    if response.status_code == 401:
        raise GithubUnavailable("github rejected the token (401)")
    if response.status_code == 403:
        raise GithubUnavailable("github rate limit or forbidden (403)")
    if response.status_code == 404:
        raise GithubUnavailable(f"repo not found: {repo} (404)")
    if response.status_code >= 400:
        raise GithubUnavailable(f"github error {response.status_code}")

    items: list[ToilItem] = []
    for issue in response.json():
        if "pull_request" in issue:
            continue
        labels = {label["name"].lower() for label in issue.get("labels", [])}
        if labels.isdisjoint(_LABELS):
            continue
        number = issue["number"]
        title = issue["title"].strip()
        items.append(
            ToilItem(
                id=make_id(ToilKind.todo_rot, f"github/{repo}", number, title),
                kind=ToilKind.todo_rot,
                path=f"{repo}#{number}",
                line=None,
                title=f"Tracked toil: {title}",
                evidence=", ".join(sorted(labels)),
                severity=_severity_for_labels(labels),
                effort=3,
                source="github",
            )
        )
    return items
