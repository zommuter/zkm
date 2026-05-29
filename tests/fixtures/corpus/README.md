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

Run this when `.eml` fixtures change or `zkm-eml` / `zkm-ner` output format changes:

```bash
# Step 1 — regenerate .eml fixtures (in zkm-eml repo)
cd plugins/zkm-eml
uv run python scripts/generate_corpus.py

# Step 2 — convert .eml → .md + populate entities[] via NER (from repo root)
# Uses Python API directly so source_dir is precise (env var EML_SOURCE_DIR
# is not read by the converter — config-key only, post-M2).
uv run python - <<'EOF'
import sys; sys.path.insert(0, "plugins/zkm-eml")
from pathlib import Path
from convert import convert
store = Path("/tmp/zkm-corpus-regen")
store.mkdir(parents=True, exist_ok=True)
(store / ".git").mkdir(exist_ok=True)
for d in ("mail/messages", "mail/threads", "originals/mail"):
    (store / d).mkdir(parents=True, exist_ok=True)
created = convert(store, {"source_dir": "plugins/zkm-eml/tests/fixtures/corpus",
                           "keep_originals": False, "quote_strip": False})
print(f"Converted {len(created)} .md files")
EOF
# Run NER amender from zkm-ner's own venv (avoids numpy venv conflicts in core):
(cd plugins/zkm-ner && uv run python -c "
from pathlib import Path
from convert import convert
convert(Path('/tmp/zkm-corpus-regen'), {})
")

# Step 3 — copy only .md files to core (no .amendments.json)
find /tmp/zkm-corpus-regen/mail/messages -name '*.md' | while read f; do
  dest="tests/fixtures/corpus/mail/messages/${f#/tmp/zkm-corpus-regen/mail/messages/}"
  mkdir -p "$(dirname "$dest")"; command cp "$f" "$dest"
done

# Step 4 — update the manifest (update sha256 entries for any new/changed .eml)
# edit tests/fixtures/corpus/CORPUS_MANIFEST.json manually

# Step 5 — commit
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
