"""Proof of the upgrade path: the same server over streamable-http.

    python scripts/e2e_http.py [port]

This is what a claude.ai custom connector (or the mobile app) would reach.
It starts the server on a port, connects with the MCP HTTP client, performs a
real handshake and a real tool call, then shuts the server down.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession

try:  # mcp >= 2
    from mcp.client.streamable_http import streamable_http_client as _http_client
except ImportError:  # mcp 1.x
    from mcp.client.streamable_http import streamablehttp_client as _http_client


def _streams_pair(value):
    """mcp 2.x yields (read, write); mcp 1.x yields (read, write, get_session_id)."""
    if isinstance(value, tuple):
        return value[0], value[1]
    return value.read, value.write


async def main(port: int) -> int:
    vault = Path(tempfile.mkdtemp()) / "vault"
    env = dict(os.environ, MEMORY_KIT_VAULT=str(vault))
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "memory_kit", "serve", "--http", "--port", str(port),
        env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )

    url = f"http://127.0.0.1:{port}/mcp"
    failures: list[str] = []

    try:
        # wait for the socket to accept connections
        ready = False
        for _ in range(60):
            try:
                reader, writer = await asyncio.open_connection("127.0.0.1", port)
                writer.close()
                ready = True
                break
            except OSError:
                await asyncio.sleep(0.5)
        print(f"server listening on {port}: {ready}")
        if not ready:
            out = (await proc.stdout.read(4000)).decode()
            print(out[-800:])
            return 1

        from urllib.parse import urlparse  # noqa: F401  (kept for debugging URLs)

        async with _http_client(url) as _streams:
            read, write = _streams_pair(_streams)
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                info = getattr(init, "server_info", None) or getattr(init, "serverInfo", None)
                print(f"http handshake: {info.name}")
                tools = await session.list_tools()
                n = len(tools.tools)
                print(f"tools over http: {n}")
                if n != 9:
                    failures.append(f"expected 9 tools, got {n}")

                res = await session.call_tool("memory_remember", {
                    "content": "Examen de memoire en octobre a l'ecole de journalisme",
                })
                text = "\n".join(c.text for c in res.content if getattr(c, "type", "") == "text")
                print(f"remember over http: {text.strip()[:90]}")
                if "studies" not in text:
                    failures.append("routing failed over http")

                res = await session.call_tool("memory_recall", {"query": "memoire octobre"})
                text = "\n".join(c.text for c in res.content if getattr(c, "type", "") == "text")
                if "journalisme" not in text:
                    failures.append("recall failed over http")
                print("recall over http: ok" if "journalisme" in text else "recall: FAIL")

        md = sorted(p.name for p in vault.rglob("*.md"))
        print(f"markdown written: {md}")
        if not md:
            failures.append("no markdown written")

    finally:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=10)
        except asyncio.TimeoutError:
            proc.kill()

    print("\nRESULT: " + ("all checks passed" if not failures else f"FAILED: {failures}"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 8765)))
