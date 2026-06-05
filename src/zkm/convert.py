"""Plugin registry and converter dispatch."""

from __future__ import annotations

import getpass
import importlib.metadata
import importlib.util
import inspect
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from zkm.config import load_config

# ---------------------------------------------------------------------------
# Plugin directory resolution
# ---------------------------------------------------------------------------


def plugins_dir() -> Path:
    """
    Return the directory where installed plugins live.

    Resolution order:
    1. $ZKM_PLUGINS_DIR (env override)
    2. <repo-root>/plugins/   (tool repo, detected via pyproject.toml)
    3. ~/.local/share/zkm/plugins/  (fallback for installed builds)
    """
    if p := os.environ.get("ZKM_PLUGINS_DIR"):
        return Path(p).expanduser().resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent / "plugins"
    return Path.home() / ".local" / "share" / "zkm" / "plugins"


# ---------------------------------------------------------------------------
# Plugin manifest
# ---------------------------------------------------------------------------


@dataclass
class Plugin:
    name: str
    version: str
    description: str
    path: Path
    kind: str = "converter"
    config_keys: dict[str, dict] = field(default_factory=dict)
    creates_dirs: list[str] = field(default_factory=list)
    conformance: dict = field(default_factory=dict)
    origin: str = "filesystem"
    shadows_entry_point: bool = False


def load_plugin_manifest(plugin_path: Path) -> Plugin:
    manifest = plugin_path / "plugin.yaml"
    if not manifest.exists():
        raise FileNotFoundError(f"Missing plugin.yaml at {manifest}")
    data = yaml.safe_load(manifest.read_text())
    return Plugin(
        name=data["name"],
        version=data.get("version", "0.0.0"),
        description=data.get("description", ""),
        path=plugin_path,
        kind=data.get("kind", "converter"),
        config_keys=data.get("config") or {},
        creates_dirs=data.get("creates_dirs") or [],
        conformance=data.get("conformance") or {},
    )


# ---------------------------------------------------------------------------
# Registry operations
# ---------------------------------------------------------------------------


def _plugin_from_entry_point(ep: Any) -> Plugin | None:
    """Resolve an importlib EntryPoint to a Plugin, or None on failure."""
    pkg_name = ep.value
    try:
        spec = importlib.util.find_spec(pkg_name)
    except (ModuleNotFoundError, ValueError):
        return None
    if spec is None:
        return None
    locations = list(spec.submodule_search_locations or [])
    if locations:
        pkg_dir = Path(locations[0])
    elif spec.origin:
        pkg_dir = Path(spec.origin).parent
    else:
        return None
    try:
        p = load_plugin_manifest(pkg_dir)
        p.origin = "entry-point"
        return p
    except Exception as e:
        print(f"WARN: skipping entry-point plugin {getattr(ep, 'name', pkg_name)!r}: {e}")
        return None


def list_plugins() -> list[Plugin]:
    """Return all installed plugins (entry-points + filesystem), sorted by name.

    Discovery order: entry_points(group='zkm.plugins') union filesystem scan.
    When the same plugin name appears in both, the filesystem version wins
    (dev-symlink overrides an installed wheel).
    """
    # --- entry-point plugins ---
    ep_plugins: dict[str, Plugin] = {}
    for ep in importlib.metadata.entry_points(group="zkm.plugins"):
        p = _plugin_from_entry_point(ep)
        if p is not None:
            ep_plugins[p.name] = p

    # --- filesystem plugins ---
    fs_plugins: dict[str, Plugin] = {}
    pdir = plugins_dir()
    if pdir.exists():
        for entry in sorted(pdir.iterdir()):
            if not (entry.is_dir() or entry.is_symlink()):
                continue
            if not (entry / "plugin.yaml").exists():
                continue
            try:
                p = load_plugin_manifest(entry)
                p.origin = "filesystem"
                if p.name in ep_plugins:
                    p.shadows_entry_point = True
                fs_plugins[p.name] = p
            except Exception as e:
                print(f"WARN: skipping {entry.name}: {e}")

    # filesystem wins on name collision
    merged = {**ep_plugins, **fs_plugins}
    return sorted(merged.values(), key=lambda p: p.name)


def find_plugin(name: str) -> Plugin | None:
    name = name.removeprefix("zkm-")
    return next((p for p in list_plugins() if p.name == name), None)


