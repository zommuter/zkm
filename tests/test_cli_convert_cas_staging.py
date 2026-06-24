# roadmap:dab8
"""Spec test: `zkm convert` must stage CAS objects written under <subdir>/_objects/.

Bug (id:dab8): a convert auto-commit scopes `git add` to the plugin's declared
``creates_dirs`` + the returned ``created`` paths. Plugins write content-addressed
attachment objects via ``zkm.cas.write_object(store, "<subdir>", ...)`` to
``<subdir>/_objects/<aa>/<rest>`` — but ``<subdir>/_objects`` is NOT one of the
declared ``creates_dirs`` (e.g. zkm-eml declares ``mail/messages``/``mail/threads``,
not ``mail/_objects``), and the CAS objects are not in the returned ``created``
list. So the scoped add misses them and they are left UNTRACKED in the store,
dirtying the working tree after every convert.

The fix must keep the scoping safe (never ``git add -A``): stage the CAS
``_objects/`` subdir that sits at the top-level prefix of each ``creates_dir``.
"""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner


def _write_cas_plugin(pdir: Path, name: str, subdir: str) -> None:
    """A primary converter that writes a .md under <subdir>/messages and a CAS
    object under <subdir>/_objects via zkm.cas.write_object.
    """
    d = pdir / f"zkm-{name}"
    d.mkdir(parents=True)
    (d / "plugin.yaml").write_text(
        f"name: {name}\nversion: 0.1.0\ndescription: cas fixture\n"
        f"creates_dirs: [{subdir}/messages, {subdir}/threads]\n"
    )
    (d / "convert.py").write_text(
        textwrap.dedent(
            f"""\
            from pathlib import Path

            from zkm.cas import write_object

            def convert(store_path, config):
                store_path = Path(store_path)
                md = store_path / "{subdir}" / "messages" / "{name}-0.md"
                md.parent.mkdir(parents=True, exist_ok=True)
                md.write_text("---\\nsource: {name}\\n---\\nbody\\n")
                # Attachment payload -> CAS object under <subdir>/_objects/
                write_object(store_path, "{subdir}", b"attachment-payload-bytes")
                return [md]
            """
        )
    )


@pytest.fixture()
def cas_plugin_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pdir = tmp_path / "plugins"
    pdir.mkdir()
    monkeypatch.setenv("ZKM_PLUGINS_DIR", str(pdir))
    return pdir


def _invoke_convert_commit(store: Path, plugin: str):
    from zkm.cli import main

    runner = CliRunner()
    # NOTE: no --no-commit; we want the auto-commit + staging path.
    return runner.invoke(main, ["convert", plugin, "--store", str(store)])


def test_convert_stages_cas_objects(store: Path, cas_plugin_env: Path) -> None:
    """After a committing convert, no CAS object is left untracked."""
    _write_cas_plugin(cas_plugin_env, "casml", "mail")
    result = _invoke_convert_commit(store, "casml")
    assert result.exit_code == 0, result.output

    # The CAS object exists on disk.
    objs = list((store / "mail" / "_objects").rglob("*"))
    obj_files = [p for p in objs if p.is_file()]
    assert obj_files, "convert did not write any CAS object"

    # Nothing under mail/_objects/ may be left untracked.
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "mail/_objects/"],
        cwd=store,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert untracked == "", (
        f"CAS objects left UNTRACKED after convert auto-commit:\n{untracked}"
    )


def test_convert_leaves_clean_tree(store: Path, cas_plugin_env: Path) -> None:
    """The whole working tree is clean after the committing convert (no stragglers)."""
    _write_cas_plugin(cas_plugin_env, "casml", "mail")
    result = _invoke_convert_commit(store, "casml")
    assert result.exit_code == 0, result.output

    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=store,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert status == "", f"working tree dirty after convert:\n{status}"
