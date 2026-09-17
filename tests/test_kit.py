"""End-to-end tests: real files, real SQLite, real markitdown. No mocks."""
from __future__ import annotations

import os
import zipfile
from pathlib import Path

import pytest

from memory_kit import ingest
from memory_kit.router import route
from memory_kit.store import Vault, est_tokens


@pytest.fixture()
def vault(tmp_path: Path) -> Vault:
    return Vault(tmp_path / "vault").ensure()


# ------------------------------------------------------------------- routing
@pytest.mark.parametrize(
    "text,expected",
    [
        ("Ze wants to facture the client before the mission ends", "business"),
        ("École de journalisme: examen de mémoire vendredi", "studies"),
        ("Ma mère a son anniversaire le 3 mars", "people"),
        ("Mon propriétaire veut augmenter le loyer", "personal"),
        ("Doctor appointment for my migraine medication", "health"),
        ("hello", "inbox"),
        # regression cases from the 2026-09-17 lexicon tuning pass: these all
        # landed in inbox/ before, which is friction for a non-technical user.
        ("Rate card: 90 euros per article, 250 for a feature", "business"),
        ("Interview confirmed Thursday with the deputy mayor", "business"),
        ("Thomas is a photographer, useful for event coverage", "people"),
        ("Passport expires in 2028, no renewal needed yet", "personal"),
        ("Travel: train to Marseille booked for the conference", "personal"),
        ("Doctor Moreau is the GP, appointments two weeks out", "health"),
    ],
)
def test_router(text, expected):
    assert route(text)[0] == expected


@pytest.mark.parametrize(
    "text",
    ["Photographe disponible pour le portrait", "Mon passeport expire en 2028"],
)
def test_router_french_variants(text):
    assert route(text)[0] in {"people", "personal"}


def test_router_never_drops():
    comp, score = route("qwerty zxcvb")
    assert comp == "inbox" and score == 0.0


# ------------------------------------------------------------------- storage
def test_remember_writes_markdown_and_indexes(vault: Vault):
    rec = vault.remember("Marina is training at journalist school in Nice")
    assert rec.compartment == "studies"
    path = vault.root / rec.file
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "journalist school" in text and rec.id in text
    # recall finds it again
    hits = vault.recall("journalist school")
    assert hits and hits[0].id == rec.id


def test_records_survive_db_loss(vault: Vault):
    """Files are the source of truth: deleting the index must lose nothing."""
    vault.remember("Client X owes an invoice of 450 euros", compartment="business")
    vault.remember("Examen de mémoire le 12 octobre", compartment="studies")
    vault.db_path.unlink()
    vault.ensure()
    n = vault.reindex()
    assert n == 2
    assert vault.recall("invoice")[0].compartment == "business"
    assert vault.recall("mémoire")


def test_forget_archives_never_destroys(vault: Vault):
    rec = vault.remember("A wrong fact that must go", compartment="personal")
    assert vault.forget(rec.id)
    assert not vault.recall("wrong fact")
    archived = (vault.root / "_archive" / "personal-forgotten.md").read_text(encoding="utf-8")
    assert "A wrong fact" in archived


def test_hot_index_respects_budget(tmp_path: Path):
    v = Vault(tmp_path / "v", hot_budget_tokens=300).ensure()
    for i in range(60):
        v.remember(f"Client invoice number {i} for a mission in Nice", compartment="business")
    tokens = est_tokens(v.hot_index())
    assert tokens <= 300 * 1.15, f"hot index escaped its budget: {tokens} tokens"
    assert v.status()["facts"] == 60  # nothing lost, just not injected


# ------------------------------------------------------------------ ingestion
def _make_docx(path: Path, paragraphs: list[str]) -> Path:
    """Build a valid minimal .docx without extra dependencies."""
    body = "".join(
        f"<w:p><w:r><w:t xml:space=\"preserve\">{p}</w:t></w:r></w:p>" for p in paragraphs
    )
    doc = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    ct = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", doc)
    return path


def _make_pdf(path: Path, lines: list[str]) -> Path:
    """Build a valid, text-extractable PDF without extra dependencies."""
    body = ["BT", "/F1 11 Tf", "18 TL", "50 760 Td"] + [f"({ln}) Tj T*" for ln in lines] + ["ET"]
    content = "\n".join(body).encode("latin-1")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for i, body_i in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body_i + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n").encode()
    path.write_bytes(bytes(out))
    return path


def test_ingest_docx_to_markdown(vault: Vault, tmp_path: Path):
    src = _make_docx(tmp_path / "cours-journalisme.docx", [
        "Cours de journalisme: sources et vérification",
        "Règle un: toujours vérifier une source primaire.",
        "Règle deux: protéger ses sources.",
    ])
    md = ingest.convert(src)
    assert "vérification" in md and "protéger" in md

    card = vault.store_document(md, title="Cours de journalisme", source_path=str(src),
                                compartment="studies")
    assert card["words"] > 5
    assert (vault.root / card["md_path"]).exists()
    assert card["tokens_est"] == est_tokens(md)
    # the document is recallable and openable
    assert vault.recall("journalisme")
    res = vault.open_doc(card["slug"], query="protéger mes sources")
    assert res["mode"] == "matched_sections" and "protéger" in res["sections"][0]


