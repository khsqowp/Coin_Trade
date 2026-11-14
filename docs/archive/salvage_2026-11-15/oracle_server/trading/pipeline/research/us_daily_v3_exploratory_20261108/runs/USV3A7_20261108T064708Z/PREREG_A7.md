# Addendum A7: executable and imported-code provenance
Registered 2026-11-08 KST before any US v3 market metric calculation. This addendum changes provenance enforcement only; strategy formulas, data, execution semantics, universe definitions, and output contract are unchanged from A6. No market metrics have been calculated.

## Exact code hashes
- us_v3.py: 507b1ef56df288baa7cc789a0d330d974bfbaf89dd619dbb846170434a5a38c2
- research/us_daily_v2/usbt2.py: 45f7b0916f0f5eae11dca3e9f2ecfab8ccbaef9b7432500965991d4b317c6e38
- research/us_daily_v1/usbt.py: e44a46f60d175ebfb0341fc8f4884a43a08f4e64871c124e4d52c85f4eb5672d
- src/tp/usdata.py: 235b102ad4ce91e108b9e4c63b924944dfac14abe0ea46841a5cfb826b510f66

## Runtime gate and frozen manifest
Before any market computation, verify_frozen_inputs() now requires INPUT_HASHES_PRECALC_A7.txt, verifies every listed file and the aggregate US parquet hash, and fails closed if the v3 strategy script or any of the three imported helpers are missing from the manifest or differ from their registered SHA256. The manifest preserves all A6 frozen inputs and replaces the executable hash with the A7 executable hash; it adds the three imported helper hashes. No v1/v2/source helper files were modified.

- INPUT_HASHES_PRECALC_A7.txt SHA256: 01b883dbdb2644763c53eba3c83eea1aed522868c8d2c37a0fa2ec71a0cc526e
- A6 prerequisite hash manifest remains preserved as INPUT_HASHES_PRECALC_A6.txt.
- Market execution remains blocked pending read-only A7 reviewer approval.
