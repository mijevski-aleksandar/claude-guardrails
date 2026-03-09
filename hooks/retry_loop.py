#!/usr/bin/env python3
import json, sys, hashlib

RETRY_LOG = "/tmp/claude_retry_log.json"
MAX_IDENTICAL = 2  # block on 3rd identical call

data = json.load(sys.stdin)

tool_name = data.get("tool_name", "")
tool_input = data.get("tool_input", {})

# Create a fingerprint of this exact tool call
fingerprint = hashlib.md5(
    json.dumps({"tool": tool_name, "input": tool_input}, sort_keys=True).encode()
).hexdigest()

try:
    with open(RETRY_LOG) as f:
        log = json.load(f)
except:
    log = {}

count = log.get(fingerprint, 0)

if count >= MAX_IDENTICAL:
    sys.stderr.write(
        f"RETRY LOOP DETECTED: You have attempted the exact same '{tool_name}' call "
        f"{count} times with identical inputs.\n"
        f"This approach is not working. STOP and do the following:\n"
        f"1. Explain why you think this call keeps failing.\n"
        f"2. Propose a completely different approach.\n"
        f"3. Ask the user if you are unsure how to proceed.\n"
        f"Do NOT repeat the same call again."
    )
    sys.exit(2)

log[fingerprint] = count + 1
with open(RETRY_LOG, "w") as f:
    json.dump(log, f)

sys.exit(0)
