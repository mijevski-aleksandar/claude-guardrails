#!/usr/bin/env python3
"""
Hook: context_pressure.py
Fires: PreToolUse on every tool call
Purpose: Track step count and warn Claude when sessions get long.
         Encourages concise behavior and session splitting for complex tasks.

Config:
  WARN_AT  — step count at which to start warning (default: 30)
  STOP_AT  — step count for critical warning (default: 50, warn-only)
"""

import json, sys, os

STEP_LOG = "/tmp/claude_step_count.json"
WARN_AT = 30    # warn Claude to wrap up
STOP_AT = 50    # critical warning (warn-only, does not block)

data = json.load(sys.stdin)

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
        f"CONTEXT PRESSURE CRITICAL ({steps} steps): This session is very long. "
        f"Be extremely concise. Finish the current task and suggest the user "
        f"start a new session for any remaining work. "
        f"If the task is complex, summarize progress and incomplete items."
    )
    sys.exit(0)  # warn only, never block

elif steps >= WARN_AT:
    sys.stderr.write(
        f"CONTEXT PRESSURE WARNING ({steps} steps): This session is getting long. "
        f"Be concise. Avoid reading files you've already seen. "
        f"Prioritize finishing the current task before starting anything new. "
        f"If the task is getting complex, suggest splitting into a new session."
    )
    sys.exit(0)

sys.exit(0)
