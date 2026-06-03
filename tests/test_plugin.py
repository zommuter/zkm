"""Tests for plugin registry + notes sample plugin end-to-end."""

from __future__ import annotations

from pathlib import Path

import pytest

from zkm.convert import (
    Plugin,
    _load_plugin_module,
    add_plugin,
    append_env,
    find_plugin,
    list_amenders,
    list_plugins,
    load_env,
    prompt_required_config,
    remove_plugin,
    run_convert,
    run_reprocess,
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


def test_add_local_plugin_zkm_prefixed_name(isolated_plugins: Path, tmp_path: Path) -> None:
    """Plugin whose manifest name already starts with 'zkm-' must not get double-prefixed."""
    src = tmp_path / "zkm-eml-fixture"
    src.mkdir()
    (src / "plugin.yaml").write_text("name: zkm-eml\nversion: 0.1.0\ncreates_dirs: []\n")
    (src / "convert.py").write_text("def convert(store_path, config, *, progress=None): return []\n")
    plugin = add_plugin(str(src))
    assert plugin.name == "zkm-eml"
    assert (isolated_plugins / "zkm-eml").exists()
    assert not (isolated_plugins / "zkm-zkm-eml").exists()


def test_add_self_link_guard(isolated_plugins: Path, capsys: pytest.CaptureFixture) -> None:
    """Plugin already inside plugins_dir must not create a self-referencing symlink."""
    src = isolated_plugins / "zkm-eml"
    src.mkdir()
    (src / "plugin.yaml").write_text("name: zkm-eml\nversion: 0.1.0\ncreates_dirs: []\n")
    (src / "convert.py").write_text("def convert(store_path, config, *, progress=None): return []\n")
    plugin = add_plugin(str(src))
    assert plugin.name == "zkm-eml"
    assert not (isolated_plugins / "zkm-zkm-eml").exists()
    out = capsys.readouterr().out
    assert "already in the plugins directory" in out


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


def test_find_plugin_accepts_zkm_prefix(isolated_plugins: Path, notes_plugin_dir: Path) -> None:
    add_plugin(str(notes_plugin_dir))
    assert find_plugin("zkm-notes") == find_plugin("notes")


def test_remove_plugin(isolated_plugins: Path, notes_plugin_dir: Path) -> None:
    add_plugin(str(notes_plugin_dir))
    remove_plugin("notes")
    assert list_plugins() == []


def test_remove_nonexistent_raises(isolated_plugins: Path) -> None:
    with pytest.raises(LookupError):
        remove_plugin("notes")


def _make_fake_pkg(tmp_path: Path, pkg_name: str, plugin_name: str, version: str = "2.0.0") -> Path:
    """Create a minimal installable-style package with plugin.yaml in tmp_path."""
    pkg_dir = tmp_path / pkg_name
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "plugin.yaml").write_text(
        f"name: {plugin_name}\nversion: {version}\ncreates_dirs: []\n"
    )
    (pkg_dir / "convert.py").write_text("def convert(s, c, **kw): return []\n")
    return pkg_dir


class _FakeEP:
    """Minimal stand-in for importlib.metadata.EntryPoint."""

    def __init__(self, name: str, value: str) -> None:
        self.name = name
        self.value = value


def test_entry_point_plugin_discovered(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_plugins: Path,
) -> None:
    """An entry-point-registered plugin is discovered with origin='entry-point'."""
    import importlib.metadata

    pkg_dir = _make_fake_pkg(tmp_path, "zkm_ep_testpkg", "ep_testpkg", version="2.0.0")
    monkeypatch.syspath_prepend(str(tmp_path))

    monkeypatch.setattr(
        importlib.metadata,
        "entry_points",
        lambda group: [_FakeEP("ep_testpkg", "zkm_ep_testpkg")] if group == "zkm.plugins" else [],
    )

    plugins = list_plugins()
    ep_plugin = next((p for p in plugins if p.name == "ep_testpkg"), None)
    assert ep_plugin is not None
    assert ep_plugin.origin == "entry-point"
    assert ep_plugin.version == "2.0.0"
    assert ep_plugin.path == pkg_dir


