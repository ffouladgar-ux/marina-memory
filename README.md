# marina-memory

Local-first memory for Claude, over MCP. Her notes live as plain Markdown files
on her own machine; Claude reads and writes them through a small MCP server.

Built for one person, not a market: it runs locally, costs nothing to run, and
makes no network calls. Nothing is uploaded anywhere.

## Why it lowers burn rate

Four mechanisms, all deliberate:

1. **Two tiers.** The only thing designed to sit in context is `index.md`, a
   pointer list capped at ~900 tokens. Everything else is cold Markdown, read
   on demand, in sections.
2. **Documents become Markdown once.** A PDF/DOCX/PPTX is converted locally
   (~90-95% smaller) and stored. It is never re-pasted into the chat, so it is
   never re-billed.
3. **Reads are sectional.** `memory_open(slug, query)` returns only the sections
   that match, not the whole file.
4. **No embeddings, no LLM calls.** Search is SQLite FTS5, locally. Storing a
   fact costs zero tokens, so memory can accumulate as much as she likes.

## Install: double-click (no typing)

**Windows**

1. Get the folder: GitHub page → green **Code** button → **Download ZIP**, then
   unzip it. (Or Fadi sends you the folder.)
2. Double-click **`Install Marina Memory.bat`**.
3. Wait 2 to 5 minutes. The window shows progress and stays open at the end.
4. Quit Claude completely: right-click the Claude icon next to the clock
   (system tray) and choose **Quit**. Closing the window is not enough, it will
   not reload. Reopen it, and the memory is on.
   (Nothing to paste: the server installs its own instructions into Claude
   during the handshake. `CLAUDE-INSTRUCTIONS.md` is optional insurance.)

Nothing needs installing first. If `uv` is missing the installer fetches it,
and `uv` fetches Python itself. On a work or school PC where PowerShell is
blocked, the installer prints the one command to run manually instead of dying.

**macOS**

Same, using `Install Marina Memory.command`, but **right-click → Open** the
first time (macOS asks you to confirm a downloaded script), and quit Claude with
**Cmd+Q**.

### Verification status of the installers

Honest state, so nobody is surprised:

- **macOS: verified end to end** on a simulated fresh Mac (empty home, no `uv`,
  no Python, `PATH` restricted to system binaries). It bootstrapped, installed,
  created the vault, wired Claude, and finished with `mm doctor` reporting
  ready.
- **Windows: not yet executed on a real Windows machine from our side.** It is
  guarded by `python scripts/check_installers.py` (CRLF line endings, correct
  steps, manual fallback present) and the Windows config path plus
  `%APPDATA%` writing are covered by unit tests, but that is not the same as
  running it on Windows. Report anything that fails and it gets fixed.

## Install: by hand (5 minutes)

```bash
# 1. Get the folder
git clone https://github.com/ffouladgar-ux/marina-memory.git
cd marina-memory

# 2. Everything at once (installer, vault, Claude wiring, verification)
./install.sh

# 3. Quit Claude Desktop completely (Cmd+Q) and reopen it.
#    Ask Claude: "read my memory index"
```

Verify any time with `mm doctor`.

### Using Claude Code instead of Claude Desktop

```bash
claude mcp add marina-memory --env MEMORY_KIT_VAULT="$HOME/MemoryVault" \
  -- python3 -m memory_kit serve
```

`mm connect-claude` prints the exact command with the right interpreter path.

## The three rules for her

Everything Claude does well here comes from these:

1. **Never paste a document.** Save the file, then say
   *"ingest ~/Downloads/chapter3.pdf"*. Claude converts it to Markdown, stores
   it once, and reads it in sections afterwards.
2. **Never re-explain.** If she has told Claude something once, it calls
   `memory_recall` before asking again. If it does ask twice, say so — that is
   a bug in the habit, not in her.
3. **Let it file itself.** Compartments are chosen automatically
   (`business`, `studies`, `people`, `personal`, `health`, and `inbox` when it
   is unsure). Nothing is ever dropped: anything unclear lands in `inbox` for
   her to refile with one sentence.

