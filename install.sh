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

# Copy only the two token-saving hooks
cp "$REPO_DIR/hooks/duplicate_reads.py" "$HOOKS_DIR/"
cp "$REPO_DIR/hooks/retry_loop.py" "$HOOKS_DIR/"
chmod +x "$HOOKS_DIR/duplicate_reads.py" "$HOOKS_DIR/retry_loop.py"
echo -e "${GREEN}✓ Hooks installed${NC}"

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
        # Append if not already present
        existing_matchers = [h.get("matcher") for h in existing_hooks[event]]
        for item in hook_list:
            if item.get("matcher") not in existing_matchers:
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

# Create log cleanup script
cat > "$CLAUDE_DIR/clear-logs.sh" << 'CLEAR'
#!/usr/bin/env bash
rm -f /tmp/claude_read_log.json \
       /tmp/claude_retry_log.json
echo "✓ Claude guardrail logs cleared"
CLEAR
chmod +x "$CLAUDE_DIR/clear-logs.sh"
echo -e "${GREEN}✓ Log cleanup script created at ~/.claude/clear-logs.sh${NC}"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}  Installation complete!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Hooks installed:"
echo "  • duplicate_reads   — blocks 3rd+ read of the same file"
echo "  • retry_loop        — blocks identical tool calls repeated 3×"
echo ""
echo "  Run before each new session:"
echo "  $ ~/.claude/clear-logs.sh"
echo ""
echo "  To uninstall:"
echo "  $ bash uninstall.sh"
echo ""
