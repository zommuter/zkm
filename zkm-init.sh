#!/usr/bin/env bash
# zkm init — Initialize the knowledge store
set -euo pipefail

STORE="${ZKM_STORE:-$HOME/knowledge}"
BINARY_BACKEND="${1:-auto}"  # auto | annex | lfs | none

echo "Initializing zkm store at: $STORE"
mkdir -p "$STORE"/{inbox,notes,originals}
cd "$STORE"

if [ -d .git ]; then
    echo "Git repo already exists, skipping init."
    exit 0
fi

git init

# Binary backend selection
if [ "$BINARY_BACKEND" = "auto" ]; then
    if command -v git-annex &>/dev/null; then
        BINARY_BACKEND=annex
    elif command -v git-lfs &>/dev/null; then
        BINARY_BACKEND=lfs
    else
        BINARY_BACKEND=none
    fi
fi

case "$BINARY_BACKEND" in
    annex)
        git annex init "zkm-$(hostname)"
        # Annex tracks originals/ — large files stay out of git proper
        cat > .gitattributes << 'EOF'
originals/** annex.largefiles=anything
EOF
        echo "binary_backend=annex" > .zkm-config
        echo "git-annex initialized. Use 'git annex add' for originals/."
        ;;
    lfs)
        git lfs install --local
        cat > .gitattributes << 'EOF'
originals/** filter=lfs diff=lfs merge=lfs -text
EOF
        echo "binary_backend=lfs" > .zkm-config
        echo "git-lfs initialized."
        ;;
    none)
        touch .gitattributes
        echo "binary_backend=none" > .zkm-config
        echo "WARN: No binary backend. Large files in originals/ will bloat the repo."
        ;;
esac

cat > .gitignore << 'EOF'
.env
.zkm-index/
.embeddings/
*.swp
.DS_Store
EOF

touch .env
for d in inbox notes originals; do touch "$d/.gitkeep"; done

git add -A
git commit -m "feat: initialize zkm knowledge store (binary: $BINARY_BACKEND)"

echo "Done. Export ZKM_STORE=$STORE in your shell profile."
echo "Usage: zkm-init.sh [annex|lfs|none]  (default: auto-detect)"
