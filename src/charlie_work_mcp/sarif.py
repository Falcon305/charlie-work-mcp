from __future__ import annotations

from . import __version__
from .models import ToilItem

_INFO_URI = "https://github.com/Falcon305/charlie-work-mcp"

_RULE_HELP = {
    "charlie/skipped-test": "Re-enable or delete the skipped test.",
    "charlie/flaky-test": "Fix the underlying flake instead of retrying.",
    "charlie/focused-test": "Remove .only/fit so the whole suite runs.",
    "charlie/todo-rot": "Resolve or file the TODO/FIXME as tracked work.",
    "charlie/dead-flag": "Remove the flag or wire up its definition.",
    "charlie/expiring-cert": "Rotate the certificate before it expires.",
    "charlie/unowned-runbook": "Add an owner or a CODEOWNERS entry.",
    "charlie/debug-leftover": "Remove the debug statement.",
    "charlie/vulnerable-dep": "Upgrade to a patched version.",
    "charlie/outdated-dep": "Upgrade the dependency.",
    "charlie/dependency-risk": "Pin the dependency to an exact version.",
}


def _level(item: ToilItem) -> str:
    if item.severity >= 5:
        return "error"
    if item.severity >= 3:
        return "warning"
    return "note"


def _rule_entry(rule_id: str, sample: ToilItem) -> dict:
    return {
        "id": rule_id,
        "name": rule_id.split("/")[-1].replace("-", "_"),
        "shortDescription": {"text": sample.kind.value.replace("_", " ")},
        "fullDescription": {"text": sample.title},
        "help": {"text": _RULE_HELP.get(rule_id, "Resolve this toil.")},
        "defaultConfiguration": {"level": _level(sample)},
        "properties": {"tags": ["toil", sample.confidence]},
    }


def _result(item: ToilItem) -> dict:
    region: dict = {"startLine": item.line or 1}
    if item.col:
        region["startColumn"] = item.col
    if item.line_end:
        region["endLine"] = item.line_end
    properties: dict = {"confidence": item.confidence}
    if item.security_severity is not None:
        properties["security-severity"] = str(item.security_severity)
    message = item.title if not item.fix else f"{item.title} Fix: {item.fix}"
    return {
        "ruleId": item.rule_id,
        "level": _level(item),
        "message": {"text": message},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": item.path, "uriBaseId": "SRCROOT"},
                    "region": region,
                }
            }
        ],
        "partialFingerprints": {"primaryLocationLineHash": item.fingerprint},
        "properties": properties,
    }


def to_sarif(items: list[ToilItem]) -> dict:
    rules: dict[str, dict] = {}
    for item in items:
        rules.setdefault(item.rule_id, _rule_entry(item.rule_id, item))
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "charlie-work",
                        "informationUri": _INFO_URI,
                        "version": __version__,
                        "rules": list(rules.values()),
                    }
                },
                "results": [_result(item) for item in items],
            }
        ],
    }
