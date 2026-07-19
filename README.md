<div align="center">

<img src="./assets/pepe-silvia.jpg" alt="Charlie in front of the Pepe Silvia conspiracy board" width="640" />

# Charlie Work

**A code-health tool that surfaces — and dignifies — the toil in your repo.**
An MCP server *and* a CLI *and* a CI gate.

The un-fun, load-bearing maintenance work everyone ignores until it bites: flaky tests, a TLS cert nine days from death, **known-vulnerable dependencies**, **committed secrets**, dead feature flags, TODO rot, scripts nobody owns. Charlie Work scans your repo with real parsers and real vulnerability data, ranks the findings by where your team actually bleeds time, and keeps a **credit ledger** so the invisible work finally shows up in standup.

*Named after the episode where the gang realizes Charlie has been quietly holding Paddy's together the whole time.*

</div>

---

> **THIS IS CHARLIE WORK. Nobody else will do it. That's why it's yours.**

The jokes are a **toggle, not a tax** — pass `mode="plain"` (or set `CHARLIE_VOICE=off`) and every response is flavor-free, paste-into-a-ticket clean. CI and SARIF output are always plain.

## Use it with any agent

Charlie is a stdio MCP server, so it drops into **every** MCP client — Claude Code, Codex, Cursor, VS Code, Claude Desktop, Windsurf, Zed, Gemini, Cline. The universal config is one block:

```json
{
  "mcpServers": {
    "charlie-work": { "command": "uvx", "args": ["charlie-work-mcp"] }
  }
}
```

