#!/usr/bin/env python3
import json, sys, os

READ_LOG = "/tmp/claude_read_log.json"

data = json.load(sys.stdin)

if data.get("tool_name") != "Read":
    sys.exit(0)

file_path = data.get("tool_input", {}).get("file_path", "")

try:
    with open(READ_LOG) as f:
        reads = json.load(f)
except:
    reads = {}

count = reads.get(file_path, 0)

if count >= 2:
    sys.stderr.write(
        f"DUPLICATE READ BLOCKED: You have already read '{file_path}' {count} times.\n"
        f"Do NOT read it again. Use the content you already retrieved.\n"
        f"If you're looking for something specific, state what it is and reason from memory.\n"
        f"If the file has genuinely changed since your last read, explain why before retrying."
    )
    sys.exit(2)  # exit code 2 = block + send stderr to Claude

reads[file_path] = count + 1
with open(READ_LOG, "w") as f:
    json.dump(reads, f)

sys.exit(0)
