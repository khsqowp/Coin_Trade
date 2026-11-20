# Contract–mark deviation M2 diagnostic

Status: **historical exploratory diagnostic; not untouched OOS, not an execution result, and not Core approval.**

- Trial: `mark-deviation-m2-20261121-v1`
- Data fingerprint: `7a1f9dd85d9bfb9f5cd23fb75bd9cedeb24e942b9aa4f37f223926bec7b3095c`
- Selected-target manifest SHA-256: `c7093f18d25e637e47a92d89e9f5852617d863c272d8da8c12f9f3bfffd97200`
- Whole-manifest snapshot SHA-256: `69ddfb9dc4a65ed77ada013b2e4621db83aa311a3c2a7284bf3e0d9ed7c96997` (rows=13648; unrelated appends are outside the frozen input set)
- Scoring interval: `[2026-07-01T00:00:00Z, 2026-11-01T00:00:00Z)`
- Scoring symbols: 34 fixed symbols; the full list is in the preregistration.
- Preregistration SHA-256: `753992091c191f086a2b9e61fc502cf868fb6e0707157ca47f97f1d8963ea94e`
- Runner SHA-256: `3b71acd108ba7d25df0307b7b8d71c0cfe3dbcaf888135a53f79ff5720d2649a`

| Horizon | Signals | Symbols | M2 target-first | Wilson 95% | 7d block M2 95% | M1 direction | Momentum M2 | Coverage | Net base fee proxy | Net stress fee proxy | Frozen gates |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 10m (primary) | 165929 | 34 | 47.98% (79608/165929) | 47.74%–48.22% | 47.69%–48.29% | 49.997% | 48.060% | 2.757% | -0.102% | -0.302% | FAIL |
| 20m (secondary) | 165929 | 34 | 49.17% (81588/165929) | 48.93%–49.41% | 48.85%–49.51% | 49.968% | 49.202% | 2.757% | -0.102% | -0.302% | FAIL |

Primary H=10 fixed-gate disposition: **REJECT_FIXED_CANDIDATE**.
H=20 is secondary and cannot rescue a failed primary. Results use contract OHLC proxies and legacy fee scenarios; no bid/ask, measured slippage, or proven fill simulation is available.

## Audit limits

The fixed primary H=10 gates fail: M2 >=80%, coverage >=10%, Wilson lower bound above the same-event momentum baseline, and positive mean net return under both fee proxies. Sample and symbol-count gates pass. H=20 is secondary and also fails the 80% and positive-net criteria.

All 416 frozen files matched the current local data manifest by byte size and SHA-256; the minute-grid and funding timestamp checks passed. This does not reconstruct original ZIP response bodies or independently validate publisher hashes for those downloads. The test interval is historical and market-period overlap exists with earlier hourly research. The score is therefore exploratory only.

## Reproduction

Scoring command (completed once; do not rerun): `PYTHONDONTWRITEBYTECODE=1 /Users/user/CODE/trading_data/external/crypto/.venv/bin/python scripts/research/mark_deviation_m2_probe.py --root /Volumes/home/mac/CODE/trading_data/external/crypto --out-dir docs/research/inventory/runs/mark_deviation_m2_20261121`
