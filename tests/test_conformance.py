"""Tests for the zkm plugin conformance validator (zkm test <plugin>)."""

from __future__ import annotations

from pathlib import Path

FIXTURE_PLUGINS = Path(__file__).parent / "fixtures" / "test_plugins"


def _load_plugin(subdir: str):
    """Load a fixture plugin directly by subdir name (no find_plugin name-matching)."""
    from zkm.convert import load_plugin_manifest
    path = FIXTURE_PLUGINS / subdir
    return load_plugin_manifest(path)


# ---------------------------------------------------------------------------
# validate_frontmatter unit tests
# ---------------------------------------------------------------------------


class TestValidateFrontmatter:
    def test_valid_minimal(self):
        from zkm.conformance import validate_frontmatter

        meta = {
            "source": "myplugin",
            "date": "2026-01-01T10:00:00+01:00",
            "tags": [],
            "sha256": "abc123",
            "processor": "myplugin",
            "processor_version": "0.1.0",
        }
        assert validate_frontmatter(meta, "myplugin") == []

    def test_missing_required_fields(self):
        from zkm.conformance import validate_frontmatter

        fails = validate_frontmatter({}, "myplugin")
        messages = [f.message for f in fails]
        assert any("source" in m for m in messages)
        assert any("sha256" in m for m in messages)
        assert any("processor" in m for m in messages)

    def test_source_mismatch(self):
        from zkm.conformance import validate_frontmatter

        meta = {
            "source": "other",
            "date": "2026-01-01T10:00:00+01:00",
            "tags": [],
            "sha256": "abc",
            "processor": "myplugin",
            "processor_version": "0.1.0",
        }
        fails = [f for f in validate_frontmatter(meta, "myplugin") if f.level == "fail"]
        assert any("source" in f.message for f in fails)

    def test_date_without_timezone(self):
        from zkm.conformance import validate_frontmatter

        meta = {
            "source": "p",
            "date": "2026-01-01",  # no time component or tz
            "tags": [],
            "sha256": "x",
            "processor": "p",
            "processor_version": "0.1.0",
        }
        fails = [f for f in validate_frontmatter(meta, "p") if f.level == "fail"]
        assert any("date" in f.message for f in fails)

    def test_tags_not_list(self):
        from zkm.conformance import validate_frontmatter

        meta = {
            "source": "p",
            "date": "2026-01-01T10:00:00+01:00",
            "tags": "notalist",
            "sha256": "x",
            "processor": "p",
            "processor_version": "0.1.0",
        }
        fails = [f for f in validate_frontmatter(meta, "p") if f.level == "fail"]
        assert any("tags" in f.message for f in fails)

    def test_messaging_extension_valid(self):
        from zkm.conformance import validate_frontmatter

        meta = {
            "source": "p",
            "date": "2026-01-01T10:00:00+01:00",
            "tags": [],
            "sha256": "x",
            "processor": "p",
            "processor_version": "0.1.0",
            "message_id": "<abc@example.com>",
            "thread_id": "<abc@example.com>",
            "participants": [
                {"address": "alice@example.com", "role": "from"},
                {"address": "bob@example.com", "role": "to"},
            ],
        }
        assert validate_frontmatter(meta, "p") == []

    def test_messaging_extension_missing_thread_id(self):
        from zkm.conformance import validate_frontmatter

        meta = {
            "source": "p",
            "date": "2026-01-01T10:00:00+01:00",
            "tags": [],
            "sha256": "x",
            "processor": "p",
            "processor_version": "0.1.0",
            "message_id": "<abc@example.com>",
            "participants": [{"address": "a@b.com", "role": "from"}],
        }
        fails = [f for f in validate_frontmatter(meta, "p") if f.level == "fail"]
        assert any("thread_id" in f.message for f in fails)

    def test_messaging_extension_uppercase_address(self):
        from zkm.conformance import validate_frontmatter

        meta = {
            "source": "p",
            "date": "2026-01-01T10:00:00+01:00",
            "tags": [],
            "sha256": "x",
            "processor": "p",
            "processor_version": "0.1.0",
            "message_id": "<abc@example.com>",
            "thread_id": "<abc@example.com>",
            "participants": [{"address": "Alice@Example.COM", "role": "from"}],
        }
        fails = [f for f in validate_frontmatter(meta, "p") if f.level == "fail"]
        assert any("lowercase" in f.message for f in fails)


