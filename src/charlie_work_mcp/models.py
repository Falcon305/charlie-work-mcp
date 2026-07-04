from __future__ import annotations

import hashlib
from enum import Enum

from pydantic import BaseModel, Field


class ToilKind(str, Enum):
    flaky_test = "flaky_test"
    skipped_test = "skipped_test"
    focused_test = "focused_test"
    todo_rot = "todo_rot"
    dependency_risk = "dependency_risk"
    vulnerable_dep = "vulnerable_dep"
    outdated_dep = "outdated_dep"
    secret_leak = "secret_leak"
    dead_flag = "dead_flag"
    expiring_cert = "expiring_cert"
    unowned_runbook = "unowned_runbook"
    debug_leftover = "debug_leftover"


VERIFIED = "verified"
HIGH = "high"
HEURISTIC = "heuristic"


class SourceFile(BaseModel):
    path: str
    text: str


class ToilItem(BaseModel):
    id: str = Field(description="Stable identifier for this piece of toil.")
    kind: ToilKind = Field(description="Category of toil.")
    path: str = Field(description="Repo-relative path where the toil lives.")
    line: int | None = Field(default=None, description="1-indexed line, when it maps to one.")
    line_end: int | None = Field(default=None, description="1-indexed end line for a span.")
    col: int | None = Field(default=None, description="1-indexed column when known.")
    title: str = Field(description="Plain one-line description of the work.")
    evidence: str = Field(description="The matched text or detail that triggered the finding.")
    severity: int = Field(ge=1, le=5, description="How much it hurts if ignored, 1 low to 5 high.")
    effort: int = Field(ge=1, le=5, description="How much work to clear it, 1 trivial to 5 heavy.")
    confidence: str = Field(default=HIGH, description="verified, high, or heuristic.")
    rule_id: str = Field(default="", description="Stable rule identifier for config and SARIF.")
    fingerprint: str = Field(default="", description="Line-independent identity for baseline dedup.")
    est_minutes: int = Field(default=0, description="Estimated remediation minutes.")
    owner: str | None = Field(default=None, description="CODEOWNERS owner of the path, when known.")
    security_severity: float | None = Field(
        default=None, description="0.0 to 10.0 severity for security findings."
    )
    fix: str | None = Field(default=None, description="Suggested concrete fix, when known.")
    hotspot_multiplier: float = Field(default=1.0, description="Churn x complexity weight.")
    staleness_days: int | None = Field(
        default=None, description="Age or time-to-deadline in days when known."
    )
    source: str = Field(default="local", description="Where the finding came from: local or github.")
    priority: float = Field(default=0.0, description="Computed rank, higher means do it sooner.")

    def model_post_init(self, _context: object) -> None:
        if not self.rule_id:
            self.rule_id = f"charlie/{self.kind.value.replace('_', '-')}"
        if not self.fingerprint:
            self.fingerprint = make_fingerprint(self.rule_id, self.path, self.evidence)


class ScanResult(BaseModel):
    report: str = Field(description="Human-readable prioritized report.")
    items: list[ToilItem] = Field(description="The prioritized toil queue for this page.")
    total: int = Field(description="Total toil items found across the whole scan.")
    count: int = Field(description="Number of items on this page.")
    offset: int = Field(description="Offset of this page into the full queue.")
    has_more: bool = Field(description="Whether more items exist past this page.")
    next_offset: int | None = Field(default=None, description="Offset to pass for the next page.")


class LedgerEntry(BaseModel):
    toil_id: str
    kind: str
    title: str
    who: str
    at: str
    note: str | None = None


class LedgerResult(BaseModel):
    report: str
    entries: list[LedgerEntry]
    credits: dict[str, int]
    champion: str | None = None


def make_id(kind: ToilKind, path: str, line: int | None, evidence: str) -> str:
    raw = f"{kind.value}:{path}:{line or 0}:{evidence.strip()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def make_fingerprint(rule_id: str, path: str, evidence: str) -> str:
    raw = f"{rule_id}:{path}:{evidence.strip()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
