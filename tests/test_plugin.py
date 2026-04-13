"""Tests for plugin registry + notes sample plugin end-to-end."""

from __future__ import annotations

import textwrap
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


@pytest.fixture()
def notes_plugin_dir(tmp_path: Path) -> Path:
    """Build a self-contained notes plugin directory in tmp_path.

    Mirrors examples/zkm-notes but is created inline so tests don't depend
    on untracked files being visible inside subprocesses.
    """
    plugin_dir = tmp_path / "zkm-notes"
    plugin_dir.mkdir()

    (plugin_dir / "plugin.yaml").write_text(textwrap.dedent("""\
        name: notes
        version: 0.1.0
        description: Import plain .txt/.md files from a directory as notes
        license: MIT
        creates_dirs:
          - notes
        config:
          NOTES_SOURCE_DIR:
            required: true
            description: Directory to scan recursively for .txt/.md files
          NOTES_DEFAULT_TAGS:
            required: false
            default: ""
            description: Comma-separated tags to add to every imported note
    """))

    (plugin_dir / "convert.py").write_text(textwrap.dedent("""\
        from __future__ import annotations
        import hashlib, re
        from datetime import datetime, timezone
        from pathlib import Path
        import frontmatter

        SUFFIXES = {".txt", ".md", ".markdown"}

        def convert(store_path: Path, config: dict) -> list[Path]:
            src = Path(config["NOTES_SOURCE_DIR"]).expanduser().resolve()
            if not src.exists():
                raise FileNotFoundError(f"NOTES_SOURCE_DIR does not exist: {src}")
            notes_dir = store_path / "notes"
            notes_dir.mkdir(parents=True, exist_ok=True)
            raw_tags = config.get("NOTES_DEFAULT_TAGS", "").split(",")
            default_tags = [t.strip() for t in raw_tags if t.strip()]
            existing_shas = _scan_shas(notes_dir)
            created: list[Path] = []
            for f in sorted(src.rglob("*")):
                if not f.is_file() or f.suffix.lower() not in SUFFIXES:
                    continue
                raw = f.read_text(encoding="utf-8", errors="replace")
                sha = hashlib.sha256(raw.encode()).hexdigest()
                if sha in existing_shas:
                    continue
                mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).astimezone()
                date_str = mtime.isoformat(timespec="seconds")
                try:
                    post = frontmatter.loads(raw)
                    body, meta = post.content, dict(post.metadata)
                except Exception:
                    body, meta = raw, {}
                meta.setdefault("source", "notes")
                meta.setdefault("date", date_str)
                existing_tags = list(meta.get("tags") or [])
                meta["tags"] = existing_tags + [t for t in default_tags if t not in existing_tags]
                meta["sha256"] = sha
                meta["original_path"] = str(f)
                slug = re.sub(r"_+", "_", re.sub(r"[^\\w\\-]+", "_",
                              f.stem.lower())).strip("_") or "note"
                out = notes_dir / f"{date_str[:10]}_{slug}.md"
                i = 1
                while out.exists():
                    out = notes_dir / f"{date_str[:10]}_{slug}_{i}.md"; i += 1
                out.write_text(frontmatter.dumps(frontmatter.Post(body, **meta)), encoding="utf-8")
                created.append(out)
                existing_shas.add(sha)
            return created

        def _scan_shas(d: Path) -> set[str]:
            shas: set[str] = set()
            for md in d.rglob("*.md"):
                try:
                    sha = frontmatter.load(md).metadata.get("sha256")
                    if isinstance(sha, str): shas.add(sha)
                except Exception:
                    pass
            return shas
    """))

    return plugin_dir


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
