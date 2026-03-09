# Claude Code Guardrails

> Two lightweight hooks that save tokens by blocking duplicate file reads and retry loops in Claude Code sessions.

Works globally across **all your projects and VS Code windows** with a single install.

---

## Why This Exists

Claude Code can develop expensive habits mid-session:

| Problem | What happens | Token cost |
|---|---|---|
| **Duplicate reads** | Claude re-reads the same file 4-5 times | 500-3000 wasted tokens per duplicate |
| **Retry loops** | Claude repeats the same failing call over and over | 200-2000 wasted tokens per loop |

Guardrails intercepts these patterns in real-time, blocks the wasteful action, and tells Claude to use what it already has.

---

## Quick Install

```bash
git clone https://github.com/mijevski-aleksandar/claude-guardrails.git
cd claude-guardrails
bash install.sh
```

That's it. Hooks are installed globally to `~/.claude/` and apply to every Claude Code session.

---

## What Gets Installed

```
~/.claude/
├── settings.json          ← registers hooks globally
├── clear-logs.sh          ← run between sessions to reset counters
└── hooks/
    ├── duplicate_reads.py
    └── retry_loop.py
```

---

## Hooks

### `duplicate_reads.py`
**Fires:** `PreToolUse` on Read calls
**Blocks:** The 3rd+ read of the same file in a session
**Says to Claude:** *"You've already read this file. Use what you have."*

Typical savings: **500-3000 tokens per blocked read** (depends on file size).

**Config:** Edit `MAX_READS` in the script (default: 2)

---

### `retry_loop.py`
**Fires:** `PreToolUse` on any tool call
**Blocks:** The 3rd+ identical tool call (same tool, same inputs)
**Says to Claude:** *"This is a retry loop. Stop and propose a different approach."*

Typical savings: **200-2000 tokens per blocked loop** (tool call + response + reasoning).

**Config:** Edit `MAX_IDENTICAL` in the script (default: 2)

---

## Usage

**Before each new session** — reset counters:
```bash
~/.claude/clear-logs.sh
```

Or add this alias so logs clear automatically:
```bash
# ~/.bashrc or ~/.zshrc
alias claude='~/.claude/clear-logs.sh && claude'
```

---

## Token Savings Estimate

| Metric | Value |
|---|---|
| Hook overhead per tool call | ~40-60 tokens (2 lightweight JSON checks) |
| Savings per blocked duplicate read | 500-3000 tokens |
| Savings per blocked retry loop | 200-2000 tokens |
| **Net savings per session** | **1,000-13,000 tokens** |

The hooks have asymmetric payoff: tiny cost on every call, large savings when they trigger.

---

## How Hooks Work

Claude Code exposes lifecycle events. Guardrails uses `PreToolUse` — it fires before any tool runs. Exit code `2` + stderr message = the tool call is blocked and the message is sent directly to Claude as feedback.

---

## Customising

Each hook has config variables at the top:

```python
# duplicate_reads.py
MAX_READS = 2  # change to 3 for more lenient behaviour

# retry_loop.py
MAX_IDENTICAL = 2  # change to 3 to allow more retries
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
