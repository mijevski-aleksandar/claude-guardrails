# Contributing to Claude Code Guardrails

Thanks for your interest in contributing! This project is intentionally simple — plain Python scripts that hook into Claude Code's lifecycle. Here's how to add your own hook.

## Adding a New Hook

Each feature is a self-contained module under `modules/<name>/`:

```
modules/your-hook/
├── hook.py                    # the script
├── module.json                # what gets symlinked where
└── settings.fragment.json     # the slice of settings.json to merge
```

### 1. Create `modules/<name>/hook.py`

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

If the hook needs state, import the shared per-session helper instead of using a global file (see `modules/retry-loop/hook.py` for the import pattern; use `os.path.realpath(__file__)`, not `abspath`, because the installed file is a symlink):

```python
from state_paths import get_state_path
STATE = get_state_path("your_hook", data.get("session_id", ""))
```

### 2. Describe it in `module.json` and `settings.fragment.json`

`module.json`:

```json
{
  "name": "your-hook",
  "description": "One line on what it does",
  "type": "hook",
  "hook_events": ["PreToolUse"],
  "install": { "hook.py": "~/.claude/hooks/your_hook.py" },
  "requires_shared": true
}
```

`settings.fragment.json` (merged into `~/.claude/settings.json` on install, removed on uninstall):

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
- Keep state per session via `shared/state_paths.py`; never a single global file (concurrent sessions would overwrite each other)
- Test `bash install.sh --install your-hook` and `bash uninstall.sh --uninstall your-hook` against a scratch `HOME` before opening a PR
- Always handle `FileNotFoundError` and `json.JSONDecodeError` when reading log files
- Write clear, actionable messages to stderr — Claude reads them and acts on them
- Add a docstring at the top of every hook explaining what it does and what config options exist
