from __future__ import annotations

import json
import subprocess
import sys

INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "smoke", "version": "0"},
    },
}


def test_stdio_stdout_is_clean_jsonrpc():
    proc = subprocess.Popen(
        [sys.executable, "-m", "charlie_work_mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        out, _ = proc.communicate(input=json.dumps(INITIALIZE) + "\n", timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, _ = proc.communicate()

    lines = [line for line in out.splitlines() if line.strip()]
    assert lines, "server wrote nothing to stdout on initialize"
    for line in lines:
        parsed = json.loads(line)
        assert parsed.get("jsonrpc") == "2.0"
    first = json.loads(lines[0])
    assert first.get("id") == 1
    assert "result" in first
