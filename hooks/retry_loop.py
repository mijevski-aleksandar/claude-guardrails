#!/usr/bin/env python3
"""
Hook: retry_loop.py
Fires: PreToolUse on every tool call
Purpose: Detect when Claude is repeating the exact same tool call with the same inputs,
         which indicates it is stuck in a retry loop. Block and force a new approach.
Config:  Set MAX_IDENTICAL below to adjust how many repeats are allowed.
"""

import json
import sys
import hashlib

RETRY_LOG = "/tmp/claude_retry_log.json"
MAX_IDENTICAL = 2  # block on the (MAX_IDENTICAL + 1)th identical call

data = json.load(sys.stdin)

tool_name = data.get("tool_name", "")
tool_input = data.get("tool_input", {})

# Fingerprint this exact tool call (tool name + inputs)
fingerprint = hashlib.md5(
    json.dumps({"tool": tool_name, "input": tool_input}, sort_keys=True).encode()
).hexdigest()

# Load retry history
try:
    with open(RETRY_LOG) as f:
        log = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    log = {}

count = log.get(fingerprint, 0)

if count >= MAX_IDENTICAL:
    sys.stderr.write(
        f"[guardrail: retry_loop] BLOCKED: You have made the exact same '{tool_name}' "
        f"call {count} time(s) with identical inputs. This is a retry loop.\n"
        f"STOP. Do the following before making any more tool calls:\n"
        f"1. Explain why you think this call keeps failing or not producing the right result.\n"
        f"2. Propose a completely different approach to solve the problem.\n"
        f"3. If you are unsure how to proceed, ask the user for guidance.\n"
        f"Do NOT repeat the same call again."
    )
    sys.exit(2)

log[fingerprint] = count + 1
with open(RETRY_LOG, "w") as f:
    json.dump(log, f)

sys.exit(0)
