#!/usr/bin/env python3
"""
Shared helper: per-session state file paths for guardrail hooks.

Concurrent Claude Code sessions previously shared a single global state file
per hook (e.g. /tmp/claude_retry_log.json), keyed by one "session_id" field.
When a second session's hook fired, it saw a session_id mismatch and reset
the whole file — silently wiping the first session's counters. Namespacing
by session_id removes the collision: each session gets its own file, so
resetting on "session changed" is no longer needed at all.
"""

import os

STATE_ROOT = "/tmp/claude-guardrails"


def get_state_path(hook_name: str, session_id: str) -> str:
    session_id = session_id or "unknown"
    hook_dir = os.path.join(STATE_ROOT, hook_name)
    os.makedirs(hook_dir, exist_ok=True)
    return os.path.join(hook_dir, f"{session_id}.json")