[![Add to Cursor](https://img.shields.io/badge/Add_to-Cursor-000?logo=cursor)](cursor://anysphere.cursor-deeplink/mcp/install?name=charlie-work&config=eyJjb21tYW5kIjogInV2eCIsICJhcmdzIjogWyJjaGFybGllLXdvcmstbWNwIl19)

**Don't hand-write it — let Charlie wire himself in:**

```bash
uvx --from charlie-work-mcp charlie-work install --client cursor --write   # or: codex, claude-code, vscode, …
```

`install` knows each client's dialect and prints (or, for project-local clients, `--write`s) the exact config. Run `install --client all` to see every one.

<details><summary><b>Per-client config (copy-paste)</b></summary>

**Claude Code** — `claude mcp add --transport stdio charlie-work -- uvx charlie-work-mcp` (or the block above in `.mcp.json`).

**OpenAI Codex CLI** — `~/.codex/config.toml`:
```toml
[mcp_servers.charlie-work]
command = "uvx"
args = ["charlie-work-mcp"]
```

**Cursor** (`.cursor/mcp.json`), **Claude Desktop** (`claude_desktop_config.json`), **Windsurf**, **Gemini CLI**, **Cline** — the universal `mcpServers` block above.

**VS Code** — `.vscode/mcp.json` uses `servers` (not `mcpServers`):
```json
{ "servers": { "charlie-work": { "type": "stdio", "command": "uvx", "args": ["charlie-work-mcp"] } } }
```

**Zed** — `settings.json` uses `context_servers`:
```json
{ "context_servers": { "charlie-work": { "source": "custom", "command": "uvx", "args": ["charlie-work-mcp"] } } }
```
</details>

**Teach every agent the drill** — write a Charlie section into `AGENTS.md` (the cross-vendor rules file read by Codex, Cursor, Copilot, Gemini, Aider, Windsurf, Zed; Claude reads it too):

```bash
uvx --from charlie-work-mcp charlie-work init
```

**As a CLI:**

```bash
uvx --from charlie-work-mcp charlie-work scan     # the prioritized toil queue
charlie-work next                                 # the single next best fix, as a patch
charlie-work fix --top 5 | git apply              # patch the safe ones
charlie-work summary                              # toil budget + A–E grade
```

**As a CI gate** — fail a PR only when it introduces *new* high-severity toil ("Clean as You Code"):

```yaml
- uses: Falcon305/charlie-work-mcp@master
  with:
    severity: "4"
```

**As a scheduled watchman** — some toil is *time-based*: a cert quietly ticks toward expiry, a TODO ages, a new CVE lands against a dep you already shipped. A nightly scan catches it before it pages you:

```yaml
on:
  schedule: [{ cron: "0 7 * * *" }]
jobs:
  charlie:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: uvx --from charlie-work-mcp charlie-work sarif -o charlie.sarif
      - uses: github/codeql-action/upload-sarif@v3
        with: { sarif_file: charlie.sarif }
```

> Until the PyPI release lands, replace `uvx charlie-work-mcp` with `uvx --from git+https://github.com/Falcon305/charlie-work-mcp charlie-work-mcp` (and likewise `--from git+…` for the CLI).

## Trustworthy detection (not regex theater)

Every scanner is backed by a parser or an authoritative data source, and every finding carries a **confidence tier** (`verified` / `high` / `heuristic`) so CI gates on facts, not guesses.

| Kind | How it's detected |
|------|-------------------|
| `vulnerable_dep` | Lockfiles → **OSV.dev** (free, no key). Emits the CVE + the exact fixed version. |
| `secret_leak` | gitleaks-style provider regexes + Shannon-entropy gate + allowlists. |
| `skipped_test` / `flaky_test` / `focused_test` | **Python AST** and **tree-sitter** (JS/TS/Go) — never matches a string or a comment. |
| `debug_leftover` | AST calls: `breakpoint()`, `pdb.set_trace`, `debugger`, `console.log`. |
| `dead_flag` | Flags **read but never set anywhere** (the Pepe Silvia case), via AST literal extraction. |
| `expiring_cert` | Real X.509 parsing — `.pem`/`.crt` within 30 days of expiry, or already dead. |
| `outdated_dep` | Registry queries (PyPI/npm/crates/Go) → majors-behind. |
| `todo_rot` | `TODO`/`FIXME`/`HACK` in real comments, aged by git blame. |
| `dependency_risk` / `unowned_runbook` | Unpinned deps; operational scripts with no owner or CODEOWNERS. |

The difference from regex, in one line: the Python string `"pytest.mark.skip"` and a `# breakpoint()` comment are **not** flagged. Only real code is.

## Where your team actually bleeds — hotspots + a toil budget

Charlie ranks by **churn × complexity** (CodeScene-style): debt in a file edited 40× this quarter outranks the same debt in one untouched for years. `charlie-work summary` rolls it into a **toil budget** — total remediation minutes, a SQALE-style debt ratio, and an A–E grade. Google SRE says keep toil under 50%.

## Not just a reporter — a doer

Charlie returns **patches, not prose**. `charlie_next` hands the agent the single highest-value item — where it is, why it matters (hotspot × severity), and a **ready-to-apply unified diff** when it's safely fixable:

```bash
$ charlie-work next
breakpoint() left in the code at pay.py:88 — severity 4, in a hotspot (2.1x). [auto-safe]
--- a/pay.py
+++ b/pay.py
@@ -85,7 +85,6 @@
-    breakpoint()
```

Every patch is a diff you (or CI) apply with `git apply` — **the server never edits your files**. Fixes are labelled `auto-safe` (mechanical: delete a `breakpoint()`) or `needs-review` (changes behaviour: un-skip a test, delete a stale TODO). Secrets, certs, and dependency bumps are surfaced for a human, never auto-patched.

| Tool | What it does |
|------|--------------|
| `charlie_next` | The single next best fix, as a patch + why + follow-up actions. |
| `charlie_fix` | Unified-diff patches for a finding (or the top N), labelled auto-safe / needs-review. |
| `charlie_scan_toil` | Prioritized, paginated toil queue (structured output). |
| `charlie_summary` | Toil budget: score, debt ratio, A–E grade. |
| `charlie_triage` | Top-N action plan for an agent to work through. |
| `charlie_explain` | Why a finding is debt — evidence, hotspot, owner, fix. |
| `charlie_trend` | Records a snapshot and reports the delta over time. |
| `charlie_did_it` / `charlie_ledger` | The credit ledger — who cleared what, Champion of the Grease Trap. |

Plus `toil://queue` + `toil://item/{id}` **resources** and four **prompts** (slash commands in any client): `triage_toil`, `fix_next`, `pre_pr_check`, `charlie_rules`. Things a dashboard can't do: *"fix the next thing, run the tests, and credit me in the ledger."*

## Not a toy: token discipline + evals

- **The heavy work happens server-side.** An agent finding this toil itself would read the whole repo into context; Charlie returns only a compact ranked queue. The raw files never enter the model's context.
- **A reproducible eval harness** (`evals/run.py`) plants known toil and asserts the *end state* — recall and ranking — plus a token-cost measurement. There's also an optional model-graded tool-selection eval (`evals/agentic.py`).

```
$ uv run evals/run.py
kinds recalled : 9/9  (100% recall)   top item is the cert : True
naive: read whole repo : 1881 tokens
charlie work queue     : 1353 tokens  →  28% fewer tokens
RESULT: PASS
```

That 28% is on a tiny fixture; the gap widens fast — naive cost grows with the repo, the queue stays bounded to one page.

## Configuration & suppression

Zero-config to start. Tune via `[tool.charlie]` in `pyproject.toml` (or `charlie.toml`):

```toml
[tool.charlie]
exclude = ["vendor/**"]
disable = ["charlie/todo-rot"]
min_confidence = "high"
[tool.charlie.per-file-ignores]
"tests/**" = ["secret_leak"]
```

Plus inline `# charlie: ignore[rule]`, a `.charlieignore`, and a committed baseline (`charlie-work baseline`) so a fresh install starts at "0 new."

## Development

```bash
uv sync --extra dev
uv run ruff check . && uv run mypy && uv run pytest -q
uv run python evals/run.py
```

CI runs ruff + mypy(typed) + pytest + evals across Python 3.11–3.13. Releases publish to PyPI via OIDC Trusted Publishing.

## The gang (roadmap)

Each ships as its own standalone MCP server: **The Implication** (auth & dark-pattern auditor), **Pepe Silvia** (dead-code tracer), **The D.E.N.N.I.S. System** (rollout comms planner).

## License

Code: MIT. The hero image is a still from *It's Always Sunny in Philadelphia* (© FX Networks), used for identification and commentary; it is not covered by the MIT license. An original vector rendition ships at [`assets/hero.svg`](./assets/hero.svg).
