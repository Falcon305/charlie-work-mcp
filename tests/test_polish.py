from __future__ import annotations

import subprocess
from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from charlie_work_mcp import cli
from charlie_work_mcp.gitmeta import detect_github_repo
from charlie_work_mcp.models import SourceFile
from charlie_work_mcp.scanners import certs
from charlie_work_mcp.services import store


def _cert_pem(days: int) -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=days))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM).decode()


def test_cert_bundle_flags_every_expiring_cert():
    bundle = _cert_pem(3) + _cert_pem(10)
    items = certs.scan([SourceFile(path="chain.pem", text=bundle)])
    assert len(items) == 2
    assert {i.id for i in items} != {items[0].id}
    assert all(i.staleness_days is not None for i in items)


def test_cert_bundle_ignores_healthy_certs():
    bundle = _cert_pem(3) + _cert_pem(400)
    items = certs.scan([SourceFile(path="chain.pem", text=bundle)])
    assert len(items) == 1


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def test_detect_github_repo_from_remote(tmp_path):
    _git(tmp_path, "init")
    _git(tmp_path, "remote", "add", "origin", "git@github.com:Falcon305/charlie-work-mcp.git")
    assert detect_github_repo(str(tmp_path)) == "Falcon305/charlie-work-mcp"


def test_detect_github_repo_none_without_remote(tmp_path):
    _git(tmp_path, "init")
    assert detect_github_repo(str(tmp_path)) is None


def test_did_it_cli_records_credit(tmp_path):
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@t.co")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "app.py").write_text("def f():\n    breakpoint()\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "base")
    from charlie_work_mcp.scan import scan_repo

    toil_id = scan_repo(str(tmp_path), online=False)[0].id
    code = cli.main(["did-it", toil_id, "--who", "dee", "--path", str(tmp_path), "--plain"])
    assert code == 0
    entries = store.load_entries(str(tmp_path))
    assert any(e.who == "dee" and e.toil_id == toil_id for e in entries)
