"""Plugin-dispatched scrub command — retroactive frontmatter field cleanup."""

from __future__ import annotations

import importlib.util
import inspect
import json
import types
from pathlib import Path

from zkm.convert import find_plugin, Plugin


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
    resume: bool = False,
    **extra_kwargs,
) -> dict[str, int]:
    """Dispatch to *plugin_name*'s ``scrub()`` function and return stats.

    Returns a dict with keys ``files_scanned``, ``files_changed``, ``entities_removed``.
    Raises ``LookupError`` when the plugin is not found.
    Raises ``AttributeError`` when the plugin has no ``scrub`` function.

    Any *extra_kwargs* are forwarded to the plugin's ``scrub()`` unchanged, so
    plugin-specific flags (e.g. ``with_verifier``) can be threaded through
    without modifying the core dispatch layer.

    When *resume* is True, the last-processed file is read from a watermark at
    ``.zkm-state/scrub-<plugin>-watermark.json`` and forwarded to the plugin so
    it can skip already-processed files.  The watermark is deleted on successful
    completion; it is preserved on any exception so the run can be resumed.
    """
    from zkm.atomic import write_atomic

    plugin = find_plugin(plugin_name)
    if plugin is None:
        raise LookupError(f"Plugin '{plugin_name}' is not installed")

    mod = _load_module(plugin)
    if not hasattr(mod, "scrub"):
        raise AttributeError(
            f"Plugin '{plugin_name}' does not implement scrub(). "
            "See docs/plugin-spec.md for the contract."
        )

    from zkm.config import load_config
    cfg = load_config(store_path)
    config = cfg.for_plugin(plugin_name)

    # ---- watermark support ------------------------------------------------
    watermark_path = store_path / ".zkm-state" / f"scrub-{plugin.name}-watermark.json"
    resume_after_file: str | None = None

    if resume and watermark_path.exists():
        try:
            wm = json.loads(watermark_path.read_text(encoding="utf-8"))
            resume_after_file = wm.get("last_file") or None
        except Exception:
            pass  # corrupt watermark → start fresh

    def on_file_done(rel_path: str) -> None:
        watermark_path.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(watermark_path, json.dumps({"last_file": rel_path, "plugin": plugin.name}))

    # ---- dispatch ---------------------------------------------------------
    # Only forward extra_kwargs to plugins that declare **kwargs in their
    # signature, so existing plugins without the new flags continue to work.
    sig = inspect.signature(mod.scrub)
    accepts_var_kwargs = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )
    kwargs = {**extra_kwargs} if accepts_var_kwargs else {}
    if accepts_var_kwargs:
        kwargs["resume_after_file"] = resume_after_file
        kwargs["on_file_done"] = on_file_done

    result = mod.scrub(store_path, config, dry_run=dry_run, verbose=verbose, progress=progress, **kwargs)
    # Watermark is only deleted on clean completion; exceptions leave it intact.
    watermark_path.unlink(missing_ok=True)
    return result
