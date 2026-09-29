#!/usr/bin/env python3
"""
Hook: handoff_before_gap.py
Fires:
  - Stop            -> stamp current time as "last stop" for this session
  - UserPromptSubmit -> check gap since last stop; if long, inject a
                        recap instruction for Claude's next reply

Purpose: Replace the intent of the removed PreCompact-based handoff
(session_summary.py / last-session.md), which broke silently for months
because it depended on ordering within a fragile PreCompact hook chain.
This is anchored to Stop/UserPromptSubmit instead - both fire on every
turn regardless of what else is happening, so there's no ordering
dependency on other hooks to get right.

Never blocks - this is advisory context injection only, exit 0 always.

Config:
  GAP_THRESHOLD_SECONDS — idle gap that triggers the recap prompt (default: 1800 = 30 min)
"""

import json
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "shared"))
from state_paths import get_state_path

GAP_THRESHOLD_SECONDS = 1800  # 30 minutes

data = json.load(sys.stdin)
event = data.get("hook_event_name", "")
session_id = data.get("session_id", "")

STATE = get_state_path("handoff_before_gap", session_id)


def load_last_stop():
    try:
        with open(STATE) as f:
            return json.load(f).get("last_stop_time")
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_last_stop(t):
    with open(STATE, "w") as f:
        json.dump({"last_stop_time": t}, f)


if event == "Stop":
    save_last_stop(time.time())
    sys.exit(0)

if event == "UserPromptSubmit":
    last_stop = load_last_stop()
    now = time.time()

    if last_stop is not None:
        gap = now - last_stop
        if gap >= GAP_THRESHOLD_SECONDS:
            minutes = int(gap / 60)
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": (
                        f"It has been about {minutes} minutes since the last turn in "
                        f"this session. Before addressing the new message below, briefly "
                        f"state your understanding of where things stood - what was done, "
                        f"what's in progress, key files touched - in 2-3 sentences. Then "
                        f"continue with the new request."
                    ),
                }
            }))
    sys.exit(0)

sys.exit(0)
