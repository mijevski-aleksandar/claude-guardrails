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
    ├── failed_tools.py       (PostToolUse)
    ├── compaction_reset.py   (PreCompact)
    ├── session_summary.py    (PreCompact)
    └── post_compact.py       (PostCompact)
```

---

## Hooks

### `duplicate_reads.py`
**Fires:** `PreToolUse` on Read calls
**Warns:** On 2nd+ read of the same unchanged file (non-blocking, never blocks)

Smart behaviors:
- **File change detection** — if the file was modified on disk since the last read, the counter resets and the read is allowed
- **Auto-reset per session** — no manual cleanup between sessions
- **Warn, never block** — 2nd+ read gets a suggestion to use Grep or offset/limit instead. Reads are never blocked because Claude's memory degrades after compaction — re-reading is always safer than guessing

**Config:** Edit `WARN_AT` (default: 2) in the script

---

### `retry_loop.py`
**Fires:** `PreToolUse` on tool calls (except Read/Grep/Glob which are handled separately)
**Warns:** On 2nd identical call (non-blocking)
**Blocks:** 3rd+ identical tool call

Smart behaviors:
- **Bash normalization** — ignores the `description` field so retrying the same command with a different description is still caught
- **ExitPlanMode count-based tracking** — tracks by invocation count (not content fingerprint) so editing the plan between attempts doesn't evade detection. Warns on 2nd call, blocks on 3rd
- **Skips safe tools** — Read, Grep, Glob are idempotent searches and handled by `duplicate_reads`
- **Auto-reset per session** — no manual cleanup between sessions

**Config:** Edit `MAX_IDENTICAL` (default: 3) and `WARN_AT` (default: 2) for general tools; `EPM_MAX` (default: 3) and `EPM_WARN` (default: 2) for ExitPlanMode

---

### `context_pressure.py`
**Fires:** `PreToolUse` on every tool call
**Warns:** At step 50 — encourages concise behavior
**Critical warning:** At step 80 — suggests wrapping up or splitting sessions

This hook tracks step count per session and applies increasing pressure to keep sessions focused. Both thresholds are warn-only — Claude is never hard-blocked. Counters auto-reset when the session changes.

**Config:** Edit `WARN_AT` (default: 50) and `STOP_AT` (default: 80) in the script

---

### `failed_tools.py`
**Fires:** `PostToolUse` on every tool call
**On any failure:** Warns Claude to diagnose before retrying
**After 3 failures:** Escalates — forces Claude to list failures and ask for help

Detects actual failures using structured signals (`is_error` field, non-zero exit codes, `Error:` prefixes) — not keyword matching, which caused false positives in earlier versions. Failure counts auto-reset when the session changes.

**Config:** Edit `MAX_FAILURES` (default: 3) in the script

---

### `session_summary.py`
**Fires:** `PreCompact` (before context compaction)
**Action:** Prompts Claude to write a structured handoff summary

Before compaction clears context, this hook asks Claude to write a human-readable summary to `~/.claude/last-session.md` and append it to `~/.claude/session-history.md`. The summary captures what was worked on, what's complete, what's incomplete, and how to continue — enabling seamless cross-session continuity.

Fires on PreCompact (not Stop) because VSCode extension sessions don't reliably emit Stop events. Uses a session-scoped flag to avoid re-triggering on subsequent compactions.

**Config:** Edit `MIN_STEPS` (default: 5) to control the minimum session length for summaries

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
WARN_AT = 2     # warn (non-blocking) at this count — never blocks

# retry_loop.py
MAX_IDENTICAL = 3   # block after this many identical calls
WARN_AT = 2         # warn at this count
EPM_MAX = 3         # block ExitPlanMode after this many calls
EPM_WARN = 2        # warn ExitPlanMode at this count

# context_pressure.py
WARN_AT = 50    # warn to be concise
STOP_AT = 80    # critical warning

# failed_tools.py
MAX_FAILURES = 3  # escalate after this many failures

# session_summary.py
MIN_STEPS = 5   # skip summary for trivial sessions
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
