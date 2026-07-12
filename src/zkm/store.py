"""Knowledge store initialization and path helpers."""

import os
import shutil
import subprocess
from pathlib import Path

import yaml

_GITIGNORE = """\
.env
.zkm-secrets.yaml
# Ignore most .zkm-index/ contents (bm25.pkl = T4 regenerate; never synced).
# Use wildcard so the negation below can un-ignore the specific annexed artifact.
.zkm-index/*
# embeddings.npz is annexed (T3 — synced-derived); un-ignore so git-annex can track it.
# See docs/meeting-notes/2026-06-24-1350-storage-tiers-restore-sync.md (D3).
!.zkm-index/embeddings.npz
.zkm-state/
*.swp
.DS_Store
*.lock
"""

# Match both the root-level `originals/` dir AND the per-plugin nested CAS object
# dirs (`<subdir>/_objects/`). The root-anchored `originals/**` alone never matched
# nested `_objects/` paths, so CAS binaries bypassed the backend and bloated git
# history — see docs/meeting-notes/2026-06-23-2251-knowledge-git-bloat-annex-anchoring.md.
_GITATTRIBUTES_ANNEX = (
    "originals/** annex.largefiles=anything\n"
    "**/_objects/** annex.largefiles=anything\n"
    # CAS metadata sidecars (`_objects/<aa>/<hash>.json`) are tiny mutable text
    # (`producers[]` grows); keep them in git, not annex — diffable, no key churn.
    # See docs/meeting-notes/2026-06-24-1350-storage-tiers-restore-sync.md (D1).
    "**/_objects/**/*.json annex.largefiles=nothing\n"
    # Embeddings artifact — large non-append binary; annexed (T3, synced-derived).
    # bm25.pkl stays gitignored (T4 — cheap regenerate; no annex rule needed).
    # See docs/meeting-notes/2026-06-24-1350-storage-tiers-restore-sync.md (D3).
    ".zkm-index/embeddings.npz annex.largefiles=anything\n"
)
_GITATTRIBUTES_LFS = (
    "originals/** filter=lfs diff=lfs merge=lfs -text\n"
    "**/_objects/** filter=lfs diff=lfs merge=lfs -text\n"
    "**/_objects/**/*.json !filter !diff !merge text\n"
)


def store_path() -> Path:
    """Return the active store path: $ZKM_STORE or ~/knowledge."""
    raw = os.environ.get("ZKM_STORE", "")
    return Path(raw).expanduser() if raw else Path.home() / "knowledge"


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True)


def _detect_backend() -> str:
    if shutil.which("git-annex"):
        return "annex"
    if shutil.which("git-lfs"):
        return "lfs"
    return "none"


def init_store(path: Path, backend: str = "auto") -> None:
    """
    Initialize the knowledge store at *path*.

    Idempotent: if the store is already a git repo, exits immediately.
    backend: 'auto' | 'annex' | 'lfs' | 'none'
    """
    path = path.expanduser().resolve()

    for subdir in ("inbox", "notes", "originals"):
        (path / subdir).mkdir(parents=True, exist_ok=True)

    if (path / ".git").exists():
        print(f"Store already initialized at {path}. Nothing to do.")
        return

    print(f"Initializing zkm store at: {path}")

    _git(["init"], cwd=path)

    if backend == "auto":
        backend = _detect_backend()

    if backend == "annex":
        _git(["annex", "init", f"zkm-{_hostname()}"], cwd=path)
        # Enable tracking of dotfile paths (e.g. .zkm-index/embeddings.npz).
        # Without this flag, git-annex silently adds dotfiles to git regardless
        # of annex.largefiles gitattributes — see D3 in the storage-tiers meeting note.
        _git(["annex", "config", "--set", "annex.dotfiles", "true"], cwd=path)
        (path / ".gitattributes").write_text(_GITATTRIBUTES_ANNEX)
    elif backend == "lfs":
        _git(["lfs", "install", "--local"], cwd=path)
        (path / ".gitattributes").write_text(_GITATTRIBUTES_LFS)
    else:
        (path / ".gitattributes").write_text("")
        if backend != "none":
            print(f"WARN: unknown backend '{backend}', falling back to none.")
        print("WARN: No binary backend. Large files in originals/ will bloat the repo.")

    (path / ".zkm-config").write_text(f"binary_backend={backend}\n")
    cfg_data = {"core": {"binary_backend": backend}}
    (path / "zkm-config.yaml").write_text(yaml.dump(cfg_data, default_flow_style=False))
    (path / ".gitignore").write_text(_GITIGNORE)
    (path / ".env").touch()

    for subdir in ("inbox", "notes", "originals"):
        (path / subdir / ".gitkeep").touch()

    _git(["add", "-A"], cwd=path)
    _git(
        ["commit", "-m", f"feat: initialize zkm knowledge store (binary: {backend})"],
        cwd=path,
    )

    print(f"\nDone. Add to your shell profile:\n  export ZKM_STORE={path}")
    print("\nNext steps:")
    print("  zkm plugin add <git-url>   # install a converter plugin")
    print("  zkm convert <plugin>       # run a plugin")
    print("  zkm index                  # build search index")


