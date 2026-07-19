from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from . import history, scoring
from .actions import fix_findings, next_action
from .constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from .fixers import build_fix
from .gitmeta import detect_github_repo
from .models import (
    Explanation,
    FixResult,
    LedgerEntry,
    LedgerResult,
    NextAction,
    ScanResult,
    Summary,
    ToilItem,
    TrendReport,
    TriagePlan,
)
from .persona import render_ledger, render_scan
from .scan import scan_repo, summarize_repo
from .services import store
from .services.github import GithubUnavailable, fetch_labeled_issues

Mode = Literal["charlie", "plain"]

_INSTRUCTIONS = """Charlie Work finds and dignifies the toil in a repository — the un-fun, load-bearing
maintenance nobody else will do: flaky/skipped/focused tests, TODO rot, expiring TLS certs, dead feature
flags, unpinned/vulnerable/outdated dependencies, unowned runbooks, and stray debug statements.

Typical workflow: call charlie_scan_toil (or charlie_triage for the top N) to see the prioritized queue,
then charlie_next to get the single highest-value item as a ready-to-apply patch, or charlie_fix for a
specific finding. Findings are ranked by git-hotspot x severity, so the top of the queue is where the
team actually bleeds. Use charlie_explain for the evidence behind any finding.

Fixes are patch-first: charlie_next and charlie_fix return a unified diff — this server never edits the
user's files, so apply the diff yourself (git apply) or open a PR. Patches labelled auto-safe are
mechanical; needs-review patches change behaviour and want a human glance. Secrets, certificates, and
major dependency bumps are never auto-patched — surface them for a person.

Each finding carries a confidence tier (verified, high, heuristic); a charlie.toml can exclude paths,
raise the confidence floor, and suppress rules, and inline "# charlie: ignore[rule]" is respected. Set
mode="plain" (or CHARLIE_VOICE=off) for flavour-free output suitable for CI."""

mcp = FastMCP("charlie-work", instructions=_INSTRUCTIONS)

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


def _github_items(
    include_github: bool, github_repo: str | None, repo: str = "."
) -> tuple[list[ToilItem], str | None]:
    if not include_github:
        return [], None
    target = github_repo or detect_github_repo(repo)
    if not target:
        return [], "(github integration skipped: no github_repo given and no origin remote found)"
    try:
        return fetch_labeled_issues(target), None
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
    online: bool = True,
) -> ScanResult:
    resolved = _resolve_mode(mode)
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    offset = max(0, offset)
    extra, note = _github_items(include_github, github_repo, repo)
    everything = scan_repo(repo, kinds=kinds, extra_items=extra, online=online)
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
    for item in scan_repo(repo, online=False):
        if item.id == toil_id:
            match = item
            break
    entry = LedgerEntry(
        toil_id=toil_id,
        kind=match.kind.value if match else "unknown",
        title=match.title if match else "cleared toil",
        who=who,
        at=datetime.now(UTC).isoformat(),
        note=note,
    )
    entries = store.append_entry(repo, entry)
    counts = store.credit_counts(entries)
    open_count = len(scan_repo(repo, online=False))
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
    minutes = _reclaimed_minutes(entries)
    open_count = len(scan_repo(repo, online=False))
    report = render_ledger(entries, counts, store.champion(counts), open_count, resolved)
    return LedgerResult(
        report=report,
        entries=entries,
        credits=counts,
        minutes=minutes,
        champion=store.champion(counts),
    )


def _reclaimed_minutes(entries: list[LedgerEntry]) -> dict[str, int]:
    from .models import ToilKind

    minutes: dict[str, int] = {}
    for entry in entries:
        try:
            kind = ToilKind(entry.kind)
        except ValueError:
            continue
        minutes[entry.who] = minutes.get(entry.who, 0) + scoring._EST_MINUTES.get(kind, 10)
    return minutes


@mcp.tool(
    title="Charlie: the toil budget",
    description=(
        "Report the repo's toil budget: total estimated remediation minutes, a debt ratio, an A-E "
        "maintainability grade, and counts by kind. Google SRE says keep toil under 50 percent."
    ),
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
)
def charlie_summary(repo: str = ".", online: bool = True) -> Summary:
    _, summary = summarize_repo(repo, online=online)
    hours = round(summary["total_minutes"] / 60, 1)
    report = (
        f"Grade {summary['grade']} — {summary['count']} item(s), ~{hours}h of Charlie Work, "
        f"debt ratio {summary['debt_ratio']:.1%}."
    )
    return Summary(report=report, **summary)


@mcp.tool(
    title="Charlie: explain this",
    description="Explain why a specific finding (by its toil id) is real debt, with evidence and a fix.",
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
)
def charlie_explain(finding_id: str, repo: str = ".", online: bool = True) -> Explanation:
    match = next((i for i in scan_repo(repo, online=online) if i.id == finding_id), None)
    if match is None:
        return Explanation(
            report=f"No open finding with id {finding_id}. Maybe somebody already did it.", found=False
        )
    hot = (
        f" It sits in a hotspot (churn x complexity {match.hotspot_multiplier}x)."
        if match.hotspot_multiplier > 1
        else ""
    )
    owner = f" Owner: {match.owner}." if match.owner else ""
    fix = f" Fix: {match.fix}" if match.fix else ""
    report = (
        f"{match.title} at {match.path}:{match.line or '?'}. Confidence {match.confidence}, "
        f"severity {match.severity}, ~{match.est_minutes}m to clear.{hot}{owner}{fix} Evidence: {match.evidence}"
    )
    return Explanation(report=report, found=True, item=match)


