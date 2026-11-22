# Community4 deduplication notes

- Read all four existing `INDEX.csv` files before collection: `github_tv` (138 rows), `community` (20), `community2` (81), and `community3` (80), for 319 pre-existing index entries.
- Compared normalized strategy names against all existing index names and omitted exact normalized-name matches. No existing source URL was reused in this pass.
- Kept similarly named implementations only when they came from separate Pine files and exposed a different entry/exit implementation. This is source-level distinctness, not evidence that their economic behavior is independent.
- IDs and output slugs are unique within `community4`. No previous archive files were edited.
- One additional, separately sourced Upbit K=0.5 volatility-breakout record was added from an article with explicit daily rules; its instrument and exit differ from the existing academic Upbit ETH entries.
- The source repository contains many near-duplicates and scraped scripts. The selected set is a targeted collection, not a claim that all strategies in the repository are independent or high quality.
