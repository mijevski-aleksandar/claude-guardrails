#!/usr/bin/env bash
set -e

CLAUDE_DIR="$HOME/.claude"
HOOKS_DIR="$CLAUDE_DIR/hooks"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"
BACKUP_FILE="$CLAUDE_DIR/settings.backup.json"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   Claude Code Guardrails — Uninstaller"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

HOOK_FILES=("duplicate_reads.py" "retry_loop.py" "compaction_reset.py")

for hook in "${HOOK_FILES[@]}"; do
  if [ -f "$HOOKS_DIR/$hook" ]; then
    rm "$HOOKS_DIR/$hook"
    echo -e "${GREEN}✓ Removed $hook${NC}"
  fi
done

# Restore backup settings if it exists
if [ -f "$BACKUP_FILE" ]; then
  cp "$BACKUP_FILE" "$SETTINGS_FILE"
  rm "$BACKUP_FILE"
  echo -e "${GREEN}✓ Restored original settings.json from backup${NC}"
else
  # Remove hooks section from settings.json
  python3 - <<EOF
import json
try:
    with open("$SETTINGS_FILE") as f:
        settings = json.load(f)
    settings.pop("hooks", None)
    with open("$SETTINGS_FILE", "w") as f:
        json.dump(settings, f, indent=2)
    print("Removed hooks from settings.json")
except:
    print("settings.json not found or already clean")
EOF
  echo -e "${GREEN}✓ Hooks removed from settings.json${NC}"
fi

# Clear temp logs
rm -f /tmp/claude_read_log.json /tmp/claude_retry_log.json
echo -e "${GREEN}✓ Temp logs cleared${NC}"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}  Uninstall complete.${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
