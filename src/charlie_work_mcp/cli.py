from __future__ import annotations

import argparse
import json
import sys

from . import history
from .baseline import filter_new, load_baseline, write_baseline
from .config import load_config
from .diff import added_lines, filter_to_diff
from .models import ToilItem
from .persona import render_scan
from .sarif import to_sarif
from .scan import scan_repo, summarize_repo
from .services import store


def _scan(path: str, online: bool) -> list[ToilItem]:
    return scan_repo(path, online=online)


def _print_items(items: list[ToilItem]) -> None:
    for item in items:
        location = f"{item.path}:{item.line}" if item.line else item.path
        print(f"  [{item.confidence}] {item.rule_id}  {location}  {item.title}")


def _cmd_scan(args: argparse.Namespace) -> int:
    items = _scan(args.path, not args.offline)
    if args.json:
        print(json.dumps([i.model_dump() for i in items], indent=2))
        return 0
    mode = "plain" if args.plain else "charlie"
    print(render_scan(items, len(items), 0, mode))
    return 0


def _cmd_gate(args: argparse.Namespace) -> int:
    config = load_config(args.path)
    items = _scan(args.path, not args.offline)
    if args.base:
        items = filter_to_diff(items, added_lines(args.path, args.base))
    if args.baseline:
        items = filter_new(items, load_baseline(args.path))
    min_severity = args.severity if args.severity is not None else config.gate_min_severity
    min_rank = config.confidence_rank(args.confidence or config.gate_min_confidence)
    blocking = [
        i for i in items if i.severity >= min_severity and config.confidence_rank(i.confidence) >= min_rank
    ]
    if blocking:
        print(f"Charlie Work: {len(blocking)} new blocking item(s) — nobody else was gonna catch these.")
        _print_items(blocking)
        return 1
    print("Charlie Work: no new blocking toil. The grease trap is clean.")
    return 0


def _cmd_baseline(args: argparse.Namespace) -> int:
    items = _scan(args.path, not args.offline)
    count = write_baseline(args.path, items)
    print(f"Charlie Work: wrote baseline with {count} fingerprint(s).")
    return 0