# ---------------------------------------------------------------------------
# Fixture plugin tests
# ---------------------------------------------------------------------------


class TestGoodPlugin:
    def test_conformant(self):
        from zkm.conformance import run_conformance

        plugin = _load_plugin("good")
        report = run_conformance(plugin)
        assert not report.failed, f"Expected no failures; got: {report.findings}"
        assert report.dynamic_ran

    def test_no_fail_findings(self):
        from zkm.conformance import run_conformance

        plugin = _load_plugin("good")
        report = run_conformance(plugin)
        fails = [f for f in report.findings if f.level == "fail"]
        assert fails == []


class TestBadManifest:
    def test_fails(self):
        from zkm.conformance import run_conformance

        plugin = _load_plugin("bad_manifest")
        report = run_conformance(plugin)
        assert report.failed

    def test_zkm_prefix_flagged(self):
        from zkm.conformance import check_manifest

        plugin = _load_plugin("bad_manifest")
        findings = check_manifest(plugin)
        assert any("zkm-" in f.message for f in findings if f.level == "fail")

    def test_bad_version_flagged(self):
        from zkm.conformance import check_manifest

        plugin = _load_plugin("bad_manifest")
        findings = check_manifest(plugin)
        assert any("version" in f.message for f in findings if f.level == "fail")

    def test_absolute_creates_dirs_flagged(self):
        from zkm.conformance import check_manifest

        plugin = _load_plugin("bad_manifest")
        findings = check_manifest(plugin)
        assert any("absolute" in f.message for f in findings if f.level == "fail")

    def test_dotdot_creates_dirs_flagged(self):
        from zkm.conformance import check_manifest

        plugin = _load_plugin("bad_manifest")
        findings = check_manifest(plugin)
        assert any(".." in f.message for f in findings if f.level == "fail")

    def test_non_dict_config_entry_flagged(self):
        from zkm.conformance import check_manifest

        plugin = _load_plugin("bad_manifest")
        findings = check_manifest(plugin)
        assert any("key1" in f.message and f.level == "fail" for f in findings)

    def test_absolute_gitignore_pattern_flagged(self, tmp_path):
        from zkm.conformance import check_manifest
        from zkm.convert import load_plugin_manifest

        (tmp_path / "plugin.yaml").write_text(
            "name: p\nversion: 0.1.0\ncreates_dirs: []\ngitignore_patterns:\n  - /inbox/bad\n"
        )
        plugin = load_plugin_manifest(tmp_path)
        findings = check_manifest(plugin)
        assert any("leading /" in f.message for f in findings if f.level == "fail")


class TestBadSignature:
    def test_fails(self):
        from zkm.conformance import run_conformance

        plugin = _load_plugin("bad_signature")
        report = run_conformance(plugin)
        assert report.failed

    def test_progress_flagged(self):
        from zkm.conformance import check_interface

        plugin = _load_plugin("bad_signature")
        findings = check_interface(plugin)
        assert any("progress" in f.message for f in findings if f.level == "fail")


class TestBadFrontmatter:
    def test_fails(self):
        from zkm.conformance import run_conformance

        plugin = _load_plugin("bad_frontmatter")
        report = run_conformance(plugin)
        assert report.failed
        assert report.dynamic_ran

    def test_missing_sha256_flagged(self):
        from zkm.conformance import run_conformance

        plugin = _load_plugin("bad_frontmatter")
        report = run_conformance(plugin)
        assert any("sha256" in f.message for f in report.findings if f.level == "fail")


