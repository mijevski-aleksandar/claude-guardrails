#!/usr/bin/env python3
"""
Hook: session_summary.py
Fires: Stop event (when Claude finishes responding / session ends)
Purpose: Block the session from ending cleanly until Claude has written a structured
         handoff summary to ~/.claude/last-session.md. The summary can then be pasted
         at the start of the next session to restore full context instantly.

         Also appends a dated entry to ~/.claude/session-history.md so you build
         up a searchable log of all past sessions over time.

Config:
  SUMMARY_FILE  — where the latest session summary is written (overwritten each time)
  HISTORY_FILE  — append-only log of all session summaries with timestamps
  STEP_LOG      — reads step count to decide if summary is worth generating
  MIN_STEPS     — don't bother summarising very short sessions (default: 5)
"""

import json
import sys
import os
from datetime import datetime

SUMMARY_FILE = os.path.expanduser("~/.claude/last-session.md")
HISTORY_FILE = os.path.expanduser("~/.claude/session-history.md")
STEP_LOG     = "/tmp/claude_step_count.json"
COMPACT_LOG  = "/tmp/claude_compact_log.json"
MIN_STEPS    = 5  # skip summary for very short sessions

# ── Read session metadata ───────────────────────────────────────────────────
try:
    with open(STEP_LOG) as f:
        state = json.load(f)
    steps = state.get("steps", 0)
except (FileNotFoundError, json.JSONDecodeError):
    steps = 0

try:
    with open(COMPACT_LOG) as f:
        compact_state = json.load(f)
    compact_count = compact_state.get("compact_count", 0)
except (FileNotFoundError, json.JSONDecodeError):
    compact_count = 0

# ── Skip trivial sessions ───────────────────────────────────────────────────
if steps < MIN_STEPS:
    sys.exit(0)

# ── Check if summary already written this session ──────────────────────────
# We use a flag file to avoid re-triggering on every Stop event
FLAG_FILE = "/tmp/claude_summary_written.flag"
if os.path.exists(FLAG_FILE):
    sys.exit(0)

# ── Build the prompt that gets sent to Claude ───────────────────────────────
timestamp   = datetime.now().strftime("%Y-%m-%d %H:%M")
date_header = datetime.now().strftime("%Y-%m-%d")

sys.stderr.write(
    f"[guardrail: session_summary] SESSION ENDING — {steps} steps completed"
    + (f", {compact_count} compaction(s) triggered" if compact_count else "")
    + f".\n"
    f"\n"
    f"Before this session closes, you MUST write a handoff summary so the next "
    f"session can resume without losing context.\n"
    f"\n"
    f"Write the following content to the file: {SUMMARY_FILE}\n"
    f"\n"
    f"Use EXACTLY this markdown structure:\n"
    f"\n"
    f"---\n"
    f"# Session Handoff — {timestamp}\n"
    f"\n"
    f"## What Was Worked On\n"
    f"[2-4 sentences describing the overall goal of this session]\n"
    f"\n"
    f"## What Was Completed\n"
    f"[Bullet list of everything that was finished and is working]\n"
    f"\n"
    f"## What Is Incomplete\n"
    f"[Bullet list of tasks started but not finished, with current status]\n"
    f"\n"
    f"## Key Files Changed\n"
    f"[List of file paths that were created or modified, one per line]\n"
    f"\n"
    f"## Important Decisions Made\n"
    f"[Any architectural, naming, or logic decisions that the next session needs to know]\n"
    f"\n"
    f"## How To Continue\n"
    f"[Exact instructions for picking up where we left off — what to do first]\n"
    f"---\n"
    f"\n"
    f"After writing {SUMMARY_FILE}, ALSO append the same content to: {HISTORY_FILE}\n"
    f"(Create the file if it does not exist. Prepend a horizontal rule '---' before each entry.)\n"
    f"\n"
    f"Once both files are written, confirm with: "
    f"'Session summary saved to ~/.claude/last-session.md'"
)

# Write the flag so we don't trigger again on this session
open(FLAG_FILE, "w").close()

sys.exit(2)  # block Stop, force Claude to write the summary first
