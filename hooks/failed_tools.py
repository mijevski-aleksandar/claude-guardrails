#!/usr/bin/env python3
"""
Hook: failed_tools.py
Fires: PostToolUse on every tool call
Purpose: Detect tool failures and escalate after repeated failures.
         Prevents blind retry loops by forcing Claude to diagnose before retrying.

Config:
  MAX_FAILURES — escalate after this many total failures (default: 3)
"""

import json, sys

FAIL_LOG = "/tmp/claude_fail_log.json"
MAX_FAILURES = 3  # escalate after this many total failures

data = json.load(sys.stdin)

# PostToolUse hook — check if the tool result indicates failure
tool_name = data.get("tool_name", "")
tool_response = data.get("tool_response", {})

# Detect failure signals in the response
response_str = json.dumps(tool_response).lower()
failure_keywords = ["error", "failed", "permission denied", "no such file", "not found", "exception", "traceback"]

is_failure = any(kw in response_str for kw in failure_keywords)

if not is_failure:
    sys.exit(0)

# Log the failure
try:
    with open(FAIL_LOG) as f:
        log = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    log = {"count": 0, "failures": []}

log["count"] += 1
log["failures"].append({"tool": tool_name, "response_snippet": response_str[:200]})

with open(FAIL_LOG, "w") as f:
    json.dump(log, f)

total_failures = log["count"]

if total_failures >= MAX_FAILURES:
    sys.stderr.write(
        f"REPEATED FAILURES ({total_failures} total): Multiple tool calls have failed this session.\n"
        f"Before continuing, you MUST:\n"
        f"1. List all the tools that have failed and why.\n"
        f"2. Check for permission issues (e.g. missing virtualenv, wrong directory, migrations not run).\n"
        f"3. Ask the user for help if the root cause is unclear.\n"
        f"Do NOT keep attempting variations of the same failing call."
    )
    sys.exit(2)
else:
    sys.stderr.write(
        f"TOOL FAILURE DETECTED ('{tool_name}'): This tool call failed. "
        f"Before retrying, explain what went wrong and what you will do differently. "
        f"Do not blindly retry the same call."
    )
    sys.exit(2)
