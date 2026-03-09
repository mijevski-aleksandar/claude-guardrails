#!/usr/bin/env python3
"""
Hook: context_pressure.py
Fires: PreToolUse on every tool call
Purpose: Track session length by step count. Warn Claude when the session is getting
         long, and force a graceful handoff summary when it is critically long.
Config:  Adjust WARN_AT and STOP_AT thresholds below.
"""

import json
import sys

STEP_LOG = "/tmp/claude_step_count.json"
WARN_AT = 30   # issue a warning, don't block
STOP_AT = 50   # block and force session summary + handoff

# Load step count
try:
    with open(STEP_LOG) as f:
        state = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    state = {"steps": 0}

state["steps"] += 1
steps = state["steps"]

with open(STEP_LOG, "w") as f:
    json.dump(state, f)

if steps >= STOP_AT:
    sys.stderr.write(
        f"[guardrail: context_pressure] CRITICAL — {steps} steps reached. "
        f"Context window is near its limit.\n"
        f"You MUST stop all tool usage immediately and do the following:\n"
        f"1. Write a clear summary of everything you have done this session.\n"
        f"2. List all tasks that are still incomplete.\n"
        f"3. List any important file paths, variable names, or decisions made.\n"
        f"4. Tell the user to start a NEW Claude Code session and paste this summary "
        f"at the start.\n"
        f"Do NOT make any more tool calls until the summary is complete."
    )
    sys.exit(2)

elif steps >= WARN_AT:
    sys.stderr.write(
        f"[guardrail: context_pressure] WARNING — {steps} steps used this session. "
        f"Context is getting long.\n"
        f"Be concise. Avoid re-reading files you have already seen. "
        f"Finish the current task before starting anything new. "
        f"If the scope is expanding, suggest splitting into a new session."
    )
    # Warning only — do not block (exit 0)
    sys.exit(0)

sys.exit(0)
