#!/usr/bin/env python3
"""
Hook: compaction_reset.py
Fires: PreCompact event (before context compaction)
Purpose: Reset all guardrail counters when compaction occurs, because
the context Claude previously built is lost after compaction.
Blocking re-reads or re-triggering warnings after compaction would
degrade output quality.

Resets: duplicate_reads, retry_loop, context_pressure (step count),
        auto_compact (compact log), failed_tools (failure count).
"""

import json
import sys
import os

READ_LOG    = "/tmp/claude_read_log.json"
RETRY_LOG   = "/tmp/claude_retry_log.json"
STEP_LOG    = "/tmp/claude_step_count.json"
COMPACT_LOG = "/tmp/claude_compact_log.json"
FAIL_LOG    = "/tmp/claude_fail_log.json"

data = json.load(sys.stdin)
session_id = data.get("session_id", "")

# Reset read counters but preserve session_id
try:
    with open(READ_LOG) as f:
        state = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    state = {}

if state.get("session_id") == session_id:
    state["reads"] = {}
    with open(READ_LOG, "w") as f:
        json.dump(state, f)

# Reset retry counters
try:
    with open(RETRY_LOG) as f:
        state = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    state = {}

if state.get("session_id") == session_id:
    state["calls"] = {}
    with open(RETRY_LOG, "w") as f:
        json.dump(state, f)

# Reset step counter (context_pressure + auto_compact share this)
try:
    with open(STEP_LOG) as f:
        step_state = json.load(f)
    step_state["steps"] = 0
    with open(STEP_LOG, "w") as f:
        json.dump(step_state, f)
except (FileNotFoundError, json.JSONDecodeError):
    pass

# Reset compact log
try:
    with open(COMPACT_LOG) as f:
        compact_state = json.load(f)
    compact_state["last_compact_at"] = 0
    with open(COMPACT_LOG, "w") as f:
        json.dump(compact_state, f)
except (FileNotFoundError, json.JSONDecodeError):
    pass

# Reset failure log
try:
    with open(FAIL_LOG) as f:
        fail_state = json.load(f)
    fail_state["count"] = 0
    fail_state["failures"] = []
    with open(FAIL_LOG, "w") as f:
        json.dump(fail_state, f)
except (FileNotFoundError, json.JSONDecodeError):
    pass

sys.exit(0)  # never block compaction
