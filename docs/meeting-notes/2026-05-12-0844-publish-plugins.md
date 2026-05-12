# 2026-05-12 — Publish zkm plugins to GitHub + first READMEs

**Started:** 2026-05-12 08:44
**Session:** 5c2a370d-beeb-4ff4-9fe3-f3fe90464be2
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity)
**Topic:** Decide how to publicly publish the six separately-versioned zkm plugins (currently fievel-only) and what minimum README + license scaffolding each needs.

## Agenda

1. Topology + venue (one GitHub repo per plugin, naming, visibility)
2. LICENSE policy (none currently in any of the 7 repos)
3. README scope + template (3 plugins have no README at all; eml/photo/pdf are minimal-to-substantive)
4. Privacy re-check before going public (the 2026-05-08 audit covered only core + zkm-eml)
5. Sequencing + execution (canary vs all-at-once; this session vs TODO)

## Discussion

### Item 1 — Topology + venue

**🏗️ Archie:** Six GitHub repos mirroring fievel, `github.com/zommuter/zkm-<name>`. Cross-link from core README. Avoid `--mirror`; use explicit `push github main && push github --tags`. The eml README already cross-references `Zommuter/zkm` (casing TBD) and a `messaging-spec.md` URL, anticipating the public shape.

**😈 Riku:** Three risks: (1) casing consistency — GitHub redirects but raw URLs can be case-sensitive depending on transport; (2) avoid `git push --mirror` which would push internal refs; (3) polyrepo = 6 discoverability surfaces, need cross-link list on core README.

**✂️ Petra:** Topology decided already by the 2026-05-08 reorg meeting. Don't re-litigate. One GitHub repo per plugin, names identical to fievel. No org, no monorepo subtree.

**User decision:** All public.

**User correction:** GitHub uses lowercase username — canonical is `zommuter/...`. Updates: all cross-links must use `zommuter` (lowercase); zkm-eml README's `Zommuter/zkm` references need sweeping.

### Item 2 — LICENSE policy

**🏗️ Archie:** One license for the whole polyrepo (core + 6 plugins). Standard choices for solo-maintained Python tooling: MIT (matches dep tree: uv/click/httpx/markdownify), Apache-2.0 (patent grant + NOTICE — heavier), GPL-3.0 (copyleft — overkill).

**😈 Riku:** AGPL has real effect only if (a) someone hosts a fork as a network service AND (b) you want their modifications back. Phase 3 of zkm is a FastAPI WebUI so (a) is on-roadmap. **But:** AGPL → MIT for *future state* is irreversible the moment an external contributor commits — only forks contemporaneous with MIT keep MIT permissions; the upstream re-license is unilateral while solo-authored. WTFPL is mechanically MIT but with packager-acceptance friction and a "not serious" signal that contradicts the tagged-release/spec-driven discipline already invested. AGPL on a polyrepo also creates "are plugins derivative works of the core's plugin interface?" obligation-chain questions nobody wants to answer for a personal tool.

**✂️ Petra:** Bikeshed warning. Three weeks of debate on a personal CLI is wasted. Pick MIT, move on.

**User correction on Riku's framing:** "A fork of MIT licensed state wouldn't have to adapt a later AGPL switch." Correct — only future contributions to upstream would be under the new license; forks under MIT keep their MIT permissions. Recorded for accuracy.

**Copyright line discussion:** User chose `Tobias Kienzler (Zommuter / Tobias Kienzler Solutions)` — natural-person disclosure with pseudonym + freelance-business identity. MIT accepts any holder string; this is documentary, not legal advice.

### Item 3 — README scope + template

**🏗️ Archie:** Current state: zkm-eml (171 lines, substantive), zkm-photo (78), zkm-pdf (42), zkm-ner/zkm-notmuch/zkm-scan (none).

**✂️ Petra:** N=2 satisfied: three reference READMEs already exist (eml/photo/pdf). Uniform shape: title + tagline + bullets + dev-install + license footer. Strict minimum-viable scope.

**😈 Riku:** Two hazards: (1) eml README cross-links to `messaging-spec.md` on `Zommuter/zkm` — verify it exists on the public core repo before the publish; (2) `zkm plugin add <git-url>` install path: untested for GitHub URLs in the wild. Document `cd plugins/...` dev-mode install in v1 READMEs; upgrade to `plugin add` only when verified end-to-end.

**User correction:** Add `zkm-notes` to the MVP-README authoring set — it should be usable, not just a dev demo.

**User aside (forward-flag):** "set up a new TODO on how to handle per-plugin TODOs, currently everything is directly in zkm, right? Might be an option to use gh issues for bigger ones even, though that would require /meetings modifications." Captured as Amendment session below.

### Amendment session — per-plugin TODO topology

