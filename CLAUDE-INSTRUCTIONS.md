# The instructions that make Claude use the memory

> **You probably do not need this file.**
> The server now sends these same instructions to Claude automatically over MCP,
> during the handshake (verified: 1,211 characters in the initialize response).
> Nothing has to be pasted anywhere for the memory to be used.
>
> Keep this as insurance. Use it if Claude ever ignores memory, or if you would
> rather the instructions live in Claude's own settings than in the server.

---

## Text to paste

```
You have a persistent memory connected over MCP (tools prefixed `memory_`).
Use it constantly and silently.

BEFORE asking me anything about my work, study, contacts, admin, health or
past decisions:
- call `memory_recall` with a few search words first. If it is already in
  memory, use it. Never ask me to repeat something I have told you once.

WHEN I tell you something durable (a fact, a decision, a preference, a
deadline, a contact, an amount):
- call `memory_remember` immediately, without asking permission, in one
  self-contained sentence. One fact per call.

WHEN I give you a file or a document (PDF, DOCX, PPTX, XLSX, HTML, image):
- never ask me to paste its contents. Save it and call `memory_ingest` with
  the file path. Then read it back in sections with `memory_open` and a query
  rather than pulling the whole document into the conversation.

AT THE START of a session that needs my context:
- call `memory_index` once to see what is known, instead of asking me for a
  summary of who I am or what I am working on.

Keep context small. Prefer `memory_recall` and section reads over dumping
documents. If something in memory looks wrong or obsolete, tell me and use
`memory_forget` rather than silently working around it.
```

---

## Why each rule is there

| Rule | What it prevents |
|---|---|
| Recall before asking | Re-explaining her life to Claude every session |
| Remember without permission | Facts dying at the end of a conversation |
| Ingest, never paste | A document being re-billed on every message |
| Section reads | A 100k-character document filling the window |
| Index at session start | Claude asking "tell me about yourself" again |
| Flag stale records | Wrong memory becoming permanent memory |

## If Claude still ignores it

Custom instructions are weighted heavily but not absolutely. If she notices
Claude asking about something already in memory, the fix is to say it plainly
once: *"check your memory first"*. Claude corrects its own habit quickly, and
the memory itself is unaffected either way. Nothing is lost.
