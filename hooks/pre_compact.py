#!/usr/bin/env python3
"""
Hook: pre_compact.py
Fires: PreCompact (before context compaction runs)
Purpose: Scrape the current session JSONL to build a structured handoff file.
         The handoff is injected back by post_compact.py so Claude resumes
         with full task context instead of re-exploring from scratch.

Handoff captures (zero LLM cost — pure file scraping):
  - Files written/edited this session
  - Last 5 tool calls (what Claude was doing immediately before compact)
  - Active plan file (if any)
  - Session stats
"""

import json
import sys
import os
from datetime import datetime
from collections import defaultdict

HANDOFF_FILE = "/tmp/claude_handoff.json"
PLANS_DIR    = os.path.expanduser("~/.claude/plans/")

data = json.load(sys.stdin)
session_id = data.get("session_id", "")

# ── Find session JSONL ──────────────────────────────────────────────────────
session_file = None
if session_id:
    for project_dir in os.listdir(os.path.expanduser("~/.claude/projects")):
        candidate = os.path.join(
            os.path.expanduser("~/.claude/projects"), project_dir,
            f"{session_id}.jsonl"
        )
        if os.path.isfile(candidate):
            session_file = candidate
            break

# ── Find active plan file ───────────────────────────────────────────────────
active_plan = None
if os.path.isdir(PLANS_DIR):
    plans = [
        f for f in os.listdir(PLANS_DIR)
        if f.endswith(".md") and os.path.isfile(os.path.join(PLANS_DIR, f))
    ]
    if plans:
        plans.sort(key=lambda f: os.path.getmtime(os.path.join(PLANS_DIR, f)), reverse=True)
        active_plan = os.path.join(PLANS_DIR, plans[0])

# ── Scrape session file ─────────────────────────────────────────────────────
files_written  = []   # (path, tool) tuples
files_read     = defaultdict(int)
last_tool_calls = []  # last N tool calls for context
bash_commands  = []   # last bash commands

if session_file:
    try:
        with open(session_file) as f:
            lines = f.readlines()

        for line in lines:
            try:
                obj = json.loads(line)
            except Exception:
                continue

            if obj.get("type") != "assistant":
                continue

            content = obj.get("message", {}).get("content", [])
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue

                tname  = block.get("name", "")
                inputs = block.get("input", {})

                if tname in ("Write", "Edit", "NotebookEdit"):
                    fp = inputs.get("file_path", inputs.get("path", ""))
                    if fp:
                        files_written.append((fp, tname))

                elif tname == "Read":
                    fp = inputs.get("file_path", "")
                    if fp:
                        files_read[fp] += 1

                elif tname == "Bash":
                    cmd = inputs.get("command", "")
                    if cmd:
                        bash_commands.append(cmd[:120])

                last_tool_calls.append({"tool": tname, "input_keys": list(inputs.keys())})

    except Exception:
        pass  # graceful degradation — don't block compaction

# Deduplicate files_written, keep order
seen = set()
unique_written = []
for fp, tool in reversed(files_written):
    if fp not in seen:
        seen.add(fp)
        unique_written.append({"path": fp, "tool": tool})
unique_written.reverse()

# ── Build handoff ───────────────────────────────────────────────────────────
handoff = {
    "created_at":    datetime.now().isoformat(),
    "session_id":    session_id,
    "active_plan":   active_plan,
    "files_modified": unique_written[-10:],   # last 10 modified files
    "most_read_files": sorted(
        [{"path": p, "reads": c} for p, c in files_read.items()],
        key=lambda x: -x["reads"]
    )[:5],
    "last_tool_calls": last_tool_calls[-5:],  # last 5 tool calls
    "last_bash":       bash_commands[-3:],    # last 3 bash commands
    "total_tool_calls": len(last_tool_calls),
}

with open(HANDOFF_FILE, "w") as f:
    json.dump(handoff, f, indent=2)

sys.stderr.write(
    f"[guardrail: pre_compact] Handoff saved — "
    f"{len(unique_written)} files modified, "
    f"{len(last_tool_calls)} total tool calls this session.\n"
)
sys.exit(0)