## What she gets

| Compartment | Typical content |
|---|---|
| `studies` | journalism school: courses, deadlines, readings, mémoire/thesis, exams |
| `business` | clients, invoices, quotes, rates, pitches |
| `people` | who's who, contacts, birthdays, introductions |
| `personal` | home, admin, travel, insurance, bank |
| `health` | appointments, symptoms, medication, sleep, focus |
| `inbox` | everything Claude could not confidently file |
| `sources` | ingested documents |

## Layout on disk

```
~/MemoryVault/
├── index.md            hot tier (auto-generated, ~900 tokens)
├── studies/2026-09.md  cold tier — append-only Markdown
├── business/2026-09.md
├── inbox/2026-09.md
├── sources/chapter3.md  ingested documents, as Markdown
├── _archive/            anything "forgotten" — kept, never destroyed
└── .index/store.db      disposable search index (rebuild: mm reindex)
```

**The Markdown files are the memory.** The database is a cache. Delete it
whenever you like; `mm reindex` rebuilds it from the files. Her notes stay
readable in any text editor, and open natively in Obsidian.

## Command reference

```bash
mm init                    # create the vault
mm remember "..."          # store a fact  (-c business -t invoice)
mm recall "query"          # search       (no query = print hot index)
mm ingest FILE...          # convert + store documents
mm open SLUG -q "question" # read a document, matched sections only
mm index                   # regenerate index.md (--print to see it)
mm reindex                 # rebuild the DB from the Markdown files
mm forget ID               # archive a record
mm status                  # counts, compartments, hot-index cost, path
mm connect-claude          # wire into Claude Desktop
mm doctor                  # verify everything
```

## Privacy

This matters for a journalist, so it is stated plainly:

- The **code** is public; your **memory is not**. Nothing in the repository
  contains or touches your notes.
- No network calls at runtime. Conversion and search are local.
- No API keys, no accounts, no telemetry, no analytics.
- Your data never leaves your machine unless you put the vault in a git repo
  yourself.
- Optional: commit `~/MemoryVault` to a **private** git repo for versioned
  backup. `.index/` is gitignored; the Markdown is the history.

## Upgrade path: phone and claude.ai web (only if she needs it)

Claude Desktop and Claude Code run the server **on her machine** over stdio.
That covers laptop use and keeps everything local.

If she later wants the same memory from the Claude mobile app or claude.ai in a
browser, custom connectors are fetched from Anthropic's cloud, so the server
needs a public HTTPS endpoint. The same code already supports it:

```bash
mm serve --http --port 8765          # streamable-http on http://127.0.0.1:8765/mcp
```

Put that behind an authenticated tunnel or a small VPS and register the URL as a
custom connector in Claude. Nothing else changes: same vault, same tools, same
Markdown files. Verified by `scripts/e2e_http.py`.

Do this only when she actually needs it. It moves her data from "on her disk" to
"reachable from the internet", which is a real decision for a journalist, not a
default.

## Verifying it works

```bash
python -m pytest tests/ -q              # 30 tests: routing, storage, ingest, budget, MCP, Windows paths
python scripts/e2e_mcp.py               # real stdio handshake + tool calls (9 checks)
python scripts/e2e_http.py 8791         # real streamable-http handshake (upgrade path)
python scripts/check_installers.py      # installer guards (CRLF, steps, fallbacks)
```

## Limits (honest)

- Retrieval is lexical (FTS5 keyword/prefix matching), not semantic. It is very
  good at proper nouns, dates, project names and exact terms; it will not infer
  that "burnout" relates to a note that only says "exhausted". Claude
  paraphrases queries well enough to compensate in practice.
- Scanned/image-only PDFs and audio need extras:
  `pip install 'marina-memory[extras]'`.
- Compartment routing is lexicon-based (EN + FR). Mis-files go to `inbox`,
  never into the void.
