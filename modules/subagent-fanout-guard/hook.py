#!/usr/bin/env python3
"""
Hook: subagent_fanout_guard.py
Fires:
  - SubagentStart -> increment in-flight counter for this session
  - SubagentStop  -> decrement in-flight counter for this session
  - PreToolUse (matcher: Agent) -> check counter before allowing another spawn

Purpose: Cost control against runaway parallel subagent fan-out. Each
subagent pays its own prompt-cache-write cost on spawn (subagents cannot
share a cache prefix with each other or the parent - confirmed against
Claude Code docs), so spawning many at once is a real, direct cost driver.

SubagentStart/SubagentStop cannot block (no exit-2 support on Start; Stop's
exit-2 only prevents that one subagent from stopping). The only enforcement
point is PreToolUse on the Agent tool call itself, checked BEFORE the spawn
that would push the count over the limit.

Config:
  WARN_AT — warn (non-blocking) when this many agents are already in flight
            before allowing one more (default: 3, matches typical /pr-review
            fan-out width)
  MAX     — block (exit 2) when this many agents are already in flight
            (default: 6)
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "shared"))
from state_paths import get_state_path

WARN_AT = 3
MAX = 6

data = json.load(sys.stdin)
event = data.get("hook_event_name", "")
session_id = data.get("session_id", "")

STATE = get_state_path("subagent_fanout", session_id)


def load_count():
    try:
        with open(STATE) as f:
            return json.load(f).get("in_flight", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        return 0


def save_count(n):
    with open(STATE, "w") as f:
        json.dump({"in_flight": max(0, n)}, f)


if event == "SubagentStart":
    save_count(load_count() + 1)
    sys.exit(0)

if event == "SubagentStop":
    save_count(load_count() - 1)
    sys.exit(0)

# PreToolUse on Agent: check before allowing the spawn that would follow
if data.get("tool_name") != "Agent":
    sys.exit(0)

in_flight = load_count()

if in_flight >= MAX:
    sys.stderr.write(
        f"[guardrail] BLOCKED: {in_flight} subagents are already in flight this "
        f"session. Each spawn pays its own prompt-cache-write cost. Wait for "
        f"some to finish before launching more, or confirm with the user that "
        f"this many parallel agents is actually needed."
    )
    sys.exit(2)

if in_flight >= WARN_AT:
    sys.stderr.write(
        f"[guardrail] {in_flight} subagents already in flight this session — "
        f"about to spawn another. Each one cold-starts its own cache prefix "
        f"(real cost, not free parallelism). Consider whether this one is "
        f"necessary before continuing to fan out."
    )

sys.exit(0)
