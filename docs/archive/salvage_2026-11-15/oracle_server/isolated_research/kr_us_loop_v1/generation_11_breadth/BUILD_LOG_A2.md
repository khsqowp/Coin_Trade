# Generation 11 breadth A2 — build and test log

- A1 remains immutable: its original freeze, single failed attempt ledger, and failed manifest are retained. The A1 failure occurred at the identical-raw-calendar check before signal generation; no curve or metrics were produced.
- Coordinator's read-only index-only audit: SPY has a longer history; each of the nine sector indexes is unique, ascending, and exactly matches the other sector indexes. This is an audit result from the coordinator, not a performance-data analysis by this builder.
- A2 changes only calendar integrity/alignment. It takes the strict intersection of the ten frozen instruments, selects exact dates only, and refuses fill/interpolation or post-intersection row dropping. The strategy rule/cost/benchmark/windows remain as preregistered.
- TDD RED: `test_gen11_a2.py` initially failed because `run_gen11_a2` did not yet exist.
- TDD GREEN: six synthetic-only A2 calendar tests pass under Python 3.12. They cover exact ten-way intersection, longer SPY history, missing sector dates, no forward fill, invalid index type, duplicate/descending dates, empty intersection, and fixed instrument set.
- No parquet files were opened in this A2 preparation stage. No A2 signals, returns, or performance metrics were calculated.
- Pending: final freeze hashes, independent root review/GO, then at most one A2 run using the reserved run ID.
