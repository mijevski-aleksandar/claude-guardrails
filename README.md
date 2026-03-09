# Claude Code Guardrails

> Lightweight hooks that save tokens by blocking duplicate file reads and retry loops in Claude Code sessions — without degrading output quality.

Works globally across **all your projects and VS Code windows** with a single install.

---

## Why This Exists

Claude Code can develop expensive habits mid-session:

| Problem | What happens | Token cost |
|---|---|---|
| **Duplicate reads** | Claude re-reads the same unchanged file 4-5 times | 500-3000 wasted tokens per duplicate |
| **Retry loops** | Claude repeats the same failing call over and over | 200-2000 wasted tokens per loop |

Guardrails intercepts these patterns in real-time, blocks the wasteful action, and tells Claude to use what it already has.

---

## Quick Install

```bash
git clone https://github.com/mijevski-aleksandar/claude-guardrails.git
cd claude-guardrails
bash install.sh
```

That's it. No manual cleanup needed between sessions — state auto-resets.

---

## What Gets Installed

```
~/.claude/
├── settings.json          ← registers hooks globally
└── hooks/
    ├── duplicate_reads.py
    ├── retry_loop.py
    └── compaction_reset.py
```

---

## Hooks

### `duplicate_reads.py`
**Fires:** `PreToolUse` on Read calls
**Warns:** On 2nd read of the same file (non-blocking)
**Blocks:** 3rd+ read of the same unchanged file

Smart behaviors:
- **File change detection** — if the file was modified on disk since the last read, the counter resets and the read is allowed
- **Auto-reset per session** — no manual cleanup between sessions
- **Warn before block** — 2nd read gets a suggestion to use Grep instead, 3rd read is blocked

**Config:** Edit `MAX_READS` (default: 3) and `WARN_AT` (default: 2) in the script

---

### `retry_loop.py`
**Fires:** `PreToolUse` on tool calls (except Read/Grep/Glob which are handled separately)
**Warns:** On 2nd identical call (non-blocking)
**Blocks:** 3rd+ identical tool call

Smart behaviors:
- **Bash normalization** — ignores the `description` field so retrying the same command with a different description is still caught
- **Skips safe tools** — Read, Grep, Glob are idempotent searches and handled by `duplicate_reads`
- **Auto-reset per session** — no manual cleanup between sessions

**Config:** Edit `MAX_IDENTICAL` (default: 3) and `WARN_AT` (default: 2) in the script

---

### `compaction_reset.py`
**Fires:** `PreCompact` (before context compaction)
**Action:** Resets all read and retry counters

After compaction, Claude loses the file content it previously read. Blocking re-reads at that point would degrade output quality. This hook ensures counters reset so Claude can re-read files it needs.

---

## Design Principles

1. **Never degrade output** — if there's any legitimate reason to re-read (file changed, context compacted), allow it
2. **Warn before blocking** — give Claude a chance to self-correct before hard-blocking
3. **Zero maintenance** — state auto-resets per session, no scripts to run
4. **Minimal overhead** — ~40-60 tokens per tool call for the JSON state checks

---

## How Hooks Work

Claude Code exposes lifecycle events. Guardrails uses:
- **`PreToolUse`** — fires before any tool runs. Exit `2` + stderr = blocked with feedback to Claude. Exit `0` + stderr = warning only.
- **`PreCompact`** — fires before context compaction. Used to reset counters.

Claude receives stderr messages as direct feedback and adjusts its behavior.

---

## Customising

Each hook has config variables at the top:

```python
# duplicate_reads.py
MAX_READS = 3   # block after this many reads of unchanged file
WARN_AT = 2     # warn (non-blocking) at this count

# retry_loop.py
MAX_IDENTICAL = 3   # block after this many identical calls
WARN_AT = 2         # warn at this count
```

No restart needed — hooks are loaded fresh on each tool call.

---

## Uninstall

```bash
bash uninstall.sh
```

Removes hooks and restores your original `settings.json` from backup.

---

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed
- Python 3

---

## License

MIT