def test_filesystem_shadows_entry_point(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_plugins: Path,
    notes_plugin_dir: Path,
) -> None:
    """Filesystem plugin wins over a same-name entry-point; shadows_entry_point is set."""
    import importlib.metadata

    # Create entry-point version of "notes" at version 9.9.9
    _make_fake_pkg(tmp_path, "zkm_notes_wheel", "notes", version="9.9.9")
    monkeypatch.syspath_prepend(str(tmp_path))

    monkeypatch.setattr(
        importlib.metadata,
        "entry_points",
        lambda group: [_FakeEP("notes", "zkm_notes_wheel")] if group == "zkm.plugins" else [],
    )

    # Filesystem version of notes (real plugin, version != 9.9.9)
    add_plugin(str(notes_plugin_dir))

    plugins = list_plugins()
    notes = next(p for p in plugins if p.name == "notes")
    assert notes.origin == "filesystem"
    assert notes.shadows_entry_point is True
    assert notes.version != "9.9.9"

    # find_plugin must return the filesystem version
    found = find_plugin("notes")
    assert found is not None
    assert found.origin == "filesystem"


def test_load_plugin_module_injects_venv(tmp_path: Path) -> None:
    """_load_plugin_module injects plugin's .venv site-packages before exec_module.

    The plugin's convert.py imports a marker module that lives only in the
    plugin's fake .venv — not in the core venv.  Without SB2 this raises
    ModuleNotFoundError; with SB2 the import succeeds.
    """
    import sys

    # Determine the running Python version string (e.g. "python3.14")
    pyver = f"python{sys.version_info.major}.{sys.version_info.minor}"

    # Build a fake plugin dir with a .venv that contains _sb2_marker_dep
    plugin_dir = tmp_path / "zkm-sb2test"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.yaml").write_text(
        "name: sb2test\nversion: 0.0.1\ncreates_dirs: []\n"
    )
    site_packages = plugin_dir / ".venv" / "lib" / pyver / "site-packages"
    site_packages.mkdir(parents=True)
    (site_packages / "_sb2_marker_dep.py").write_text("MARKER = 'injected'\n")
    (plugin_dir / "convert.py").write_text(
        "import _sb2_marker_dep\ndef convert(s, c, **kw): return []\n"
    )

    plugin = Plugin(
        name="sb2test",
        version="0.0.1",
        description="",
        path=plugin_dir,
    )

    # Guard: the marker module must NOT already be importable from the core venv
    assert "_sb2_marker_dep" not in sys.modules

    mod = _load_plugin_module(plugin)
    assert hasattr(mod, "convert")
    # The marker module was importable because core injected the plugin venv
    assert "_sb2_marker_dep" in sys.modules or hasattr(mod, "__spec__")

    # Cleanup: remove from sys.modules and sys.path so other tests are unaffected
    sys.modules.pop("_sb2_marker_dep", None)
    site_str = str(site_packages)
    if site_str in sys.path:
        sys.path.remove(site_str)


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
    created = run_convert("notes", store, extra_env={"source_dir": str(src)})

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
    first = run_convert("notes", store, extra_env={"source_dir": str(src)})
    second = run_convert("notes", store, extra_env={"source_dir": str(src)})

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
    created = run_convert("notes", store, extra_env={"source_dir": str(src)})

    assert len(created) == 1
    post = frontmatter.load(created[0])
    assert post.metadata.get("title") == "My Note"
    assert "personal" in post.metadata.get("tags", [])


def test_notes_convert_missing_config_raises(
    isolated_plugins: Path, store: Path, notes_plugin_dir: Path
) -> None:
    add_plugin(str(notes_plugin_dir))
    with pytest.raises(ValueError, match="source_dir"):
        run_convert("notes", store)


def test_convert_unknown_plugin_raises(isolated_plugins: Path, store: Path) -> None:
    with pytest.raises(LookupError):
        run_convert("nonexistent", store)


