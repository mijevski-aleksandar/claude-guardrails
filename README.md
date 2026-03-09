# 🛡️ Claude Code Guardrails

> A set of intelligent hooks that make Claude Code self-correcting — stopping retry loops, preventing duplicate reads, managing context pressure, and recovering from failures automatically.

Works globally across **all your projects and VS Code windows** with a single install.

---

## Why This Exists

Claude Code is powerful but can develop expensive habits mid-session:

| Problem | What happens | Cost |
|---|---|---|
| **Duplicate reads** | Claude re-reads the same file 4–5 times | Wasted input tokens |
| **Retry loops** | Claude repeats the same failing call over and over | Spiralling token spend |
| **Context pressure** | Session runs too long, context degrades silently | Hallucinations, lost state |
| **Failed tools** | Claude keeps trying variations of a broken call | Time + token waste |

Guardrails intercepts these patterns in real-time, blocks the bad action, and sends Claude a clear explanation of what went wrong and what to do instead.

---

## Quick Install

```bash
git clone https://github.com/mijevski-aleksandar/claude-guardrails.git
cd claude-code-guardrails
bash install.sh
```

That's it. Hooks are installed globally to `~/.claude/` and apply to every Claude Code session on your machine — no per-project setup needed.

---

## What Gets Installed

```
~/.claude/
├── settings.json          ← registers all hooks globally
├── clear-logs.sh          ← run between sessions to reset counters
└── hooks/
    ├── duplicate_reads.py
    ├── retry_loop.py
    ├── context_pressure.py
    └── failed_tools.py
```

---

## Hooks

### 🔁 `duplicate_reads.py`
**Fires:** `PreToolUse` → Read  
**Blocks:** The 3rd+ read of the same file in a session  
**Says to Claude:** *"You've already read this file. Use what you have. If you need something specific, ask."*

**Config:** Edit `MAX_READS` in the script (default: 2)

---

### ♾️ `retry_loop.py`
**Fires:** `PreToolUse` → any tool  
**Blocks:** The 3rd+ identical tool call (same tool, same inputs)  
**Says to Claude:** *"This is a retry loop. Stop, explain why it's failing, and propose a different approach."*

**Config:** Edit `MAX_IDENTICAL` in the script (default: 2)

---

### 🗜️ `auto_compact.py`
**Fires:** `PreToolUse` → any tool  
**Blocks:** The next tool call when `COMPACT_AT` steps have passed since the last compaction  
**Says to Claude:** *"Run /compact now before continuing. Context needs to be compressed."*

Works alongside `"autoCompact": false` in settings.json — you take back manual control of compaction so it happens at the right moment, not reactively when the window is already full. Recovers ~16% more context window than letting Claude Code manage it automatically.

**Config:** Edit `COMPACT_AT` in the script (default: 25 steps between compactions)

---

### 📈 `context_pressure.py`
**Fires:** `PreToolUse` → any tool  
**Warns at:** 30 steps (non-blocking)  
**Blocks at:** 50 steps  
**Says to Claude:** *"Session is critically long. Summarise what you've done, list what's incomplete, and tell the user to start a new session."*

**Config:** Edit `WARN_AT` and `STOP_AT` in the script (defaults: 30, 50)

---

### ❌ `failed_tools.py`
**Fires:** `PostToolUse` → any tool  
**Blocks:** After 3 total tool failures in a session  
**Says to Claude:** *"Multiple tools have failed. List each failure, identify the root cause, and fix that before retrying."*

**Config:** Edit `MAX_FAILURES` and `FAILURE_KEYWORDS` in the script

---

### 📝 `session_summary.py`
**Fires:** `Stop` event (when Claude finishes responding)  
**Blocks:** Session from closing until Claude writes a structured handoff summary  
**Writes to:** `~/.claude/last-session.md` (latest) and `~/.claude/session-history.md` (append log)

The summary includes: what was worked on, what was completed, what's incomplete, key files changed, decisions made, and exact instructions for resuming. Skips sessions under 5 steps.

**Config:** Edit `MIN_STEPS` in the script (default: 5) and `COMPACT_AT` thresholds

---

## Session Workflow

**Before starting a new session** — reset all counters:
```bash
~/.claude/clear-logs.sh
```

**Resume a previous session** — paste the handoff summary:
```bash
cat ~/.claude/last-session.md
# Copy the output and paste it at the start of your new Claude Code session
```

**Browse session history:**
```bash
cat ~/.claude/session-history.md
```

Or add this alias so logs clear automatically every time you start Claude:
```bash
# ~/.bashrc or ~/.zshrc
alias claude='~/.claude/clear-logs.sh && claude'
```

---

## How Hooks Work

Claude Code exposes lifecycle events at key points in every session. Guardrails taps into two of them:

- **`PreToolUse`** — fires before any tool runs. Exit `2` + write to stderr = tool is blocked and your message is sent to Claude.
- **`PostToolUse`** — fires after a tool completes. Same blocking mechanism.

Claude receives the stderr message as direct feedback and adjusts its behaviour accordingly. It's not just a log — Claude actually reads and acts on it.

---

## Customising

Each hook is a standalone Python script with config variables at the top. Edit thresholds directly:

```python
# duplicate_reads.py
MAX_READS = 2  # change to 3 if you want more lenient behaviour

# context_pressure.py
WARN_AT = 30
STOP_AT = 50  # increase for longer sessions
```

No restart needed — hooks are loaded fresh at each tool call.

---

## Adding Your Own Hook

See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for a full guide and hook template.

Some ideas:
- **Secret scanner** — block file writes if content contains API keys
- **Large file warning** — warn before reading files over 500 lines
- **Test enforcer** — require tests to pass before allowing git commits
- **Scope creep detector** — warn if Claude edits files unrelated to the original task

---

## Uninstall

```bash
bash uninstall.sh
```

Removes all hooks and restores your original `settings.json` from backup.

---

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed
- Python 3 (already on macOS/Linux by default)

---

## License

MIT — do whatever you want with it.

---

*Inspired by sessions gone wrong. Built to make sure they don't happen again.*