def _cmd_sarif(args: argparse.Namespace) -> int:
    items = _scan(args.path, not args.offline)
    document = to_sarif(items)
    payload = json.dumps(document, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(payload)
        print(f"Charlie Work: wrote {len(items)} finding(s) to {args.output}")
    else:
        print(payload)
    return 0


def _cmd_summary(args: argparse.Namespace) -> int:
    _, summary = summarize_repo(args.path, online=not args.offline)
    hours = round(summary["total_minutes"] / 60, 1)
    print(
        f"Grade {summary['grade']} — {summary['count']} item(s), ~{hours}h of Charlie Work, "
        f"debt ratio {summary['debt_ratio']:.1%} across {summary['loc']} lines."
    )
    return 0


def _cmd_trend(args: argparse.Namespace) -> int:
    _, summary = summarize_repo(args.path, online=not args.offline)
    history.record(args.path, summary)
    delta = history.delta(args.path)
    if delta is None:
        print(f"Charlie Work: first snapshot — toil score {summary['toil_score']}, grade {summary['grade']}.")
    else:
        direction = "down" if delta["toil_score_delta"] <= 0 else "UP"
        print(
            f"Charlie Work: toil score {direction} {abs(delta['toil_score_delta'])} "
            f"(now {summary['toil_score']}, grade {summary['grade']})."
        )
    return 0


def _cmd_ledger(args: argparse.Namespace) -> int:
    from .persona import render_ledger

    entries = store.load_entries(args.path)
    counts = store.credit_counts(entries)
    open_count = len(_scan(args.path, False))
    mode = "plain" if args.plain else "charlie"
    print(render_ledger(entries, counts, store.champion(counts), open_count, mode))
    return 0


def _cmd_install(args: argparse.Namespace) -> int:
    from .install import CLIENTS, guidance, write_project_config

    if args.client == "all":
        for key in CLIENTS:
            print(guidance(key, args.transport, args.url))
            print()
        return 0
    if args.client not in CLIENTS:
        print(f"Unknown client '{args.client}'. Options: {', '.join(CLIENTS)}, all.")
        return 2
    if args.write:
        try:
            path = write_project_config(args.client, args.root, args.transport, args.url)
        except ValueError as exc:
            print(f"Charlie Work: {exc}.\n")
            print(guidance(args.client, args.transport, args.url))
            return 1
        print(f"Charlie Work: wired Charlie into {args.client} at {path}. Restart the client to pick it up.")
        return 0
    print(guidance(args.client, args.transport, args.url))
    return 0


def _cmd_next(args: argparse.Namespace) -> int:
    from .actions import next_action

    result = next_action(args.path, online=not args.offline)
    if not result.found:
        print(result.report)
        return 0
    print(f"{result.report} [{result.fixability}]")
    if result.patch:
        print()
        print(result.patch, end="" if result.patch.endswith("\n") else "\n")
    return 0


def _cmd_fix(args: argparse.Namespace) -> int:
    from .actions import fix_findings

    result = fix_findings(args.path, finding_id=args.id, top_n=args.top, online=not args.offline)
    print(f"# {result.report}")
    for item in result.patches:
        print(f"\n# {item.path}:{item.line or '?'}  [{item.fixability}]  {item.title}")
        print(item.patch, end="" if (item.patch or "").endswith("\n") else "\n")
    for item in result.manual:
        location = f"{item.path}:{item.line}" if item.line else item.path
        print(f"\n# manual: {location}  {item.title} — {item.fix or 'handle by hand'}")
    return 0


def _cmd_init(args: argparse.Namespace) -> int:
    from .rules import agents_block, upsert

    if args.print:
        print(agents_block())
        return 0
    path, action = upsert(args.root, args.file)
    print(f"Charlie Work: {action} the Charlie section in {path}. Every agent that reads it now knows the drill.")
    return 0


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", nargs="?", default=".", help="Repository root to scan.")
    parser.add_argument("--offline", action="store_true", help="Skip network dependency checks.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="charlie-work", description="Find the toil nobody wants to do.")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="Scan and print the prioritized toil queue.")
    _add_common(scan)
    scan.add_argument("--plain", action="store_true", help="Flavor-free output.")
    scan.add_argument("--json", action="store_true", help="Machine-readable JSON output.")
    scan.set_defaults(func=_cmd_scan)

    gate = sub.add_parser("gate", help="Fail if the diff introduces new blocking toil.")
    _add_common(gate)
    gate.add_argument("--base", help="Base git ref to diff against (e.g. origin/main).")
    gate.add_argument("--baseline", action="store_true", help="Only fail on items not in the baseline.")
    gate.add_argument("--severity", type=int, help="Minimum severity that blocks (default 4).")
    gate.add_argument("--confidence", help="Minimum confidence that blocks (default high).")
    gate.set_defaults(func=_cmd_gate)

    base = sub.add_parser("baseline", help="Snapshot current findings so only new ones fail later.")
    _add_common(base)
    base.set_defaults(func=_cmd_baseline)

    sarif = sub.add_parser("sarif", help="Emit SARIF 2.1.0 for GitHub code scanning.")
    _add_common(sarif)
    sarif.add_argument("-o", "--output", help="Write SARIF to this file instead of stdout.")
    sarif.set_defaults(func=_cmd_sarif)

    ledger = sub.add_parser("ledger", help="Show the credit ledger.")
    _add_common(ledger)
    ledger.add_argument("--plain", action="store_true", help="Flavor-free output.")
    ledger.set_defaults(func=_cmd_ledger)

    summary = sub.add_parser("summary", help="Show the toil budget: score, debt ratio, grade.")
    _add_common(summary)
    summary.set_defaults(func=_cmd_summary)

    trend = sub.add_parser("trend", help="Record a snapshot and show the toil-budget delta.")
    _add_common(trend)
    trend.set_defaults(func=_cmd_trend)

    nxt = sub.add_parser("next", help="Print the single next best fix, with a ready-to-apply patch.")
    _add_common(nxt)
    nxt.set_defaults(func=_cmd_next)

    fix = sub.add_parser("fix", help="Print unified-diff patches for fixable toil (pipe to git apply).")
    _add_common(fix)
    fix.add_argument("--id", help="Fix a specific finding id.")
    fix.add_argument("--top", type=int, default=5, help="How many top items to consider (default 5).")
    fix.set_defaults(func=_cmd_fix)

    install = sub.add_parser("install", help="Print or write the MCP config to wire Charlie into an AI agent.")
    install.add_argument(
        "--client",
        required=True,
        help="codex, claude-code, claude-desktop, cursor, vscode, windsurf, zed, gemini, cline, or all.",
    )
    install.add_argument("--transport", choices=("stdio", "http"), default="stdio", help="Transport to configure.")
    install.add_argument("--url", help="HTTP endpoint when --transport http.")
    install.add_argument(
        "--write", action="store_true", help="Write project-local config (Claude Code, Cursor, VS Code)."
    )
    install.add_argument("--root", default=".", help="Project root for --write.")
    install.set_defaults(func=_cmd_install)

    init = sub.add_parser("init", help="Write a Charlie section into AGENTS.md so any agent knows how to use it.")
    init.add_argument("--root", default=".", help="Project root.")
    init.add_argument("--file", default="AGENTS.md", help="File to write the block into (default AGENTS.md).")
    init.add_argument("--print", action="store_true", help="Print the block instead of writing it.")
    init.set_defaults(func=_cmd_init)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
