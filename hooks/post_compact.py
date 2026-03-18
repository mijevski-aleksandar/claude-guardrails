#!/usr/bin/env python3
"""
Hook: post_compact.py
Fires: PostCompact (after context compaction completes)
Purpose: Inject the handoff snapshot written by pre_compact.py back into
         Claude's awareness so it can resume without re-exploring.
         Falls back to minimal reminder if no handoff file exists.
"""

import json
import sys
import os

HANDOFF_FILE = "/tmp/claude_handoff.json"

data = json.load(sys.stdin)

# ── Load handoff ────────────────────────────────────────────────────────────
handoff = None
if os.path.isfile(HANDOFF_FILE):
    try:
        with open(HANDOFF_FILE) as f:
            handoff = json.load(f)
    except Exception:
        handoff = None

# ── Build injection message ─────────────────────────────────────────────────
parts = ["[guardrail: post_compact] Context was just compacted. Resume from this handoff:\n"]

if handoff:
    if handoff.get("active_plan"):
        parts.append(f"ACTIVE PLAN: {handoff['active_plan']} — re-read this first.")

    modified = handoff.get("files_modified", [])
    if modified:
        paths = [os.path.basename(f["path"]) for f in modified[-5:]]
        parts.append(f"FILES MODIFIED THIS SESSION: {', '.join(paths)}")

    last_tools = handoff.get("last_tool_calls", [])
    if last_tools:
        tool_names = [t["tool"] for t in last_tools]
        parts.append(f"LAST ACTIONS BEFORE COMPACT: {' → '.join(tool_names)}")

    last_bash = handoff.get("last_bash", [])
    if last_bash:
        parts.append(f"LAST BASH: {last_bash[-1][:100]}")

    parts.append(
        f"Re-read modified files before continuing. "
        f"Do NOT re-explore the codebase from scratch — pick up where you left off."
    )
else:
    # Fallback: no handoff available
    plans_dir = os.path.expanduser("~/.claude/plans/")
    if os.path.isdir(plans_dir):
        plans = [
            f for f in os.listdir(plans_dir)
            if f.endswith(".md") and os.path.isfile(os.path.join(plans_dir, f))
        ]
        if plans:
            plans.sort(key=lambda f: os.path.getmtime(os.path.join(plans_dir, f)), reverse=True)
            parts.append(f"ACTIVE PLAN: {os.path.join(plans_dir, plans[0])} — re-read to restore context.")

    parts.append("Re-read any critical files before continuing.")

sys.stderr.write(" ".join(parts))
sys.exit(0)
