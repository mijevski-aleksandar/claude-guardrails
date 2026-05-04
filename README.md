# Claude Code Guardrails

> Lightweight hooks that save tokens and maintain output quality in Claude Code sessions — by managing context pressure, blocking duplicate reads, preventing retry loops, and detecting tool failures.

Works globally across **all your projects and VS Code windows** with a single install.

---

## Why This Exists

Claude Code can develop expensive habits mid-session:

| Problem | What happens | Token cost |
|---|---|---|
| **Duplicate reads** | Claude re-reads the same bytes of an unchanged file 4-5 times (often by varying `offset/limit` to evade naive guards) | 500-3000 wasted tokens per duplicate |
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
**Warns:** On 2nd read of an overlapping byte range in an unchanged file
**Blocks:** On 3rd read of an overlapping byte range in an unchanged file (exit 2)

Smart behaviors:
- **Byte-range tracking** — state is keyed on `file_path` only, but each read records the line range it covers (`[offset, offset+limit)`, or `[1, EOF)` for full reads). Subsequent reads only count as "duplicate" if they overlap a prior range. This closes the `offset/limit` evasion where the same file could be read 5+ times under different keys.
- **Non-overlapping reads always allowed** — legitimate paginated reads (lines 1-40 then 80-120 then 150-190) never trigger a warning or block.
- **File change detection (mtime safety)** — if `os.path.getmtime` shows the file was modified since the last read, all tracking for that file is reset and the read is allowed. Edits, editor saves, and external changes never trigger a false block.
- **Auto-reset per session** — no manual cleanup between sessions.
- **Block message tells Claude what to do** — work from prior memory of the file, use Grep for a targeted lookup, or read a *different* byte range. Output quality is preserved because Claude has alternatives.

**Why block now (it used to only warn):** The warn-only version never reduced re-read volume in practice — Claude rationalised the warning and re-read anyway, often via `offset/limit` variants. Blocking on the 3rd overlapping read forces a real change in approach. The mtime safety net guarantees no legitimate re-read of changed content is ever blocked.

**Config:** Edit `WARN_AT` (default: 2) and `BLOCK_AT` (default: 3) in the script

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
**Fires:** `PreCompact` (after `pre_compact.py` has written `claude_handoff.json`)
**Action:** Renders the handoff JSON as markdown into `~/.claude/last-session.md` and appends to `~/.claude/session-history.md`. **Zero LLM cost** — pure Python.

The previous version of this hook wrote a stderr message asking Claude to write the summary itself. That never worked: PreCompact fires immediately before context wipe, so Claude has no turn to act on the message. The current version writes the file directly from the JSON that `pre_compact.py` already collects (active plan, files modified, last tool calls, last bash, key findings, do-not-reread list).

Hook order in `settings.json` matters: `pre_compact.py` → `compaction_reset.py` → `session_summary.py`. When `session_summary.py` fires, the handoff JSON is fresh.

Uses a per-session flag (`/tmp/claude_summary_<session_id>.flag`) to avoid re-triggering on subsequent compactions in the same session.

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

1. **Never degrade output** — every block has a legitimate-reason escape hatch. File changed on disk (mtime bumped), context compacted (counters reset), or a different byte range is requested? Allowed. The block only fires when the *same* unchanged content is being read for a 3rd time.
2. **Warn before blocking** — give Claude a chance to self-correct before hard-blocking
3. **Block messages always say what to do instead** — "use Grep, read a different range, work from prior memory." Claude needs alternatives, not just denial.
4. **Zero maintenance** — state auto-resets per session, no scripts to run
5. **Minimal overhead** — ~40-60 tokens per tool call for the JSON state checks
6. **Counters reset on compaction** — post-compaction is a fresh start

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
WARN_AT  = 2    # warn at this many overlapping reads of unchanged file
BLOCK_AT = 3    # block (exit 2) at this many overlapping reads of unchanged file

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
