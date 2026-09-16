"""Document ingestion: PDF / DOCX / PPTX / XLSX / HTML / EPUB / images / audio
-> Markdown, via markitdown, fully local.

Why Markdown: Office formats shrink ~90-95% when converted (a 536 KB DOCX
becomes ~29 KB of Markdown with headings and tables intact). That is the single
biggest lever on burn rate — and it means a document is stored once, read in
sections, instead of being re-pasted into the conversation every few turns.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

SUPPORTED = {
    ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".csv", ".tsv",
    ".html", ".htm", ".epub", ".msg", ".json", ".xml", ".txt", ".md", ".rtf",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp",
    ".mp3", ".wav", ".m4a", ".flac", ".ogg",
}


class IngestError(RuntimeError):
    pass


def _markitdown_cli() -> str | None:
    return shutil.which("markitdown")


def convert(path: str | Path) -> str:
    """Convert one file to Markdown text. Raises IngestError with the reason."""
    p = Path(path).expanduser()
    if not p.exists():
        raise IngestError(f"file not found: {p}")
    if p.suffix.lower() not in SUPPORTED:
        raise IngestError(
            f"unsupported format '{p.suffix}'. Supported: {', '.join(sorted(SUPPORTED))}"
        )
    if p.suffix.lower() in {".txt", ".md", ".csv", ".tsv"} :
        # Already text: converting adds nothing, reading it is enough.
        return p.read_text(encoding="utf-8", errors="replace")

    # Preferred: the library (no subprocess, no temp files).
    try:
        from markitdown import MarkItDown  # type: ignore

        md = MarkItDown(enable_plugins=False).convert(str(p))
        text = getattr(md, "text_content", None) or getattr(md, "markdown", "")
        if text and text.strip():
            return text
        raise IngestError(
            "markitdown returned no text — likely a scanned/image-only file. "
            "Install the extras: pip install 'marina-memory[extras]' (OCR engines)."
        )
    except ImportError:
        pass

    cli = _markitdown_cli()
    if not cli:
        raise IngestError(
            "markitdown is not installed. Run: pip install 'markitdown[pdf,docx,pptx,xlsx]'"
        )
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / (p.stem + ".md")
        res = subprocess.run(
            [cli, str(p), "-o", str(out)], capture_output=True, text=True, timeout=600
        )
        if not out.exists() or not out.read_text(encoding="utf-8", errors="replace").strip():
            raise IngestError(f"markitdown failed: {(res.stderr or res.stdout)[-400:]}")
        return out.read_text(encoding="utf-8", errors="replace")


def compression_report(original: Path, markdown: str) -> dict:
    raw = original.stat().st_size
    md_bytes = len(markdown.encode("utf-8"))
    pct = round(100 * (1 - md_bytes / raw), 1) if raw else 0.0
    return {"raw_bytes": raw, "md_bytes": md_bytes, "reduction_pct": pct}
