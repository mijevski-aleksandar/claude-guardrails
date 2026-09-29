#!/usr/bin/env python3
"""
Hook: failed_tools.py
Fires: PostToolUse on every tool call
Purpose: Detect tool failures and escalate after repeated failures.
         Prevents blind retry loops by forcing Claude to diagnose before retrying.

Detection: Uses the tool_response structure to find actual errors —
           checks for 'is_error' field and stderr-only responses,
           NOT keyword matching on response content (which causes false positives).

Config:
  MAX_FAILURES — escalate after this many total failures (default: 3)
"""

import json, sys, os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "shared"))
from state_paths import get_state_path

MAX_FAILURES = 3  # escalate after this many total failures

# System/lifecycle tools that should never be tracked as failures
SKIP_TOOLS = {
    "ExitPlanMode", "EnterPlanMode", "ExitWorktree", "EnterWorktree",
    "TodoWrite", "Skill", "ToolSearch", "AskUserQuestion",
    "Agent", "SendMessage", "NotebookEdit",
}

data = json.load(sys.stdin)

tool_name = data.get("tool_name", "")
tool_response = data.get("tool_response", {})
session_id = data.get("session_id", "")

# Skip system/lifecycle tools entirely
if tool_name in SKIP_TOOLS:
    sys.exit(0)

# Detect actual failures using structured signals, not keyword matching.
# NOTE: real tool_result payloads carry is_error as a top-level sibling of
# content (verified against actual session transcripts), not nested inside
# a dict-shaped tool_response — check both the top-level hook payload and
# tool_response itself, since the exact nesting has changed across Claude
# Code versions. Bash failures show up as a string starting with
# "Exit code <n>" (n != 0), never an "Error:" prefix.
is_failure = False

if data.get("is_error") is True:
    is_failure = True
elif isinstance(tool_response, dict):
    if tool_response.get("is_error") is True:
        is_failure = True
    elif tool_response.get("exitCode", 0) != 0:
        is_failure = True
elif isinstance(tool_response, str):
    if tool_response.startswith("Error:") or tool_response.startswith("error:"):
        is_failure = True
    elif tool_response.startswith("Exit code") and not tool_response.startswith("Exit code 0"):
        is_failure = True
    elif tool_response.startswith("<tool_use_error>"):
        is_failure = True

if not is_failure:
    sys.exit(0)

FAIL_LOG = get_state_path("failed_tools", session_id)

# Log the failure
try:
    with open(FAIL_LOG) as f:
        log = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    log = {"count": 0, "failures": []}

log["count"] += 1

# Store a short snippet for debugging, but sanitize it
snippet = str(tool_response)[:200] if tool_response else "(empty)"
log["failures"].append({"tool": tool_name, "response_snippet": snippet})

with open(FAIL_LOG, "w") as f:
    json.dump(log, f)

total_failures = log["count"]

if total_failures >= MAX_FAILURES:
    # Build a summary of unique failing tools
    failing_tools = set(f["tool"] for f in log["failures"])
    tool_list = ", ".join(failing_tools)

    sys.stderr.write(
        f"REPEATED FAILURES ({total_failures} total, tools: {tool_list}): "
        f"Multiple tool calls have failed this session.\n"
        f"Before continuing, you MUST:\n"
        f"1. List all the tools that have failed and why.\n"
        f"2. Check for permission issues (e.g. missing virtualenv, wrong directory, migrations not run).\n"
        f"3. Ask the user for help if the root cause is unclear.\n"
        f"Do NOT keep attempting variations of the same failing call."
    )
    sys.exit(2)
else:
    sys.stderr.write(
        f"[guardrail] Tool '{tool_name}' returned an error (failure {total_failures}/{MAX_FAILURES}). "
        f"Before retrying, explain what went wrong and what you will do differently."
    )
    sys.exit(0)  # warn only below threshold, don't block