def _hostname() -> str:
    import socket

    return socket.gethostname()


def read_zkm_config(store: Path) -> dict[str, str]:
    """Parse binary_backend from the store. Returns {} if absent."""
    new_cfg = store / "zkm-config.yaml"
    if new_cfg.exists():
        from zkm.config import load_config
        cfg = load_config(store)
        backend = cfg.core_value("binary_backend")
        return {"binary_backend": backend} if backend else {}
    # Legacy fallback
    cfg_path = store / ".zkm-config"
    if not cfg_path.exists():
        return {}
    result: dict[str, str] = {}
    for line in cfg_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, _, v = line.partition("=")
            result[k.strip()] = v.strip()
    return result


def _git_output(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def remote_add(store: Path, name: str, url: str) -> None:
    _git(["remote", "add", name, url], cwd=store)


def remote_list(store: Path) -> str:
    return _git_output(["remote", "-v"], cwd=store)


def clone_store(url: str, dest: Path) -> str:
    """Clone a store and re-initialise its binary backend. Returns the backend name."""
    dest = dest.resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    _git(["clone", url, str(dest)], cwd=dest.parent)
    cfg = read_zkm_config(dest)
    backend = cfg.get("binary_backend", "none")
    if backend == "annex":
        _git(["annex", "init", f"zkm-{_hostname()}"], cwd=dest)
    elif backend == "lfs":
        _git(["lfs", "install", "--local"], cwd=dest)
    return backend


def _resolve_push_remote(store: Path) -> str:
    """Resolve a default remote for an annex *content* push.

    ``git annex copy --to`` needs an explicit target remote. Prefer the current
    branch's tracking remote, else ``origin`` when configured. Raise a clear
    error otherwise so the user knows to pass a remote or ``--no-content``.
    """
    try:
        branch = _git_output(["rev-parse", "--abbrev-ref", "HEAD"], cwd=store).strip()
        tracking = _git_output(
            ["config", "--get", f"branch.{branch}.remote"], cwd=store
        ).strip()
        if tracking:
            return tracking
    except subprocess.CalledProcessError:
        pass
    try:
        remotes = _git_output(["remote"], cwd=store).split()
    except subprocess.CalledProcessError:
        remotes = []
    if "origin" in remotes:
        return "origin"
    raise ValueError(
        "zkm push: no remote specified and no default could be resolved "
        "(no tracking remote, no 'origin'). Pass a remote name explicitly, "
        "or use --no-content to push refs only."
    )


def push_store(store: Path, remote: str | None = None, *, content: bool = True) -> None:
    """Push store commits (and, by default, annex content) to a remote.

    One-directional *durability* push (never a bidirectional sync): git refs go
    up and, for the annex backend, content is uploaded with correct location
    tracking. A diverged remote makes the ref push fail loudly rather than
    silently merging remote history back (see the 2026-07-12 D2 meeting note).
    """
    backend = read_zkm_config(store).get("binary_backend", "none")
    if backend == "annex":
        # Content via `git annex copy --to` (push-only, records location);
        # refs via `git annex sync --no-pull --no-content` (git-annex-branch
        # aware, one-directional). `copy --to` requires an explicit target.
        if content:
            target = remote or _resolve_push_remote(store)
            _git(["annex", "copy", "--to", target], store)
            _git(["annex", "sync", "--no-pull", "--no-content", target], store)
            return
        args = ["annex", "sync", "--no-pull", "--no-content"]
        if remote:
            args.append(remote)
    elif backend == "lfs":
        args = ["lfs", "push", "--all"]
        if remote:
            args.append(remote)
    else:
        args = ["push"]
        if remote:
            args.append(remote)
    _git(args, store)


def pull_store(store: Path, remote: str | None = None, *, content: bool = False) -> None:
    """Pull store commits (and optionally annex content) from a remote."""
    backend = read_zkm_config(store).get("binary_backend", "none")
    if backend == "annex":
        args = ["annex", "sync"]
        if content:
            args.append("--content")
        if remote:
            args.append(remote)
    elif backend == "lfs":
        args = ["lfs", "pull"]
        if remote:
            args.append(remote)
    else:
        args = ["pull", "--rebase"]
        if remote:
            args.append(remote)
    _git(args, store)
