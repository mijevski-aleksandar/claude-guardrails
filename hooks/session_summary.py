#!/usr/bin/env python3
"""
Hook: session_summary.py
Fires: PreCompact (after pre_compact.py has written claude_handoff.json)

Purpose: Render the handoff JSON written by pre_compact.py as markdown into
         ~/.claude/last-session.md (overwritten) and append the same entry to
         ~/.claude/session-history.md (append-only log).

Why this is a Python script, not a stderr prompt to Claude:
         The previous version asked Claude (via stderr) to write the summary
         itself during PreCompact. That never worked — PreCompact fires
         immediately before context wipe, so Claude has no turn to act on the
         message. This version writes the file directly, zero LLM cost,
         guaranteed to run.

Config:
  HANDOFF_FILE  — JSON written by pre_compact.py (this hook reads it)
  SUMMARY_FILE  — markdown summary, overwritten each compact
  HISTORY_FILE  — append-only log
  MIN_STEPS     — skip very short sessions (default: 5)
"""

import json
import sys
import os
from datetime import datetime

HANDOFF_FILE = "/tmp/claude_handoff.json"
SUMMARY_FILE = os.path.expanduser("~/.claude/last-session.md")
HISTORY_FILE = os.path.expanduser("~/.claude/session-history.md")
STEP_LOG     = "/tmp/claude_step_count.json"
MIN_STEPS    = 5

try:
    data = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    data = {}
session_id = data.get("session_id", "unknown")

# Per-session flag prevents re-fire on multi-compact sessions
FLAG_FILE = f"/tmp/claude_summary_{session_id}.flag"
if os.path.exists(FLAG_FILE):
    sys.exit(0)

# Skip trivial sessions
try:
    with open(STEP_LOG) as f:
        steps = json.load(f).get("steps", 0)
except (FileNotFoundError, json.JSONDecodeError):
    steps = 0
if steps < MIN_STEPS:
    sys.exit(0)

# Load the handoff produced by pre_compact.py
if not os.path.isfile(HANDOFF_FILE):
    sys.exit(0)
try:
    with open(HANDOFF_FILE) as f:
        handoff = json.load(f)
except (json.JSONDecodeError, ValueError):
    sys.exit(0)

timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")


def render_markdown(handoff: dict, steps: int, timestamp: str) -> str:
    parts = [f"---", f"# Session Handoff — {timestamp}", ""]

    parts.append(f"**Session:** `{handoff.get('session_id', 'unknown')}`  ")
    parts.append(f"**Steps:** {steps}  ")
    parts.append(f"**Total tool calls:** {handoff.get('total_tool_calls', 0)}")
    parts.append("")

    if handoff.get("active_plan"):
        parts.append(f"## Active Plan")
        parts.append(f"`{handoff['active_plan']}`")
        parts.append("")

    modified = handoff.get("files_modified", []) or []
    if modified:
        parts.append("## Files Modified")
        for f in modified:
            parts.append(f"- `{f.get('path', '?')}` (via {f.get('tool', '?')})")
        parts.append("")

    most_read = handoff.get("most_read_files", []) or []
    if most_read:
        parts.append("## Most-Read Files")
        for f in most_read:
            parts.append(f"- {f.get('reads', 0)}× `{f.get('path', '?')}`")
        parts.append("")

    last_tools = handoff.get("last_tool_calls", []) or []
    if last_tools:
        parts.append("## Last Tool Calls")
        for t in last_tools:
            parts.append(f"- {t.get('tool', '?')}")
        parts.append("")

    last_bash = handoff.get("last_bash", []) or []
    if last_bash:
        parts.append("## Last Bash Commands")
        for b in last_bash:
            line = (b if isinstance(b, str) else str(b)).strip().splitlines()[0][:120]
            parts.append(f"- `{line}`")
        parts.append("")

    findings = handoff.get("key_findings", []) or []
    if findings:
        parts.append("## Key Findings (last 3 assistant statements)")
        for fnd in findings:
            snippet = (fnd or "").strip().replace("\n", " ")[:300]
            parts.append(f"- {snippet}")
        parts.append("")

    do_not_reread = handoff.get("do_not_reread", []) or []
    if do_not_reread:
        parts.append("## Do Not Re-Read (already read 2+ times)")
        for p in do_not_reread:
            parts.append(f"- `{p}`")
        parts.append("")

    parts.append("## How To Continue")
    if handoff.get("active_plan"):
        parts.append(f"Re-read the **Brief** of the active plan first via `Read offset=1 limit=80`:")
        parts.append(f"  `{handoff['active_plan']}`")
    elif modified:
        parts.append("Pick up by reviewing the most recently modified file:")
        parts.append(f"  `{modified[-1].get('path', '?')}`")
    else:
        parts.append("Review last tool calls above to determine resumption point.")
    parts.append("")
    parts.append("---")
    parts.append("")

    return "\n".join(parts)


markdown = render_markdown(handoff, steps, timestamp)

try:
    with open(SUMMARY_FILE, "w") as f:
        f.write(markdown)
except OSError as e:
    sys.stderr.write(f"[guardrail: session_summary] Failed to write {SUMMARY_FILE}: {e}\n")
    sys.exit(0)

try:
    with open(HISTORY_FILE, "a") as f:
        f.write(markdown)
except OSError as e:
    sys.stderr.write(f"[guardrail: session_summary] Wrote summary, failed to append history: {e}\n")

# Mark this session as summarised
try:
    open(FLAG_FILE, "w").close()
except OSError:
    pass

sys.stderr.write(
    f"[guardrail: session_summary] Wrote {SUMMARY_FILE} ({steps} steps).\n"
)
sys.exit(0)
