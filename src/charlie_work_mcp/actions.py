from __future__ import annotations

from .fixers import build_fix
from .models import FixResult, NextAction, ToilItem
from .scan import scan_repo


def _location(item: ToilItem) -> str:
    return f"{item.path}:{item.line}" if item.line else item.path


def next_action(repo: str = ".", online: bool = True) -> NextAction:
    items = scan_repo(repo, online=online)
    if not items:
        return NextAction(report="Nothing in the pile — the grease trap is clean.", found=False)
    top = build_fix(items[0], repo)
    hot = (
        f", sitting in a hotspot (churn x complexity {top.hotspot_multiplier}x)"
        if top.hotspot_multiplier > 1
        else ""
    )
    report = f"{top.title} at {_location(top)} — severity {top.severity}, ~{top.est_minutes}m to clear{hot}."
    actions: list[str] = []
    if top.patch:
        actions.append("Apply the unified diff in `patch` with `git apply`, then run the tests.")
        actions.append(f"Record the win: charlie_did_it(toil_id='{top.id}').")
    else:
        actions.append(top.fix or "Handle this one by hand — Charlie won't guess a patch here.")
    actions.append("Call charlie_next again for the item after this one.")
    return NextAction(
        report=report,
        found=True,
        item=top,
        fixability=top.fixability,
        patch=top.patch,
        next_actions=actions,
    )


def fix_findings(repo: str = ".", finding_id: str | None = None, top_n: int = 5, online: bool = True) -> FixResult:
    items = scan_repo(repo, online=online)
    items = [i for i in items if i.id == finding_id] if finding_id is not None else items[: max(1, min(top_n, 20))]
    patches: list[ToilItem] = []
    manual: list[ToilItem] = []
    for item in items:
        build_fix(item, repo)
        (patches if item.patch else manual).append(item)
    if finding_id is not None and not items:
        report = f"No open finding with id {finding_id}. Maybe somebody already did it."
    else:
        report = (
            f"{len(patches)} patch(es) ready to apply, {len(manual)} that want a human. "
            "Every patch is a diff — apply it yourself, Charlie never edits your files."
        )
    return FixResult(report=report, patches=patches, manual=manual)
