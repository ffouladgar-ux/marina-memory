"""MCP server (stdio) — what Claude actually talks to.

Tool design rule: every tool returns a COMPACT answer. The store is large; the
context window is not. `memory_recall` returns a handful of short lines, and
`memory_open` returns matched sections rather than whole documents. That is the
burn-rate lever.
"""
from __future__ import annotations

from pathlib import Path

# MCP SDK compat: mcp 2.x renamed FastMCP -> MCPServer (mcp.server.mcpserver).
# Both majors expose the same surface we use: `.tool()`, `.run(transport=)`,
# `.list_tools()`. Supporting both keeps the install working whichever the
# user's environment resolves.
try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer as _Server
except ModuleNotFoundError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server  # type: ignore

from . import ingest
from .config import resolve_vault
from .store import Vault, est_tokens

mcp = _Server("marina-memory")
_vault: Vault | None = None


def tool_names() -> list[str]:
    """Tool names actually registered on the server (works on both SDK majors)."""
    import asyncio
    import inspect

    res = mcp.list_tools()
    if inspect.isawaitable(res):
        res = asyncio.run(res)
    return [getattr(t, "name", str(t)) for t in res]


def get_vault() -> Vault:
    global _vault
    if _vault is None:
        _vault = Vault(resolve_vault()).ensure()
    return _vault


@mcp.tool()
def memory_recall(query: str, limit: int = 6, compartment: str | None = None) -> str:
    """Search her memory for things already known. USE THIS BEFORE ASKING HER
    TO REPEAT ANYTHING. Returns short records with ids. `compartment` may be
    business, studies, people, personal, health, inbox, sources."""
    recs = get_vault().recall(query, limit=limit, compartment=compartment)
    if not recs:
        return (f"No stored memory matches '{query}'. Nothing is known — "
                "ask her, then call memory_remember so it is never asked again.")
    out = [f"Memory: {len(recs)} record(s) for '{query}':"]
    for r in recs:
        out.append(f"- [{r.id}] ({r.compartment}, {r.created_at[:10]}) {r.text[:400]}")
    return "\n".join(out)


@mcp.tool()
def memory_remember(content: str, compartment: str | None = None,
                    tags: list[str] | None = None) -> str:
    """Store a durable fact, decision, preference or event so future sessions
    start knowing it. One self-contained statement per call. Pass `compartment`
    only when you are certain; otherwise leave it empty and it is auto-filed."""
    rec = get_vault().remember(content, compartment=compartment, tags=tags, source="claude")
    return f"Stored in '{rec.compartment}' as [{rec.id}]: {rec.text[:200]}"


@mcp.tool()
def memory_ingest(path: str, compartment: str | None = None) -> str:
    """Store a DOCUMENT (PDF, DOCX, PPTX, XLSX, HTML, EPUB, image, audio) by its
    file path. It is converted to Markdown locally and stored once, so it is
    never re-pasted into the conversation. Returns a compact card, not the text.
    ALWAYS prefer this over asking her to paste a document's contents."""
    try:
        md = ingest.convert(path)
    except ingest.IngestError as e:
        return f"Ingest failed: {e}"
    src = Path(path).expanduser()
    vault = get_vault()
    title = src.stem.replace("_", " ").replace("-", " ").strip() or src.name
    card = vault.store_document(md, title=title, source_path=str(src), compartment=compartment)
    rep = ingest.compression_report(src, md)
    headings = ", ".join(card["headings"][:10]) or "none detected"
    return (
        f"Ingested '{title}'\n"
        f"- slug: {card['slug']}  compartment: {card['compartment']}\n"
        f"- {card['words']} words (~{card['tokens_est']} tokens as Markdown, "
        f"down from {rep['raw_bytes'] // 1024} KB raw, {rep['reduction_pct']}% smaller)\n"
        f"- sections: {headings}\n"
        f"- opening: {card['opening'][:220]}\n"
        f"Read it with memory_open(slug='{card['slug']}') — or add a query to pull only the "
        f"relevant sections instead of the whole file."
    )


@mcp.tool()
def memory_open(slug: str, query: str | None = None, max_chars: int = 4000) -> str:
    """Read a stored document. With `query`, only the matching sections are
    returned — cheaper and more focused than the full text. Without it, you get
    the opening plus a pointer to the rest."""
    res = get_vault().open_doc(slug, query=query, max_chars=max_chars)
    if res.get("error"):
        return f"{res['error']}\nAvailable: {', '.join(res.get('available', [])) or 'none'}"
    head = f"# {res['title']} (slug: {slug})\n"
    if res["mode"] == "matched_sections":
        body = "\n\n---\n\n".join(res["sections"])
        return (f"{head}Returned {res['returned_chars']} of {res['full_chars']} chars "
                f"(matched sections only).\n\n{body}")
    return (f"{head}{res['content']}\n\n[...{res['full_chars'] - res['returned_chars']} chars "
            f"not shown. {res['next']}]")


@mcp.tool()
def memory_stored_documents() -> str:
    """List every document she has stored, with the slug to read it by."""
    v = get_vault()
    slugs = v.doc_slugs()
    if not slugs:
        return "No documents stored yet."
    lines = []
    for s in slugs[:40]:
        d = v.get_doc(s)
        lines.append(f"- {d['title']} [{d['compartment']}, {d['words']} words] → memory_open(slug='{s}')")
    return "Stored documents:\n" + "\n".join(lines)


@mcp.tool()
def memory_index() -> str:
    """Return the hot memory index — a compact overview of everything known,
    grouped by compartment (business, studies, people, personal, health). Read
    this at the start of a session that needs her context."""
    v = get_vault()
    return v.hot_index()


@mcp.tool()
def memory_status() -> str:
    """Vault stats: record counts per compartment, documents, hot-index token
    cost, and the vault path on disk."""
    s = get_vault().status()
    comps = ", ".join(f"{k}={v}" for k, v in sorted(s["compartments"].items())) or "empty"
    return (f"vault: {s['vault']}\nfacts: {s['facts']} ({comps})\ndocuments: {s['documents']}\n"
            f"hot index: ~{s['hot_index_tokens']} tokens (budget {s['hot_budget_tokens']})")


@mcp.tool()
def memory_refile(id: str, compartment: str) -> str:
    """Move a record to a different compartment: business, studies, people,
    personal, health, inbox, sources."""
    v = get_vault()
    rec = v.get(id)
    if not rec:
        return f"No record with id {id}."
    v.forget(id)
    new = v.remember(rec.text, compartment=compartment, tags=rec.tags, source="refile")
    return f"Moved [{id}] → '{new.compartment}' as [{new.id}]."


@mcp.tool()
def memory_forget(id: str) -> str:
    """Remove a record from active memory. It is archived in _archive/, never
    destroyed. Use when a fact is wrong or obsolete."""
    ok = get_vault().forget(id)
    return f"Archived [{id}]." if ok else f"No record with id {id}."


def main() -> None:
    get_vault()  # fail fast and loudly before Claude connects
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
