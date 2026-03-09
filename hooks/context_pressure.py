#!/usr/bin/env python3
import json, sys, os

STEP_LOG = "/tmp/claude_step_count.json"
WARN_AT = 30    # warn Claude to wrap up
STOP_AT = 50    # force Claude to stop and summarize

data = json.load(sys.stdin)

try:
    with open(STEP_LOG) as f:
        state = json.load(f)
except:
    state = {"steps": 0}

state["steps"] += 1
steps = state["steps"]

with open(STEP_LOG, "w") as f:
    json.dump(state, f)

if steps >= STOP_AT:
    sys.stderr.write(
        f"CONTEXT LIMIT CRITICAL ({steps} steps): This session is very long and context "
        f"is near its limit. You MUST stop what you are doing and:\n"
        f"1. Summarize everything you have done so far.\n"
        f"2. List what is still incomplete.\n"
        f"3. Tell the user to start a NEW Claude Code session and paste your summary.\n"
        f"Do NOT proceed with any more tool calls until you have done this."
    )
    sys.exit(2)

elif steps >= WARN_AT:
    sys.stderr.write(
        f"CONTEXT PRESSURE WARNING ({steps} steps): This session is getting long. "
        f"Be concise. Avoid reading files you've already seen. "
        f"Prioritize finishing the current task before starting anything new. "
        f"If the task is getting complex, suggest splitting into a new session."
    )
    # exit 0 — warning only, don't block
    sys.exit(0)

sys.exit(0)
