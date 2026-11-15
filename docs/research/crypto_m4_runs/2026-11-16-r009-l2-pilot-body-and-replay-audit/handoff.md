# R009 handoff

- R005 remains performance-unscored; the 10% coverage gate still conflicts with its 20T refractory rule (R007).
- The live pilot body is intact but remains named `capture.jsonl.partial`; do not rename it or fabricate a completion manifest.
- Raw SHA-256: `d7171431565a7ab2ae82b749e09f04bd99eb00e29cc65fde9d02fe337583f1ec`; 172,649,813 bytes; 143,774 valid records; observed receive span 3,600.689s.
- Compact replay was byte-identical twice: `744ae55db75cafdb4b76467cd9db71b12d63103765d98a688e27d359376f1e34`.
- Window replay was byte-identical twice: `12861858308af481ed543fa64b5eb58151686f8a2b78f1d105056d8a850ecb92`; 720 windows, 718 quality-ready, two not ready, zero late rows, zero disconnect records.
- Capture exit was code 10 / `RuntimeError`; expected manifest is absent. Cause is unresolved because CLI prints only the exception type.
- Next: add a sanitized exception diagnostic plus a regression test for finalization/stop races, verify locally, commit/push, then rerun a fresh one-hour integrity pilot. Do not score R005 signal outcomes before the new acceptance protocol and remaining recorder/data/cost gates are frozen.
