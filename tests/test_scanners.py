from __future__ import annotations

from datetime import datetime, timedelta, timezone

from charlie_work_mcp.models import SourceFile, ToilKind
from charlie_work_mcp.scanners import certs, dead_flags, debug, deps, runbooks, tests, todos


def _f(path: str, text: str) -> SourceFile:
    return SourceFile(path=path, text=text)


def test_detects_skipped_focused_and_flaky():
    files = [
        _f("test_a.py", "@pytest.mark.skip\ndef test_one():\n    pass\n"),
        _f("b.test.js", "it.only('focus', () => {})\n"),
        _f("test_c.py", "@pytest.mark.flaky\ndef test_two():\n    pass\n"),
    ]
    kinds = {i.kind for i in tests.scan(files)}
    assert ToilKind.skipped_test in kinds
    assert ToilKind.focused_test in kinds
    assert ToilKind.flaky_test in kinds


def test_todos_markers_and_severity():
    files = [_f("m.py", "x = 1  # TODO clean this\ny = 2  # FIXME broken\n")]
    found = todos.scan(files)
    markers = {i.evidence.split(":")[0] for i in found}
    assert "TODO" in markers
    assert "FIXME" in markers
    fixme = next(i for i in found if i.evidence.startswith("FIXME"))
    todo = next(i for i in found if i.evidence.startswith("TODO"))
    assert fixme.severity > todo.severity


def test_dead_flag_flagged_only_when_never_set():
    files = [
        _f("read.py", 'if is_enabled("ghost_flag"):\n    go()\n'),
        _f("read2.py", 'if is_enabled("real_flag"):\n    go()\n'),
        _f("config.py", '"real_flag": True\n'),
    ]
    found = dead_flags.scan(files)
    names = {i.title for i in found}
    assert any("ghost_flag" in n for n in names)
    assert not any("real_flag" in n for n in names)


def test_deps_loose_pins():
    npm = _f("package.json", '{"dependencies": {"left-pad": "*", "react": "^18.2.0"}}')
    req = _f("requirements.txt", "flask\nrequests==2.31.0\n")
    found = deps.scan([npm, req])
    flagged = {i.evidence.split(":")[0].split(" ")[0] for i in found}
    assert any("left-pad" in i.evidence for i in found)
    assert not any("react" in i.evidence for i in found)
    assert any("flask" in i.evidence for i in found)
    assert not any("requests" in i.evidence for i in found)
    assert flagged


def test_runbook_unowned():
    files = [_f("scripts/deploy.sh", "#!/bin/bash\nkubectl apply -f .\n")]
    found = runbooks.scan(files)
    assert found and found[0].kind == ToilKind.unowned_runbook


def test_runbook_owned_is_skipped():
    files = [_f("scripts/deploy.sh", "#!/bin/bash\n# Owner: platform-team\nkubectl apply -f .\n")]
    assert runbooks.scan(files) == []


def test_debug_ignores_tests_and_comments():
    files = [
        _f("app.py", "def f():\n    breakpoint()\n"),
        _f("test_app.py", "def test():\n    breakpoint()\n"),
        _f("c.js", "// console.log('nope')\n"),
    ]
    found = debug.scan(files)
    assert len(found) == 1
    assert found[0].path == "app.py"


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


def test_cert_expiring_soon_is_flagged():
    files = [_f("certs/staging.pem", _make_cert(9))]
    found = certs.scan(files)
    assert found and found[0].kind == ToilKind.expiring_cert
    assert found[0].staleness_days is not None and found[0].staleness_days <= 9


def test_cert_with_long_life_is_ignored():
    files = [_f("certs/prod.pem", _make_cert(400))]
    assert certs.scan(files) == []
