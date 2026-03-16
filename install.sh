#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
HOOKS_DIR="$CLAUDE_DIR/hooks"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"
BACKUP_FILE="$CLAUDE_DIR/settings.backup.json"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   Claude Code Guardrails — Installer"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check Python 3
if ! command -v python3 &>/dev/null; then
  echo -e "${RED}✗ Python 3 is required but not found. Please install it first.${NC}"
  exit 1
fi
echo -e "${GREEN}✓ Python 3 found$(python3 --version | awk '{print " ("$2")"}')${NC}"

# Create ~/.claude/hooks if it doesn't exist
mkdir -p "$HOOKS_DIR"
echo -e "${GREEN}✓ Hooks directory ready: $HOOKS_DIR${NC}"

# Copy all hooks
HOOK_FILES=(
  duplicate_reads.py
  retry_loop.py
  context_pressure.py
  auto_compact.py
  failed_tools.py
  compaction_reset.py
  post_compact.py
)

for hook in "${HOOK_FILES[@]}"; do
  cp "$REPO_DIR/hooks/$hook" "$HOOKS_DIR/"
done
chmod +x "${HOOK_FILES[@]/#/$HOOKS_DIR/}"
echo -e "${GREEN}✓ Hooks installed (${#HOOK_FILES[@]} files)${NC}"

# Handle existing settings.json
if [ -f "$SETTINGS_FILE" ]; then
  echo -e "${YELLOW}⚠ Existing settings.json found — backing up to settings.backup.json${NC}"
  cp "$SETTINGS_FILE" "$BACKUP_FILE"

  # Merge hooks into existing settings using Python
  python3 - <<EOF
import json, sys

with open("$SETTINGS_FILE") as f:
    existing = json.load(f)

with open("$REPO_DIR/config/settings.json") as f:
    new_hooks = json.load(f)

# Deep merge hooks
existing_hooks = existing.get("hooks", {})

for event, hook_list in new_hooks.get("hooks", {}).items():
    if event not in existing_hooks:
        existing_hooks[event] = hook_list
    else:
        # Merge hook commands, avoiding duplicates
        existing_commands = set()
        for group in existing_hooks[event]:
            for h in group.get("hooks", []):
                existing_commands.add(h.get("command", ""))

        for item in hook_list:
            new_commands = [
                h for h in item.get("hooks", [])
                if h.get("command", "") not in existing_commands
            ]
            if new_commands:
                # Add to existing matcher group or create new one
                matcher = item.get("matcher")
                matched = False
                for group in existing_hooks[event]:
                    if group.get("matcher") == matcher:
                        group["hooks"].extend(new_commands)
                        matched = True
                        break
                if not matched:
                    existing_hooks[event].append(item)

existing["hooks"] = existing_hooks

with open("$SETTINGS_FILE", "w") as f:
    json.dump(existing, f, indent=2)

print("Merged successfully")
EOF
  echo -e "${GREEN}✓ Hooks merged into existing settings.json${NC}"
else
  cp "$REPO_DIR/config/settings.json" "$SETTINGS_FILE"
  echo -e "${GREEN}✓ settings.json created${NC}"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}  Installation complete!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Hooks installed:"
echo ""
echo "  PreToolUse (fires before every tool call):"
echo "  • duplicate_reads    — warns on 2nd read, blocks 3rd+ (allows re-reads if file changed)"
echo "  • retry_loop         — warns on 2nd identical call, blocks 3rd+"
echo "  • context_pressure   — warns at step 30, critical warning at step 50"
echo "  • auto_compact       — suggests /compact every 25 steps"
echo ""
echo "  PostToolUse (fires after every tool call):"
echo "  • failed_tools       — detects failures, escalates after 3"
echo ""
echo "  PreCompact (fires before context compaction):"
echo "  • compaction_reset   — resets all counters after compaction"
echo ""
echo "  PostCompact (fires after context compaction):"
echo "  • post_compact       — reminds Claude to re-read plan/task files"
echo ""
echo "  State auto-resets per session — no manual cleanup needed."
echo ""
echo "  To uninstall:"
echo "  $ bash uninstall.sh"
echo ""
