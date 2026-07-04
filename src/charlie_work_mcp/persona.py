from __future__ import annotations

from .constants import CHARACTER_LIMIT
from .models import LedgerEntry, ToilItem, ToilKind

_EMOJI = {
    ToilKind.flaky_test: "🐀",
    ToilKind.skipped_test: "🙈",
    ToilKind.focused_test: "🎯",
    ToilKind.todo_rot: "📌",
    ToilKind.dependency_risk: "📦",
    ToilKind.vulnerable_dep: "🚨",
    ToilKind.outdated_dep: "🕰️",
    ToilKind.secret_leak: "🔑",
    ToilKind.dead_flag: "🧵",
    ToilKind.expiring_cert: "🔒",
    ToilKind.unowned_runbook: "📋",
    ToilKind.debug_leftover: "🖨️",
}

_CHARLIE_HEADER = "THIS IS CHARLIE WORK. Nobody else will do it. That's why it's yours."
_CHARLIE_EMPTY = "Grease trap's clean. No Charlie Work today. Go run a scheme."
_PLAIN_EMPTY = "No toil found."


def _location(item: ToilItem) -> str:
    if item.line:
        return f"{item.path}:{item.line}"
    return item.path


def _charlie_line(item: ToilItem) -> str:
    emoji = _EMOJI.get(item.kind, "•")
    tail = ""
    if item.kind == ToilKind.expiring_cert and item.staleness_days is not None:
        tail = " — the clock is running, Frank"
    elif item.kind == ToilKind.dead_flag:
        tail = " — there is no Pepe Silvia"
    elif item.kind == ToilKind.flaky_test:
        tail = " — it keeps rat-nesting in CI"
    elif item.kind == ToilKind.secret_leak:
        tail = " — you left the keys under the mat"
    elif item.kind == ToilKind.vulnerable_dep:
        tail = " — this one's a ticking bomb"
    fix = f" [fix: {item.fix}]" if item.fix else ""
    return f"{emoji} {item.title} ({_location(item)}){tail}{fix}"


def _plain_line(item: ToilItem) -> str:
    age = f", {item.staleness_days}d" if item.staleness_days is not None else ""
    return (
        f"- [{item.kind.value}] {item.title} "
        f"({_location(item)}) sev={item.severity} effort={item.effort}{age}"
    )


def _clamp(lines: list[str], header: str) -> str:
    body = header + "\n\n"
    out: list[str] = []
    for line in lines:
        if len(body) + len("\n".join(out)) + len(line) > CHARACTER_LIMIT:
            out.append("… truncated. Filter by `kinds` or page with `offset` to see the rest.")
            break
        out.append(line)
    return body + "\n".join(out)


def render_scan(items: list[ToilItem], total: int, offset: int, mode: str) -> str:
    if not items:
        return _CHARLIE_EMPTY if mode == "charlie" else _PLAIN_EMPTY
    if mode == "plain":
        header = f"Toil queue — {total} item(s), showing {len(items)} from offset {offset}."
        return _clamp([_plain_line(i) for i in items], header)
    header = _CHARLIE_HEADER
    footer = f"\n\n{total} thing(s) nobody wanted to do. Showing {len(items)} from #{offset}."
    return _clamp([_charlie_line(i) for i in items], header) + footer


def render_ledger(
    entries: list[LedgerEntry],
    credits: dict[str, int],
    champion: str | None,
    open_count: int,
    mode: str,
) -> str:
    if mode == "plain":
        lines = [f"Credit ledger — {len(entries)} entries, {open_count} still open."]
        for who, count in sorted(credits.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"- {who}: {count}")
        return "\n".join(lines)
    lines = ["THE LEDGER. Somebody did the work. It gets written down."]
    if champion:
        lines.append(f"👑 Champion of the Grease Trap: {champion}")
    for who, count in sorted(credits.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"  {who} cleared {count} — respect.")
    lines.append(f"Still on the board: {open_count}. Somebody's gotta do it.")
    return "\n".join(lines)
