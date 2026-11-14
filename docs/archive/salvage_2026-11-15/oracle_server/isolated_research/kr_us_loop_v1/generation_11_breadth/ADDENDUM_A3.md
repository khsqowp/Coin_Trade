# Addendum A3 — full-source-row price integrity gate

Date: 2026-11-06 (Asia/Seoul)

Before any A2 performance run, preserve the original integrity requirement from `PREREG.md`: required OHLC/adjusted-close columns, finite positive values, and raw OHLC bounds are validated across every row in each of the ten frozen parquet files, including rows excluded from the eventual common calendar. Only after this source-wide integrity validation does A2 form the exact ten-way calendar intersection and align rows for signals and returns.

This is a fail-closed data validation clarification only. It does not change the candidate universe, common-calendar rule, indicator, threshold, exposure, timing, return construction, fees, benchmark, windows, or decision rule. No excluded row is added to the calculation, and no row is repaired, sorted, filled, interpolated, or otherwise altered.

The A2 runner, tests, this addendum, A1 dependencies, preregistration, and all ten frozen input file hashes must be re-fingerprinted together. A synthetic test deliberately places an invalid price outside the common calendar and verifies rejection. The A2 attempt remains pending independent root GO until these hashes and tests are rechecked. If approved, the reserved single attempt ID remains `gen11-breadth-20261106-a2`; no second execution or parameter variant is permitted.
