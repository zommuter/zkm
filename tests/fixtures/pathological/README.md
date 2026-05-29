# Pathological test fixtures

These fixtures deliberately violate or stress-test converter output assumptions.
They document known edge cases and limitations — not bugs to fix in the tests,
but invariants to assert about the indexing/embedding pipeline's behaviour.

## oversized_entities.md

Contains enough `entities[]` entries that their combined `value` strings exceed
`_MAX_PREFIX_CHARS` (500 chars). Tests that `_chunk_texts` in `embed.py` applies
the prefix cap and never produces a chunk with a metadata prefix longer than 500 chars.

## html_entity_ner.md

Contains `entities[]` with HTML-entity artifact strings (e.g. `&gt;&nbsp;`) that
have been marked `valid: false` by the NER pipeline. Tests that `_tokenize_doc`
in `index.py` and `_chunk_texts` in `embed.py` both skip `valid: false` entries,
so these artifacts do not pollute the search index.

The root cause (HTML entities undecoded pre-NER in zkm-eml) is tracked as
**N9c-html** in `TODO.md`.

## subject_only.md

Contains a `subject:` field in frontmatter but no `title:` field, and the
subject term does not appear in the body. Documents the known limitation:
`index.py` reads `title` for BM25 tokenisation, not `subject` — so a document
is not searchable by its subject-line alone.

This is a drift trap: `zkm-eml/frontmatter.py` writes `subject:`, never `title:`.
Any hand-authored `.md` fixture using `title:` teaches the wrong schema.
The fix (write `title:` from `subject:` in the converter) is tracked separately.
