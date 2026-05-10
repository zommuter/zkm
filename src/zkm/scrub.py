"""Plugin-dispatched scrub command — retroactive frontmatter field cleanup."""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from zkm.convert import find_plugin, load_env, Plugin


def _load_module(plugin: Plugin) -> types.ModuleType:
    convert_py = plugin.path / "convert.py"
    if not convert_py.exists():
        raise FileNotFoundError(f"{convert_py} not found")
    spec_obj = importlib.util.spec_from_file_location(f"zkm_plugin_{plugin.name}", convert_py)
    if spec_obj is None or spec_obj.loader is None:
        raise ImportError(f"Could not load {convert_py}")
    mod = importlib.util.module_from_spec(spec_obj)
    spec_obj.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def run_scrub(
    plugin_name: str,
    store_path: Path,
    *,
    dry_run: bool = True,
    verbose: bool = False,
    progress=None,
) -> dict[str, int]:
    """Dispatch to *plugin_name*'s ``scrub()`` function and return stats.

    Returns a dict with keys ``files_scanned``, ``files_changed``, ``entities_removed``.
    Raises ``LookupError`` when the plugin is not found.
    Raises ``AttributeError`` when the plugin has no ``scrub`` function.
    """
    plugin = find_plugin(plugin_name)
    if plugin is None:
        raise LookupError(f"Plugin '{plugin_name}' is not installed")

    mod = _load_module(plugin)
    if not hasattr(mod, "scrub"):
        raise AttributeError(
            f"Plugin '{plugin_name}' does not implement scrub(). "
            "See docs/plugin-spec.md for the contract."
        )

    config = load_env(store_path)
    return mod.scrub(store_path, config, dry_run=dry_run, verbose=verbose, progress=progress)
