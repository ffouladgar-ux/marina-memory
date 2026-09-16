"""End-to-end proof: launch the MCP server exactly as Claude does (stdio),
perform a real handshake, list tools, and call them.

    python scripts/e2e_mcp.py [vault_path]

Exits non-zero on any failure. No mocks: a real subprocess, real JSON-RPC,
real files on disk.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main(vault: Path) -> int:
    env = dict(os.environ, MEMORY_KIT_VAULT=str(vault), PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "memory_kit", "serve"], env=env
    )
    failures: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}{' — ' + detail if detail else ''}")
        if not ok:
            failures.append(label)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            info = getattr(init, "server_info", None) or getattr(init, "serverInfo", None)
            print(f"handshake: {info.name} v{info.version}")

            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            print(f"tools ({len(names)}): {', '.join(names)}")
            check("9 tools exposed", len(names) == 9, str(len(names)))

            async def call(name: str, args: dict) -> str:
                res = await session.call_tool(name, args)
                return "\n".join(
                    c.text for c in res.content if getattr(c, "type", "") == "text"
                )

            # 1. remember a fact, then recall it in a fresh call
            out = await call("memory_remember", {
                "content": "Marina is training at journalist school in Nice, examen de memoire in October",
            })
            check("remember files it under studies", "studies" in out, out.strip()[:90])

            out = await call("memory_recall", {"query": "journalist school"})
            check("recall finds it", "journalist school" in out)

            # 2. ingest a real document (built here) and read it back in sections
            docx = vault / "cours-enquete.docx"
            _write_docx(docx, [
                "Enquete: la verification des sources",
                "Toujours croiser deux sources independantes avant publication.",
                "Proteger les sources confidentielles est une obligation deontologique.",
            ])
            out = await call("memory_ingest", {"path": str(docx), "compartment": "studies"})
            check("ingest returns a compact card, not the document",
                  "slug:" in out and "sections:" in out and len(out) < 1200, f"{len(out)} chars")
            slug = [l for l in out.splitlines() if "slug:" in l][0].split("slug:")[1].split()[0]

            out = await call("memory_open", {"slug": slug, "query": "proteger sources"})
            check("sectional read is bounded", "matched sections only" in out, f"{len(out)} chars")

            out = await call("memory_index", {})
            check("hot index is compact", "hot tier" in out and len(out) < 6000, f"{len(out)} chars")

            out = await call("memory_status", {})
            check("status reports 2 records", "facts: 2" in out, out.replace("\n", " | ")[:110])

    # files are the source of truth: everything must exist as Markdown
    md_files = sorted(p.relative_to(vault).as_posix() for p in vault.rglob("*.md"))
    check("markdown on disk", any("studies" in f for f in md_files) and any("sources/" in f for f in md_files),
          ", ".join(md_files))
    hot = (vault / "index.md").read_text(encoding="utf-8")
    check("index.md regenerated", "Memory index (hot tier)" in hot)

    print("\nRESULT: " + ("all checks passed" if not failures else f"FAILED: {failures}"))
    return 1 if failures else 0


def _write_docx(path: Path, paragraphs: list[str]) -> None:
    import zipfile

    body = "".join(f'<w:p><w:r><w:t xml:space="preserve">{p}</w:t></w:r></w:p>' for p in paragraphs)
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f"<w:body>{body}</w:body></w:document>")
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
          "</Types>")
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", doc)


if __name__ == "__main__":
    vault = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp()) / "vault"
    vault.mkdir(parents=True, exist_ok=True)
    print(f"vault: {vault}\n")
    raise SystemExit(asyncio.run(main(vault)))
