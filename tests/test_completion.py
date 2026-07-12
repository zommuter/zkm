"""RED spec for id:e9e2 — shell autocompletion for zkm.

Two acceptance criteria:

1. `zkm completion [bash|zsh|fish]` prints a shell completion script and exits 0.
2. Dynamic plugin-name completion: the `convert` command's `plugin` argument
   completes from the live discovered plugin set (`list_plugins()`), using the
   lightweight manifest scan — NOT a heavy `_load_plugin_module` import.

These fail until id:e9e2 ships:
- there is no `completion` subcommand yet, and
- the `plugin` argument carries no `shell_complete` callback (Click's default
  returns no completions).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from zkm.cli import main


@pytest.fixture()
def isolated_plugins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pdir = tmp_path / "plugins"
    pdir.mkdir()
    monkeypatch.setenv("ZKM_PLUGINS_DIR", str(pdir))
    return pdir


def _make_plugin(pdir: Path, name: str) -> None:
    d = pdir / f"zkm-{name}"
    d.mkdir()
    (d / "plugin.yaml").write_text(
        f"name: {name}\nversion: 0.1.0\ndescription: test\nlicense: MIT\n"
    )
    (d / "convert.py").write_text("def convert(*a, **k):\n    return []\n")


@pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
def test_completion_command_prints_script(shell: str) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["completion", shell])
    assert result.exit_code == 0, result.output
    assert result.output.strip(), f"empty completion script for {shell}"


def test_convert_plugin_arg_completes_from_discovered_plugins(
    isolated_plugins: Path,
) -> None:
    _make_plugin(isolated_plugins, "alpha")
    _make_plugin(isolated_plugins, "beta")

    convert_cmd = main.commands["convert"]
    plugin_param = next(p for p in convert_cmd.params if p.name == "plugin")

    ctx = convert_cmd.make_context("convert", [], resilient_parsing=True)
    completions = plugin_param.shell_complete(ctx, "")
    values = {getattr(c, "value", c) for c in completions}

    assert "alpha" in values
    assert "beta" in values
