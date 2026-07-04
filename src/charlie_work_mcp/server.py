from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from .models import LedgerEntry, LedgerResult, ScanResult, ToilItem
from .persona import render_ledger, render_scan
from .scan import scan_repo
from .services import store
from .services.github import GithubUnavailable, fetch_labeled_issues

Mode = Literal["charlie", "plain"]

mcp = FastMCP("charlie-work")

_SCAN_DESCRIPTION = (
    "Scan a repository for toil — the un-fun, load-bearing maintenance work everyone ignores: "
    "flaky, skipped, and focused tests; TODO/FIXME/HACK rot; expiring TLS certs; feature flags "
    "read but never set; unpinned dependencies; unowned operational scripts; and stray debug "
    "statements. Returns a prioritized queue. Set mode='plain' for a flavor-free report."
)


def _resolve_mode(mode: Mode | None) -> Mode:
    if mode is not None:
        return mode
    voice = os.environ.get("CHARLIE_VOICE", "").strip().lower()
    if voice in {"off", "0", "false", "plain", "no"}:
        return "plain"
    return "charlie"


def _github_items(include_github: bool, github_repo: str | None) -> tuple[list[ToilItem], str | None]:
    if not include_github or not github_repo:
        return [], None
    try:
        return fetch_labeled_issues(github_repo), None
    except GithubUnavailable as exc:
        return [], f"(github integration skipped: {exc})"


@mcp.tool(
    title="Charlie: scan for toil",
    description=_SCAN_DESCRIPTION,
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
)
def charlie_scan_toil(
    repo: str = ".",
    kinds: list[str] | None = None,
    mode: Mode | None = None,
    offset: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    include_github: bool = False,
    github_repo: str | None = None,
) -> ScanResult:
    resolved = _resolve_mode(mode)
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    offset = max(0, offset)
    extra, note = _github_items(include_github, github_repo)
    everything = scan_repo(repo, kinds=kinds, extra_items=extra)
    total = len(everything)
    page = everything[offset : offset + limit]
    report = render_scan(page, total, offset, resolved)
    if note:
        report = f"{note}\n\n{report}"
    has_more = offset + limit < total
    return ScanResult(
        report=report,
        items=page,
        total=total,
        count=len(page),
        offset=offset,
        has_more=has_more,
        next_offset=(offset + limit) if has_more else None,
    )


@mcp.tool(
    title="Charlie: I did it",
    description=(
        "Record that someone cleared a piece of toil, by its toil_id from a scan. Persists to a "
        "local ledger so the invisible work becomes visible. Rescans to resolve the item's title."
    ),
    annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=False),
)
def charlie_did_it(
    toil_id: str,
    who: str,
    repo: str = ".",
    note: str | None = None,
    mode: Mode | None = None,
) -> LedgerResult:
    resolved = _resolve_mode(mode)
    match: ToilItem | None = None
    for item in scan_repo(repo):
        if item.id == toil_id:
            match = item
            break
    entry = LedgerEntry(
        toil_id=toil_id,
        kind=match.kind.value if match else "unknown",
        title=match.title if match else "cleared toil",
        who=who,
        at=datetime.now(timezone.utc).isoformat(),
        note=note,
    )
    entries = store.append_entry(repo, entry)
    counts = store.credit_counts(entries)
    open_count = len(scan_repo(repo))
    report = render_ledger(entries, counts, store.champion(counts), open_count, resolved)
    return LedgerResult(
        report=report,
        entries=entries,
        credits=counts,
        champion=store.champion(counts),
    )


@mcp.tool(
    title="Charlie: the ledger",
    description=(
        "Report the credit ledger for standup or retro: who cleared what toil, the current "
        "Champion of the Grease Trap, and how much is still open."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
def charlie_ledger(repo: str = ".", mode: Mode | None = None) -> LedgerResult:
    resolved = _resolve_mode(mode)
    entries = store.load_entries(repo)
    counts = store.credit_counts(entries)
    open_count = len(scan_repo(repo))
    report = render_ledger(entries, counts, store.champion(counts), open_count, resolved)
    return LedgerResult(
        report=report,
        entries=entries,
        credits=counts,
        champion=store.champion(counts),
    )
