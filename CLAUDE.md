# marina-memory: install contract for coding agents

If a user hands you this repository URL and says something like *"install that"*,
follow these steps exactly. Do not improvise a different install method, and do
not substitute a manual JSON edit for the installer.

## What you are installing

A local-first Markdown memory server for Claude, spoken over MCP. One user, one
machine. Notes are plain `.md` files in `~/MemoryVault`. No hosted service, no
account, no API key, no telemetry, and no network calls at runtime.

Targets, in the order you should check for them: **Claude Desktop / Cowork**
(config file, handled by the installer), **Claude Code** (`claude mcp add`,
handled by the installer).

## Steps

**1. Get the repository onto disk.** If you are not already inside it:

```bash
git clone https://github.com/ffouladgar-ux/marina-memory.git
cd marina-memory
```

The repository is **private**. If the clone fails with an authentication error,
**stop and tell the user**: they must accept the GitHub collaborator invite, then
authorize GitHub once (`gh auth login`, which opens a browser and shows a
one-time code). Never try to work around authentication, and never ask the user
to paste a token into the conversation.

**2. Run the installer, in agent mode.**

```bash
# macOS / Linux
bash install.sh --agent

# Windows (cmd.exe or PowerShell)
cmd /c "Install Marina Memory.bat" --agent
```

Agent mode is non-interactive and prints machine-readable result lines. Nothing
needs to be installed first: if `uv` is missing, the installer fetches it, and
`uv` fetches Python itself.

**3. Verify. This is the acceptance test, not a formality.**

```bash
mm doctor
```

It must end with `RESULT: ready`. Anything else: report the raw output verbatim
and stop.

**4. Tell the user the two remaining manual actions.** They are not optional and
you cannot do them for them:

- Quit Claude completely and reopen it. macOS: `Cmd+Q`. Windows: right-click the
  Claude icon next to the clock (system tray) and choose Quit. Closing the window
  does not reload the MCP config.
- Paste the block under "Text to paste" in `CLAUDE-INSTRUCTIONS.md` into Claude's
  **Settings → Profile → Custom Instructions**. Without it the tools exist but
  Claude will not reliably use them.

**5. Confirm it works end to end.** After the user restarts Claude, ask them to
say *"read my memory index"*. Expected: Claude calls `memory_index` and describes
an empty but valid memory. If instead it has no such tool, step 1 or 2 failed;
re-run `mm doctor` and report.

## Rules

- **Idempotent.** Re-running is always safe.
- **Never delete, move, or rewrite the user's vault.** `~/MemoryVault` is their
  data. You may read it to debug; never upload it, never paste its contents into
  a conversation, never commit it anywhere.
- **Never clobber other MCP servers.** The installer merges into
  `claude_desktop_config.json` and backs it up first. Keep it that way.
- **Do not silently continue on failure.** Print the raw output.
- **Do not invent flags.** The supported surface is exactly: `install.sh
  [--agent]`, `mm init`, `mm connect [--agent]`, `mm doctor`, `mm remember`,
  `mm recall`, `mm ingest`, `mm open`, `mm index`, `mm reindex`, `mm forget`,
  `mm status`, `mm serve`.

## Success criteria

```
mm doctor              -> RESULT: ready
mm connect --agent     -> CONNECT_RESULT: desktop=yes claude_code=yes vault=...
```

Claude Code verification, if you wired it: `claude mcp list` shows
`marina-memory` with **Status: ✔ Connected** and **Scope: User config** (not
`local`, which would bind it to one folder only).

## If you are Claude Cowork or Claude Code and want the design rationale

Read `README.md`. Short version: Markdown files are the source of truth, a SQLite
FTS5 index is disposable and rebuildable with `mm reindex`, a small generated
`index.md` is the only thing meant to sit in context, and documents are converted
once to Markdown then read back by section. Retrieval is lexical by design, to
keep storing a fact free of any token cost.
