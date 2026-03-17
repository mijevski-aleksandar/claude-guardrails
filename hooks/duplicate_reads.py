#!/usr/bin/env python3
"""
Hook: duplicate_reads.py
Fires: PreToolUse on Read calls
Purpose: Warn about repeated reads of unchanged files, but NEVER block them.
         Blocking reads degrades output quality because Claude's memory of
         file contents degrades after compaction or long sessions. It's always
         better to let Claude re-read than to force it to guess.

Smart behaviors:
  - Auto-resets counters when session changes (no manual clear-logs.sh needed)
  - Allows re-reads if the file was modified on disk since the last read
  - Warns on 2nd+ read with escalating guidance (never blocks)
  - Suggests using Grep for targeted lookups or reading specific line ranges

Config:
  WARN_AT  — warn at this many reads of unchanged file (default: 2)
  READ_LOG — path to state file
"""

import json
import sys
import os

READ_LOG = "/tmp/claude_read_log.json"
WARN_AT = 2  # warn starting at 2nd read (non-blocking)

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

# Record this read
entry["count"] = count + 1
entry["last_mtime"] = current_mtime
reads[file_path] = entry
state["reads"] = reads

with open(READ_LOG, "w") as f:
    json.dump(state, f)

# Warn but NEVER block — Claude's memory of file contents is unreliable
# after compaction, so re-reading is always safer than guessing
if count + 1 >= WARN_AT:
    basename = os.path.basename(file_path)
    nth = count + 1
    suffix = {2: "nd", 3: "rd"}.get(nth, "th")
    sys.stderr.write(
        f"[guardrail] You are reading '{basename}' for the {nth}{suffix} time "
        f"and it has not changed on disk. "
        f"If you need a specific section, use Grep or read with offset/limit "
        f"instead of the full file."
    )

sys.exit(0)  # NEVER block reads — always exit 0
