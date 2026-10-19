#!/usr/bin/env python3
"""Run the skill-maker MCP server; forward all options to its existing CLI.

Defaults to stdio and this repository's built skills/, regardless of cwd.
Use --http [HOST:PORT] for HTTP, or --help for the server's full option list.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SOURCE = Path(__file__).resolve().parent / "src"
if str(_SOURCE) not in sys.path:
    sys.path.insert(0, str(_SOURCE))


def main() -> int:
    from skillmaker.mcp_server import main as serve

    return serve()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
