#!/usr/bin/env bash
# One-command install for marina-memory. Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")"

echo "== marina-memory installer =="

if command -v uv >/dev/null 2>&1; then
  echo "-> installing with uv tool"
  uv tool install --force .
elif command -v pipx >/dev/null 2>&1; then
  echo "-> installing with pipx"
  pipx install --force .
else
  echo "-> no uv/pipx found; installing with pip --user"
  python3 -m pip install --user --upgrade .
fi

# Ensure `mm` is reachable in this shell before the next steps.
if ! command -v mm >/dev/null 2>&1; then
  for d in "$HOME/.local/bin" "$HOME/.cargo/bin"; do
    [ -x "$d/mm" ] && export PATH="$d:$PATH"
  done
fi

command -v mm >/dev/null 2>&1 || {
  echo "!! 'mm' is not on PATH. Add it (usually ~/.local/bin) and re-run: mm init"
  exit 1
}

mm init
mm connect-claude
echo
echo "== done. Now quit Claude Desktop entirely (Cmd+Q) and reopen it. =="
echo "Then ask Claude: \"read my memory index\""
