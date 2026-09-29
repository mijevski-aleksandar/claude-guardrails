#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
MODULES_DIR="$REPO_DIR/modules"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

usage() {
  echo ""
  echo "Claude Code Guardrails — Modular Installer"
  echo ""
  echo "Usage:"
  echo "  bash install.sh --list                 List available modules"
  echo "  bash install.sh --install <module>      Install one module by name"
  echo "  bash install.sh --install all           Install every module"
  echo ""
  echo "This installer creates SYMLINKS from ~/.claude/{hooks,agents,commands}/"
  echo "into this repo. The repo is the live source of truth — edit files here"
  echo "and the change applies immediately, no reinstall needed."
  echo ""
}

list_modules() {
  echo "Available modules:"
  echo ""
  for dir in "$MODULES_DIR"/*/; do
    name=$(basename "$dir")
    desc=$(python3 -c "import json; print(json.load(open('$dir/module.json'))['description'])" 2>/dev/null || echo "(no description)")
    echo -e "  ${GREEN}$name${NC}"
    echo "    $desc"
  done
}

install_module() {
  local name="$1"
  local module_dir="$MODULES_DIR/$name"

  if [ ! -d "$module_dir" ]; then
    echo -e "${RED}✗ Unknown module: $name${NC}"
    echo "  Run 'bash install.sh --list' to see available modules."
    exit 1
  fi

  local module_json="$module_dir/module.json"
  local requires_shared
  requires_shared=$(python3 -c "import json; print(json.load(open('$module_json')).get('requires_shared', False))")

  if [ "$requires_shared" = "True" ]; then
    mkdir -p "$CLAUDE_DIR/hooks"
    if [ ! -e "$CLAUDE_DIR/hooks/state_paths.py" ]; then
      ln -sf "$REPO_DIR/shared/state_paths.py" "$CLAUDE_DIR/hooks/state_paths.py"
      echo -e "${GREEN}✓ Linked shared/state_paths.py${NC}"
    fi
  fi

  # Read the install map (source path in module -> target path in ~/.claude) and symlink each
  python3 -c "
import json, os
module_json = json.load(open('$module_json'))
for src_rel, target in module_json.get('install', {}).items():
    print(f'{src_rel}\t{target}')
" | while IFS=$'\t' read -r src_rel target; do
    src_abs="$module_dir/$src_rel"
    target_expanded="${target/#\~/$HOME}"
    target_dir=$(dirname "$target_expanded")
    mkdir -p "$target_dir"
    ln -sf "$src_abs" "$target_expanded"
    echo -e "${GREEN}✓ Linked${NC} $target -> $src_abs"
  done

  # Merge this module's settings fragment, if it has one
  local fragment="$module_dir/settings.fragment.json"
  if [ -f "$fragment" ]; then
    python3 "$REPO_DIR/lib/settings_merge.py" merge "$fragment"
    echo -e "${GREEN}✓ Merged settings for $name${NC}"
  fi

  echo -e "${GREEN}✓ Installed: $name${NC}"
}

install_all() {
  for dir in "$MODULES_DIR"/*/; do
    install_module "$(basename "$dir")"
    echo ""
  done
}

# ── Argument parsing ─────────────────────────────────────────────────────────
case "$1" in
  --list)
    list_modules
    ;;
  --install)
    if [ -z "$2" ]; then
      echo -e "${RED}✗ Missing module name. Usage: bash install.sh --install <module|all>${NC}"
      exit 1
    fi
    if [ "$2" = "all" ]; then
      install_all
    else
      install_module "$2"
    fi
    ;;
  *)
    usage
    ;;
esac
