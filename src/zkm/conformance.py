"""Plugin conformance validator for `zkm test <plugin>`."""

from __future__ import annotations

import inspect
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Schema constants — single source of truth for required frontmatter fields
# ---------------------------------------------------------------------------

FRONTMATTER_REQUIRED = [
    "source",
    "date",
    "tags",
    "sha256",
    "processor",
    "processor_version",
]

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+")

# config entry keys allowed by the plugin spec
_CONFIG_ENTRY_KNOWN_KEYS = {"required", "default", "description", "secret"}

# ---------------------------------------------------------------------------
# Finding / Report model
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    level: str   # "fail" | "warn"
    check: str   # "manifest" | "interface" | "frontmatter" | "dynamic"
    message: str

    def __str__(self) -> str:
        tag = "FAIL" if self.level == "fail" else "WARN"
        return f"  [{tag}] {self.check}: {self.message}"


@dataclass
class Report:
    plugin: str
    findings: list[Finding] = field(default_factory=list)
    dynamic_ran: bool = False

    @property
    def failed(self) -> bool:
        return any(f.level == "fail" for f in self.findings)


# ---------------------------------------------------------------------------
# Frontmatter validator (reusable helper)
# ---------------------------------------------------------------------------


def validate_frontmatter(meta: dict, plugin_name: str) -> list[Finding]:
    """
    Validate a single frontmatter metadata dict against the core schema.

    Returns a list of Findings (level="fail") for each violation.
    """
    findings: list[Finding] = []

    for key in FRONTMATTER_REQUIRED:
        if key not in meta:
            findings.append(Finding("fail", "frontmatter", f"missing required field '{key}'"))

    if meta.get("source") and meta["source"] != plugin_name:
        findings.append(Finding(
            "fail", "frontmatter",
            f"source={meta['source']!r} != plugin name {plugin_name!r}",
        ))
    if meta.get("processor") and meta["processor"] != plugin_name:
        findings.append(Finding(
            "fail", "frontmatter",
            f"processor={meta['processor']!r} != plugin name {plugin_name!r}",
        ))

    if "date" in meta:
        from datetime import datetime as _dt
        date_val = meta["date"]
        if isinstance(date_val, _dt):
            # python-frontmatter parsed the YAML date — require tz-awareness
            if date_val.tzinfo is None:
                findings.append(Finding("fail", "frontmatter", "date has no timezone"))
        else:
            # Raw string — check for ISO 8601 with tz markers
            date_str = str(date_val)
            if "T" not in date_str or (
                not date_str.endswith("Z")
                and "+" not in date_str[10:]
                and date_str.count("-") < 3  # negative UTC offset has extra "-"
            ):
                findings.append(Finding(
                    "fail", "frontmatter",
                    f"date={date_str!r} is not ISO 8601 with timezone",
                ))

    if "tags" in meta and not isinstance(meta["tags"], list):
        findings.append(Finding("fail", "frontmatter", "tags must be a list"))

    # Messaging extension: conditional on message_id presence
    if "message_id" in meta:
        for mfield in ("thread_id", "participants"):
            if mfield not in meta:
                findings.append(Finding(
                    "fail", "frontmatter",
                    f"messaging plugin: missing '{mfield}' (message_id present)",
                ))
        participants = meta.get("participants", [])
        if isinstance(participants, list):
            for i, p in enumerate(participants):
                if not isinstance(p, dict):
                    findings.append(
                        Finding("fail", "frontmatter", f"participants[{i}] must be a dict")
                    )
                    continue
                if "address" not in p:
                    findings.append(
                        Finding("fail", "frontmatter", f"participants[{i}] missing 'address'")
                    )
                elif p["address"] != p["address"].lower():
                    findings.append(Finding(
                        "fail", "frontmatter",
                        f"participants[{i}].address must be lowercase",
                    ))
                if "role" not in p:
                    findings.append(
                        Finding("fail", "frontmatter", f"participants[{i}] missing 'role'")
                    )

    return findings


# ---------------------------------------------------------------------------
# Check 1: manifest
# ---------------------------------------------------------------------------


def check_manifest(plugin) -> list[Finding]:  # plugin: Plugin
    findings: list[Finding] = []

    # name must be bare (no zkm- prefix) and match the dir name after stripping
    dir_name = plugin.path.name.removeprefix("zkm-")
    if plugin.name.startswith("zkm-"):
        findings.append(
            Finding("fail", "manifest", f"name={plugin.name!r} must not carry 'zkm-' prefix")
        )
    elif plugin.name != dir_name:
        findings.append(
            Finding(
                "warn",
                "manifest",
                f"name={plugin.name!r} does not match dir name '{dir_name}'"
                " (expected same after removeprefix)",
            )
        )

    # version must look like semver
    if not _SEMVER_RE.match(plugin.version):
        findings.append(
            Finding("fail", "manifest", f"version={plugin.version!r} does not match semver X.Y.Z")
        )

    # creates_dirs: each must be a relative POSIX path with no leading / or ..
    for d in plugin.creates_dirs:
        p = Path(d)
        if p.is_absolute():
            findings.append(Finding("fail", "manifest", f"creates_dirs entry {d!r} is absolute"))
        elif ".." in p.parts:
            findings.append(Finding("fail", "manifest", f"creates_dirs entry {d!r} contains '..'"))

    # config entries: each value must be a dict with only known keys
    for k, spec in plugin.config_keys.items():
        if not isinstance(spec, dict):
            findings.append(
                Finding("fail", "manifest", f"config.{k} must be a dict, got {type(spec).__name__}")
            )
            continue
        unknown = set(spec.keys()) - _CONFIG_ENTRY_KNOWN_KEYS
        if unknown:
            findings.append(
                Finding("warn", "manifest", f"config.{k} has unknown keys: {sorted(unknown)}")
            )

    # recommended: description
    if not plugin.description:
        findings.append(Finding("warn", "manifest", "missing 'description' field (recommended)"))

    # recommended: README.md
    if not (plugin.path / "README.md").exists():
        findings.append(Finding("warn", "manifest", "missing README.md (recommended)"))

    return findings


