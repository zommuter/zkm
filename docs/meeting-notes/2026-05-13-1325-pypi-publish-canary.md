# 2026-05-13 — PyPI publishing — canary + name reservation (Stage 1)

**Started:** 2026-05-13 13:25
**Session:** c7847d86-a368-4771-8eb9-d2cd4d6ac423
**Mode:** Class 2 planning record (no meeting was held — plan-mode output)
**Topic:** Publish core `zkm` to PyPI and reserve 6 plugin names as 0.0.1 stubs.

## Context

TODO item "ASAP: PyPI publishing" from the 2026-05-12-0844-publish-plugins.md session.
After GitHub publishing (A1–A9 done), PyPI is the next distribution step. Exploration
surfaced one structural blocker (filesystem-only plugin discovery) plus uniform metadata
gaps across all 7 pyprojects.

## Plan

Staged execution:
- **Stage 1 (this session):** Metadata baseline + broken-pin fix in all 7 pyprojects;
  bump-and-tag (7 commits, 7 tags); manual `uv publish` for core 0.5.0; 6 plugin names
  reserved via 0.0.1 stub wheels from `/tmp/pypi-stubs/` scratch dirs.
- **Stage 2 (follow-up):** OIDC Trusted Publisher + `.github/workflows/release.yml` in
  all 7 repos. Tracked as a new TODO item.
- **Session B (Class 3 meeting):** Plugin discovery via entry-point groups; replaces
  0.0.1 stubs with real plugin wheels.

Key scoping decisions from the planning session:
- Plugin name reservation = genuine 0.0.1 stubs from scratch dirs (not functional code
  with a caveat); avoids a confusing 0.7.0→0.0.1→0.8.0 git history in plugin repos.
- `requires-python = ">=3.14"` kept for this session; testing `>=3.11` is a separate
  TODO (classifiers will be broadened when the floor drops).
- `zkm-ner` spaCy model URL deps left as-is for this session; they are a publish blocker
  only for the real plugin code (which ships in Session B, not as a stub).

## Implementation findings

- All 7 pyproject.toml files updated: `authors`, `keywords`, `readme`, `classifiers`,
  `[project.urls]`; zkm pin widened from `>=0.3.0,<0.4.0` to `>=0.4,<1.0` in 6 plugins.
- Versions bumped: core 0.4.0→0.5.0, eml 0.7.0→0.8.0, ner 0.12.0→0.13.0,
  notmuch 0.1.1→0.2.0, pdf/photo 0.2.0→0.3.0, scan 0.1.1→0.2.0.
- `uv build` produced `dist/zkm-0.5.0-py3-none-any.whl` + `.tar.gz` cleanly.
- 400 core tests pass post-bump (no regressions).
- All 7 commits + tags pushed to fievel + GitHub.
- Docs updated: `docs/install.md` (PyPI section), `README.md` (plugin stub caveat),
  `CLAUDE.md` (Versioning one-liner), `TODO.md` (partial-done + 3 follow-ups).

Publish steps pending user prerequisites (PyPI accounts + tokens):

```bash
# Core: test.pypi.org canary, then real PyPI
cd ~/src/zkm
UV_PUBLISH_TOKEN=<test-token> uv publish --index testpypi
# verify: https://test.pypi.org/project/zkm/0.5.0/
UV_PUBLISH_TOKEN=<real-token> uv publish

# 6 stub wheels (repeat for ner/notmuch/pdf/photo/scan):
NAME=eml; MOD=zkm_$NAME
WORK=/tmp/pypi-stubs/zkm-$NAME
rm -rf $WORK && mkdir -p $WORK/src/$MOD
# (full template in plan file: nifty-toasting-reddy.md § S7)
cd $WORK && uv build && UV_PUBLISH_TOKEN=<real-token> uv publish
```

## Decisions

- **Stub form:** Genuine 0.0.1 placeholder wheels from `/tmp/pypi-stubs/` scratch dirs,
  NOT from plugin git repos — keeps git history clean; no confusing version regression.
- **`requires-python`:** `">=3.14"` unchanged this session; classifiers list only
  Python 3.14 (honest about the floor). Follow-up: test 3.11/3.12/3.13 separately.
- **zkm-ner spaCy deps:** Left as-is; publish blocker only for the real code (Session B).
  Stub uses `requires-python = ">=3.11"` and `dependencies = []`.
- **OIDC:** Stage 2 follow-up; per-project tokens available post-first-publish.
- **Plugin discovery:** Deferred to Session B (Class 3 meeting) — architectural change
  touching `convert.py:find_plugin`.

## Action items

- [x] `~/src/zkm/pyproject.toml` — metadata baseline, version 0.4.0→0.5.0, tagged v0.5.0
- [x] `plugins/zkm-eml/pyproject.toml` — metadata + pin widen, 0.7.0→0.8.0, tagged v0.8.0
- [x] `plugins/zkm-ner/pyproject.toml` — metadata + pin widen, 0.12.0→0.13.0, tagged v0.13.0
- [x] `plugins/zkm-notmuch/pyproject.toml` — metadata + pin widen, 0.1.1→0.2.0, tagged v0.2.0
- [x] `plugins/zkm-pdf/pyproject.toml` — metadata + pin widen, 0.2.0→0.3.0, tagged v0.3.0
- [x] `plugins/zkm-photo/pyproject.toml` — metadata + pin widen, 0.2.0→0.3.0, tagged v0.3.0
- [x] `plugins/zkm-scan/pyproject.toml` — metadata + pin widen, 0.1.1→0.2.0, tagged v0.2.0
- [x] `docs/install.md` — PyPI install section added
- [x] `README.md` — plugin stub caveat added
- [x] `CLAUDE.md` — Versioning one-liner added
- [x] `TODO.md` — ASAP item [~] + 3 follow-ups (Session B, Stage 2, Python 3.11 test)
- [x] `uv build` — `dist/zkm-0.5.0-py3-none-any.whl` + `.tar.gz` built
- [ ] `uv publish --index testpypi` — pending user PyPI prerequisites
- [ ] `uv publish` — pending test.pypi.org canary verification
- [ ] 6 × stub wheel publish from `/tmp/pypi-stubs/zkm-<name>/` — pending user tokens
