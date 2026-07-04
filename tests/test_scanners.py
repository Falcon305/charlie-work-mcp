from __future__ import annotations

from datetime import UTC, datetime, timedelta

from charlie_work_mcp.models import SourceFile, ToilKind
from charlie_work_mcp.scanners import certs, code, deps, py_ast, runbooks, secrets, treesitter_scan
from charlie_work_mcp.services.lockfiles import parse_lockfiles


def _f(path: str, text: str) -> SourceFile:
    return SourceFile(path=path, text=text)


def test_py_ast_detects_and_ignores_strings_and_comments():
    src = (
        "import pytest\n"
        "@pytest.mark.skip\n"
        "def test_a():\n"
        "    pass\n"
        "@pytest.mark.skipif(True, reason='x')\n"
        "def test_b():\n"
        "    pass\n"
        "def test_c():\n"
        "    breakpoint()\n"
        "    x = 'pytest.mark.skip'\n"
        "    # breakpoint() in a comment\n"
    )
    items = py_ast.scan_python(_f("test_x.py", src))
    kinds = [i.kind for i in items]
    assert kinds.count(ToilKind.skipped_test) == 2
    assert ToilKind.debug_leftover in kinds
    assert len(items) == 3


def test_py_ast_flag_reads_vs_defs():
    src = (
        "def f():\n"
        "    if is_enabled('ghost'):\n"
        "        pass\n"
        "    if is_enabled('real'):\n"
        "        pass\n"
        "CONFIG = {'real': True}\n"
    )
    reads, defs = py_ast.collect_flags(_f("m.py", src))
    assert "ghost" in reads and "real" in reads
    assert "real" in defs and "ghost" not in defs


def test_treesitter_js_and_go():
    js = _f(
        "a.test.js",
        "describe.skip('s',()=>{});\nit.only('f',()=>{debugger;});\nxit('l',()=>{});\nconsole.log('x');\nfoo.skip();\n",
    )
    kinds = [i.kind for i in treesitter_scan.scan_file(js)]
    assert kinds.count(ToilKind.skipped_test) == 2
    assert ToilKind.focused_test in kinds
    assert kinds.count(ToilKind.debug_leftover) == 2
    go = _f("c_test.go", 'func TestX(t *testing.T){ t.Skip("later") }\n')
    assert any(i.kind == ToilKind.skipped_test for i in treesitter_scan.scan_file(go))


def test_code_scan_dead_flag_cross_file():
    files = [
        _f("read.py", "def f():\n    if is_enabled('ghost_flag'):\n        go()\n"),
        _f("read2.js", "if (isEnabled('real_flag')) { go() }\n"),
        _f("config.py", "FLAGS = {'real_flag': True}\n"),
    ]
    dead = [i for i in code.scan(files) if i.kind == ToilKind.dead_flag]
    titles = " ".join(i.title for i in dead)
    assert "ghost_flag" in titles
    assert "real_flag" not in titles


def test_secrets_catches_real_ignores_placeholder():
    files = [
        _f("app.py", "AWS_KEY = 'AKIAIOSFODNN7ABCD1XZ'\n"),
        _f("gh.py", "token = 'ghp_" + "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8'\n"),
        _f("doc.py", "example = 'AKIAIOSFODNN7EXAMPLE'\n"),
    ]
    found = secrets.scan(files)
    rules = {i.rule_id for i in found}
    assert "charlie/secret-aws-access-key" in rules
    assert "charlie/secret-github-token" in rules
    assert all(i.path != "doc.py" for i in found)


def test_secrets_skips_test_and_markdown_paths():
    files = [_f("tests/fixtures/keys.py", "AWS = 'AKIAIOSFODNN7REALKEY0'\n")]
    assert secrets.scan(files) == []


def test_deps_loose_pins():
    npm = _f("package.json", '{"dependencies": {"left-pad": "*", "react": "^18.2.0"}}')
    req = _f("requirements.txt", "flask\nrequests==2.31.0\n")
    found = deps.scan([npm, req])
    assert any("left-pad" in i.evidence for i in found)
    assert not any("react" in i.evidence for i in found)
    assert any("flask" in i.evidence for i in found)


def test_runbook_unowned_and_owned():
    assert runbooks.scan([_f("scripts/deploy.sh", "#!/bin/bash\nkubectl apply -f .\n")])
    assert runbooks.scan([_f("scripts/deploy.sh", "#!/bin/bash\n# Owner: team\nkubectl\n")]) == []


def test_lockfile_parsing():
    poetry = _f("poetry.lock", '[[package]]\nname = "requests"\nversion = "2.20.0"\n')
    reqs = _f("requirements.txt", "jinja2==2.4.1\nflask>=1.0\n")
    pkgs = {(p.ecosystem, p.name, p.version) for p in parse_lockfiles([poetry, reqs])}
    assert ("PyPI", "requests", "2.20.0") in pkgs
    assert ("PyPI", "jinja2", "2.4.1") in pkgs
    assert not any(name == "flask" for _, name, _ in pkgs)


def _make_cert(days: int) -> str:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "staging-api")])
    now = datetime.now(UTC)
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


def test_cert_expiring_and_healthy():
    hot = certs.scan([_f("certs/staging.pem", _make_cert(9))])
    assert hot and hot[0].kind == ToilKind.expiring_cert
    assert certs.scan([_f("certs/prod.pem", _make_cert(400))]) == []
