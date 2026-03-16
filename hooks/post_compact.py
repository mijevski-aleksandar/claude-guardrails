#!/usr/bin/env python3
"""
Hook: post_compact.py
Fires: PostCompact (after context compaction completes)
Purpose: Inject critical task context back into Claude's awareness after
         compaction, preventing "task forgetting" in long sessions.
         Points Claude to active plan files and task lists so it can
         restore context without re-exploring the codebase.
"""

import json, sys, os

data = json.load(sys.stdin)

# Check if there's an active plan file
plans_dir = os.path.expanduser("~/.claude/plans/")
active_plan = None
if os.path.isdir(plans_dir):
    plans = [
        f for f in os.listdir(plans_dir)
        if f.endswith(".md") and os.path.isfile(os.path.join(plans_dir, f))
    ]
    if plans:
        plans.sort(
            key=lambda f: os.path.getmtime(os.path.join(plans_dir, f)),
            reverse=True,
        )
        active_plan = os.path.join(plans_dir, plans[0])

# Build context injection message
parts = ["[guardrail: post_compact] Context was just compacted."]

if active_plan:
    parts.append(f"ACTIVE PLAN: {active_plan} — re-read this to restore task context.")

parts.append(
    "Re-read any critical files before continuing. "
    "Check your task list if one exists."
)

sys.stderr.write(" ".join(parts))
sys.exit(0)  # never block