**🏗️ Archie:** Today, `~/src/zkm/TODO.md` is the single ledger. Publishing creates three plausible topologies: (1) keep central; (2) per-plugin TODO.md + central for cross-cutting; (3) GitHub Issues for big items + TODO.md for tactical.

**😈 Riku:** Option 3 (GH Issues) requires /meeting-skill changes — current action-item emission targets `TODO.md` exclusively. Non-trivial scope; don't bundle.

**✂️ Petra:** Load-bearing follow-up but not blocking publish. Capture as TODO; dedicated meeting later. (Recorded — see Action item A12.)

### Item 4 — Privacy re-check before going public

**Privacy scan (live during meeting):**

| Concern | Result |
|---|---|
| Real names in code | zkm-ner textfilter + tests contain "Tobias"/"Kienzler" as NER false-positive stoplist patterns |
| `/home/tobias/` paths in src/tests | None |
| `.env` files tracked | None |
| `__pycache__` tracked | None |
| `.gitignore` present | 5 of 6 plugins; **zkm-scan missing** |
| zkm-ner gazetteers/orgs.yaml | Only public-corp aliases — no personal-corpus-derived entries |
| Plugin-level CLAUDE.md | Only zkm-eml has one (architecture docs) |
| Pre-reorg stale paths in READMEs | Found in eml/photo/pdf READMEs + eml/CLAUDE.md — `~/src/zkm-<name>` legacy paths |

**🏗️ Archie:** The textfilter real-name disclosure is the only non-trivial finding. The LICENSE-line decision in Item 2 already discloses real name, so the textfilter is consistent.

**😈 Riku:** Per low-paranoia-infra-disclosure profile entry, user previously chose "leave as-is" on machine names. But explicit confirmation needed; don't assume.

**User decisions:**
- **Replace** `Tobias`/`Kienzler` in zkm-ner textfilter + tests with placeholder names ("the published repo is not supposed to be tailored to my personal needs"). **Add TODO** for runtime user-identity config so any user can extend the greeting stoplist without source patching.
- **Strip** the personal-path header line from zkm-eml/CLAUDE.md ("not helpful for potential contributors with other checkout paths").

### Item 5 — Sequencing + execution

**✂️ Petra:** Canary (eml first, verify, then 5-plugin batch) reduces risk of partial-public state and catches naming/cross-link issues on one repo before multiplying.

**😈 Riku:** Concur. zkm-eml is the most cross-referenced; validating cross-link resolution on the live GitHub instance is the cheapest place to catch a bad URL.

**🏗️ Archie:** Must verify `docs/messaging-spec.md` exists on main of public core repo before eml publish.

**User concern:** Context-window compression mid-batch risk. **Mitigation accepted:** Write meeting note BEFORE execution begins (durable recovery anchor). Then proceed with canary + batch in this session.

**PyPI:** Out of scope this round (user-confirmed); add to TODO as ASAP.

## Decisions

1. **Topology.** Six public `github.com/zommuter/zkm-<name>` repos (lowercase namespace). One-to-one mirror of fievel. Explicit `git push github main && --tags`. Out of scope: GitHub Org, monorepo subtree, mixed-visibility, `--mirror`.
2. **License.** MIT, applied uniformly to core + 6 plugins. `LICENSE` file at root; `license = "MIT"` SPDX string in pyproject (hatchling 1.27+ form). Copyright line: `Copyright (c) 2026 Tobias Kienzler (Zommuter / Tobias Kienzler Solutions)`. Out of scope: CLA, CONTRIBUTING.md, NOTICE, per-plugin divergence.
3. **READMEs.** MVP-author 4 (`zkm-ner`, `zkm-notmuch`, `zkm-scan`, refresh `zkm-notes`); sweep existing 3 (`zkm-eml`, `zkm-photo`, `zkm-pdf`) for license footer + stale-path replacement (`~/src/zkm-<name>` → `plugins/zkm-<name>`) + `Zommuter` → `zommuter`. Out of scope: deep config docs, PyPI install instructions.
4. **Generality.** Published repos must not be user-tailored. Replace `Tobias`/`Kienzler` in zkm-ner stoplist+tests with `Maxine`/`Mustermann`; strip personal-path headers from eml CLAUDE.md and any README. Add runtime user-identity config as future work.
5. **Hygiene.** Add `.gitignore` to `zkm-scan` (use sibling-plugin template).
6. **Sequencing.** Meeting note written first as recovery anchor. Then: all-layer canary on `zkm-eml`, push, verify cross-links and install. Then batch the remaining 5. Verify `docs/messaging-spec.md` exists on core/main pre-canary.
7. **PyPI.** Out of scope this session; TODO tagged ASAP.
8. **Per-plugin TODO topology.** Captured as TODO + future-meeting topic; out of scope this session.

## Action items