class TestNoFixtures:
    def test_conformant_static_only(self):
        from zkm.conformance import run_conformance

        plugin = _load_plugin("no_fixtures")
        report = run_conformance(plugin)
        assert not report.failed
        assert not report.dynamic_ran


# ---------------------------------------------------------------------------
# Amender 'created' parameter expectation (ROADMAP id:e1fc — currently RED)
# roadmap:e1fc
# ---------------------------------------------------------------------------


def _make_tmp_plugin(tmp_path, *, kind: str, convert_src: str):
    """Build a throwaway plugin dir and return its loaded manifest."""
    from zkm.convert import load_plugin_manifest

    kind_line = f"kind: {kind}\n" if kind else ""
    (tmp_path / "plugin.yaml").write_text(
        f"name: tmpfix\nversion: 0.1.0\ndescription: fixture\n{kind_line}"
    )
    (tmp_path / "convert.py").write_text(convert_src)
    return load_plugin_manifest(tmp_path)


_CONVERT_NO_CREATED = (
    "def convert(store_path, config, *, progress=None):\n    return []\n"
)
_CONVERT_WITH_CREATED = (
    "def convert(store_path, config, *, progress=None, created=None):\n    return []\n"
)


class TestAmenderCreatedParam:
    # roadmap:e1fc — RED spec
    def test_amender_without_created_param_warns(self, tmp_path):
        from zkm.conformance import check_interface

        plugin = _make_tmp_plugin(tmp_path, kind="amender", convert_src=_CONVERT_NO_CREATED)
        warns = [f for f in check_interface(plugin) if f.level == "warn"]
        assert any("created" in f.message for f in warns), (
            "amender convert() without 'created' kwarg must produce a warn-level finding"
        )

    # roadmap:e1fc — GUARD (green pre-implementation; pins warn-not-fail + scoping)
    def test_amender_with_created_param_no_warning(self, tmp_path):
        from zkm.conformance import check_interface

        plugin = _make_tmp_plugin(tmp_path, kind="amender", convert_src=_CONVERT_WITH_CREATED)
        assert not any("created" in f.message for f in check_interface(plugin))

    # roadmap:e1fc — GUARD: converter-kind plugins are exempt
    def test_converter_without_created_param_no_warning(self, tmp_path):
        from zkm.conformance import check_interface

        plugin = _make_tmp_plugin(tmp_path, kind="", convert_src=_CONVERT_NO_CREATED)
        assert not any("created" in f.message for f in check_interface(plugin))

    # roadmap:e1fc — RED spec: never fail-level (existing amenders must stay shippable)
    def test_amender_created_finding_is_warn_not_fail(self, tmp_path):
        from zkm.conformance import check_interface

        plugin = _make_tmp_plugin(tmp_path, kind="amender", convert_src=_CONVERT_NO_CREATED)
        findings = [f for f in check_interface(plugin) if "created" in f.message]
        assert findings and all(f.level == "warn" for f in findings)


class TestResolveConformanceConfig:
    """roadmap:a285 — run_dynamic must not clobber non-path config scalars."""

    # roadmap:a285 — RED spec: a real fixture path resolves; a scalar selector
    # (e.g. `network: linkedin`) passes through UNCHANGED. The current loop
    # resolves every value as a plugin-relative path, so the scalar is clobbered.
    def test_run_dynamic_preserves_non_path_config(self, tmp_path):
        from zkm.conformance import _resolve_conformance_config

        (tmp_path / "fixtures").mkdir()
        conf_config = {"fixtures": "fixtures", "network": "linkedin"}

        resolved = _resolve_conformance_config(tmp_path, conf_config)

        # real path key → absolute, points at the existing dir
        assert resolved["fixtures"] == str((tmp_path / "fixtures").resolve())
        # scalar selector key → unchanged (NOT a bogus resolved path)
        assert resolved["network"] == "linkedin"
