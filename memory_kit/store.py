"""Markdown-first memory store.

Layout
------
    <vault>/index.md              hot tier, auto-generated, token-budgeted
    <vault>/<compartment>/YYYY-MM.md   cold tier, append-only Markdown log
    <vault>/sources/<slug>.md     ingested documents, converted to Markdown
    <vault>/_archive/             soft-deleted records (nothing is destroyed)
    <vault>/.index/store.db       disposable SQLite + FTS5 index

Invariant: every fact exists as a human-readable line in a `.md` file. Delete
`.index/store.db` at any time; `reindex()` rebuilds it from the files.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .router import COMPARTMENTS, route

BLOCK_RE = re.compile(
    r"^### (?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}) · (?P<id>[0-9a-f]{6})(?P<flags>[^\n]*)\n"
    r"(?P<body>.*?)(?=^### |\Z)",
    re.M | re.S,
)
HEADING_RE = re.compile(r"^(#{1,3})\s+(.*)$", re.M)


def est_tokens(text: str) -> int:
    """Cheap, dependency-free token estimate (~4 chars/token, EN+FR)."""
    return max(1, round(len(text) / 4))


def _slug(text: str, maxlen: int = 60) -> str:
    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return (t[:maxlen].rstrip("-")) or "document"


def _rid(text: str) -> str:
    stamp = datetime.now().isoformat(timespec="microseconds")
    return hashlib.sha1(f"{stamp}|{text}".encode()).hexdigest()[:6]


def _clean(text: str) -> str:
    """Never let user text break the record format."""
    lines = [ln for ln in text.strip().splitlines() if not ln.startswith("### ")]
    return "\n".join(lines).strip()


@dataclass
class Record:
    id: str
    compartment: str
    text: str
    created_at: str
    file: str = ""
    tags: list[str] = field(default_factory=list)
    source: str = "chat"
    rank: float | None = None

    def line(self) -> str:
        tag = f"_tags: {', '.join(self.tags)}_" if self.tags else ""
        return f"[{self.id}] {self.created_at[11:16]} {self.compartment}: {self.text}"


class Vault:
    def __init__(self, root: Path | str, hot_budget_tokens: int = 900):
        self.root = Path(root).expanduser()
        self.hot_budget_tokens = hot_budget_tokens
        self.db_path = self.root / ".index" / "store.db"

    # ---------------------------------------------------------------- setup
    def ensure(self) -> "Vault":
        for c in COMPARTMENTS + ("sources",):
            (self.root / c).mkdir(parents=True, exist_ok=True)
        (self.root / "_archive").mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS records (
                    id TEXT PRIMARY KEY, compartment TEXT, text TEXT, tags TEXT,
                    created_at TEXT, file TEXT, source TEXT, kind TEXT
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(
                    text, rid UNINDEXED, compartment UNINDEXED,
                    tokenize='unicode61 remove_diacritics 2'
                );
                CREATE TABLE IF NOT EXISTS docs (
                    slug TEXT PRIMARY KEY, title TEXT, source_path TEXT, md_path TEXT,
                    words INTEGER, tokens_est INTEGER, compartment TEXT,
                    created_at TEXT, headings TEXT, opening TEXT
                );
                CREATE TABLE IF NOT EXISTS ledger (
                    ts TEXT, action TEXT, rid TEXT, detail TEXT
                );
                """
            )
        return self

    def _conn(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _log(self, conn: sqlite3.Connection, action: str, rid: str, detail: str = "") -> None:
        conn.execute(
            "INSERT INTO ledger(ts, action, rid, detail) VALUES(?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), action, rid, detail),
        )

    # -------------------------------------------------------------- writing
    def remember(
        self,
        text: str,
        compartment: str | None = None,
        tags: list[str] | None = None,
        source: str = "chat",
        when: datetime | None = None,
    ) -> Record:
        text = _clean(text)
        if not text:
            raise ValueError("empty note")
        comp, _score = route(text, explicit=compartment)
        when = when or datetime.now()
        rid = _rid(text)
        rec = Record(
            id=rid, compartment=comp, text=text,
            created_at=when.strftime("%Y-%m-%d %H:%M"),
            tags=tags or [], source=source,
        )
        path = self.root / comp / f"{when.strftime('%Y-%m')}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        header = f"### {rec.created_at} · {rec.id}\n"
        tagline = f"_tags: {', '.join(rec.tags)}_\n" if rec.tags else ""
        if not path.exists():
            path.write_text(
                f"# {comp.title()} — {when.strftime('%B %Y')}\n\n", encoding="utf-8"
            )
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"{header}{tagline}{rec.text}\n\n")
        rec.file = str(path.relative_to(self.root))
        with self._conn() as conn:
            self._upsert(conn, rec, kind="fact")
            self._log(conn, "remember", rid, comp)
        self.rebuild_index()
        return rec

    def _upsert(self, conn: sqlite3.Connection, rec: Record, kind: str = "fact") -> None:
        conn.execute("DELETE FROM records WHERE id=?", (rec.id,))
        conn.execute("DELETE FROM fts WHERE rid=?", (rec.id,))
        conn.execute(
            "INSERT OR REPLACE INTO records(id, compartment, text, tags, created_at,"
            " file, source, kind) VALUES(?,?,?,?,?,?,?,?)",
            (rec.id, rec.compartment, rec.text, ", ".join(rec.tags), rec.created_at,
             rec.file, rec.source, kind),
        )
        conn.execute(
            "INSERT INTO fts(text, rid, compartment) VALUES(?,?,?)",
            (f"{rec.compartment} {rec.text} {' '.join(rec.tags)}", rec.id, rec.compartment),
        )

    # ------------------------------------------------------------- reading
    @staticmethod
    def _fts_query(query: str) -> str | None:
        toks = re.findall(r"[\w\u00c0-\u024f]+", query, re.UNICODE)
        toks = [t for t in toks if len(t) > 1]
        if not toks:
            return None
        return " OR ".join(f'"{t}"' for t in toks)

    def recall(
        self, query: str, limit: int = 6, compartment: str | None = None
    ) -> list[Record]:
        fq = self._fts_query(query)
        with self._conn() as conn:
            if not fq:
                return []
            sql = (
                "SELECT r.*, bm25(fts) AS rank FROM fts JOIN records r ON r.id = fts.rid"
                " WHERE fts MATCH ?"
            )
            params: list = [fq]
            if compartment and compartment in COMPARTMENTS:
                sql += " AND r.compartment = ?"
                params.append(compartment)
            sql += " ORDER BY rank LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
        return [
            Record(id=r["id"], compartment=r["compartment"], text=r["text"],
                   created_at=r["created_at"], file=r["file"],
                   tags=[t for t in (r["tags"] or "").split(", ") if t],
                   source=r["source"], rank=r["rank"])
            for r in rows
        ]

    def get(self, rid: str) -> Record | None:
        with self._conn() as conn:
            r = conn.execute("SELECT * FROM records WHERE id=?", (rid,)).fetchone()
        if not r:
            return None
        return Record(id=r["id"], compartment=r["compartment"], text=r["text"],
                      created_at=r["created_at"], file=r["file"],
                      tags=[t for t in (r["tags"] or "").split(", ") if t])

    def forget(self, rid: str) -> bool:
        """Soft delete: record moves to _archive/, never destroyed."""
        rec = self.get(rid)
        if not rec:
            return False
        src = self.root / rec.file
        if src.exists():
            text = src.read_text(encoding="utf-8")
            text = re.sub(
                rf"^### [^\n]*· {re.escape(rid)}[^\n]*\n.*?(?=^### |\Z)", "", text,
                flags=re.M | re.S,
            )
            src.write_text(text, encoding="utf-8")
        arch = self.root / "_archive" / f"{rec.compartment}-forgotten.md"
        with arch.open("a", encoding="utf-8") as fh:
            fh.write(f"### {rec.created_at} · {rec.id} (forgotten)\n{rec.text}\n\n")
        with self._conn() as conn:
            conn.execute("DELETE FROM records WHERE id=?", (rid,))
            conn.execute("DELETE FROM fts WHERE rid=?", (rid,))
            self._log(conn, "forget", rid, rec.compartment)
        self.rebuild_index()
        return True

    # --------------------------------------------------------- document tier
    def store_document(
        self,
        md: str,
        title: str,
        source_path: str = "",
        compartment: str | None = None,
        slug: str | None = None,
    ) -> dict:
        """Persist a converted document. Returns the compact card, not the text."""
        slug = slug or _slug(title)
        comp = compartment if (compartment and compartment in COMPARTMENTS) else "studies"
        headings = [h.strip() for _lvl, h in HEADING_RE.findall(md)][:40]
        plain = re.sub(r"^#+\s*", "", md, flags=re.M).strip()
        opening = re.sub(r"\s+", " ", plain)[:280]
        words = len(md.split())
        path = self.root / "sources" / f"{slug}.md"
        path.write_text(md, encoding="utf-8")
        card = {
            "slug": slug, "title": title, "source_path": source_path,
            "md_path": str(path.relative_to(self.root)), "words": words,
            "tokens_est": est_tokens(md), "compartment": comp,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "headings": headings, "opening": opening,
        }
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO docs(slug,title,source_path,md_path,words,"
                "tokens_est,compartment,created_at,headings,opening)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                (slug, title, source_path, card["md_path"], words, card["tokens_est"],
                 comp, card["created_at"], json.dumps(headings), opening),
            )
            self._upsert(conn, Record(
                id=hashlib.sha1(slug.encode()).hexdigest()[:6], compartment=comp,
                text=f"Document '{title}' ({words} words) stored as sources/{slug}.md"
                     + (f". Sections: {', '.join(headings[:12])}" if headings else ""),
                created_at=card["created_at"], file=card["md_path"], source="ingest",
            ), kind="source")
            self._log(conn, "ingest", slug, source_path)
        self.rebuild_index()
        return card

    def open_doc(self, slug: str, query: str | None = None, max_chars: int = 4000) -> dict:
        doc = self.get_doc(slug)
        if not doc:
            return {"error": f"unknown document '{slug}'", "available": self.doc_slugs()}
        md = (self.root / doc["md_path"]).read_text(encoding="utf-8")
        if query:
            sections = self._match_sections(md, query, max_chars)
            return {"title": doc["title"], "slug": slug, "mode": "matched_sections",
                    "sections": sections, "returned_chars": sum(len(s) for s in sections),
                    "full_chars": len(md), "note":
                    "Returned only the sections matching the query, to protect context."}
        head = md[:max_chars]
        return {"title": doc["title"], "slug": slug, "mode": "head",
                "content": head, "returned_chars": len(head), "full_chars": len(md),
                "next": f"call memory_open(slug='{slug}', query='...') to pull specific parts"}

    @staticmethod
    def _match_sections(md: str, query: str, max_chars: int) -> list[str]:
        parts = re.split(r"(?m)^(?=#{1,3} )", md)
        terms = {t for t in re.findall(r"[\w\u00c0-\u024f]{3,}", query.lower())}
        scored: list[tuple[int, str]] = []
        for p in parts:
            if not p.strip():
                continue
            low = p.lower()
            score = sum(low.count(t) for t in terms)
            if score:
                scored.append((score, p))
        scored.sort(key=lambda x: -x[0])
        out, used = [], 0
        for _s, p in scored:
            if used + len(p) > max_chars and out:
                break
            out.append(p.strip()[:max_chars])
            used += len(p)
        return out or [md[:max_chars]]

    def get_doc(self, slug: str) -> dict | None:
        with self._conn() as conn:
            r = conn.execute("SELECT * FROM docs WHERE slug=?", (slug,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["headings"] = json.loads(d.get("headings") or "[]")
        return d

    def doc_slugs(self) -> list[str]:
        with self._conn() as conn:
            return [r["slug"] for r in conn.execute("SELECT slug FROM docs ORDER BY created_at DESC")]

    # ------------------------------------------------------------ hot tier
    def rebuild_index(self) -> str:
        """Regenerate index.md — the only thing that should sit in context."""
        with self._conn() as conn:
            counts = {
                r["compartment"]: r["n"]
                for r in conn.execute(
                    "SELECT compartment, COUNT(*) n FROM records WHERE kind='fact'"
                    " GROUP BY compartment"
                )
            }
            total = conn.execute(
                "SELECT COUNT(*) n FROM records WHERE kind='fact'"
            ).fetchone()["n"]
            docs = conn.execute("SELECT COUNT(*) n FROM docs").fetchone()["n"]
            rows = conn.execute(
                "SELECT * FROM records WHERE kind='fact' ORDER BY created_at DESC"
            ).fetchall()
        budget = self.hot_budget_tokens * 4
        head = (
            "# Memory index (hot tier)\n\n"
            "This file is auto-generated. Do not edit by hand.\n"
            f"Facts stored: {total} · documents: {docs} · "
            f"compartments: {', '.join(sorted(counts)) or 'none'}\n\n"
            "How to use: this is a pointer list, not the memory. When a question\n"
            "touches anything below, call memory_recall to pull the full record.\n"
            "Do not assume, and do not ask her to re-explain what is already here.\n\n"
        )
        body: list[str] = []
        used = len(head)
        by_comp: dict[str, list] = {}
        for r in rows:
            by_comp.setdefault(r["compartment"], []).append(r)
        for comp in sorted(by_comp):
            head_c = f"## {comp} ({counts.get(comp, 0)})\n"
            if used + len(head_c) > budget:
                break
            body.append(head_c)
            used += len(head_c)
            for r in by_comp[comp][:12]:
                snippet = re.sub(r"\s+", " ", r["text"])[:110]
                line = f"- [{r['id']}] {r['created_at'][:10]} {snippet}\n"
                if used + len(line) > budget:
                    break
                body.append(line)
                used += len(line)
            body.append("\n")
        if docs:
            body.append(f"## stored documents ({docs})\n")
            with self._conn() as conn:
                for d in conn.execute(
                    "SELECT slug, title, words FROM docs ORDER BY created_at DESC LIMIT 15"
                ):
                    body.append(f"- {d['title']} → memory_open(slug='{d['slug']}') [{d['words']} words]\n")
        text = head + "".join(body)
        (self.root / "index.md").write_text(text, encoding="utf-8")
        return text

    def hot_index(self) -> str:
        p = self.root / "index.md"
        return p.read_text(encoding="utf-8") if p.exists() else self.rebuild_index()

    # -------------------------------------------------------------- upkeep
    def reindex(self) -> int:
        """Rebuild the SQLite index from the Markdown files (files are truth)."""
        with self._conn() as conn:
            conn.execute("DELETE FROM records")
            conn.execute("DELETE FROM fts")
            n = 0
            for comp in COMPARTMENTS + ("sources",):
                for path in sorted((self.root / comp).glob("*.md")):
                    text = path.read_text(encoding="utf-8")
                    for m in BLOCK_RE.finditer(text):
                        body = m.group("body")
                        tags: list[str] = []
                        tm = re.match(r"^_tags: (.*)_\n?", body)
                        if tm:
                            tags = [t.strip() for t in tm.group(1).split(",") if t.strip()]
                            body = body[tm.end():]
                        rid = m.group("id")
                        rec = Record(
                            id=rid, compartment=comp, text=body.strip(),
                            created_at=m.group("ts"), file=str(path.relative_to(self.root)),
                            tags=tags, source="reindex",
                        )
                        self._upsert(conn, rec, kind="fact")
                        n += 1
            self._log(conn, "reindex", "-", str(n))
        self.rebuild_index()
        return n

    def status(self) -> dict:
        with self._conn() as conn:
            counts = {
                r["compartment"]: r["n"]
                for r in conn.execute(
                    "SELECT compartment, COUNT(*) n FROM records WHERE kind='fact'"
                    " GROUP BY compartment"
                )
            }
            docs = conn.execute("SELECT COUNT(*) n FROM docs").fetchone()["n"]
            total = conn.execute("SELECT COUNT(*) n FROM records").fetchone()["n"]
        hot = self.hot_index()
        return {
            "vault": str(self.root),
            "facts": total,
            "documents": docs,
            "compartments": counts,
            "hot_index_tokens": est_tokens(hot),
            "hot_budget_tokens": self.hot_budget_tokens,
            "db_bytes": self.db_path.stat().st_size if self.db_path.exists() else 0,
        }