def list_amenders() -> list[Plugin]:
    """Return all installed plugins with kind == 'amender', sorted by name."""
    return [p for p in list_plugins() if p.kind == "amender"]


def add_plugin(source: str) -> Plugin:
    """
    Install a plugin from a local directory path or git URL.

    Local path  → symlink into plugins/zkm-<name>/
    Git URL     → git clone into plugins/<repo-name>/
    """
    pdir = plugins_dir()
    pdir.mkdir(parents=True, exist_ok=True)

    src_path = Path(source).expanduser()
    is_local = src_path.exists() and src_path.is_dir()

    if is_local:
        src_path = src_path.resolve()
        manifest = src_path / "plugin.yaml"
        if not manifest.exists():
            raise FileNotFoundError(f"No plugin.yaml in {src_path}")
        name = yaml.safe_load(manifest.read_text())["name"]
        dir_name = name if name.startswith("zkm-") else f"zkm-{name}"
        dest = pdir / dir_name
        # Already in place — dev plugin repo nested inside plugins_dir()
        if src_path.parent == pdir.resolve():
            plugin = load_plugin_manifest(src_path)
            print(f"Plugin '{plugin.name}' is already in the plugins directory")
            return plugin
        if dest.exists() or dest.is_symlink():
            raise FileExistsError(f"Plugin '{name}' already installed at {dest}")
        dest.symlink_to(src_path, target_is_directory=True)
        return load_plugin_manifest(dest)
    else:
        # Git URL: derive dir name from last path component
        repo_name = source.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
        dest = pdir / repo_name
        if dest.exists():
            raise FileExistsError(f"Plugin directory already exists: {dest}")
        subprocess.run(["git", "clone", source, str(dest)], check=True)
        return load_plugin_manifest(dest)


def remove_plugin(name: str) -> None:
    """Remove an installed plugin by its manifest name."""
    plugin = find_plugin(name)
    if plugin is None:
        raise LookupError(f"Plugin not installed: {name}")
    if plugin.path.is_symlink():
        plugin.path.unlink()
    else:
        shutil.rmtree(plugin.path)


# ---------------------------------------------------------------------------
# .env loading
# ---------------------------------------------------------------------------


def load_env(store_path: Path) -> dict[str, str]:
    """Parse $ZKM_STORE/.env into a flat dict (KEY=VALUE lines, no expansion)."""
    env_file = store_path / ".env"
    if not env_file.exists():
        return {}
    env: dict[str, str] = {}
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip().strip("\"'")
    return env


def append_env(store_path: Path, key: str, value: str) -> None:
    """Atomically append KEY=VALUE (quoted when needed) to $ZKM_STORE/.env."""
    env_file = store_path / ".env"
    existing = env_file.read_text(encoding="utf-8") if env_file.exists() else ""
    if " " in value or "#" in value or '"' in value:
        escaped = value.replace('"', '\\"')
        line = f'{key}="{escaped}"\n'
    else:
        line = f"{key}={value}\n"
    new_content = existing + line
    fd, tmp = tempfile.mkstemp(dir=store_path, prefix=".env.tmp")
    try:
        os.write(fd, new_content.encode("utf-8"))
    finally:
        os.close(fd)
    os.replace(tmp, env_file)
    env_file.chmod(0o600)


_SECRET_RE = re.compile(r"PASS(WORD)?|TOKEN|KEY|SECRET", re.IGNORECASE)


def prompt_required_config(
    plugin: Plugin,
    store_path: Path,
    *,
    interactive: bool = True,
) -> list[str]:
    """
    Prompt for each required config key that is not already configured and has no default.

    Returns the list of keys still missing after prompting (empty = all satisfied).
    When interactive=False, immediately returns all missing keys without prompting.
    """
    cfg = load_config(store_path)
    plugin_bare = plugin.name.removeprefix("zkm-")
    existing = cfg.for_plugin(plugin.name)
    missing: list[str] = []

    for key, spec in plugin.config_keys.items():
        if not spec.get("required"):
            continue
        if "default" in spec:
            continue
        if key in existing:
            continue
        if not interactive:
            missing.append(key)
            continue

        description = spec.get("description") or key
        prompt_text = f"  {description} [{key}]"
        value = ""
        for _ in range(3):
            try:
                if _SECRET_RE.search(key):
                    value = getpass.getpass(prompt_text + ": ")
                else:
                    import click as _click  # noqa: PLC0415
                    value = _click.prompt(prompt_text, default="")
            except (EOFError, KeyboardInterrupt):
                value = ""
            if value:
                break
        if value:
            if _SECRET_RE.search(key):
                _write_yaml_key(store_path / ".zkm-secrets.yaml", plugin_bare, key, value)
            else:
                _write_yaml_key(store_path / "zkm-config.yaml", plugin_bare, key, value)
        else:
            missing.append(key)

    return missing


