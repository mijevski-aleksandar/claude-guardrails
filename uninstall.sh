#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
MODULES_DIR="$REPO_DIR/modules"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

usage() {
  echo ""
  echo "Claude Code Guardrails — Modular Uninstaller"
  echo ""
  echo "Usage:"
  echo "  bash uninstall.sh --uninstall <module>      Remove one module by name"
  echo "  bash uninstall.sh --uninstall all            Remove every module"
  echo ""
}

uninstall_module() {
  local name="$1"
  local module_dir="$MODULES_DIR/$name"

  if [ ! -d "$module_dir" ]; then
    echo -e "${RED}✗ Unknown module: $name${NC}"
    exit 1
  fi

  local module_json="$module_dir/module.json"

  # Remove symlinks this module created
  python3 -c "
import json
module_json = json.load(open('$module_json'))
for src_rel, target in module_json.get('install', {}).items():
    print(target)
" | while read -r target; do
    target_expanded="${target/#\~/$HOME}"
    if [ -L "$target_expanded" ]; then
      rm "$target_expanded"
      echo -e "${GREEN}✓ Removed symlink${NC} $target"
    fi
  done

  # Unmerge settings fragment, if any
  local fragment="$module_dir/settings.fragment.json"
  if [ -f "$fragment" ]; then
    python3 "$REPO_DIR/lib/settings_merge.py" unmerge "$fragment"
    echo -e "${GREEN}✓ Unmerged settings for $name${NC}"
  fi

  echo -e "${GREEN}✓ Uninstalled: $name${NC}"
}

uninstall_all() {
  for dir in "$MODULES_DIR"/*/; do
    uninstall_module "$(basename "$dir")"
    echo ""
  done
  # Only remove the shared symlink once nothing references it
  if [ -L "$CLAUDE_DIR/hooks/state_paths.py" ]; then
    rm "$CLAUDE_DIR/hooks/state_paths.py"
    echo -e "${GREEN}✓ Removed shared/state_paths.py link${NC}"
  fi
}

case "$1" in
  --uninstall)
    if [ -z "$2" ]; then
      echo -e "${RED}✗ Missing module name. Usage: bash uninstall.sh --uninstall <module|all>${NC}"
      exit 1
    fi
    if [ "$2" = "all" ]; then
      uninstall_all
    else
      uninstall_module "$2"
    fi
    ;;
  *)
    usage
    ;;
esac
