#!/usr/bin/env bash
# Auto-tag the repo when pyproject.toml version changes.
# post-commit hook — exits 0 unconditionally; failure warns but never rolls back a commit.
#
# Install via:  bash contrib/install-autotag-hooks.sh

main() {
    # Only act when pyproject.toml was part of the last commit.
    # git show works for both root commits and regular commits;
    # git diff-tree --no-commit-id is silent on the root commit.
    git show --name-only --format='' HEAD 2>/dev/null \
        | grep -q '^pyproject\.toml$' || return 0

    local version
    version=$(grep -m1 '^version\s*=' pyproject.toml 2>/dev/null \
              | sed 's/.*=\s*"\([^"]*\)".*/\1/')
    [[ -n "$version" ]] || return 0

    local tag="v${version}"

    # Idempotent: skip if tag already exists
    git tag --list | grep -qx "$tag" && return 0

    git tag "$tag"
    echo "[autotag] Tagged: $tag"
}

main
exit 0