def test_ingest_pdf(vault: Vault, tmp_path: Path):
    src = tmp_path / "note-terrain.pdf"
    _make_pdf(src, [
        "Enquete de terrain: la verification des sources",
        "Une source primaire est toujours preferable.",
        "Proteger ses sources est une obligation deontologique.",
    ])
    md = ingest.convert(src)
    assert "verification" in md.lower()
    rep = ingest.compression_report(src, md)
    assert rep["raw_bytes"] > 0 and len(md.split()) > 5


def test_ingest_real_pdf_if_available(vault: Vault, tmp_path: Path):
    """A real-world text PDF, exercised when one happens to be on disk."""
    candidates: list[Path] = []
    # os.walk with onerror, not rglob: ~/Documents contains macOS bundles that
    # raise OSError (Resource deadlock avoided) when descended into.
    for root, dirs, files in os.walk(Path.home() / "Documents", onerror=lambda _e: None):
        dirs[:] = [d for d in dirs if not d.endswith((".palmier", ".app", ".bundle"))]
        for fn in files:
            if fn.lower().endswith(".pdf"):
                p = Path(root) / fn
                try:
                    if p.stat().st_size <= 8_000_000:
                        candidates.append(p)
                except OSError:
                    continue
        if len(candidates) >= 6:
            break
    for pdf in candidates:
        try:
            md = ingest.convert(pdf)
        except ingest.IngestError:
            continue  # image-only PDFs are expected to refuse cleanly
        if len(md.split()) > 50:
            card = vault.store_document(md, title=pdf.stem)
            assert (vault.root / card["md_path"]).exists()
            assert vault.recall(pdf.stem.split()[0]) is not None
            return
    pytest.skip("no text-extractable PDF on disk")


def test_image_only_pdf_refuses_cleanly(vault: Vault, tmp_path: Path):
    """Image-only PDFs must fail loudly, not silently store an empty document."""
    if not (Path.home() / ".hermes" / "3-steps-to-make-ai-work.pdf").exists():
        pytest.skip("no image-only sample")
    with pytest.raises(ingest.IngestError) as e:
        ingest.convert(Path.home() / ".hermes" / "3-steps-to-make-ai-work.pdf")
    assert "scanned" in str(e.value) or "no text" in str(e.value)


def test_ingest_rejects_unknown_and_missing(vault: Vault, tmp_path: Path):
    with pytest.raises(ingest.IngestError):
        ingest.convert(tmp_path / "nope.pdf")
    bad = tmp_path / "file.xyz"
    bad.write_text("x")
    with pytest.raises(ingest.IngestError):
        ingest.convert(bad)


def test_open_doc_sections_are_bounded(vault: Vault, tmp_path: Path):
    md = "# Title\n\n## A\n" + ("alpha " * 400) + "\n\n## B\n" + ("beta " * 400)
    card = vault.store_document(md, title="Long doc")
    res = vault.open_doc(card["slug"], query="beta", max_chars=500)
    assert res["returned_chars"] < res["full_chars"]
    assert "beta" in res["sections"][0]


# ----------------------------------------------------------------- windows
def test_claude_config_path_windows(monkeypatch, tmp_path):
    """Windows is Marina's platform, so this path must be right."""
    import sys as _sys

    from memory_kit import config

    monkeypatch.setattr(_sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    p = config.claude_desktop_config_path()
    assert p.name == "claude_desktop_config.json"
    assert "Claude" in p.parts
    assert str(tmp_path) in str(p)
    assert "system tray" in config.quit_claude_hint()


def test_claude_config_path_macos(monkeypatch):
    import sys as _sys

    from memory_kit import config

    monkeypatch.setattr(_sys, "platform", "darwin")
    p = config.claude_desktop_config_path()
    assert "Application Support" in p.parts
    assert "Cmd+Q" in config.quit_claude_hint()


def test_claude_config_path_windows_without_appdata(monkeypatch):
    """A stripped environment must not crash the installer."""
    import sys as _sys

    from memory_kit import config

    monkeypatch.setattr(_sys, "platform", "win32")
    monkeypatch.delenv("APPDATA", raising=False)
    p = config.claude_desktop_config_path()
    assert p.name == "claude_desktop_config.json"


def test_connect_claude_writes_windows_path(monkeypatch, tmp_path):
    """End to end for the Windows branch: real JSON written to %APPDATA%."""
    import json
    import sys as _sys

    monkeypatch.setattr(_sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("MEMORY_KIT_VAULT", str(tmp_path / "vault"))
    from memory_kit import cli

    args = type("A", (), {"vault": str(tmp_path / "vault")})()
    assert cli.cmd_connect_claude(args) == 0
    cfg = json.loads((tmp_path / "Roaming" / "Claude" / "claude_desktop_config.json").read_text())
    assert cfg["mcpServers"]["marina-memory"]["env"]["MEMORY_KIT_VAULT"] == str(tmp_path / "vault")


# --------------------------------------------------------------------- server
def test_mcp_tools_are_registered(monkeypatch, tmp_path):
    monkeypatch.setenv("MEMORY_KIT_VAULT", str(tmp_path / "mv"))
    from memory_kit import server

    names = set(server.tool_names())
    assert {
        "memory_recall", "memory_remember", "memory_ingest", "memory_open",
        "memory_index", "memory_status", "memory_forget", "memory_refile",
        "memory_stored_documents",
    } <= names
    out = server.memory_remember("Doctor appointment for migraine medication")
    assert "health" in out
    assert "migraine" in server.memory_recall("migraine")
    assert "~" in server.memory_status()
    assert "hot tier" in server.memory_index()
