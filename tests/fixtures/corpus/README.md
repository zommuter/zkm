# Synthetic test corpus

Committed `.md` files generated from `.eml` fixtures by the `zkm-eml` converter.
Used by core pytest as a realistic mail corpus without requiring a live store.

## Structure

```
corpus/
├── CORPUS_MANIFEST.json   # inputs + regen command
├── README.md              # this file
└── mail/
    └── messages/
        └── YYYY/MM/       # one .md per email, as produced by zkm-eml convert
```

## Regen procedure

Run this when `.eml` fixtures change or `zkm-eml` output format changes:

```bash
# Step 1 — regenerate .eml fixtures and run the converter (in zkm-eml repo)
cd plugins/zkm-eml
uv run python scripts/generate_corpus.py

# Step 2 — copy the .md output to core (from repo root)
cp -r plugins/zkm-eml/tests/fixtures/corpus/mail/messages tests/fixtures/corpus/mail/

# Step 3 — update the manifest
cp plugins/zkm-eml/tests/fixtures/corpus/CORPUS_MANIFEST.json tests/fixtures/corpus/

# Step 4 — commit
git add tests/fixtures/corpus/
git commit -m "chore(corpus): regenerate synthetic corpus"
```

## Staleness signal

The **roundtrip test in `plugins/zkm-eml/tests/`** going red is the canonical
staleness signal. If `test_corpus_roundtrip.py` fails in the zkm-eml repo, the
committed corpus here is likely out of date.

Running `uv run pytest tests/test_pathological.py` in core also cross-checks
invariants; failures there indicate a pipeline regression, not a corpus staleness.

## Drift trap: subject vs. title

`zkm-eml/frontmatter.py` writes `subject:` in frontmatter, never `title:`.
The core indexers (`index.py:65`, `embed.py:479`) read `title:`, not `subject:`.

**Do not hand-author `.md` fixtures with `title:`.** Use `.eml` → converter to
produce fixtures; hand-authored files that use `title:` will silently teach the
wrong schema and mask the known subject/title gap.

The `tests/fixtures/pathological/subject_only.md` fixture documents this gap.
