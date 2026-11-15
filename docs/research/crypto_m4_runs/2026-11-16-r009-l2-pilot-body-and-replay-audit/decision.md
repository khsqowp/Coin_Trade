# R009 decision

The capture body spans 3,600.689 seconds, contains 143,774 newline-terminated valid JSON records, and replays deterministically through compact and 10-second aggregation outputs. The capture process nevertheless exited 10 with `RuntimeError` and wrote no run manifest. Therefore the pilot is **not fully accepted**. Preserve the `.partial` body and classify it only as integrity/replay evidence; no signal or strategy performance was tested.

The generic CLI error concealed the exception message, so the precise failure point cannot be proven from this run. Instrument finalization errors safely and perform a new capture under a new run ID before treating the recorder as operationally verified.
