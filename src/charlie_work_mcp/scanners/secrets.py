from __future__ import annotations

import math
import re

from ..models import HEURISTIC, HIGH, SourceFile, ToilItem, ToilKind, make_id

_SKIP_EXT = (".md", ".rst", ".txt", ".lock", ".map", ".min.js", ".svg")
_SKIP_HINT = ("test", "fixture", "example", "sample", "mock", "spec")

_STOPWORDS = {
    "example",
    "sample",
    "placeholder",
    "changeme",
    "your",
    "xxxxxxxx",
    "redacted",
    "dummy",
    "notreal",
    "test",
}


def _shannon(value: str) -> float:
    if not value:
        return 0.0
    counts: dict[str, int] = {}
    for char in value:
        counts[char] = counts.get(char, 0) + 1
    length = len(value)
    return -sum((c / length) * math.log2(c / length) for c in counts.values())


class Rule:
    def __init__(
        self,
        rule_id: str,
        title: str,
        keywords: tuple[str, ...],
        pattern: str,
        entropy: float,
        verified: bool,
    ) -> None:
        self.rule_id = rule_id
        self.title = title
        self.keywords = keywords
        self.regex = re.compile(pattern)
        self.entropy = entropy
        self.verified = verified


_RULES = [
    Rule("aws-access-key", "AWS access key", ("akia", "asia", "abia", "acca"),
         r"\b((?:AKIA|ASIA|ABIA|ACCA)[A-Z0-9]{16})\b", 3.0, True),
    Rule("github-token", "GitHub token", ("ghp_", "gho_", "ghu_", "ghs_", "ghr_"),
         r"\b((?:ghp|gho|ghu|ghs|ghr)_[0-9A-Za-z]{36})\b", 3.0, True),
    Rule("anthropic-key", "Anthropic API key", ("sk-ant-",),
         r"(sk-ant-[a-z0-9]{2,}-[A-Za-z0-9_\-]{20,})", 3.5, True),
    Rule("openai-key", "OpenAI API key", ("sk-",),
         r"\b(sk-[A-Za-z0-9]{20,})\b", 3.5, False),
    Rule("slack-token", "Slack token", ("xoxb", "xoxp", "xoxa", "xoxr"),
         r"\b(xox[baprs]-[0-9A-Za-z-]{10,})\b", 3.0, True),
    Rule("private-key", "Private key block", ("private key",),
         r"(-----BEGIN (?:RSA |EC |OPENSSH |PGP |DSA )?PRIVATE KEY(?: BLOCK)?-----)", 0.0, True),
    Rule("generic-secret", "Generic hardcoded secret", ("secret", "token", "apikey", "api_key", "passwd", "password"),
         r"""(?i)(?:secret|token|api[_-]?key|passwd|password)\s*[:=]\s*['"]([A-Za-z0-9+/_\-]{16,})['"]""", 3.5, False),
]


def _looks_placeholder(secret: str) -> bool:
    lowered = secret.lower()
    if any(word in lowered for word in _STOPWORDS):
        return True
    if len(set(secret)) <= 3:
        return True
    return bool(re.search(r"(.)\1{5,}", secret))


def _skip_file(path: str) -> bool:
    lowered = path.lower()
    if lowered.endswith(_SKIP_EXT):
        return True
    return any(hint in lowered for hint in _SKIP_HINT)


def scan(files: list[SourceFile]) -> list[ToilItem]:
    items: list[ToilItem] = []
    for file in files:
        if _skip_file(file.path):
            continue
        for lineno, line in enumerate(file.text.splitlines(), start=1):
            lowered = line.lower()
            for rule in _RULES:
                if not any(keyword in lowered for keyword in rule.keywords):
                    continue
                match = rule.regex.search(line)
                if not match:
                    continue
                secret = match.group(match.lastindex or 0)
                if rule.entropy and _shannon(secret) < rule.entropy:
                    continue
                if _looks_placeholder(secret):
                    continue
                items.append(
                    ToilItem(
                        id=make_id(ToilKind.secret_leak, file.path, lineno, rule.rule_id),
                        kind=ToilKind.secret_leak,
                        path=file.path,
                        line=lineno,
                        title=f"{rule.title} committed to the repo",
                        evidence=f"{rule.title} near column {match.start() + 1}",
                        severity=5,
                        effort=2,
                        confidence=HIGH if rule.verified else HEURISTIC,
                        rule_id=f"charlie/secret-{rule.rule_id}",
                        security_severity=9.5 if rule.verified else 7.0,
                        fix="Rotate the credential and move it to a secret manager or env var.",
                    )
                )
                break
    return items
