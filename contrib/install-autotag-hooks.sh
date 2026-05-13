#!/usr/bin/env bash
# Install (or uninstall) the auto-tag post-commit hook in all zkm repos.
# Usage:
#   bash contrib/install-autotag-hooks.sh            # install
#   bash contrib/install-autotag-hooks.sh --uninstall

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HOOK_SRC="$SCRIPT_DIR/hooks/post-commit-autotag.sh"
HOOK_NAME="post-commit"

REPOS=(
    "$ROOT"
    "$ROOT/plugins/zkm-eml"
    "$ROOT/plugins/zkm-ner"
    "$ROOT/plugins/zkm-notmuch"
    "$ROOT/plugins/zkm-pdf"
    "$ROOT/plugins/zkm-photo"
    "$ROOT/plugins/zkm-scan"
)

UNINSTALL=false
[[ "${1:-}" == "--uninstall" ]] && UNINSTALL=true

for repo in "${REPOS[@]}"; do
    hook_path="$repo/.git/hooks/$HOOK_NAME"

    if $UNINSTALL; then
        if [[ -L "$hook_path" && "$(readlink "$hook_path")" == "$HOOK_SRC" ]]; then
            rm "$hook_path"
            echo "Removed: $hook_path"
        fi
        continue
    fi

    if [[ -e "$hook_path" && ! -L "$hook_path" ]]; then
        echo "SKIP (not a symlink, chain manually): $hook_path"
        continue
    fi
    if [[ -L "$hook_path" && "$(readlink "$hook_path")" != "$HOOK_SRC" ]]; then
        echo "SKIP (points elsewhere, chain manually): $hook_path"
        continue
    fi

    ln -sf "$HOOK_SRC" "$hook_path"
    echo "Installed: $hook_path"
done