- [ ] **A1 — License boilerplate.** Add `LICENSE` (MIT, copyright `Tobias Kienzler (Zommuter / Tobias Kienzler Solutions)`) + `license = "MIT"` SPDX string in `[project]` of `pyproject.toml` for: `~/src/zkm/`, `plugins/zkm-eml/`, `plugins/zkm-ner/`, `plugins/zkm-notmuch/`, `plugins/zkm-pdf/`, `plugins/zkm-photo/`, `plugins/zkm-scan/`. Contract: `find ~/src/zkm -name LICENSE -not -path '*/node_modules/*' -not -path '*/.git/*' | wc -l` ≥ 7; each pyproject grep shows `^license = "MIT"$`.
- [ ] **A2 — Author MVP READMEs.** Create `plugins/zkm-ner/README.md`, `plugins/zkm-notmuch/README.md`, `plugins/zkm-scan/README.md`; refresh `examples/zkm-notes/README.md` to match the uniform shape. Contract: each file ≥25 lines, links to `https://github.com/zommuter/zkm`, ends with `License: MIT — see LICENSE`.
- [ ] **A3 — Sweep existing READMEs.** Update `plugins/zkm-eml/README.md`, `plugins/zkm-pdf/README.md`, `plugins/zkm-photo/README.md`: append uniform license footer; replace `~/src/zkm-<name>` and `~/src/zkm/plugins/zkm-<name>` with `plugins/zkm-<name>` (relative form); fix `Zommuter/zkm` → `zommuter/zkm`. Contract: `grep -r '~/src/zkm' plugins/*/README.md` returns empty; `grep -r 'Zommuter' plugins/*/README.md plugins/*/CLAUDE.md` returns empty.
- [ ] **A4 — Generality fixes for zkm-ner.** Replace `Tobias`/`Kienzler` in `plugins/zkm-ner/src/zkm_ner/textfilter.py` and `plugins/zkm-ner/tests/test_textfilter.py` with `Maxine`/`Mustermann` placeholder. Contract: `grep -i -E 'tobias|kienzler' plugins/zkm-ner/src plugins/zkm-ner/tests` returns empty; existing tests still pass (`uv run pytest` in plugin dir green).
- [ ] **A5 — Strip personal headers from eml CLAUDE.md.** Remove `Repo: ~/src/zkm/plugins/zkm-eml/` and rewrite any dev-setup commands to relative paths. Contract: `grep -E '~/src|/home/' plugins/zkm-eml/CLAUDE.md` returns empty.
- [ ] **A6 — Add `.gitignore` to zkm-scan.** Use the same template as `plugins/zkm-eml/.gitignore`. Contract: `test -f plugins/zkm-scan/.gitignore` passes; `git -C plugins/zkm-scan check-ignore __pycache__/foo.pyc` succeeds.
- [ ] **A7 — Canary: publish zkm-eml.** From `plugins/zkm-eml/`: `gh repo create zommuter/zkm-eml --public --source=. --remote=github` (or equivalent); `git push github main && git push github --tags`. Verify `docs/messaging-spec.md` exists on `zommuter/zkm` main pre-push. Contract: `gh repo view zommuter/zkm-eml` returns public; raw-githubusercontent fetch of README succeeds; messaging-spec.md cross-link returns 200.
- [ ] **A8 — Batch: publish the other 5 plugins.** Same pattern as A7 for `zkm-ner`, `zkm-notmuch`, `zkm-pdf`, `zkm-photo`, `zkm-scan`. Add `zkm-plugin` topic during create. Contract: all 6 listed at `gh repo list zommuter --topic zkm-plugin`.
- [ ] **A9 — Cross-link from core README.** Add a "Plugins" section in `~/src/zkm/README.md` listing all 6 plugin repos with one-line descriptions. Contract: `grep -c 'github.com/zommuter/zkm-' README.md` ≥ 6.
- [ ] **A10 — TODO ASAP: PyPI publishing.** Add to `~/src/zkm/TODO.md` an item tagged ASAP: investigate PyPI publishing for core + 6 plugins (account, name reservation, `uv build`/`uv publish`, classifiers, version-bump-and-publish workflow).
- [ ] **A11 — TODO: runtime user-identity config for zkm-ner.** Add to `~/src/zkm/TODO.md`: spec a `ZKM_NER_USER_NAMES` env var (or per-store config) so the greeting stoplist can be extended at runtime without source patching. Useful for any deployment beyond Tobias's own corpus.
- [ ] **A12 — TODO + future meeting: per-plugin TODO topology.** Add to `~/src/zkm/TODO.md`: decide how to split TODO ownership across plugin repos now that they're independently published (single-central / per-plugin / GH Issues). The GH-Issues option would need /meeting-skill modifications to emit issue refs as action items. Schedule a dedicated design meeting.
