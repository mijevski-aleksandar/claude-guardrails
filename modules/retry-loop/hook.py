#!/usr/bin/env python3
"""
Hook: retry_loop.py
Fires: PreToolUse on any tool call
Purpose: Detect and stop retry loops — both exact and near-identical tool calls.

Smart behaviors:
  - State namespaced per session_id (see state_paths.py) — concurrent
    sessions no longer reset each other's counters
  - Detects exact duplicates (same tool + same inputs)
  - Detects near-duplicates for Bash calls (same command, different description)
  - Warns on 1st identical call (non-blocking), blocks on 2nd+
  - Skips safe-to-repeat tools (Read, Grep, Glob) — those are handled
    by duplicate_reads or are naturally idempotent searches

Config:
  MAX_IDENTICAL — block after this many identical calls (default: 2)
  WARN_AT       — warn (non-blocking) at this count (default: 1)
"""

import json
import sys
import os
import hashlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "shared"))
from state_paths import get_state_path

MAX_IDENTICAL = 2   # block on 2nd identical call
WARN_AT = 1         # warn on 1st

# Tools that are safe to repeat, handled elsewhere, or are lifecycle/system tools
SKIP_TOOLS = {
    "Read", "Grep", "Glob", "Skill", "ToolSearch",
    "EnterPlanMode", "ExitWorktree", "EnterWorktree",
    "TodoWrite", "AskUserQuestion", "Agent", "SendMessage", "NotebookEdit",
}

# ExitPlanMode is tracked by invocation count (not fingerprint) because Claude
# evades fingerprint detection by editing the plan slightly between attempts.
# The EPM_MAX limit applies to total calls regardless of content.
EPM_MAX = 3   # block on 3rd ExitPlanMode call in a session
EPM_WARN = 2  # warn on 2nd

data = json.load(sys.stdin)

tool_name = data.get("tool_name", "")
tool_input = data.get("tool_input", {})
session_id = data.get("session_id", "")

# Skip tools that are safe to repeat
if tool_name in SKIP_TOOLS:
    sys.exit(0)

RETRY_LOG = get_state_path("retry_loop", session_id)

# Load state
try:
    with open(RETRY_LOG) as f:
        state = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    state = {"calls": {}, "epm_count": 0}

# ── ExitPlanMode: count-based tracking (ignores content/fingerprint) ────────
if tool_name == "ExitPlanMode":
    epm_count = state.get("epm_count", 0) + 1
    state["epm_count"] = epm_count

    with open(RETRY_LOG, "w") as f:
        json.dump(state, f)

    if epm_count >= EPM_MAX:
        sys.stderr.write(
            f"RETRY LOOP DETECTED: You have called ExitPlanMode {epm_count} times "
            f"this session. The user keeps rejecting your plan.\n"
            f"STOP and use AskUserQuestion to clarify what the user wants changed "
            f"before attempting ExitPlanMode again."
        )
        sys.exit(2)
    elif epm_count >= EPM_WARN:
        sys.stderr.write(
            f"[guardrail] ExitPlanMode called {epm_count} times this session. "
            f"If the user rejected your plan, ask what needs to change before "
            f"re-submitting."
        )
        sys.exit(0)

    sys.exit(0)

# ── All other tools: fingerprint-based tracking ─────────────────────────────
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

if count + 1 >= MAX_IDENTICAL:
    sys.stderr.write(
        f"RETRY LOOP DETECTED: You have attempted the same '{tool_name}' call "
        f"{count} time(s) already with identical inputs.\n"
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
        f"{count + 1}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(count + 1, 'th') } time. "
        f"If it didn't work before, consider a different approach."
    )
    sys.exit(0)

sys.exit(0)
