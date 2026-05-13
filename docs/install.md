# Installing zkm

## Install from PyPI

```bash
uv tool install zkm    # or: pipx install zkm
```

Verify:

```bash
zkm --version
```

Plugins are **not yet installable via PyPI** — the plugin discovery mechanism is
filesystem-based and is being extended to support pip-installed plugins in a future
release (1.0+). Until then, install plugins via the git-clone path below.

PyPI placeholder packages are reserved for each plugin (`pip install zkm-eml` etc.)
but they ship stub wheels only and do not provide functional plugin code.

---

## Development install

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

## Periodic embed + doctor timer

`zkm embed` runs dense embeddings (GPU-bound, slower) and `zkm doctor` checks
store health. These are too slow for the mbsync post-commit path; run them on a
30-minute systemd timer instead.

Install the user units from `contrib/systemd/`:

```bash
mkdir -p ~/.config/systemd/user
cp ~/src/zkm/contrib/systemd/zkm-embed.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now zkm-embed.timer
```

Verify the timer is active:

```bash
systemctl --user list-timers zkm-embed.timer
```

If your store is not at `~/knowledge`, add a drop-in override:

```bash
systemctl --user edit zkm-embed.service
# Add under [Service]:
# Environment=ZKM_STORE=/path/to/store
```

Logs are queryable via journald:

```bash
journalctl --user -t zkm-embed -n 50
```

To run immediately (outside the timer schedule):

```bash
systemctl --user start zkm-embed.service
```

## mbsync auto-trigger

After installing, follow the hook setup in `plugins/zkm-eml/README.md` to wire up
`zkm convert zkm-eml && zkm index` as a `~/mail` post-commit hook.
