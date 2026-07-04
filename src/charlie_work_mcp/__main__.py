from __future__ import annotations

import sys

from .server import mcp


def main() -> None:
    transport = "stdio"
    if "--http" in sys.argv:
        transport = "streamable-http"
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