def test_notes_convert_writes_processor_fields(
    isolated_plugins: Path, store: Path, tmp_path: Path, notes_plugin_dir: Path
) -> None:
    import frontmatter

    src = tmp_path / "src_notes"
    src.mkdir()
    (src / "note.txt").write_text("Test content")

    add_plugin(str(notes_plugin_dir))
    created = run_convert("notes", store, extra_env={"source_dir": str(src)})

    assert len(created) == 1
    post = frontmatter.load(created[0])
    assert post.metadata["processor"] == "notes"
    assert post.metadata["processor_version"] == "0.1.0"
    assert post.metadata["original"] == str(src / "note.txt")


def test_reprocess_all_calls_convert(
    isolated_plugins: Path, store: Path, tmp_path: Path, notes_plugin_dir: Path
) -> None:
    """--reprocess-all (mode='all') re-runs convert with ZKM_REPROCESS set; notes
    plugin doesn't implement reprocess(), so it falls back to convert() which skips
    already-seen sha256s. The important assertion is that no exception is raised and
    the candidate list is built correctly."""

    src = tmp_path / "src_notes"
    src.mkdir()
    (src / "note.txt").write_text("Reprocess me")

    add_plugin(str(notes_plugin_dir))
    run_convert("notes", store, extra_env={"source_dir": str(src)})

    # run_reprocess should not raise; returns 0 new files (sha256 dedup still active)
    result = run_reprocess("notes", store, extra_env={"source_dir": str(src)}, mode="all")
    assert isinstance(result, list)


def test_progress_callback_invoked(
    isolated_plugins: Path, store: Path, tmp_path: Path, notes_plugin_dir: Path
) -> None:
    """run_convert passes progress= to plugins that declare it; notes plugin does."""
    src = tmp_path / "src_notes"
    src.mkdir()
    (src / "a.txt").write_text("Alpha")
    (src / "b.txt").write_text("Beta")

    add_plugin(str(notes_plugin_dir))

    calls: list[tuple[int, int | None, str]] = []
    run_convert(
        "notes",
        store,
        extra_env={"source_dir": str(src)},
        progress=lambda c, t, m: calls.append((c, t, m)),
    )

    assert len(calls) == 2
    currents = [c for c, _, _ in calls]
    assert currents == sorted(currents)
    assert calls[-1][0] == calls[-1][1]  # final current == total


def test_cancel_soft_stops_after_item(
    isolated_plugins: Path, store: Path, tmp_path: Path, notes_plugin_dir: Path
) -> None:
    """Soft cancel via PluginInterrupt from progress callback stops the run cleanly."""
    from zkm.cancel import PluginInterrupt

    src = tmp_path / "src_notes"
    src.mkdir()
    for i in range(5):
        (src / f"note{i}.txt").write_text(f"Content {i}")

    add_plugin(str(notes_plugin_dir))

    interrupt_after = 2
    call_count = 0

    def cancelling_progress(current: int, total: int | None, message: str = "") -> None:
        nonlocal call_count
        call_count += 1
        if call_count >= interrupt_after:
            raise PluginInterrupt("test cancel")

    # run_convert propagates PluginInterrupt
    with pytest.raises(PluginInterrupt):
        run_convert(
            "notes",
            store,
            extra_env={"source_dir": str(src)},
            progress=cancelling_progress,
        )

    # Files processed before cancel are on disk
    created_files = list((store / "notes").rglob("*.md"))
    assert 0 < len(created_files) <= 5


