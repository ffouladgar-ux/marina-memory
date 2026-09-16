"""`mm` — the command line she actually types (and the installer for Claude)."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import __version__, ingest
from .config import (claude_desktop_config_path, read_config, resolve_vault,
                     write_config)
from .store import Vault, est_tokens


def _vault(args) -> Vault:
    root = Path(args.vault).expanduser() if getattr(args, "vault", None) else resolve_vault()
    return Vault(root, hot_budget_tokens=getattr(args, "hot_budget", 900) or 900).ensure()


# --------------------------------------------------------------------- commands
def cmd_init(args) -> int:
    root = Path(args.path).expanduser() if args.path else resolve_vault()
    Vault(root).ensure().rebuild_index()
    write_config(vault=str(root))
    print(f"Vault created at {root}")
    print("Compartments: " + ", ".join(sorted(p.name for p in root.iterdir() if p.is_dir())))
    print(f"Config written to ~/.memory-kit.json")
    print("Next: mm connect-claude")
    return 0


def cmd_remember(args) -> int:
    rec = _vault(args).remember(args.text, compartment=args.compartment,
                                tags=args.tag or [], source="cli")
    print(f"[{rec.id}] {rec.compartment}: {rec.text}")
    return 0


def cmd_recall(args) -> int:
    v = _vault(args)
    if args.query:
        recs = v.recall(args.query, limit=args.limit, compartment=args.compartment)
        if not recs:
            print("nothing found")
            return 1
        for r in recs:
            print(r.line())
    else:
        print(v.hot_index())
    return 0


def cmd_ingest(args) -> int:
    v = _vault(args)
    for path in args.paths:
        try:
            md = ingest.convert(path)
        except ingest.IngestError as e:
            print(f"FAILED {path}: {e}", file=sys.stderr)
            continue
        src = Path(path).expanduser()
        title = src.stem.replace("_", " ").replace("-", " ").strip() or src.name
        card = v.store_document(md, title=title, source_path=str(src),
                                compartment=args.compartment)
        rep = ingest.compression_report(src, md)
        print(f"OK [{card['slug']}] {title} — {card['words']} words, "
              f"~{card['tokens_est']} tokens ({rep['reduction_pct']}% smaller than "
              f"{rep['raw_bytes'] // 1024} KB raw)")
    return 0


def cmd_open(args) -> int:
    v = _vault(args)
    res = v.open_doc(args.slug, query=args.query, max_chars=args.max_chars)
    if res.get("error"):
        print(res["error"], file=sys.stderr)
        print("available: " + (", ".join(res.get("available", [])) or "none"))
        return 1
    if res["mode"] == "matched_sections":
        print("\n\n---\n\n".join(res["sections"]))
        print(f"\n[{res['returned_chars']}/{res['full_chars']} chars — matched sections]",
              file=sys.stderr)
    else:
        print(res["content"])
        print(f"\n[{res['full_chars']} chars total]", file=sys.stderr)
    return 0


def cmd_status(args) -> int:
    s = _vault(args).status()
    print(json.dumps(s, indent=2))
    return 0


def cmd_index(args) -> int:
    text = _vault(args).rebuild_index()
    if args.print:
        print(text)
    else:
        print(f"index.md regenerated — ~{est_tokens(text)} tokens")
    return 0


def cmd_reindex(args) -> int:
    n = _vault(args).reindex()
    print(f"Reindexed {n} records from Markdown files (files were the source of truth).")
    return 0


def cmd_forget(args) -> int:
    ok = _vault(args).forget(args.id)
    print("archived" if ok else "no such id")
    return 0 if ok else 1


def cmd_serve(args) -> int:
    from .server import main as serve

    serve()
    return 0


def cmd_connect_claude(args) -> int:
    """Wire the MCP server into Claude Desktop, with correct absolute paths."""
    vault = Path(args.vault).expanduser() if args.vault else resolve_vault()
    Vault(vault).ensure()
    cfg_path = claude_desktop_config_path()
    entry = {
        "command": sys.executable,
        "args": ["-m", "memory_kit", "serve"],
        "env": {"MEMORY_KIT_VAULT": str(vault)},
    }
    cfg: dict = {}
    if cfg_path.exists():
        shutil.copy2(cfg_path, str(cfg_path) + ".bak-marina-memory")
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8")) or {}
        except Exception:
            print(f"WARNING: {cfg_path} exists but is not valid JSON — it was backed up. "
                  "Fix it, then re-run.", file=sys.stderr)
            return 1
    cfg.setdefault("mcpServers", {})["marina-memory"] = entry
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(f"Claude Desktop configured: {cfg_path}")
    print(json.dumps({"marina-memory": entry}, indent=2))
    print("\nNow: quit Claude Desktop completely (Cmd+Q) and reopen it.")
    print("Then ask: 'read my memory index'.")
    print("\nUsing Claude Code instead? Run:")
    print(f'  claude mcp add marina-memory --env MEMORY_KIT_VAULT="{vault}" '
          f'-- "{sys.executable}" -m memory_kit serve')
    return 0


def cmd_doctor(args) -> int:
    ok = True
    print(f"marina-memory {__version__}")
    print(f"python: {sys.executable}")
    vault = resolve_vault()
    print(f"vault: {vault} {'(exists)' if vault.exists() else '(missing — run: mm init)'}")
    if not vault.exists():
        ok = False
    try:
        from mcp.server.mcpserver import MCPServer  # noqa: F401  (mcp >= 2)

        print("mcp SDK: ok (2.x)")
    except ModuleNotFoundError:
        try:
            from mcp.server.fastmcp import FastMCP  # noqa: F401  (mcp 1.x)

            print("mcp SDK: ok (1.x)")
        except Exception as e:  # pragma: no cover
            print(f"mcp SDK: MISSING ({e}) — run: pip install 'mcp>=1.2'")
            ok = False
    try:
        from markitdown import MarkItDown  # noqa: F401

        print("markitdown: ok")
    except Exception:
        print(f"markitdown: CLI only ({shutil.which('markitdown') or 'MISSING'})")
    try:
        v = Vault(vault).ensure()
        s = v.status()
        print(f"store: {s['facts']} facts, {s['documents']} documents, "
              f"hot index ~{s['hot_index_tokens']} tokens")
    except Exception as e:  # pragma: no cover
        print(f"store: ERROR {e}"); ok = False
    cfg_path = claude_desktop_config_path()
    wired = False
    if cfg_path.exists():
        try:
            wired = "marina-memory" in (json.loads(cfg_path.read_text()) or {}).get("mcpServers", {})
        except Exception:
            wired = False
    print(f"claude desktop config: {cfg_path} {'WIRED' if wired else 'not wired'}")
    print("\nRESULT: " + ("ready" if ok else "problems above"))
    return 0 if ok else 1


# ------------------------------------------------------------------------ main
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mm", description="Local-first Markdown memory for Claude.")
    p.add_argument("--vault", help="vault path (default: ~/MemoryVault)")
    p.add_argument("--hot-budget", type=int, default=900, help="hot index token budget")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init", help="create the vault")
    sp.add_argument("--path")
    sp.set_defaults(fn=cmd_init)

    sp = sub.add_parser("remember", help="store one fact")
    sp.add_argument("text")
    sp.add_argument("-c", "--compartment")
    sp.add_argument("-t", "--tag", action="append")
    sp.set_defaults(fn=cmd_remember)

    sp = sub.add_parser("recall", help="search memory (or print the hot index)")
    sp.add_argument("query", nargs="?")
    sp.add_argument("-l", "--limit", type=int, default=6)
    sp.add_argument("-c", "--compartment")
    sp.set_defaults(fn=cmd_recall)

    sp = sub.add_parser("ingest", help="convert + store documents (PDF/DOCX/PPTX/XLSX/...)")
    sp.add_argument("paths", nargs="+")
    sp.add_argument("-c", "--compartment")
    sp.set_defaults(fn=cmd_ingest)

    sp = sub.add_parser("open", help="read a stored document")
    sp.add_argument("slug")
    sp.add_argument("-q", "--query")
    sp.add_argument("--max-chars", type=int, default=4000)
    sp.set_defaults(fn=cmd_open)

    sub.add_parser("status", help="vault stats").set_defaults(fn=cmd_status)

    sp = sub.add_parser("index", help="regenerate the hot index")
    sp.add_argument("--print", action="store_true")
    sp.set_defaults(fn=cmd_index)

    sub.add_parser("reindex", help="rebuild the SQLite index from Markdown").set_defaults(fn=cmd_reindex)

    sp = sub.add_parser("forget", help="archive a record")
    sp.add_argument("id")
    sp.set_defaults(fn=cmd_forget)

    sub.add_parser("connect-claude", help="wire this vault into Claude Desktop").set_defaults(fn=cmd_connect_claude)
    sub.add_parser("doctor", help="verify the install").set_defaults(fn=cmd_doctor)
    sub.add_parser("serve", help="run the MCP server (Claude calls this)").set_defaults(fn=cmd_serve)

    args = p.parse_args(argv)
    return int(args.fn(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
