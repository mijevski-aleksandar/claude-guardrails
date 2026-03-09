#!/usr/bin/env python3
"""
Hook: compaction_reset.py
Fires: PreCompact event (before context compaction)
Purpose: Reset duplicate_reads counters when compaction occurs, because
the file content Claude previously read is lost from context after
compaction. Blocking re-reads after compaction would degrade output.

Also resets retry_loop counters since the context of previous failures
is lost too.
"""

import json
import sys
import os

READ_LOG = "/tmp/claude_read_log.json"
RETRY_LOG = "/tmp/claude_retry_log.json"

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

sys.exit(0)  # never block compaction