# ---------------------------------------------------------------------------
# Check 2: interface
# ---------------------------------------------------------------------------


def check_interface(plugin) -> list[Finding]:  # plugin: Plugin
    from zkm.convert import _load_plugin_module

    findings: list[Finding] = []
    try:
        mod = _load_plugin_module(plugin)
    except (FileNotFoundError, ImportError, AttributeError, Exception) as e:
        findings.append(Finding("fail", "interface", f"could not load plugin module: {e}"))
        return findings

    # convert() — must exist and accept (store_path, config) positionally + progress kwarg
    try:
        sig = inspect.signature(mod.convert)
        params = list(sig.parameters.values())
        positional = [
            p for p in params
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        ]
        if len(positional) < 2:
            findings.append(Finding(
                "fail", "interface",
                "convert() needs ≥2 positional params (store_path, config);"
                f" got {len(positional)}",
            ))
        if "progress" not in sig.parameters:
            findings.append(
                Finding("fail", "interface", "convert() missing 'progress' keyword parameter")
            )
    except (TypeError, ValueError) as e:
        findings.append(Finding("fail", "interface", f"cannot inspect convert() signature: {e}"))

    # scrub() — optional; if present check shape
    if hasattr(mod, "scrub"):
        try:
            sig = inspect.signature(mod.scrub)
            params = sig.parameters
            for required_kw in ("dry_run", "verbose", "progress"):
                if required_kw not in params:
                    findings.append(
                        Finding(
                            "fail", "interface",
                            f"scrub() missing keyword param '{required_kw}'",
                        )
                    )
        except (TypeError, ValueError) as e:
            findings.append(Finding("fail", "interface", f"cannot inspect scrub() signature: {e}"))

    # reprocess() — optional; if present check shape
    if hasattr(mod, "reprocess"):
        try:
            sig = inspect.signature(mod.reprocess)
            params = list(sig.parameters.values())
            positional = [
                p for p in params
                if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
            ]
            if len(positional) < 3:
                findings.append(Finding(
                    "fail", "interface",
                    "reprocess() needs ≥3 positional params (store_path, config, existing);"
                    f" got {len(positional)}",
                ))
            if "progress" not in sig.parameters:
                findings.append(Finding(
                    "fail", "interface",
                    "reprocess() missing 'progress' keyword parameter",
                ))
        except (TypeError, ValueError) as e:
            findings.append(Finding(
                "fail", "interface",
                f"cannot inspect reprocess() signature: {e}",
            ))

    return findings


# ---------------------------------------------------------------------------
# Check 3 (dynamic): run convert() against conformance fixtures
# ---------------------------------------------------------------------------


def run_dynamic(plugin) -> list[Finding]:  # plugin: Plugin
    """
    Run convert() against the plugin's declared conformance fixtures in a temp store
    and validate every emitted frontmatter document against FRONTMATTER_REQUIRED.

    Calls the plugin module directly (bypasses find_plugin / run_convert) so that
    conformance tests work regardless of ZKM_PLUGINS_DIR configuration.
    """
    import shutil

    import frontmatter as _fm

    from zkm.convert import _load_plugin_module, _supports_progress

    findings: list[Finding] = []
    conf_config: dict = plugin.conformance.get("config", {})

    # Resolve relative fixture paths against the plugin root
    config: dict[str, str] = {}
    for k, v in conf_config.items():
        resolved = plugin.path / str(v)
        config[k] = str(resolved.resolve())

    tmp = tempfile.mkdtemp(prefix="zkm-test-")
    tmp_store = Path(tmp)
    try:
        (tmp_store / "originals").mkdir()

        try:
            mod = _load_plugin_module(plugin)
        except Exception as e:
            findings.append(Finding("fail", "dynamic", f"could not load module: {e}"))
            return findings

        # Create declared dirs (mirrors what run_convert does)
        for d in plugin.creates_dirs:
            (tmp_store / d).mkdir(parents=True, exist_ok=True)

        kwargs: dict = {}
        if _supports_progress(mod.convert):
            kwargs["progress"] = None

        try:
            produced = mod.convert(tmp_store, config, **kwargs) or []
            produced = [Path(p) for p in produced]
        except Exception as e:
            findings.append(Finding("fail", "dynamic", f"convert() raised an exception: {e}"))
            return findings

        if not produced:
            findings.append(Finding(
                "fail", "dynamic",
                "convert() produced 0 files against conformance fixtures",
            ))

        for md_path in produced:
            try:
                post = _fm.load(md_path)
                meta = post.metadata
            except Exception as e:
                findings.append(Finding(
                    "fail", "dynamic",
                    f"{md_path.name}: could not parse frontmatter: {e}",
                ))
                continue
            for f in validate_frontmatter(meta, plugin.name):
                findings.append(Finding(f.level, "dynamic", f"{md_path.name}: {f.message}"))

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return findings


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_conformance(plugin) -> Report:
    """Run all applicable conformance checks for *plugin* and return a Report."""
    report = Report(plugin=plugin.name)

    report.findings.extend(check_manifest(plugin))
    report.findings.extend(check_interface(plugin))

    conf_config = plugin.conformance.get("config", {})
    if conf_config:
        report.dynamic_ran = True
        report.findings.extend(run_dynamic(plugin))

    return report