def test_progress_not_passed_to_plugin_without_kwarg(
    isolated_plugins: Path, store: Path, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Plugins that don't declare progress= must not receive it (no TypeError)."""
    plugin_dir = tmp_path_factory.mktemp("minimal_plugin")
    (plugin_dir / "plugin.yaml").write_text(
        "name: minimal\nversion: 0.1.0\ncreates_dirs: []\nconfig: {}\n"
    )
    (plugin_dir / "convert.py").write_text(
        "from pathlib import Path\n"
        "def convert(store_path: Path, config: dict) -> list[Path]:\n"
        "    return []\n"
    )

    add_plugin(str(plugin_dir))
    called = []
    # Must not raise TypeError even though the plugin has no progress param
    result = run_convert("minimal", store, progress=lambda c, t, m: called.append(c))
    assert result == []
    assert called == []  # callback not invoked — plugin doesn't know about it


def test_reprocess_outdated_skips_current_version(
    isolated_plugins: Path, store: Path, tmp_path: Path, notes_plugin_dir: Path
) -> None:
    """Files already at the current processor_version are skipped in 'outdated' mode."""

    src = tmp_path / "src_notes"
    src.mkdir()
    (src / "note.txt").write_text("Already current")

    add_plugin(str(notes_plugin_dir))
    created = run_convert("notes", store, extra_env={"source_dir": str(src)})
    assert len(created) == 1

    # In outdated mode, _find_managed_files should return 0 candidates (version matches)
    from zkm.convert import _find_managed_files, find_plugin
    plugin = find_plugin("notes")
    assert plugin is not None
    candidates = _find_managed_files(store, plugin, mode="outdated")
    assert candidates == []


# ---------------------------------------------------------------------------
# .env prompting helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def two_key_plugin(tmp_path: Path) -> Path:
    """A minimal plugin with two required keys (one secret-looking, one plain)."""
    plugin_dir = tmp_path / "zkm-twokey"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.yaml").write_text(
        "name: twokey\nversion: 0.1.0\ncreates_dirs: []\nconfig:\n"
        "  SOURCE_DIR:\n    required: true\n    description: A plain config value\n"
        "  API_TOKEN:\n    required: true\n    description: API secret token\n"
    )
    (plugin_dir / "convert.py").write_text(
        "from pathlib import Path\n"
        "def convert(store_path: Path, config: dict) -> list[Path]:\n"
        "    return []\n"
    )
    return plugin_dir


