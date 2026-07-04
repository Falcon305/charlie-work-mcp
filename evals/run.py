from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from charlie_work_mcp.constants import DEFAULT_PAGE_SIZE
from charlie_work_mcp.fs import walk_repo
from charlie_work_mcp.models import ToilKind
from charlie_work_mcp.scan import scan_repo
from charlie_work_mcp.server import charlie_scan_toil

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_repo")

EXPECTED_KINDS = {
    ToilKind.skipped_test,
    ToilKind.flaky_test,
    ToilKind.focused_test,
    ToilKind.todo_rot,
    ToilKind.debug_leftover,
    ToilKind.dead_flag,
    ToilKind.dependency_risk,
    ToilKind.unowned_runbook,
    ToilKind.expiring_cert,
}


def _make_cert(days: int) -> str:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "staging-api")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=days))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")


def _stage() -> str:
    tmp = tempfile.mkdtemp(prefix="charlie-eval-")
    dest = os.path.join(tmp, "repo")
    shutil.copytree(FIXTURE, dest)
    certs_dir = os.path.join(dest, "certs")
    os.makedirs(certs_dir, exist_ok=True)
    with open(os.path.join(certs_dir, "staging.pem"), "w", encoding="utf-8") as handle:
        handle.write(_make_cert(9))
    return dest


def _tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _naive_context(root: str) -> str:
    return "\n".join(f.text for f in walk_repo(root))


def main() -> int:
    root = _stage()
    items = scan_repo(root, online=False)
    found_kinds = {i.kind for i in items}

    recalled = EXPECTED_KINDS & found_kinds
    missing = EXPECTED_KINDS - found_kinds
    recall = len(recalled) / len(EXPECTED_KINDS)

    top = items[0] if items else None
    cert_is_top = top is not None and top.kind == ToilKind.expiring_cert

    page = charlie_scan_toil(repo=root, mode="plain", limit=DEFAULT_PAGE_SIZE, online=False)
    synthesized = json.dumps([i.model_dump() for i in page.items])
    naive = _naive_context(root)
    naive_tokens = _tokens(naive)
    synth_tokens = _tokens(synthesized)
    reduction = 1 - (synth_tokens / naive_tokens) if naive_tokens else 0.0

    print("Charlie Work — eval report")
    print("=" * 48)
    print(f"planted kinds        : {len(EXPECTED_KINDS)}")
    print(f"kinds recalled       : {len(recalled)}")
    print(f"recall               : {recall:.0%}")
    print(f"missing              : {sorted(k.value for k in missing) or 'none'}")
    print(f"top item is the cert : {cert_is_top} ({top.kind.value if top else 'n/a'})")
    print("-" * 48)
    print(f"naive: read whole repo : {naive_tokens} tokens")
    print(f"charlie work queue     : {synth_tokens} tokens")
    print(f"token reduction        : {reduction:.0%}")
    print("=" * 48)

    ok = recall == 1.0 and cert_is_top
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
