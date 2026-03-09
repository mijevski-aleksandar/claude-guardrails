#!/usr/bin/env python3
"""
Hook: auto_compact.py
Fires: PreToolUse on every tool call
Purpose: Automatically trigger Claude Code's /compact command when the session
         reaches a step threshold, before context degrades. This recovers ~16%
         of the context window compared to letting autocompact handle it.

         Works in tandem with "autoCompact": false in settings.json — you manage
         compaction manually via this hook so it happens at the right moment,
         not reactively when the window is already full.

Config:
  COMPACT_AT  — step count at which to trigger /compact (default: 25)
  COMPACT_LOG — path to track compaction history this session
"""

import json
import sys
import os
from datetime import datetime

STEP_LOG    = "/tmp/claude_step_count.json"
COMPACT_LOG = "/tmp/claude_compact_log.json"
COMPACT_AT  = 25   # trigger /compact at this many steps

# ── Load step count (shared with context_pressure.py) ──────────────────────
try:
    with open(STEP_LOG) as f:
        state = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    state = {"steps": 0}

steps = state.get("steps", 0)

# ── Load compaction history ─────────────────────────────────────────────────
try:
    with open(COMPACT_LOG) as f:
        compact_state = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    compact_state = {"last_compact_at": 0, "compact_count": 0}

last_compact_at = compact_state.get("last_compact_at", 0)
steps_since_last = steps - last_compact_at

# ── Check if compaction is due ──────────────────────────────────────────────
# Only trigger if COMPACT_AT steps have passed since the last compaction
# (or since session start if never compacted)
if steps_since_last >= COMPACT_AT and steps > 0:

    # Record that we triggered compaction
    compact_state["last_compact_at"] = steps
    compact_state["compact_count"] += 1
    compact_state["last_triggered"] = datetime.now().isoformat()

    with open(COMPACT_LOG, "w") as f:
        json.dump(compact_state, f)

    count = compact_state["compact_count"]

    sys.stderr.write(
        f"[guardrail: auto_compact] COMPACT SUGGESTED at step {steps} "
        f"(compaction #{count} this session).\n"
        f"\n"
        f"Context is getting long. Consider running /compact to recover window space.\n"
    )
    sys.exit(0)  # warn only, don't block

sys.exit(0)
