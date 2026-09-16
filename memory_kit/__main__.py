"""Enables `python -m memory_kit ...` — the form Claude Desktop launches.

`mm connect-claude` wires Claude to `python -m memory_kit serve`, so this file
is load-bearing: without it the MCP handshake dies with
"No module named memory_kit.__main__".
"""
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
