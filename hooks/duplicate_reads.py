#!/usr/bin/env python3
"""
Hook: duplicate_reads.py
Fires: PreToolUse on Read calls
Purpose: Block re-reads of the same bytes from an unchanged file. Different
         byte ranges of the same file are allowed (legitimate paginated reads).
         Mtime change always resets tracking — modified files can be re-read freely.

Behavior:
  - 1st read of any byte range: allow
  - 2nd read of an OVERLAPPING byte range (unchanged file): warn
  - 3rd read of an OVERLAPPING byte range (unchanged file): BLOCK with guidance
  - Read of a NEW byte range: allow (counts as 1st read for that range)
  - File mtime changed since last read: reset all tracking for that file, allow

State key is file_path only; we track which byte ranges have already been read.
A "full file" read (no offset/limit) covers [0, inf) and overlaps everything.

Config:
  WARN_AT  — warn at this many overlapping reads (default: 2)
  BLOCK_AT — block at this many overlapping reads (default: 3)
  READ_LOG — path to state file
"""

import json
import sys
import os

READ_LOG = "/tmp/claude_read_log.json"
WARN_AT = 2
BLOCK_AT = 3

data = json.load(sys.stdin)

if data.get("tool_name") != "Read":
    sys.exit(0)

tool_input = data.get("tool_input", {})
file_path = tool_input.get("file_path", "")
offset = tool_input.get("offset")
limit = tool_input.get("limit")
session_id = data.get("session_id", "")

# Translate (offset, limit) into a [start, end) line range.
# offset=None means start at line 1. limit=None means read to EOF (use sentinel).
EOF_SENTINEL = 10**9
start = (offset if offset is not None else 1)
end = (start + limit) if limit is not None else EOF_SENTINEL


def overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


# Load state
try:
    with open(READ_LOG) as f:
        state = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    state = {"session_id": "", "reads": {}}

# Auto-reset on session change
if state.get("session_id") != session_id:
    state = {"session_id": session_id, "reads": {}}

reads = state.setdefault("reads", {})
# Per-file entry: {"last_mtime": float, "ranges": [[start, end, count], ...]}
entry = reads.get(file_path, {"last_mtime": 0, "ranges": []})

# Mtime check — file changed on disk since we last saw it? Reset tracking.
current_mtime = 0.0
try:
    current_mtime = os.path.getmtime(file_path)
except OSError:
    # File doesn't exist (Read will fail naturally) or permission error — allow.
    pass

if current_mtime > entry.get("last_mtime", 0) and entry["ranges"]:
    entry = {"last_mtime": current_mtime, "ranges": []}

# Find any existing range that overlaps the new one
overlap_idx = None
overlap_count = 0
for i, (s, e, c) in enumerate(entry["ranges"]):
    if overlaps(start, end, s, e):
        overlap_idx = i
        overlap_count = c
        break

new_count = overlap_count + 1

# Decide before recording, so we can block before mutating state
should_block = (new_count >= BLOCK_AT)
should_warn = (new_count >= WARN_AT and not should_block)

if should_block:
    basename = os.path.basename(file_path)
    sys.stderr.write(
        f"[guardrail] BLOCKED: '{basename}' has been read {overlap_count} times "
        f"already in this byte range and the file has not changed on disk. "
        f"Work from your prior read, or use Grep for a targeted lookup, or read "
        f"a DIFFERENT byte range with offset+limit. If the file truly changed and "
        f"this guardrail is wrong, run `stat -f %m {file_path}` to bump mtime "
        f"awareness or save the file in your editor."
    )
    sys.exit(2)  # exit 2 blocks the tool call in Claude Code

# Record this read (merge into existing range if overlap, else append)
if overlap_idx is not None:
    s, e, _ = entry["ranges"][overlap_idx]
    entry["ranges"][overlap_idx] = [min(s, start), max(e, end), new_count]
else:
    entry["ranges"].append([start, end, 1])

entry["last_mtime"] = current_mtime
reads[file_path] = entry
state["reads"] = reads

with open(READ_LOG, "w") as f:
    json.dump(state, f)

if should_warn:
    basename = os.path.basename(file_path)
    nth = new_count
    suffix = {2: "nd", 3: "rd"}.get(nth, "th")
    sys.stderr.write(
        f"[guardrail] You are reading '{basename}' for the {nth}{suffix} time "
        f"in an overlapping byte range and it has not changed on disk. "
        f"Next overlapping read will be BLOCKED. "
        f"Use Grep, read a different byte range with offset/limit, or work from memory."
    )

sys.exit(0)
