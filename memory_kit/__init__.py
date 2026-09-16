"""marina-memory — local-first Markdown memory for Claude, over MCP.

Design rules (deliberate, do not break them):
  1. Files are the source of truth. The SQLite index is disposable and can be
     rebuilt from the Markdown at any time (`mm reindex`).
  2. Zero network calls at runtime. No embeddings, no LLM calls, no API keys.
     Search is SQLite FTS5. Storage costs nothing, so it never adds burn.
  3. Two tiers: a small auto-generated hot index (~900 tokens) plus a cold
     Markdown store that is only read on demand, section by section.
  4. Nothing is ever lost: unknown text lands in `inbox/`, never dropped.
"""

__version__ = "0.1.0"

from .config import resolve_vault, VAULT_ENV  # noqa: F401
from .store import Vault  # noqa: F401

__all__ = ["Vault", "resolve_vault", "VAULT_ENV", "__version__"]
