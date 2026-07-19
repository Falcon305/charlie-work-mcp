from __future__ import annotations

import json
import os
from dataclasses import dataclass

SERVER_NAME = "charlie-work"
PACKAGE = "charlie-work-mcp"
DEFAULT_HTTP_URL = "http://127.0.0.1:8000/mcp"


@dataclass(frozen=True)
class Client:
    key: str
    label: str
    path: str
    dialect: str
    scope: str
    note: str = ""


CLIENTS: dict[str, Client] = {
    "claude-code": Client(
        "claude-code",
        "Claude Code",
        ".mcp.json",
        "mcpServers",
        "project",
        "Or run: claude mcp add --transport stdio charlie-work -- uvx charlie-work-mcp",
    ),
    "claude-desktop": Client(
        "claude-desktop",
        "Claude Desktop",
        "~/Library/Application Support/Claude/claude_desktop_config.json",
        "mcpServers",
        "global",
        "Fully quit and reopen Claude Desktop for it to load.",
    ),
    "cursor": Client("cursor", "Cursor", ".cursor/mcp.json", "mcpServers", "project"),
    "vscode": Client("vscode", "VS Code", ".vscode/mcp.json", "servers", "project"),
    "codex": Client(
        "codex",
        "OpenAI Codex CLI",
        "~/.codex/config.toml",
        "codex",
        "global",
        "Or run: codex mcp add charlie-work -- uvx charlie-work-mcp",
    ),
    "windsurf": Client("windsurf", "Windsurf", "~/.codeium/windsurf/mcp_config.json", "mcpServers", "global"),
    "zed": Client("zed", "Zed", "settings.json", "context_servers", "global"),
    "gemini": Client("gemini", "Gemini CLI", "~/.gemini/settings.json", "mcpServers", "global"),
    "cline": Client("cline", "Cline", "cline_mcp_settings.json", "mcpServers", "global"),
}


def _stdio_entry() -> dict:
    return {"command": "uvx", "args": [PACKAGE]}


def _http_entry(url: str | None) -> dict:
    return {"type": "http", "url": url or DEFAULT_HTTP_URL}


def _entry(client: Client, transport: str, url: str | None) -> dict:
    if transport == "http":
        return _http_entry(url)
    if client.dialect == "servers":
        return {"type": "stdio", **_stdio_entry()}
    if client.dialect == "context_servers":
        return {"source": "custom", **_stdio_entry()}
    return _stdio_entry()


def config_block(client_key: str, transport: str = "stdio", url: str | None = None) -> str:
    client = CLIENTS[client_key]
    if client.dialect == "codex":
        if transport == "http":
            return f'[mcp_servers.{SERVER_NAME}]\nurl = "{url or DEFAULT_HTTP_URL}"\n'
        return f'[mcp_servers.{SERVER_NAME}]\ncommand = "uvx"\nargs = ["{PACKAGE}"]\n'
    block = {client.dialect: {SERVER_NAME: _entry(client, transport, url)}}
    return json.dumps(block, indent=2)


def guidance(client_key: str, transport: str = "stdio", url: str | None = None) -> str:
    client = CLIENTS[client_key]
    lines = [
        f"# {client.label}",
        f"Add this to {client.path}:",
        "",
        config_block(client_key, transport, url),
    ]
    if client.note:
        lines += ["", client.note]
    return "\n".join(lines)


def _merge_into_json(path: str, dialect: str, entry: dict) -> None:
    existing: dict = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            content = handle.read().strip()
        if content:
            existing = json.loads(content)
    existing.setdefault(dialect, {})[SERVER_NAME] = entry
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(existing, indent=2) + "\n")


def write_project_config(
    client_key: str, root: str = ".", transport: str = "stdio", url: str | None = None
) -> str:
    client = CLIENTS[client_key]
    if client.scope != "project" or client.dialect not in ("mcpServers", "servers"):
        raise ValueError(f"{client.label} config is global — copy the block into {client.path} yourself")
    path = os.path.join(root, client.path)
    _merge_into_json(path, client.dialect, _entry(client, transport, url))
    return path
