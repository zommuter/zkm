# Human review queue <!-- budget: 15 min -->

Judgment calls encoded in red tests — confirm or correct the interpretation.
Max ~10 open boxes; the reviewer prunes resolved ones each review turn.

- [ ] **Qualify inbox item id:1e4f (url_sha256 frontmatter contract) — needs zkm-social context.**
  Ingested routed:7f55: document `url_sha256` in core `docs/plugin-spec.md`
  frontmatter + accept it in `zkm.conformance.FRONTMATTER_REQUIRED` for `source=social`, then
  drop the transitional sha256 dup in zkm-social's `_github.py`/`_linkedin.py`. Description is
  concrete, but it is a cross-cutting frontmatter/conformance CONTRACT change whose spec rationale
  lives in zkm-social's roadmap (id:72ef, D4) — a plugin repo this core review must NOT descend
  into. Left as TODO (not force-promoted to ROADMAP); qualify via a HANDOFF pass once the
  zkm-social D4 design is read, or a `/meeting` if the contract shape is still open. (Reverse-handoff
  D6, relay review 2026-06-30.)
