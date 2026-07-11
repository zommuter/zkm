# id:8fb4 (INV3a)
"""Spec tests for amender_skip_prefixes (ROADMAP/TODO id:8fb4, currently RED).

Contract: `zkm convert <plugin>`'s amender dispatch (the `created: list[Path]`
threaded to amenders per id:63bb) must filter OUT any created path whose
store-relative rel_path starts with a configured `amender_skip_prefixes`
prefix (default includes `inventory/find-dump/`) before handing `created` to
an amender. BM25/dense indexing is untouched by this filter — it only scopes
what amenders (e.g. zkm-ner) see.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

MARKER = ".amender-created.json"


def _write_plugin(pdir: Path, name: str, kind: str, convert_body: str) -> None:
    d = pdir / f"zkm-{name}"
    d.mkdir(parents=True)
    kind_line = f"kind: {kind}\n" if kind else ""
    (d / "plugin.yaml").write_text(
        f"name: {name}\nversion: 0.1.0\ndescription: test fixture\n"
        f"{kind_line}creates_dirs: [notes, inventory]\n"
    )
    (d / "convert.py").write_text(convert_body)


@pytest.fixture()
def plugin_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated plugins dir with one amender that records the `created` paths it saw."""
    pdir = tmp_path / "plugins"
    pdir.mkdir()
    monkeypatch.setenv("ZKM_PLUGINS_DIR", str(pdir))

    _write_plugin(
        pdir,
        "amark",
        "amender",
        textwrap.dedent(
            """\
            import json
            from pathlib import Path

            def convert(store_path, config, *, created=None):
                rels = sorted(
                    str(Path(p).relative_to(store_path)) for p in (created or [])
                )
                (Path(store_path) / ".amender-created.json").write_text(json.dumps(rels))
                return []
            """
        ),
    )
    return pdir


def _add_primary_multi(pdir: Path, name: str, rels: list[str]) -> None:
    """Primary converter that creates one file per given store-relative path."""
    rels_literal = repr(rels)
    _write_plugin(
        pdir,
        name,
        "",
        textwrap.dedent(
            f"""\
            from pathlib import Path

            def convert(store_path, config):
                rels = {rels_literal}
                out = []
                for rel in rels:
                    p = Path(store_path) / rel
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text("---\\nsource: {name}\\n---\\nbody\\n")
                    out.append(p)
                return out
            """
        ),
    )


def _invoke_convert(store: Path, plugin: str):
    from zkm.cli import main

    runner = CliRunner()
    return runner.invoke(main, ["convert", plugin, "--store", str(store), "--no-commit"])


def _amender_saw(store: Path) -> list[str]:
    marker = store / MARKER
    assert marker.exists(), "amender did not run"
    return json.loads(marker.read_text())


def test_find_dump_path_excluded_from_amender_created(store: Path, plugin_env: Path) -> None:
    _add_primary_multi(
        plugin_env,
        "prim2",
        ["notes/normal.md", "inventory/find-dump/drive1/0001.md"],
    )
    result = _invoke_convert(store, "prim2")
    assert result.exit_code == 0, result.output

    seen = _amender_saw(store)
    assert "notes/normal.md" in seen
    assert "inventory/find-dump/drive1/0001.md" not in seen


def test_default_prefix_applies_with_no_config(store: Path, plugin_env: Path) -> None:
    """Guard: the default amender_skip_prefixes applies even with zero explicit config."""
    cfg_path = store / "zkm-config.yaml"
    data = yaml.safe_load(cfg_path.read_text()) or {}
    assert "amender_skip_prefixes" not in (data.get("core", {}).get("convert", {}) or {})

    _add_primary_multi(
        plugin_env, "prim3", ["inventory/find-dump/drive2/0001.md"],
    )
    result = _invoke_convert(store, "prim3")
    assert result.exit_code == 0, result.output
    assert _amender_saw(store) == []


def test_explicit_amender_skip_prefixes_config(store: Path, plugin_env: Path) -> None:
    """An explicit amender_skip_prefixes config value governs the filter."""
    cfg_path = store / "zkm-config.yaml"
    data = yaml.safe_load(cfg_path.read_text()) or {}
    data.setdefault("core", {})["convert"] = {"amender_skip_prefixes": ["scratch/"]}
    cfg_path.write_text(yaml.dump(data, default_flow_style=False))

    _add_primary_multi(
        plugin_env,
        "prim4",
        ["scratch/big.md", "notes/normal.md"],
    )
    result = _invoke_convert(store, "prim4")
    assert result.exit_code == 0, result.output

    seen = _amender_saw(store)
    assert "notes/normal.md" in seen
    assert "scratch/big.md" not in seen
