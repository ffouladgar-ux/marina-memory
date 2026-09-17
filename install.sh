#!/usr/bin/env bash
# marina-memory installer. Safe to re-run. No prior tools required.
#
# Turns a fresh Mac into a working install with one step. If uv is missing it
# installs it (uv can also fetch its own Python, so nothing else is needed).
set -uo pipefail
cd "$(dirname "$0")"

say() { printf '%s\n' "$*"; }
fail() { say ""; say "SETUP FAILED: $*"; say "Send the text above to Fadi."; exit 1; }

say "== Marina Memory: installer =="
say ""

# ---------------------------------------------------------------- 1. get uv
if ! command -v uv >/dev/null 2>&1; then
  say "-> Installing 'uv' (a small tool manager, ~30 seconds)"
  curl -LsSf https://astral.sh/uv/install.sh | sh || fail "could not download uv (check internet)"
  export PATH="$HOME/.local/bin:$PATH"
fi
command -v uv >/dev/null 2>&1 || fail "uv was installed but is not on PATH"
say "-> uv: $(uv --version 2>/dev/null | head -1)"

# Keep everything in predictable, user-owned locations.
export UV_TOOL_DIR="${UV_TOOL_DIR:-$HOME/.local/share/uv/tools}"
export UV_TOOL_BIN_DIR="${UV_TOOL_BIN_DIR:-$HOME/.local/bin}"
export PATH="$UV_TOOL_BIN_DIR:$PATH"

# ------------------------------------------------------------- 2. install it
say "-> Installing marina-memory (downloads Python + Markdown converter on first run)"
uv tool install --force . || fail "could not install the package"
command -v mm >/dev/null 2>&1 || fail "'mm' command not found after install (expected in $UV_TOOL_BIN_DIR)"
say "-> mm: $UV_TOOL_BIN_DIR/mm"

# --------------------------------------------------------------- 3. the vault
say ""
say "-> Creating your memory vault (Plain Markdown files you own)"
mm init || fail "could not create the vault"

# ------------------------------------------------------------ 4. Claude wiring
say ""
say "-> Connecting it to Claude Desktop"
mm connect-claude || fail "could not write the Claude Desktop config"

# ------------------------------------------------------------------ 5. verify
say ""
say "-> Verifying"
if mm doctor | tail -20; then
  say ""
  say "================================================================"
  say " Almost done. Two steps left, once:"
  say ""
  say "   1. Quit Claude completely: press Cmd+Q (closing the window"
  say "      is not enough, it will not reload)"
  say "   2. Reopen Claude and paste the instructions from"
  say "      CLAUDE-INSTRUCTIONS.md into Settings then Profile then"
  say "      Custom Instructions"
  say ""
  say " Then just talk to it normally."
  say "================================================================"
else
  fail "the install ran but 'mm doctor' reported problems"
fi