def _write_yaml_key(yaml_path: Path, section: str, key: str, value: str) -> None:
    """Atomically set yaml_path[section][key] = value, creating the file if absent."""
    existing_data: dict = {}
    if yaml_path.exists():
        try:
            existing_data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        except Exception:
            existing_data = {}
    if not isinstance(existing_data, dict):
        existing_data = {}
    section_data = existing_data.setdefault(section, {})
    if not isinstance(section_data, dict):
        section_data = {}
        existing_data[section] = section_data
    section_data[key] = value
    fd, tmp = tempfile.mkstemp(dir=yaml_path.parent, prefix=yaml_path.name + ".tmp")
    try:
        os.write(fd, yaml.dump(existing_data, default_flow_style=False, allow_unicode=True).encode("utf-8"))
    finally:
        os.close(fd)
    os.replace(tmp, yaml_path)
    yaml_path.chmod(0o600)


# ---------------------------------------------------------------------------
# Converter dispatch
# ---------------------------------------------------------------------------


ProgressCallback = Callable[[int, "int | None", str], None]


def run_convert(
    name: str,
    store_path: Path,
    extra_env: dict[str, str] | None = None,
    progress: ProgressCallback | None = None,
) -> list[Path]:
    """
    Load plugin by name, resolve config, and call its convert() function.

    extra_env: additional key/value pairs that supplement (not replace) .env.
    progress: optional callback(current, total, message) called by the plugin.
    Returns the list of created/updated paths as reported by the plugin.
    """
    plugin = find_plugin(name)
    if plugin is None:
        raise LookupError(f"Plugin not installed: '{name}'. Run: zkm plugin list")

    cfg = load_config(store_path)
    plugin_cfg = cfg.for_plugin(name)
    if extra_env:
        plugin_cfg.update(extra_env)

    config: dict = {}
    missing = []
    for k, spec in plugin.config_keys.items():
        if k in plugin_cfg:
            config[k] = plugin_cfg[k]
        elif "default" in spec:
            config[k] = spec["default"]
        elif spec.get("required"):
            missing.append(k)

    if missing:
        raise ValueError(
            f"Plugin '{name}' requires missing config keys: {', '.join(missing)}\n"
            f"Add them to {store_path / 'zkm-config.yaml'}"
        )

    # Ensure declared dirs exist
    for d in plugin.creates_dirs:
        (store_path / d).mkdir(parents=True, exist_ok=True)

    mod = _load_plugin_module(plugin)
    kwargs: dict = {}
    if progress is not None and _supports_progress(mod.convert):
        kwargs["progress"] = progress
    result = mod.convert(store_path, config, **kwargs)
    return [Path(p) for p in (result or [])]


