#!/usr/bin/env python3
"""
Hook: duplicate_reads.py
Fires: PreToolUse on Read calls
Purpose: Block wasteful re-reads of unchanged files while allowing legitimate ones.

Smart behaviors:
  - Auto-resets counters when session changes (no manual clear-logs.sh needed)
  - Allows re-reads if the file was modified on disk since the last read
  - Warns on 2nd read (non-blocking), blocks on 3rd+ read
  - Tracks file mtime to detect genuine changes

Config:
  MAX_READS    — block after this many reads of the same unchanged file (default: 3)
  WARN_AT      — warn (non-blocking) at this many reads (default: 2)
  READ_LOG     — path to state file
"""

import json
import sys
import os

READ_LOG = "/tmp/claude_read_log.json"
MAX_READS = 3   # block on 3rd read of unchanged file
WARN_AT = 2     # warn on 2nd read (non-blocking)

data = json.load(sys.stdin)

if data.get("tool_name") != "Read":
    sys.exit(0)

file_path = data.get("tool_input", {}).get("file_path", "")
session_id = data.get("session_id", "")

# Load state
try:
    with open(READ_LOG) as f:
        state = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    state = {"session_id": "", "reads": {}}

# Auto-reset if session changed
if state.get("session_id") != session_id:
    state = {"session_id": session_id, "reads": {}}

reads = state.get("reads", {})
entry = reads.get(file_path, {"count": 0, "last_mtime": 0})

# Check if file was modified since last read
current_mtime = 0
try:
    current_mtime = os.path.getmtime(file_path)
except OSError:
    pass  # file doesn't exist yet or permission error — allow the read

file_changed = current_mtime > entry.get("last_mtime", 0) and entry["count"] > 0

if file_changed:
    # File changed on disk — reset counter, allow the read
    entry = {"count": 0, "last_mtime": 0}

count = entry["count"]

if count >= MAX_READS:
    sys.stderr.write(
        f"DUPLICATE READ BLOCKED: You have read '{os.path.basename(file_path)}' "
        f"{count} times and it has not changed on disk.\n"
        f"Use the content you already have. If you need something specific, "
        f"state what it is and search with Grep instead."
    )
    sys.exit(2)

# Record this read
entry["count"] = count + 1
entry["last_mtime"] = current_mtime
reads[file_path] = entry
state["reads"] = reads

with open(READ_LOG, "w") as f:
    json.dump(state, f)

if count + 1 == WARN_AT:
    # Warn but don't block
    sys.stderr.write(
        f"[guardrail] You are reading '{os.path.basename(file_path)}' for the "
        f"{count + 1}{'nd' if count + 1 == 2 else 'th'} time. "
        f"Consider using Grep for targeted lookups instead of full re-reads."
    )
    sys.exit(0)

sys.exit(0)