@mcp.tool(
    title="Charlie: triage",
    description="Return the top-N highest-priority toil items as an action plan for an agent to work through.",
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
)
def charlie_triage(repo: str = ".", top_n: int = 5, online: bool = True) -> TriagePlan:
    items = scan_repo(repo, online=online)[: max(1, min(top_n, 20))]
    lines = ["Top of the pile. Start here, nobody else will:"]
    for index, item in enumerate(items, start=1):
        location = f"{item.path}:{item.line}" if item.line else item.path
        lines.append(f"{index}. [{item.confidence}] {item.title} ({location}) ~{item.est_minutes}m")
    return TriagePlan(report="\n".join(lines), items=items)


@mcp.tool(
    title="Charlie: the trend",
    description="Record a toil snapshot and report how the toil budget has moved since last time.",
    annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=True),
)
def charlie_trend(repo: str = ".", online: bool = True) -> TrendReport:
    _, summary = summarize_repo(repo, online=online)
    history.record(repo, summary)
    delta = history.delta(repo)
    if delta is None:
        report = f"First snapshot: toil score {summary['toil_score']}, grade {summary['grade']}. Come back later."
    else:
        direction = "down" if delta["toil_score_delta"] <= 0 else "UP"
        report = (
            f"Toil score {direction} {abs(delta['toil_score_delta'])} since last snapshot "
            f"(now {summary['toil_score']}, grade {summary['grade']})."
        )
    return TrendReport(report=report, current=summary, delta=delta)


@mcp.tool(
    title="Charlie: the next thing to do",
    description=(
        "Return the single highest-priority piece of toil as an executable move: where it is, why it "
        "matters (hotspot x severity), a ready-to-apply unified-diff patch when Charlie can fix it "
        "safely, and the follow-up actions. Apply the patch yourself with `git apply` — Charlie never "
        "writes your files."
    ),
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
)
def charlie_next(repo: str = ".", online: bool = True) -> NextAction:
    return next_action(repo, online=online)


@mcp.tool(
    title="Charlie: fix it (patch, don't write)",
    description=(
        "Return unified-diff patches for fixable toil — by finding id, or the top N. Each patch is "
        "labelled auto-safe (mechanical) or needs-review (changes behaviour). Secrets, certs, and "
        "dependency bumps are surfaced for a human, never auto-patched. Charlie never edits files; "
        "apply the diffs yourself with `git apply` or open a PR."
    ),
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
)
def charlie_fix(finding_id: str | None = None, repo: str = ".", top_n: int = 5, online: bool = True) -> FixResult:
    return fix_findings(repo, finding_id=finding_id, top_n=top_n, online=online)


@mcp.resource("toil://queue")
def toil_queue_resource() -> str:
    items = scan_repo(".", online=False)
    return render_scan(items, len(items), 0, "plain")


@mcp.resource("toil://item/{finding_id}")
def toil_item_resource(finding_id: str) -> str:
    match = next((i for i in scan_repo(".", online=False) if i.id == finding_id), None)
    if match is None:
        return f"No open finding with id {finding_id}."
    return build_fix(match, ".").model_dump_json(indent=2)


@mcp.prompt(title="Triage my toil")
def triage_toil(max_items: int = 5) -> str:
    return (
        f"Call charlie_triage with top_n={max_items}. For each item, decide keep or fix, give a "
        "one-line rationale and an effort size (S/M/L), then propose a concrete fix for the top "
        "three. Use charlie_explain if you need the evidence behind any item."
    )


@mcp.prompt(title="Charlie: fix the next thing")
def fix_next() -> str:
    return (
        "Call charlie_next. If it returns a patch, show me the diff and a one-line summary of what it "
        "does, apply it with git apply, run the tests, and report the result. If it's manual, explain "
        "what a human needs to do. Then call charlie_next again for the one after it."
    )


@mcp.prompt(title="Charlie: pre-PR check")
def pre_pr_check(base: str = "origin/main") -> str:
    return (
        f"Run the charlie-work gate against base '{base}' (or call charlie_scan_toil and compare to the "
        "diff). List any NEW blocking toil this branch introduces, propose a fix for each via "
        "charlie_fix, and don't let me open the PR until the new toil is cleared or explicitly waived."
    )


@mcp.prompt(title="Charlie: rules for AGENTS.md")
def charlie_rules() -> str:
    from .rules import agents_block

    return (
        "Add this Charlie Work section to the repo's AGENTS.md (or CLAUDE.md) so every agent knows how "
        "and when to use it, then keep it up to date:\n\n" + agents_block()
    )