def run_reprocess(
    name: str,
    store_path: Path,
    extra_env: dict[str, str] | None = None,
    mode: str = "outdated",
    progress: ProgressCallback | None = None,
) -> list[Path]:
    """
    Re-derive already-ingested markdown files by calling the plugin's reprocess()
    hook (if exported) or falling back to convert() with ZKM_REPROCESS set in env.

    mode: "outdated" — only files where processor_version != current plugin version
          "all"      — all .md files managed by this plugin
    progress: optional callback(current, total, message) called by the plugin.
    """
    plugin = find_plugin(name)
    if plugin is None:
        raise LookupError(f"Plugin not installed: '{name}'. Run: zkm plugin list")

    cfg = load_config(store_path)
    plugin_cfg = cfg.for_plugin(name)
    if extra_env:
        plugin_cfg.update(extra_env)

    config: dict = {}
    missing = []
    for k, spec in plugin.config_keys.items():
        if k in plugin_cfg:
            config[k] = plugin_cfg[k]
        elif "default" in spec:
            config[k] = spec["default"]
        elif spec.get("required"):
            missing.append(k)

    if missing:
        raise ValueError(
            f"Plugin '{name}' requires missing config keys: {', '.join(missing)}\n"
            f"Add them to {store_path / 'zkm-config.yaml'}"
        )

    mod = _load_plugin_module(plugin)
    candidates = _find_managed_files(store_path, plugin, mode)

    if hasattr(mod, "reprocess"):
        kwargs: dict = {}
        if progress is not None and _supports_progress(mod.reprocess):
            kwargs["progress"] = progress
        result = mod.reprocess(store_path, config, candidates, **kwargs)
    else:
        old = os.environ.get("ZKM_REPROCESS")
        os.environ["ZKM_REPROCESS"] = mode
        try:
            kwargs = {}
            if progress is not None and _supports_progress(mod.convert):
                kwargs["progress"] = progress
            result = mod.convert(store_path, config, **kwargs)
        finally:
            if old is None:
                os.environ.pop("ZKM_REPROCESS", None)
            else:
                os.environ["ZKM_REPROCESS"] = old

    return [Path(p) for p in (result or [])]


def _inject_plugin_venv(plugin: Plugin) -> None:
    """Inject plugin's .venv site-packages and src/ into sys.path (idempotent).

    Needed when a dev-symlink plugin (filesystem-discovered) is loaded into the
    core zkm venv via importlib — the core venv lacks plugin-only deps such as
    pypdf, pytesseract, vobject, exifread.  Entry-point installs (`uv tool install
    zkm --with zkm-<name>`) already have deps resolved and are unaffected.
    """
    import logging

    venv_site = list((plugin.path / ".venv").glob("lib/python*/site-packages"))
    if venv_site:
        site_path = venv_site[0]
        venv_pyver = site_path.parent.name  # e.g. "python3.12"
        running_pyver = f"python{sys.version_info.major}.{sys.version_info.minor}"
        if venv_pyver != running_pyver:
            logging.getLogger(__name__).warning(
                "plugin '%s': .venv built for %s but running %s — skipping venv inject; "
                "run `uv sync` in %s to rebuild",
                plugin.name,
                venv_pyver,
                running_pyver,
                plugin.path,
            )
        else:
            site_str = str(site_path)
            if site_str not in sys.path:
                sys.path.insert(0, site_str)
    src_dir = plugin.path / "src"
    if src_dir.is_dir():
        src_str = str(src_dir)
        if src_str not in sys.path:
            sys.path.insert(0, src_str)


def _load_plugin_module(plugin: Plugin) -> types.ModuleType:
    convert_py = plugin.path / "convert.py"
    if not convert_py.exists():
        raise FileNotFoundError(f"{convert_py} not found")
    _inject_plugin_venv(plugin)
    spec_obj = importlib.util.spec_from_file_location(f"zkm_plugin_{plugin.name}", convert_py)
    if spec_obj is None or spec_obj.loader is None:
        raise ImportError(f"Could not load {convert_py}")
    mod = importlib.util.module_from_spec(spec_obj)
    spec_obj.loader.exec_module(mod)  # type: ignore[union-attr]
    if not hasattr(mod, "convert"):
        raise AttributeError(f"Plugin '{plugin.name}': convert.py has no convert() function")
    return mod


def _supports_progress(fn: object) -> bool:
    """Return True if fn declares a 'progress' keyword parameter."""
    try:
        return "progress" in inspect.signature(fn).parameters  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def _find_managed_files(store_path: Path, plugin: Plugin, mode: str) -> list[Path]:
    """Return .md files under creates_dirs that were written by this plugin."""
    import frontmatter as _fm

    candidates: list[Path] = []
    for d in plugin.creates_dirs:
        dir_path = store_path / d
        if not dir_path.exists():
            continue
        for md in sorted(dir_path.rglob("*.md")):
            try:
                post = _fm.load(md)
                if post.metadata.get("processor") != plugin.name:
                    continue
                if mode == "outdated" and post.metadata.get("processor_version") == plugin.version:
                    continue
                candidates.append(md)
            except Exception:
                continue
    return candidates
