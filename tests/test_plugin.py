"""Tests for plugin registry + notes sample plugin end-to-end."""

from __future__ import annotations

from pathlib import Path

import pytest

from zkm.convert import (
    add_plugin,
    find_plugin,
    list_plugins,
    load_env,
    remove_plugin,
    run_convert,
)
from zkm.store import init_store

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def isolated_plugins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect plugins_dir() to a temp directory."""
    pdir = tmp_path / "plugins"
    pdir.mkdir()
    monkeypatch.setenv("ZKM_PLUGINS_DIR", str(pdir))
    return pdir


@pytest.fixture()
def store(tmp_path: Path) -> Path:
    sdir = tmp_path / "store"
    init_store(sdir, backend="none")
    return sdir


_EXAMPLES_NOTES = _REPO_ROOT / "examples" / "zkm-notes"


@pytest.fixture()
def notes_plugin_dir() -> Path:
    """Path to the bundled sample plugin at examples/zkm-notes/."""
    if not (_EXAMPLES_NOTES / "plugin.yaml").exists():
        pytest.skip(f"Bundled sample plugin not found at {_EXAMPLES_NOTES}")
    return _EXAMPLES_NOTES


# ---------------------------------------------------------------------------
# Registry operations
# ---------------------------------------------------------------------------


def test_list_plugins_empty(isolated_plugins: Path) -> None:
    assert list_plugins() == []


def test_add_local_plugin(isolated_plugins: Path, notes_plugin_dir: Path) -> None:
    plugin = add_plugin(str(notes_plugin_dir))
    assert plugin.name == "notes"
    assert plugin.version == "0.1.0"
    dest = isolated_plugins / "zkm-notes"
    assert dest.is_symlink()
    assert dest.resolve() == notes_plugin_dir.resolve()


def test_add_duplicate_raises(isolated_plugins: Path, notes_plugin_dir: Path) -> None:
    add_plugin(str(notes_plugin_dir))
    with pytest.raises(FileExistsError):
        add_plugin(str(notes_plugin_dir))


def test_list_plugins_after_add(isolated_plugins: Path, notes_plugin_dir: Path) -> None:
    add_plugin(str(notes_plugin_dir))
    plugins = list_plugins()
    assert len(plugins) == 1
    assert plugins[0].name == "notes"


def test_find_plugin(isolated_plugins: Path, notes_plugin_dir: Path) -> None:
    add_plugin(str(notes_plugin_dir))
    assert find_plugin("notes") is not None
    assert find_plugin("nonexistent") is None


def test_remove_plugin(isolated_plugins: Path, notes_plugin_dir: Path) -> None:
    add_plugin(str(notes_plugin_dir))
    remove_plugin("notes")
    assert list_plugins() == []


def test_remove_nonexistent_raises(isolated_plugins: Path) -> None:
    with pytest.raises(LookupError):
        remove_plugin("notes")


# ---------------------------------------------------------------------------
# .env loading
# ---------------------------------------------------------------------------


def test_load_env(store: Path) -> None:
    (store / ".env").write_text(
        "# comment\nFOO=bar\nBAZ=hello world\nQUOTED=\"val\"\n"
    )
    env = load_env(store)
    assert env["FOO"] == "bar"
    assert env["BAZ"] == "hello world"
    assert env["QUOTED"] == "val"


# ---------------------------------------------------------------------------
# End-to-end: notes plugin
# ---------------------------------------------------------------------------


def test_notes_convert_basic(
    isolated_plugins: Path, store: Path, tmp_path: Path, notes_plugin_dir: Path
) -> None:
    import frontmatter

    src = tmp_path / "src_notes"
    src.mkdir()
    (src / "hello.txt").write_text("Hello, world!")
    (src / "diary.md").write_text("# Entry\nToday was fine.")

    add_plugin(str(notes_plugin_dir))
    created = run_convert("notes", store, extra_env={"NOTES_SOURCE_DIR": str(src)})

    assert len(created) == 2
    for p in created:
        assert p.exists()
        post = frontmatter.load(p)
        assert post.metadata["source"] == "notes"
        assert "sha256" in post.metadata
        assert "date" in post.metadata


def test_notes_convert_idempotent(
    isolated_plugins: Path, store: Path, tmp_path: Path, notes_plugin_dir: Path
) -> None:
    src = tmp_path / "src_notes"
    src.mkdir()
    (src / "note.txt").write_text("Some note content")

    add_plugin(str(notes_plugin_dir))
    first = run_convert("notes", store, extra_env={"NOTES_SOURCE_DIR": str(src)})
    second = run_convert("notes", store, extra_env={"NOTES_SOURCE_DIR": str(src)})

    assert len(first) == 1
    assert len(second) == 0


def test_notes_convert_preserves_frontmatter(
    isolated_plugins: Path, store: Path, tmp_path: Path, notes_plugin_dir: Path
) -> None:
    import frontmatter

    src = tmp_path / "src_notes"
    src.mkdir()
    (src / "existing.md").write_text(
        "---\ntitle: My Note\ntags: [personal]\n---\nBody text."
    )

    add_plugin(str(notes_plugin_dir))
    created = run_convert("notes", store, extra_env={"NOTES_SOURCE_DIR": str(src)})

    assert len(created) == 1
    post = frontmatter.load(created[0])
    assert post.metadata.get("title") == "My Note"
    assert "personal" in post.metadata.get("tags", [])


def test_notes_convert_missing_config_raises(
    isolated_plugins: Path, store: Path, notes_plugin_dir: Path
) -> None:
    add_plugin(str(notes_plugin_dir))
    with pytest.raises(ValueError, match="NOTES_SOURCE_DIR"):
        run_convert("notes", store)


def test_convert_unknown_plugin_raises(isolated_plugins: Path, store: Path) -> None:
    with pytest.raises(LookupError):
        run_convert("nonexistent", store)
