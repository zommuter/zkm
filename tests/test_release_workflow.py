"""Red-test spec for the tokenless OIDC release workflow (ROADMAP id:3aa3).

Stage 2 of PyPI publishing: `.github/workflows/release.yml` must publish on a
`vX.Y.Z` tag push via a PyPI **Trusted Publisher (OIDC)** handshake — with no API
token and no repo secret anywhere in the publish path. RED until that workflow
file lands.

Scope: the zkm CORE repo only. The plugin repos are separate git repos, untracked
here, and are TODO id:2b63 — nothing in this file speaks to them.

What this test can and cannot do (honesty about the instrument):
  - It pins the *structural* contract that makes the workflow tokenless: the tag
    trigger, `id-token: write`, the deployment environment, and the ABSENCE of any
    token/secret in the publish step. A regression back to token-based publishing
    fails here.
  - It does NOT prove a publish succeeds. It cannot: `zkm` is not on prod PyPI and
    publishing is deferred pending account recovery (2026-06-21 correction in
    docs/meeting-notes/2026-05-13-1325-pypi-publish-canary.md). The workflow is
    authored-and-dormant until TODO id:df4e registers the Trusted Publisher.

`yaml` is available transitively via python-frontmatter (a hard runtime dep), so
no new dependency is needed for this test.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"

# Anything that smells like a hand-held credential in the publish path.
TOKEN_MARKERS = (
    "UV_PUBLISH_TOKEN",
    "PYPI_API_TOKEN",
    "PYPI_TOKEN",
    "TWINE_PASSWORD",
    "password",
)


def _workflow() -> dict:
    if not RELEASE_WORKFLOW.exists():
        pytest.fail(
            f"{RELEASE_WORKFLOW.relative_to(REPO_ROOT)} does not exist — "
            "ROADMAP id:3aa3 has not shipped yet."
        )
    return yaml.safe_load(RELEASE_WORKFLOW.read_text(encoding="utf-8"))


def _publish_job(wf: dict) -> dict:
    jobs = wf.get("jobs") or {}
    assert jobs, "release.yml defines no jobs"
    # The job that runs the publish action; fall back to the sole job.
    for job in jobs.values():
        steps = job.get("steps") or []
        if any("gh-action-pypi-publish" in str(s.get("uses", "")) for s in steps):
            return job
    if len(jobs) == 1:
        return next(iter(jobs.values()))
    pytest.fail("no job in release.yml runs pypa/gh-action-pypi-publish")


def test_release_workflow_exists_and_is_valid_yaml():
    """The workflow file exists and parses."""
    wf = _workflow()
    assert isinstance(wf, dict), "release.yml must parse to a mapping"


def test_release_workflow_triggers_on_version_tag_only():
    """Tag-triggered (`v*`), never a branch push — a branch push must not publish."""
    wf = _workflow()
    # PyYAML parses a bare `on:` key as the boolean True; accept either spelling.
    on = wf.get("on", wf.get(True))
    assert on, "release.yml declares no trigger"
    push = on.get("push") if isinstance(on, dict) else None
    assert push, "release.yml does not trigger on push"
    tags = push.get("tags")
    assert tags, "release.yml must trigger on tag push, not branch push"
    assert any(str(t).startswith("v") for t in tags), (
        f"expected a v-prefixed tag pattern (e.g. 'v*'), got {tags!r}"
    )
    assert "branches" not in push, (
        "release.yml must NOT trigger on a branch push — tags only"
    )


def test_release_workflow_requests_oidc_id_token():
    """`id-token: write` is the whole point — it is what makes the publish tokenless."""
    wf = _workflow()
    job = _publish_job(wf)
    perms = job.get("permissions") or wf.get("permissions") or {}
    assert perms.get("id-token") == "write", (
        "the publishing job must declare `permissions: id-token: write` for the "
        f"PyPI OIDC handshake; got {perms!r}"
    )


def test_release_workflow_uses_a_deployment_environment():
    """A GitHub deployment environment gates who/what can trigger a publish."""
    wf = _workflow()
    job = _publish_job(wf)
    env = job.get("environment")
    name = env.get("name") if isinstance(env, dict) else env
    assert name, "the publishing job must set `environment:` (e.g. `pypi`)"


def test_release_workflow_publishes_with_the_trusted_publisher_action():
    """Build with uv, publish with pypa/gh-action-pypi-publish."""
    wf = _workflow()
    job = _publish_job(wf)
    steps = job.get("steps") or []
    uses = " ".join(str(s.get("uses", "")) for s in steps)
    runs = " ".join(str(s.get("run", "")) for s in steps)
    assert "pypa/gh-action-pypi-publish" in uses, (
        "publish must go through pypa/gh-action-pypi-publish (the Trusted-Publisher action)"
    )
    assert "uv build" in runs, "the workflow must build the distribution with `uv build`"


def test_release_workflow_carries_no_token_or_secret():
    """No API token, no `secrets.*` — a Trusted Publisher needs neither."""
    raw = RELEASE_WORKFLOW.read_text(encoding="utf-8") if RELEASE_WORKFLOW.exists() else ""
    if not raw:
        pytest.fail("release.yml does not exist — ROADMAP id:3aa3 has not shipped yet.")
    for marker in TOKEN_MARKERS:
        assert marker not in raw, (
            f"release.yml references {marker!r} — Stage 2 is tokenless OIDC publishing; "
            "no API token or password belongs in this workflow"
        )
    assert "secrets." not in raw, (
        "release.yml references `secrets.*` — a Trusted Publisher needs no repo secret"
    )
