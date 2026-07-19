from __future__ import annotations

import json

import pytest

from charlie_work_mcp import cli, install


def test_codex_uses_toml_mcp_servers_table():
    block = install.config_block("codex")
    assert "[mcp_servers.charlie-work]" in block
    assert 'command = "uvx"' in block
    assert 'args = ["charlie-work-mcp"]' in block


def test_vscode_uses_servers_key_with_stdio_type():
    block = json.loads(install.config_block("vscode"))
    assert "servers" in block and "mcpServers" not in block
    assert block["servers"]["charlie-work"]["type"] == "stdio"


def test_zed_uses_context_servers_key():
    block = json.loads(install.config_block("zed"))
    assert "context_servers" in block
    assert block["context_servers"]["charlie-work"]["command"] == "uvx"


def test_default_clients_share_mcpservers_shape():
    for key in ("cursor", "claude-code", "claude-desktop", "windsurf", "gemini", "cline"):
        block = json.loads(install.config_block(key))
        assert block["mcpServers"]["charlie-work"] == {"command": "uvx", "args": ["charlie-work-mcp"]}


def test_http_transport_emits_url_entry():
    block = json.loads(install.config_block("cursor", transport="http", url="https://x/mcp"))
    assert block["mcpServers"]["charlie-work"] == {"type": "http", "url": "https://x/mcp"}


def test_write_project_config_merges_into_existing_json(tmp_path):
    target = tmp_path / ".cursor" / "mcp.json"
    target.parent.mkdir()
    target.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))
    path = install.write_project_config("cursor", root=str(tmp_path))
    data = json.loads((tmp_path / ".cursor" / "mcp.json").read_text())
    assert data["mcpServers"]["other"] == {"command": "x"}
    assert data["mcpServers"]["charlie-work"]["command"] == "uvx"
    assert path.endswith(".cursor/mcp.json")


def test_write_rejects_global_clients(tmp_path):
    with pytest.raises(ValueError):
        install.write_project_config("codex", root=str(tmp_path))


def test_cli_install_print(tmp_path, capsys):
    code = cli.main(["install", "--client", "codex"])
    assert code == 0
    assert "[mcp_servers.charlie-work]" in capsys.readouterr().out


def test_cli_install_unknown_client(capsys):
    code = cli.main(["install", "--client", "nope"])
    assert code == 2
    assert "Unknown client" in capsys.readouterr().out
