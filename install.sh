#!/usr/bin/env bash
# marina-memory installer. Safe to re-run. No prior tools required.
#
#   ./install.sh            human mode: friendly output, ends with a summary
#   ./install.sh --agent    agent mode: non-interactive, machine-readable lines
#
# If uv is missing it is fetched over the network; uv then fetches its own
# Python, so the only prerequisite is an internet connection.
set -uo pipefail
cd "$(dirname "$0")"

AGENT=0
for arg in "$@"; do
  [ "$arg" = "--agent" ] && AGENT=1
done

say() { printf '%s\n' "$*"; }
say_agent() { [ "$AGENT" = "1" ] && printf '%s\n' "$*"; }
fail() {
  say ""
  say "SETUP FAILED: $*"
  say "Send the text above to Fadi."
  say_agent "INSTALL_RESULT: failed"
  exit 1
}

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

# ---------------------------------------------------------- 4. Claude wiring
say ""
say "-> Connecting it to your Claude apps"
if [ "$AGENT" = "1" ]; then
  mm connect --agent || fail "could not wire the Claude apps"
else
  mm connect || fail "could not wire the Claude apps"
fi

# ------------------------------------------------------------------ 5. verify
say ""
say "-> Verifying"
DOCTOR="$(mm doctor 2>&1)"
printf '%s\n' "$DOCTOR"
printf '%s' "$DOCTOR" | grep -q "RESULT: ready" || fail "the install ran but 'mm doctor' reported problems"

say_agent "INSTALL_RESULT: ok"
say_agent "VAULT: ${MEMORY_KIT_VAULT:-$HOME/MemoryVault}"

if [ "$AGENT" != "1" ]; then
  say ""
  say "================================================================"
  say " Almost done. One step left, once:"
  say ""
  say "   Quit Claude completely (Mac: Cmd+Q; Windows: right-click the"
  say "   tray icon, then Quit), then reopen it. Closing the window is"
  say "   not enough. That is it: nothing to paste, nothing to configure."
  say ""
  say " Then just talk to it normally."
  say "================================================================"
fi
