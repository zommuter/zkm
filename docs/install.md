# Installing zkm

For development with auto-triggers (mbsync hook, Syncthing watchers, etc.) install
the editable CLI so source changes are picked up live without reinstalling:

```bash
uv tool install --editable ~/src/zkm
uv tool update-shell   # ensures ~/.local/bin is on PATH
```

Verify:

```bash
which zkm   # → ~/.local/bin/zkm
```

## Dirty-tree guard

The editable install activates a safety guard in `src/zkm/devcheck.py`. State-modifying
commands (`convert`, `index`, `rm`, `gc`) refuse to run when the zkm source tree (or the
invoked plugin's tree) has uncommitted changes. This prevents WIP code from corrupting
the live store via an auto-trigger.

To bypass — for tests or deliberate dev runs:

```bash
ZKM_BYPASS_DIRTY_CHECK=1 zkm convert zkm-eml
```

Do not set `ZKM_BYPASS_DIRTY_CHECK` in your shell profile. It is an explicit opt-in
escape hatch, not a default. Non-editable installs (`uv tool install` without
`--editable`) skip the guard automatically because there is no `.git/` ancestor to check.

## mbsync auto-trigger

After installing, follow the hook setup in `plugins/zkm-eml/README.md` to wire up
`zkm convert zkm-eml && zkm index` as a `~/mail` post-commit hook.
