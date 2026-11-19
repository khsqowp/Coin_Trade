# R019 source fingerprint and claim-family review — 2026-11-19

## Scope

Read-only independent verification of the current R019 synthetic artifacts and their declared source fingerprints. No market candles, strategy outcomes, or M2 labels were opened or generated.

## Fingerprint results

- Inspected all **11** `manifest.json` files under `docs/research/crypto_m4_runs/2026-11-17-r019-block-multiplier/`.
- Recomputed **30** declared runner/dependency/source hash checks against the current tracked files: **30 matched, 0 mismatched**.
- Current source hashes:

| Source | SHA-256 |
|---|---|
| `crypto_r018_paired_baseline_calibration.py` | `829663f4d197ef19637880acf7b627b33e2b47260d10d5de7b00503fc85a0d99` |
| `crypto_r019_block_multiplier_calibration.py` | `4361240d26a5b04661f4b06c4a307d566c8bba12b1a6d048b6d1a3f5c4015b09` |
| `crypto_r019_power_missingness.py` | `5b764035425fbe5c1224851feb01ce7e821f94cbcf5b18be07fc9b0dd330f84c` |

- Recomputed archive SHA-256 values and compared them with their checked-in sidecars: both matched.
  - R19-N `r19n_panels.tar.gz`: `29b656daa0582adb5fa20be7032662957536198f13d3e4a3c9828754a17181cc`
  - R19-P `r19p_panels.tar.gz`: `69a3afbd6323e735e43601eff383edc1bbacec52e9a5d07f81967c63487414cb`

## Remaining method boundary

The R19-P synthetic calibration is registered for **24 claims / 48 baseline contrasts**. The divergence OHLC-path preregistration explicitly says its intended market family is **20 claims / 40 contrasts** and that R019's larger family is not certified as that study's inference calibration. The source-hash and archive checks above establish current artifact integrity; they do not establish statistical transport from one claim family to the other.

R19-P's five applicable missingness stress cells also report zero eligible claims and zero paired coverage. Those diagnostic cells cannot be described as passes or as proof that missing data are harmless. For any future market evaluation, unresolved outcomes must remain inconclusive, stay in the all-issued denominator, and satisfy the preregistered coverage gate.

## Decision

**Fingerprint integrity: PASS for the checked current files and sidecars. Market-label authorization: NO-GO.** Claim-family mapping, eligible data/time window, unresolved-outcome coverage, and applicability of the synthetic calibration remain separate gates. This review closes only the declared source/archive fingerprint comparison; it validates no trading signal or strategy performance.
