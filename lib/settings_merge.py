#!/usr/bin/env python3
"""
Merge or unmerge a module's settings.fragment.json into ~/.claude/settings.json.

Usage:
    python3 settings_merge.py merge   <fragment.json>
    python3 settings_merge.py unmerge <fragment.json>

merge:   adds each hook command from the fragment into the matching event/
         matcher group in settings.json (skips if already present — safe
         to run twice).
unmerge: removes each hook command in the fragment from settings.json,
         and drops any now-empty matcher group or event key.
"""

import json
import os
import sys

SETTINGS_FILE = os.path.expanduser("~/.claude/settings.json")


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    return {}


def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def merge(fragment):
    settings = load_settings()
    hooks = settings.setdefault("hooks", {})

    for event, groups in fragment.items():
        event_groups = hooks.setdefault(event, [])
        for frag_group in groups:
            matcher = frag_group.get("matcher")
            target_group = None
            for g in event_groups:
                if g.get("matcher") == matcher:
                    target_group = g
                    break
            if target_group is None:
                target_group = {"hooks": []}
                if matcher is not None:
                    target_group["matcher"] = matcher
                event_groups.append(target_group)

            existing_commands = {h.get("command", "") for h in target_group["hooks"]}
            for h in frag_group.get("hooks", []):
                if h.get("command", "") not in existing_commands:
                    target_group["hooks"].append(h)

    save_settings(settings)
    print("merged")


def unmerge(fragment):
    settings = load_settings()
    hooks = settings.get("hooks", {})

    for event, groups in fragment.items():
        if event not in hooks:
            continue
        commands_to_remove = {
            h.get("command", "")
            for frag_group in groups
            for h in frag_group.get("hooks", [])
        }

        remaining_groups = []
        for g in hooks[event]:
            g["hooks"] = [
                h for h in g.get("hooks", [])
                if h.get("command", "") not in commands_to_remove
            ]
            if g["hooks"]:
                remaining_groups.append(g)

        if remaining_groups:
            hooks[event] = remaining_groups
        else:
            hooks.pop(event, None)

    settings["hooks"] = hooks
    save_settings(settings)
    print("unmerged")


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("merge", "unmerge"):
        print("Usage: settings_merge.py merge|unmerge <fragment.json>", file=sys.stderr)
        sys.exit(1)

    mode, fragment_path = sys.argv[1], sys.argv[2]
    with open(fragment_path) as f:
        fragment = json.load(f)

    if mode == "merge":
        merge(fragment)
    else:
        unmerge(fragment)


if __name__ == "__main__":
    main()
