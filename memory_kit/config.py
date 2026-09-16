"""Vault path resolution.

Precedence:  MEMORY_KIT_VAULT env  >  ~/.memory-kit.json  >  ~/MemoryVault

The config file exists so Claude Desktop (which has a minimal environment) can
be pointed at the vault without the user having to think about paths.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

VAULT_ENV = "MEMORY_KIT_VAULT"
CFG_PATH = Path.home() / ".memory-kit.json"
DEFAULT_VAULT = Path.home() / "MemoryVault"


def read_config() -> dict:
    try:
        return json.loads(CFG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_config(**kw) -> None:
    cfg = read_config()
    cfg.update(kw)
    CFG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def resolve_vault() -> Path:
    """Return the vault directory (not necessarily created)."""
    env = os.environ.get(VAULT_ENV)
    if env:
        return Path(env).expanduser()
    cfg = read_config()
    if cfg.get("vault"):
        return Path(cfg["vault"]).expanduser()
    return DEFAULT_VAULT


def claude_desktop_config_path() -> Path:
    """Best-effort location of Claude Desktop's MCP config on this OS."""
    import sys

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if os.name == "nt":
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
