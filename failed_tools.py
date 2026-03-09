#!/usr/bin/env python3
"""
Hook: failed_tools.py
Fires: PostToolUse on every tool call
Purpose: Detect when a tool call has failed (error keywords in response). On repeated
         failures, block and force Claude to diagnose the root cause before continuing.
Config:  Adjust MAX_FAILURES and FAILURE_KEYWORDS below.
"""

import json
import sys

FAIL_LOG = "/tmp/claude_fail_log.json"
MAX_FAILURES = 3  # escalate after this many total failures in the session

FAILURE_KEYWORDS = [
    "error", "failed", "failure",
    "permission denied", "no such file", "not found",
    "exception", "traceback", "cannot", "unable to",
    "syntax error", "importerror", "modulenotfounderror",
    "does not exist", "undefined", "null pointer",
]

data = json.load(sys.stdin)

tool_name = data.get("tool_name", "")
tool_response = data.get("tool_response", {})
response_str = json.dumps(tool_response).lower()

is_failure = any(kw in response_str for kw in FAILURE_KEYWORDS)

if not is_failure:
    sys.exit(0)

# Log the failure
try:
    with open(FAIL_LOG) as f:
        log = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    log = {"count": 0, "failures": []}

log["count"] += 1
log["failures"].append({
    "tool": tool_name,
    "snippet": response_str[:300]
})

with open(FAIL_LOG, "w") as f:
    json.dump(log, f)

total = log["count"]

if total >= MAX_FAILURES:
    sys.stderr.write(
        f"[guardrail: failed_tools] ESCALATION — {total} tool failures this session.\n"
        f"Before continuing, you MUST:\n"
        f"1. List every tool that has failed and summarise why each one failed.\n"
        f"2. Identify the root cause (e.g. wrong path, missing dependency, bad input, "
        f"permissions issue).\n"
        f"3. Propose a concrete fix for the root cause — not just a retry.\n"
        f"4. Ask the user for help if the root cause is unclear.\n"
        f"Do NOT attempt any more tool calls until you have done this."
    )
    sys.exit(2)
else:
    sys.stderr.write(
        f"[guardrail: failed_tools] Tool '{tool_name}' appears to have failed "
        f"(failure {total}/{MAX_FAILURES} this session).\n"
        f"Before retrying, explain what went wrong and what you will do differently. "
        f"Do not blindly retry the same call."
    )
    sys.exit(2)
