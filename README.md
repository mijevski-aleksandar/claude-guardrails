# Claude Code Guardrails

> Lightweight hooks that save tokens and maintain output quality in Claude Code sessions — by managing context pressure, blocking duplicate reads, preventing retry loops, and detecting tool failures.

Works globally across **all your projects and VS Code windows** with a single install.

---

## Why This Exists

Claude Code can develop expensive habits mid-session:

| Problem | What happens | Token cost |
|---|---|---|
| **Duplicate reads** | Claude re-reads the same unchanged file 4-5 times | 500-3000 wasted tokens per duplicate |
| **Retry loops** | Claude repeats the same failing call over and over | 200-2000 wasted tokens per loop |
| **Context drift** | Long sessions degrade — Claude forgets what it was doing | 5-30K wasted on re-exploration |
| **Blind retries** | Tool failures aren't diagnosed before retrying | 1-5K wasted per failed retry |

Guardrails intercepts these patterns in real-time, warns or blocks the wasteful action, and tells Claude to adjust.

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
    ├── duplicate_reads.py    (PreToolUse)
    ├── retry_loop.py         (PreToolUse)
    ├── context_pressure.py   (PreToolUse)
    ├── auto_compact.py       (PreToolUse)
    ├── failed_tools.py       (PostToolUse)
    ├── compaction_reset.py   (PreCompact)
    └── post_compact.py       (PostCompact)
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

### `context_pressure.py`
**Fires:** `PreToolUse` on every tool call
**Warns:** At step 30 — encourages concise behavior
**Critical warning:** At step 50 — suggests wrapping up or splitting sessions

This hook tracks step count (shared with `auto_compact.py`) and applies increasing pressure to keep sessions focused. Both thresholds are warn-only — Claude is never hard-blocked.

**Config:** Edit `WARN_AT` (default: 30) and `STOP_AT` (default: 50) in the script

---

### `auto_compact.py`
**Fires:** `PreToolUse` on every tool call
**Suggests:** `/compact` every 25 steps since last compaction

Proactive compaction recovers ~16% more context window compared to waiting for Claude Code's built-in autocompact (which triggers reactively at ~95% capacity).

**Config:** Edit `COMPACT_AT` (default: 25) in the script

---

### `failed_tools.py`
**Fires:** `PostToolUse` on every tool call
**On any failure:** Warns Claude to diagnose before retrying
**After 3 failures:** Escalates — forces Claude to list failures and ask for help

Detects failure signals in tool responses (error, failed, permission denied, not found, traceback, exception) and prevents blind retry loops.

**Config:** Edit `MAX_FAILURES` (default: 3) in the script

---

### `compaction_reset.py`
**Fires:** `PreCompact` (before context compaction)
**Action:** Resets all guardrail counters

After compaction, Claude loses the context it previously built. This hook resets all counters (read tracking, retry tracking, step count, compact log, failure count) so Claude can re-read files and start fresh without hitting stale guardrail limits.

---

### `post_compact.py`
**Fires:** `PostCompact` (after context compaction)
**Action:** Reminds Claude to re-read active plan files and task lists

After compaction, Claude often "forgets" what it was working on. This hook injects a message pointing to the most recently modified plan file, helping Claude restore context without re-exploring the codebase.

---

## Design Principles

1. **Never degrade output** — if there's any legitimate reason to re-read (file changed, context compacted), allow it
2. **Warn before blocking** — give Claude a chance to self-correct before hard-blocking
3. **Zero maintenance** — state auto-resets per session, no scripts to run
4. **Minimal overhead** — ~40-60 tokens per tool call for the JSON state checks
5. **Counters reset on compaction** — post-compaction is a fresh start

---

## How Hooks Work

Claude Code exposes lifecycle events. Guardrails uses:
- **`PreToolUse`** — fires before any tool runs. Exit `2` + stderr = blocked with feedback to Claude. Exit `0` + stderr = warning only.
- **`PostToolUse`** — fires after any tool runs. Used to detect failures in tool responses.
- **`PreCompact`** — fires before context compaction. Used to reset counters.
- **`PostCompact`** — fires after context compaction. Used to inject context reminders.

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

# context_pressure.py
WARN_AT = 30    # warn to be concise
STOP_AT = 50    # critical warning

# auto_compact.py
COMPACT_AT = 25   # suggest /compact every N steps

# failed_tools.py
MAX_FAILURES = 3  # escalate after this many failures
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
