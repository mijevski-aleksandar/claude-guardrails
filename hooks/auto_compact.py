#!/usr/bin/env python3
"""
Hook: auto_compact.py
Fires: PreToolUse on every tool call
Purpose: Suggest running /compact when the session JSONL file reaches ~70%
         of estimated context capacity. File-size-based trigger is more
         accurate than step count since it reflects actual content growth.

Calibration (measured against live sessions):
  ~1.5 MB JSONL ≈ 70% context (sweet spot — compact before degradation)
  ~1.9 MB JSONL ≈ 85% context (Claude Code's built-in auto-compact threshold)

Config:
  COMPACT_THRESHOLD_BYTES — JSONL size that triggers suggestion (default: 1.5 MB)
  COMPACT_LOG             — path to track compaction history this session
"""

import json
import sys
import os
from datetime import datetime

COMPACT_LOG             = "/tmp/claude_compact_log.json"
COMPACT_THRESHOLD_BYTES = 1_500_000   # ~70% context sweet spot

# System/lifecycle tools — skip silently
SKIP_TOOLS = {
    "ExitPlanMode", "EnterPlanMode", "ExitWorktree", "EnterWorktree",
    "TodoWrite", "AskUserQuestion", "Skill", "ToolSearch",
    "Agent", "SendMessage", "NotebookEdit",
}

data_raw = json.load(sys.stdin)
if data_raw.get("tool_name", "") in SKIP_TOOLS:
    sys.exit(0)

# ── Find current session JSONL file ────────────────────────────────────────
session_id = data_raw.get("session_id", "")
session_file = None

if session_id:
    # Search common Claude Code project dirs
    search_dirs = [
        os.path.expanduser("~/.claude/projects"),
    ]
    for base in search_dirs:
        if not os.path.isdir(base):
            continue
        for project_dir in os.listdir(base):
            candidate = os.path.join(base, project_dir, f"{session_id}.jsonl")
            if os.path.isfile(candidate):
                session_file = candidate
                break
        if session_file:
            break

if not session_file:
    sys.exit(0)  # can't find session file — skip silently

session_size = os.path.getsize(session_file)

# ── Load compaction history ─────────────────────────────────────────────────
try:
    with open(COMPACT_LOG) as f:
        compact_state = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    compact_state = {"last_compact_at_bytes": 0, "compact_count": 0}

last_compact_at = compact_state.get("last_compact_at_bytes", 0)

# Only trigger if we've grown by at least 200KB since last suggestion
# (prevents repeated firing at the threshold boundary)
grown_since_last = session_size - last_compact_at

if session_size >= COMPACT_THRESHOLD_BYTES and grown_since_last > 200_000:

    compact_state["last_compact_at_bytes"] = session_size
    compact_state["compact_count"] += 1
    compact_state["last_triggered"] = datetime.now().isoformat()

    with open(COMPACT_LOG, "w") as f:
        json.dump(compact_state, f)

    count = compact_state["compact_count"]
    size_mb = session_size / 1_048_576

    sys.stderr.write(
        f"[guardrail: auto_compact] COMPACT SUGGESTED — session is {size_mb:.1f} MB "
        f"(~70% context, compaction #{count} this session).\n"
        f"Run /compact now to preserve continuity before context degrades.\n"
    )

sys.exit(0)
