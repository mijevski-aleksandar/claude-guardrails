#!/usr/bin/env python3
"""
Hook: retry_loop.py
Fires: PreToolUse on any tool call
Purpose: Detect and stop retry loops — both exact and near-identical tool calls.

Smart behaviors:
  - Auto-resets when session changes (no manual clear-logs.sh needed)
  - Detects exact duplicates (same tool + same inputs)
  - Detects near-duplicates for Bash calls (same command, different description)
  - Warns on 2nd identical call (non-blocking), blocks on 3rd+
  - Skips safe-to-repeat tools (Read, Grep, Glob) — those are handled
    by duplicate_reads or are naturally idempotent searches

Config:
  MAX_IDENTICAL — block after this many identical calls (default: 3)
  WARN_AT       — warn (non-blocking) at this count (default: 2)
  RETRY_LOG     — path to state file
"""

import json
import sys
import hashlib

RETRY_LOG = "/tmp/claude_retry_log.json"
MAX_IDENTICAL = 3   # block on 3rd identical call
WARN_AT = 2         # warn on 2nd

# Tools that are safe to repeat, handled elsewhere, or are lifecycle/system tools
SKIP_TOOLS = {
    "Read", "Grep", "Glob", "Skill", "ToolSearch",
    "ExitPlanMode", "EnterPlanMode", "ExitWorktree", "EnterWorktree",
    "TodoWrite", "AskUserQuestion", "Agent", "SendMessage", "NotebookEdit",
}

data = json.load(sys.stdin)

tool_name = data.get("tool_name", "")
tool_input = data.get("tool_input", {})
session_id = data.get("session_id", "")

# Skip tools that are safe to repeat
if tool_name in SKIP_TOOLS:
    sys.exit(0)

# Load state
try:
    with open(RETRY_LOG) as f:
        state = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    state = {"session_id": "", "calls": {}}

# Auto-reset if session changed
if state.get("session_id") != session_id:
    state = {"session_id": session_id, "calls": {}}

calls = state.get("calls", {})

# Create fingerprint — for Bash, normalize by ignoring the description field
# since Claude often retries the same command with a different description
if tool_name == "Bash":
    fp_input = {"tool": tool_name, "command": tool_input.get("command", "")}
else:
    fp_input = {"tool": tool_name, "input": tool_input}

fingerprint = hashlib.md5(
    json.dumps(fp_input, sort_keys=True).encode()
).hexdigest()

count = calls.get(fingerprint, 0)

if count >= MAX_IDENTICAL:
    sys.stderr.write(
        f"RETRY LOOP DETECTED: You have attempted the same '{tool_name}' call "
        f"{count} times with identical inputs.\n"
        f"STOP and either:\n"
        f"1. Try a genuinely different approach.\n"
        f"2. Ask the user for help if you're stuck."
    )
    sys.exit(2)

calls[fingerprint] = count + 1
state["calls"] = calls

with open(RETRY_LOG, "w") as f:
    json.dump(state, f)

if count + 1 == WARN_AT:
    sys.stderr.write(
        f"[guardrail] You are repeating the same '{tool_name}' call for the "
        f"{count + 1}{'nd' if count + 1 == 2 else 'th'} time. "
        f"If it didn't work before, consider a different approach."
    )
    sys.exit(0)

sys.exit(0)
