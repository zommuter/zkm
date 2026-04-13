# Temporal queries via git history

Inspired by [DiffMem](https://github.com/Growth-Kinetics/DiffMem). Phase 4 feature.

## Core idea

The knowledge store is a git repo. Every `zkm convert` run commits new/updated files. This means git already tracks the full temporal evolution of your knowledge — no separate temporal database needed.

**Two query surfaces:**

1. **Current state (HEAD):** What do I know *right now*? This is what BM25 indexes. Fast, compact, no historical noise. This is the default for `zkm search` and `zkm query`.

2. **History (git log/diff):** How has this knowledge *changed*? When did I first learn X? What did I know about Y last month? This requires git operations, not BM25.

## Concrete operations

### "When did I first mention X?"

```bash
git log --all --diff-filter=A -S "Stadtwerke" --format="%ai %s" -- '*.md'
```

Finds the commit that *added* a file containing "Stadtwerke". The commit date is when that knowledge entered the store.

### "How has my understanding of X evolved?"

```bash
git log -p -S "project-alpha" -- notes/
```

Shows every commit that changed a line containing "project-alpha", with diffs. The LLM can summarize the progression.

### "What did I know about X on date Y?"

```bash
git show $(git rev-list -1 --before="2025-12-01" HEAD):notes/project-alpha.md
```

Retrieves the exact state of a file as of a specific date. Combined with BM25 over that snapshot, you could search your past knowledge.

### "What changed in the last week?"

```bash
git diff HEAD@{7.days.ago} -- '*.md'
```

Shows all knowledge additions/modifications in the past week. Good for a "weekly review" or digest.

## Architecture in zkm

Phase 4 adds temporal query modes to `zkm query`:

```
zkm query "when did I first hear about project-alpha" --temporal
```

The query handler detects temporal intent (keywords like "when", "first", "changed", "history", "evolution") and routes to git operations instead of BM25. The git output becomes LLM context for summarization.

This mirrors DiffMem's multi-depth context assembly:

| Depth | Source | Use case |
|-------|--------|----------|
| basic | BM25 top-k from HEAD | Quick factual lookup |
| wide | BM25 with more results | Broader context |
| deep | Full file contents | Detailed reading |
| temporal | git log + diff | Evolution questions |

## Why not store timestamps in a DB?

- Git already has them (commit dates, author dates)
- Diffs are structural — they show *what changed*, not just *when*
- No sync problem — git history is the history, by definition
- `git bisect` style operations become possible for debugging knowledge conflicts
- The store remains a plain directory of markdown files, queryable with standard unix tools
- However, consider that commit dates may not reflect file or content dates, especially when importing historical memories! It might be worth considering performing historical imports in orphan branches which are then merged into the main branch, but this might become unneccesarily messy

## Limitations

- Git operations are slower than DB queries for large repos (10K+ files). Mitigation: narrow the search with path filters (`-- mail/2025/`)
- Rebasing or squashing destroys temporal information. Convention: never rebase the knowledge store, only append.
- Git doesn't index file *content* — `-S` does a full scan. For very large stores, a cached reverse index of git history might be needed.

## Relation to memory compaction

DiffMem's "writer agent" consolidates memories into entity files. In zkm, this maps to a Phase 4 compaction step:

1. Accumulate raw entries (emails, messages, notes) in their respective dirs
2. Periodically, an LLM reads all mentions of entity X across files
3. Writes/updates a summary file like `entities/frank.md`
4. The raw files remain for history; the entity file is the "current understanding"
5. Git tracks the entity file's evolution — you can see how your understanding of Frank changed over time

This is explicitly Phase 4 because it requires reliable NER (Phase 2) and a working query pipeline (Phase 1) before it adds value.
