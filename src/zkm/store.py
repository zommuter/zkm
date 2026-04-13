"""Knowledge store initialization and path helpers."""

import os
import shutil
import subprocess
from pathlib import Path

_GITIGNORE = """\
.env
.zkm-index/
.embeddings/
*.swp
.DS_Store
.git-lock-push.lock
"""

_GITATTRIBUTES_ANNEX = "originals/** annex.largefiles=anything\n"
_GITATTRIBUTES_LFS = "originals/** filter=lfs diff=lfs merge=lfs -text\n"


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
