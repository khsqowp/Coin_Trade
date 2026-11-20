# Market research inventory

This directory contains generated, read-only inventories of research and market data.
Source files remain in their original locations. No inventory command deletes, moves,
or edits source data.

Each inventory is a dated snapshot. The latest complete run is
`market_artifacts_20261120T033837Z.csv` with its paired Markdown summary,
worktree list, and 98-row registry crosswalk. Paths, sizes, Git tracking status, and any
date hints derived from paths describe the observed state at generation time.
The scanner does not calculate content hashes, and its snapshot does not prove
that a data source is licensed, point-in-time complete, or safe to delete.

Generate a fresh snapshot from the Coin_Trade root with:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/research/inventory_market_artifacts.py \
  --out-dir docs/research/inventory
```

The script writes a file-level CSV, an experiment-registry CSV, a worktree CSV,
and an aggregate Markdown report. Very large untracked trees are aggregated rather
than enumerated. It deliberately does not hash data files because they may be large
or actively written; use a separate quiescence and preservation check before any
content-level deduplication or deletion decision.