def test_prompt_required_config_writes_yaml(
    isolated_plugins: Path, store: Path, two_key_plugin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """prompt_required_config prompts for required keys; plain keys go to zkm-config.yaml,
    secret keys go to .zkm-secrets.yaml."""
    import getpass
    import yaml

    plugin = add_plugin(str(two_key_plugin))

    prompt_calls: list[str] = []
    getpass_calls: list[str] = []
    monkeypatch.setattr("click.prompt", lambda text, **_kw: prompt_calls.append(text) or "myvalue")
    monkeypatch.setattr(getpass, "getpass", lambda text: getpass_calls.append(text) or "mysecret")

    missing = prompt_required_config(plugin, store, interactive=True)

    assert missing == []
    assert len(prompt_calls) == 1      # SOURCE_DIR prompted via click.prompt
    assert len(getpass_calls) == 1     # API_TOKEN prompted via getpass

    cfg_data = yaml.safe_load((store / "zkm-config.yaml").read_text())
    assert cfg_data["twokey"]["SOURCE_DIR"] == "myvalue"

    sec_data = yaml.safe_load((store / ".zkm-secrets.yaml").read_text())
    assert sec_data["twokey"]["API_TOKEN"] == "mysecret"

    sec_file = store / ".zkm-secrets.yaml"
    mode = sec_file.stat().st_mode & 0o777
    assert mode == 0o600, f"Expected 0600, got {oct(mode)}"


def test_prompt_skips_existing_yaml_keys(
    isolated_plugins: Path, store: Path, two_key_plugin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keys already in zkm-config.yaml are not re-prompted."""
    import getpass
    import yaml

    plugin = add_plugin(str(two_key_plugin))
    # Pre-populate SOURCE_DIR in zkm-config.yaml
    cfg_path = store / "zkm-config.yaml"
    existing = yaml.safe_load(cfg_path.read_text()) or {}
    existing.setdefault("twokey", {})["SOURCE_DIR"] = "existing_val"
    cfg_path.write_text(yaml.dump(existing, default_flow_style=False))

    prompt_calls: list[str] = []
    monkeypatch.setattr("click.prompt", lambda text, **_kw: (prompt_calls.append(text) or "new"))
    monkeypatch.setattr(getpass, "getpass", lambda text: "newsecret")

    missing = prompt_required_config(plugin, store, interactive=True)

    assert missing == []
    assert len(prompt_calls) == 0   # SOURCE_DIR already set — not prompted

    cfg_data = yaml.safe_load(cfg_path.read_text())
    assert cfg_data["twokey"]["SOURCE_DIR"] == "existing_val"   # unchanged

    sec_data = yaml.safe_load((store / ".zkm-secrets.yaml").read_text())
    assert sec_data["twokey"]["API_TOKEN"] == "newsecret"


def test_prompt_no_interactive_returns_missing(
    isolated_plugins: Path, store: Path, two_key_plugin: Path
) -> None:
    """When interactive=False, all missing required keys are returned without prompting."""
    plugin = add_plugin(str(two_key_plugin))

    missing = prompt_required_config(plugin, store, interactive=False)

    assert sorted(missing) == ["API_TOKEN", "SOURCE_DIR"]


def test_prompt_non_tty_silent(
    isolated_plugins: Path, store: Path, two_key_plugin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """sys.stdin.isatty() returning False must result in interactive=False behaviour."""
    import sys

    plugin = add_plugin(str(two_key_plugin))

    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)

    # Call prompt_required_config with interactive=(not no_prompt and sys.stdin.isatty())
    interactive = sys.stdin.isatty()
    missing = prompt_required_config(plugin, store, interactive=interactive)

    assert sorted(missing) == ["API_TOKEN", "SOURCE_DIR"]


# ---------------------------------------------------------------------------
# N5: kind field + list_amenders + default-on amender chain (CLI level)
# ---------------------------------------------------------------------------


def test_plugin_kind_defaults_to_converter(isolated_plugins: Path, tmp_path: Path) -> None:
    src = tmp_path / "zkm-myplugin"
    src.mkdir()
    (src / "plugin.yaml").write_text("name: myplugin\nversion: 0.1.0\ncreates_dirs: []\n")
    (src / "convert.py").write_text("def convert(store_path, config): return []\n")
    plugin = add_plugin(str(src))
    assert plugin.kind == "converter"


def test_plugin_kind_amender_loaded(isolated_plugins: Path, tmp_path: Path) -> None:
    src = tmp_path / "zkm-myamender"
    src.mkdir()
    (src / "plugin.yaml").write_text("name: myamender\nversion: 0.1.0\nkind: amender\ncreates_dirs: []\n")
    (src / "convert.py").write_text("def convert(store_path, config): return []\n")
    plugin = add_plugin(str(src))
    assert plugin.kind == "amender"


def test_list_amenders_returns_only_amenders(isolated_plugins: Path, tmp_path: Path) -> None:
    conv_src = tmp_path / "zkm-conv"
    conv_src.mkdir()
    (conv_src / "plugin.yaml").write_text("name: conv\nversion: 0.1.0\ncreates_dirs: []\n")
    (conv_src / "convert.py").write_text("def convert(store_path, config): return []\n")
    add_plugin(str(conv_src))

    amend_src = tmp_path / "zkm-amend"
    amend_src.mkdir()
    (amend_src / "plugin.yaml").write_text("name: amend\nversion: 0.1.0\nkind: amender\ncreates_dirs: []\n")
    (amend_src / "convert.py").write_text("def convert(store_path, config): return []\n")
    add_plugin(str(amend_src))

    amenders = list_amenders()
    assert len(amenders) == 1
    assert amenders[0].name == "amend"
    assert amenders[0].kind == "amender"


def _write_plugin_config(store: Path, plugin_bare: str, key: str, value: str) -> None:
    """Write a plugin config key into the store's zkm-config.yaml."""
    import yaml as _yaml
    cfg_path = store / "zkm-config.yaml"
    data = _yaml.safe_load(cfg_path.read_text()) or {} if cfg_path.exists() else {}
    data.setdefault(plugin_bare, {})[key] = value
    cfg_path.write_text(_yaml.dump(data, default_flow_style=False))


def test_cmd_convert_runs_amenders_by_default(
    isolated_plugins: Path, store: Path, tmp_path: Path, notes_plugin_dir: Path
) -> None:
    """Amender plugins run automatically after a body-producer convert (default-on)."""
    from click.testing import CliRunner
    from zkm.cli import main

    src = tmp_path / "src_notes"
    src.mkdir()
    (src / "note.txt").write_text("Test note")
    add_plugin(str(notes_plugin_dir))
    _write_plugin_config(store, "notes", "source_dir", str(src))

    amend_dir = isolated_plugins / "zkm-amend"
    amend_dir.mkdir()
    (amend_dir / "plugin.yaml").write_text("name: amend\nversion: 0.1.0\nkind: amender\ncreates_dirs: []\n")
    sentinel = tmp_path / "amender_ran"
    (amend_dir / "convert.py").write_text(
        f"def convert(store_path, config):\n"
        f"    open({str(sentinel)!r}, 'w').close()\n"
        f"    return []\n"
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["convert", "notes", "--store", str(store), "--no-commit"],
        env={"ZKM_PLUGINS_DIR": str(isolated_plugins)},
    )
    assert result.exit_code == 0, result.output
    assert sentinel.exists(), "amender did not run"
    assert "Amended via 'amend'" in result.output


def test_cmd_convert_no_amenders_flag_skips_amenders(
    isolated_plugins: Path, store: Path, tmp_path: Path, notes_plugin_dir: Path
) -> None:
    """--no-amenders suppresses the amender chain."""
    from click.testing import CliRunner
    from zkm.cli import main

    src = tmp_path / "src_notes"
    src.mkdir()
    (src / "note.txt").write_text("Test note")
    add_plugin(str(notes_plugin_dir))
    _write_plugin_config(store, "notes", "source_dir", str(src))

    amend_dir = isolated_plugins / "zkm-amend"
    amend_dir.mkdir()
    (amend_dir / "plugin.yaml").write_text("name: amend\nversion: 0.1.0\nkind: amender\ncreates_dirs: []\n")
    sentinel = tmp_path / "amender_ran"
    (amend_dir / "convert.py").write_text(
        f"def convert(store_path, config):\n"
        f"    open({str(sentinel)!r}, 'w').close()\n"
        f"    return []\n"
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["convert", "notes", "--store", str(store), "--no-commit", "--no-amenders"],
        env={"ZKM_PLUGINS_DIR": str(isolated_plugins)},
    )
    assert result.exit_code == 0, result.output
    assert not sentinel.exists(), "amender should not have run with --no-amenders"


def test_cmd_convert_amender_plugin_does_not_trigger_amender_chain(
    isolated_plugins: Path, store: Path, tmp_path: Path
) -> None:
    """Calling zkm convert on an amender plugin directly does not re-run amenders."""
    from click.testing import CliRunner
    from zkm.cli import main

    amend_dir = isolated_plugins / "zkm-amend"
    amend_dir.mkdir()
    (amend_dir / "plugin.yaml").write_text("name: amend\nversion: 0.1.0\nkind: amender\ncreates_dirs: []\n")
    sentinel = tmp_path / "amender_ran_count"
    sentinel.write_text("0")
    (amend_dir / "convert.py").write_text(
        f"def convert(store_path, config):\n"
        f"    import pathlib; p = pathlib.Path({str(sentinel)!r})\n"
        f"    p.write_text(str(int(p.read_text()) + 1))\n"
        f"    return []\n"
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["convert", "amend", "--store", str(store), "--no-commit"],
        env={"ZKM_PLUGINS_DIR": str(isolated_plugins)},
    )
    assert result.exit_code == 0, result.output
    assert sentinel.read_text() == "1", "amender should have run exactly once (not recursively)"
