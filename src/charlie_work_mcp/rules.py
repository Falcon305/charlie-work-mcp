from __future__ import annotations

import os

START = "<!-- charlie-work:start -->"
END = "<!-- charlie-work:end -->"

_BODY = """## Charlie Work (toil scanner)

`charlie-work` surfaces the toil in this repo — flaky/skipped/focused tests, TODO rot, expiring TLS
certs, dead feature flags, unpinned/vulnerable/outdated dependencies, unowned runbooks, and stray debug
statements — ranked by git-hotspot x severity, so the top of the queue is where the code actually hurts.

- Find the highest-value fix: call the `charlie_next` tool (or run `charlie-work next`). It returns the
  top item, why it matters, and a ready-to-apply unified diff.
- Fixes are patch-first: apply the returned diff yourself with `git apply` — the tool never edits files.
  Patches labelled `auto-safe` are mechanical; `needs-review` ones change behaviour.
- Before opening a PR, run `charlie-work gate --base <default-branch>` and clear any new blocking toil.
- Secrets, certificates, and major dependency bumps are surfaced for a human, never auto-patched.
- Full queue: `charlie-work scan` or the `charlie_scan_toil` tool. Plain output: `--plain` or
  `CHARLIE_VOICE=off`."""


def agents_block() -> str:
    return f"{START}\n{_BODY}\n{END}"


def upsert(root: str = ".", filename: str = "AGENTS.md") -> tuple[str, str]:
    path = os.path.join(root, filename)
    block = agents_block()
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(block + "\n")
        return path, "created"
    with open(path, encoding="utf-8") as handle:
        content = handle.read()
    if START in content and END in content:
        head, _, rest = content.partition(START)
        _, _, tail = rest.partition(END)
        updated = f"{head}{block}{tail}"
        action = "updated"
    else:
        separator = "" if content.endswith("\n\n") else ("\n" if content.endswith("\n") else "\n\n")
        updated = f"{content}{separator}{block}\n"
        action = "appended"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(updated)
    return path, action
