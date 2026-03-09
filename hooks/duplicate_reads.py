#!/usr/bin/env python3
"""
Hook: duplicate_reads.py
Fires: PreToolUse on any Read tool call
Purpose: Block Claude from reading the same file more than MAX_READS times per session.
         Forces Claude to use content it has already retrieved instead of re-fetching.
Config:  Set MAX_READS below to adjust the threshold.
"""

import json
import sys

READ_LOG = "/tmp/claude_read_log.json"
MAX_READS = 2  # block on the (MAX_READS + 1)th read of the same file

data = json.load(sys.stdin)

# Only intercept Read tool calls
if data.get("tool_name") not in ("Read", "read_file", "view"):
    sys.exit(0)

file_path = data.get("tool_input", {}).get("file_path", "") or \
            data.get("tool_input", {}).get("path", "")

if not file_path:
    sys.exit(0)

# Load read history
try:
    with open(READ_LOG) as f:
        reads = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    reads = {}

count = reads.get(file_path, 0)

if count >= MAX_READS:
    sys.stderr.write(
        f"[guardrail: duplicate_reads] BLOCKED: '{file_path}' has already been read "
        f"{count} time(s) this session.\n"
        f"Do NOT read this file again. Use the content you already have in context.\n"
        f"If you are looking for something specific, state what it is and reason from "
        f"what you already know.\n"
        f"If the file has genuinely changed since your last read, explain why before retrying."
    )
    sys.exit(2)  # exit code 2 = block + send stderr message to Claude

# Increment and save
reads[file_path] = count + 1
with open(READ_LOG, "w") as f:
    json.dump(reads, f)

sys.exit(0)
