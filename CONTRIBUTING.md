# Contributing to Claude Code Guardrails

Thanks for your interest in contributing! This project is intentionally simple — plain Python scripts that hook into Claude Code's lifecycle. Here's how to add your own hook.

## Adding a New Hook

### 1. Create your hook script in `hooks/`

Every hook receives a JSON payload via stdin and must exit with:
- `0` — allow the action to proceed
- `2` — block the action and send your `stderr` message to Claude

```python
#!/usr/bin/env python3
import json, sys

data = json.load(sys.stdin)

tool_name = data.get("tool_name", "")
tool_input = data.get("tool_input", {})

# your logic here

sys.exit(0)  # allow
# or
sys.stderr.write("Your message to Claude explaining why this was blocked.")
sys.exit(2)  # block
```

### 2. Register it in `config/settings.json`

Add it under the appropriate event:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": ".*",
        "hooks": [
          { "type": "command", "command": "python3 ~/.claude/hooks/your_hook.py" }
        ]
      }
    ]
  }
}
```

### Hook Events

| Event | When it fires | Can block? |
|---|---|---|
| `PreToolUse` | Before any tool runs | ✅ Yes (exit 2) |
| `PostToolUse` | After tool completes | ✅ Yes (exit 2) |
| `UserPromptSubmit` | When user sends a prompt | ✅ Yes (exit 2) |
| `Stop` | When Claude finishes responding | ✅ Yes (exit 2) |

### Stdin Payload Shape

**PreToolUse:**
```json
{
  "tool_name": "Read",
  "tool_input": { "file_path": "/path/to/file" }
}
```

**PostToolUse:**
```json
{
  "tool_name": "Bash",
  "tool_input": { "command": "python manage.py migrate" },
  "tool_response": { "output": "...", "error": "..." }
}
```

## Hook Ideas Welcome

Some hooks the community could build:
- **Large file warning** — warn before reading files over N lines
- **Secret scanner** — block writes if content contains API keys or passwords
- **Test enforcer** — require tests to pass before allowing commits
- **Scope creep detector** — warn if Claude starts touching files unrelated to the original task
- **Budget tracker** — estimate token cost per step and warn when a session crosses a spend threshold

Open a PR or issue to share your idea!

## Guidelines

- Keep hooks focused — one concern per file
- Use `/tmp/claude_yourname_*.json` for any session state files
- Always handle `FileNotFoundError` and `json.JSONDecodeError` when reading log files
- Write clear, actionable messages to stderr — Claude reads them and acts on them
- Add a docstring at the top of every hook explaining what it does and what config options exist
