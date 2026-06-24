"""Smoke tests for zkm.store.init_store."""

import subprocess
from pathlib import Path

import pytest

from zkm.store import init_store


def test_init_creates_structure(tmp_path: Path) -> None:
    init_store(tmp_path, backend="none")

    assert (tmp_path / ".git").is_dir()
    assert (tmp_path / ".zkm-config").read_text().strip() == "binary_backend=none"
    assert (tmp_path / ".gitignore").exists()
    assert (tmp_path / ".env").exists()
    for d in ("inbox", "notes", "originals"):
        assert (tmp_path / d).is_dir()
        assert (tmp_path / d / ".gitkeep").exists()


def test_init_makes_initial_commit(tmp_path: Path) -> None:
    init_store(tmp_path, backend="none")

    result = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "initialize zkm knowledge store" in result.stdout


def test_init_idempotent(tmp_path: Path) -> None:
    init_store(tmp_path, backend="none")
    # Second call must not raise and must not create a second commit
    init_store(tmp_path, backend="none")

    result = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert len(result.stdout.strip().splitlines()) == 1


def test_init_auto_backend_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Force auto-detect to find nothing → should fall back to 'none'
    monkeypatch.setattr("shutil.which", lambda _: None)
    init_store(tmp_path, backend="auto")
    assert "binary_backend=none" in (tmp_path / ".zkm-config").read_text()


def test_gitattributes_annexes_nested_cas_objects(tmp_path: Path) -> None:
    """Nested CAS `<subdir>/_objects/` paths must resolve to the annex rule.

    Regression: the template was root-anchored `originals/**`, so per-plugin
    nested `_objects/` originals bypassed annex and bloated git history
    (see docs/meeting-notes/2026-06-23-2251-knowledge-git-bloat-annex-anchoring.md).
    """
    from zkm.store import _GITATTRIBUTES_ANNEX

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / ".gitattributes").write_text(_GITATTRIBUTES_ANNEX)

    for rel in (
        "originals/foo",
        "chat/whatsapp/abc/originals/_objects/aa/bbbb",
        "mail/_objects/aa/bbbb",
    ):
        out = subprocess.run(
            ["git", "check-attr", "annex.largefiles", "--", rel],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert "anything" in out, f"{rel} not annexed: {out!r}"


def test_gitattributes_lfs_covers_nested_cas_objects(tmp_path: Path) -> None:
    """Same anchoring fix must apply to the git-lfs template."""
    from zkm.store import _GITATTRIBUTES_LFS

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / ".gitattributes").write_text(_GITATTRIBUTES_LFS)

    out = subprocess.run(
        ["git", "check-attr", "filter", "--", "chat/whatsapp/abc/_objects/aa/bbbb"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "lfs" in out, f"nested _objects not lfs-filtered: {out!r}"


def _largefiles(tmp_path: Path, rel: str) -> str:
    return subprocess.run(
        ["git", "check-attr", "annex.largefiles", "--", rel],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def test_gitattributes_keeps_cas_json_sidecars_in_git(tmp_path: Path) -> None:
    """CAS-json metadata sidecars (`_objects/**/*.json`) stay in git, not annex.

    The `**/_objects/**` rule annexes by path, sweeping tiny mutable metadata
    sidecars (`sha256`/`producers[]`) into annex; a later json exception keeps
    them in git (diffable, no key churn on `producers[]` growth).
    See docs/meeting-notes/2026-06-24-1350-storage-tiers-restore-sync.md (D1).
    """
    from zkm.store import _GITATTRIBUTES_ANNEX

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / ".gitattributes").write_text(_GITATTRIBUTES_ANNEX)

    # binary CAS objects (no .json) stay annexed
    for rel in ("mail/_objects/aa/bbbb", "chat/whatsapp/x/originals/_objects/aa/bbbb"):
        assert "anything" in _largefiles(tmp_path, rel), f"{rel} not annexed"
    # nested json metadata sidecars are forced to git (largefiles=nothing)
    for rel in (
        "mail/_objects/aa/bbbb.json",
        "chat/whatsapp/x/originals/_objects/aa/bbbb.json",
    ):
        out = _largefiles(tmp_path, rel)
        assert "anything" not in out, f"{rel} wrongly annexed: {out!r}"
        assert "nothing" in out, f"{rel} not forced to git: {out!r}"


def test_gitattributes_lfs_keeps_cas_json_in_git(tmp_path: Path) -> None:
    """The json exception applies to the git-lfs template too (parity)."""
    from zkm.store import _GITATTRIBUTES_LFS

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / ".gitattributes").write_text(_GITATTRIBUTES_LFS)

    out = subprocess.run(
        ["git", "check-attr", "filter", "--", "mail/_objects/aa/bbbb.json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "lfs" not in out, f"json wrongly lfs-filtered: {out!r}"


class TestEnsureGitignorePatterns:
    def test_appends_missing(self, tmp_path: Path) -> None:
        from zkm.cli import _ensure_gitignore_patterns

        gi = tmp_path / ".gitignore"
        gi.write_text("*.swp\n")
        _ensure_gitignore_patterns(tmp_path, ["inbox/foo.db", "inbox/foo.db.crypt15"])
        lines = gi.read_text().splitlines()
        assert "inbox/foo.db" in lines
        assert "inbox/foo.db.crypt15" in lines

    def test_skips_already_present(self, tmp_path: Path) -> None:
        from zkm.cli import _ensure_gitignore_patterns

        gi = tmp_path / ".gitignore"
        gi.write_text("*.swp\ninbox/foo.db\n")
        _ensure_gitignore_patterns(tmp_path, ["inbox/foo.db"])
        assert gi.read_text().count("inbox/foo.db") == 1

    def test_creates_gitignore_if_absent(self, tmp_path: Path) -> None:
        from zkm.cli import _ensure_gitignore_patterns

        _ensure_gitignore_patterns(tmp_path, ["inbox/foo.db"])
        assert "inbox/foo.db" in (tmp_path / ".gitignore").read_text()
