# S3 / AWS batch plan (credits ~$90, expire ~2026-12-04)

Principle: big raw data stays in S3; compute reads it in AWS; only small result files come back to the Mac.
Nothing is spent before the user starts December. No resources exist now (bucket deleted 2026-11-20; verified 0 instances).
Supersedes the data-collection items in `AWS_PLAN_DEC.md` (D1 is done locally; it becomes "upload"). Keep that file's rules
(pre-registration, shared trial ledger, 2026-06-01 holdout untouched until final freeze, pass rule, funding strategies excluded).

## Facts checked 2026-11-21 (read-only)
- Account 302263081555, region ap-northeast-2. CLI currently uses ROOT keys (user chose to proceed; recommend IAM user + deleting root key).
- Spot vCPU quota 256, on-demand vCPU quota 64 -> no quota request needed.
- Local data to upload: ~/CODE/trading_data/external/crypto (18 GB), equities (1 GB), tick/parquet (1.3 GB), research bars in
  scratchpad (data_long 34 MB, bb_stoch_stc/data). Total ~21 GB. Storage cost ~ $0.5/month (estimate; measure).

## Bucket layout (one private bucket, block public access, versioning off)
```
s3://ochestration-sprint-302263081555-apne2/
  raw/crypto/binance/<dataset>/<SYMBOL>/<YYYY-MM>.parquet     # mirror of external/crypto
  raw/equities/...  raw/tick/parquet/...
  code/harness-<gitsha>.tar.gz                                  # strategy_bt + deps lock
  jobs/<sprint-id>/jobs.jsonl                                   # one line per job (see below)
  results/<sprint-id>/<job-id>/{rows.csv,meta.json,stdout.log}  # only these come back
  ledger/ledger-<sprint-id>.csv                                  # merged trial ledger
```
Lifecycle: expire `results/*/stdout.log` after 14 days; whole bucket deleted at teardown unless user keeps `raw/`.

## Job model
- Job = (item id, strategy/spec id or study id, symbol shard, params-grid slice, seed). Idempotent: skip if `results/.../meta.json` exists.
- Runner `runner.py`: reads job line -> downloads only needed raw files (S3 -> instance local NVMe/EBS) -> runs harness -> writes rows.csv + meta.json
  (git sha, params, runtime, rows hash) -> exit. No result is edited after write.
- Orchestration (simple, no extra services): launcher script on Mac creates N spot instances from one launch template; user-data
  pulls code tarball, claims jobs by atomic S3 conditional put of `claims/<job-id>`, runs until queue empty or deadline, uploads results,
  `shutdown -h now` with instance-initiated-shutdown-behavior=terminate. Max runtime guard per instance (e.g. 4 h) via `shutdown -P +240`.
- Merge step (local): `aws s3 sync results/ ...` (small), concatenate rows into shared ledger, run Reality Check / DSR over the whole pool.

## Instance choices (confirm prices on the day via `aws ec2 describe-spot-price-history`)
- CPU shard jobs (S1,S2,S4,S5,S7,S8): c7i.4xlarge..12xlarge spot, 50-100 GB gp3 EBS, DeleteOnTermination=true.
- Memory-heavy (S6 ML, tick/aggTrades conversion): r7i.2xlarge..4xlarge or m7i.
- No NAT gateway, no load balancer, no RDS, no Elastic IP, no extra snapshots. Instances in default VPC public subnet, security group no inbound.
- Use S3 gateway endpoint (free) if instances are in a private subnet; otherwise public S3 over default route (same-region transfer is free).

## Cost control (hard rules)
1. Create budget alerts at $40/$70 (needs an email subscriber - ask user for address when setting).
2. Per-item cost caps in `AWS_PLAN_DEC.md`; launcher refuses to start a job set whose estimate (instances x hours x spot price) exceeds the cap.
3. All instances tagged `project=sprint`; teardown script lists and terminates by tag; end-of-sprint audit prints
   instances, volumes, snapshots, EIPs, NAT, buckets - must all be empty/removed. EBS volumes are NOT free when detached: audit them.
4. Credits expire -> after that everything is billed: last action of sprint is deleting the bucket (or downloading `raw/` back to SSD first if wanted).

## Preparation that costs $0 (do before December, locally)
1. Package harness + pinned requirements into `harness-<sha>.tar.gz` build script.
2. Write `runner.py`, `launch.py`, `teardown.py`, `audit.py`; test fully on the Mac against a local directory acting as "S3" (same code path via a storage adapter; moto optional).
3. Pre-register each study (`sprint/<id>/PREREG.md`) incl. job counts and runtime estimates from local timing of one shard.
4. Make a data manifest check: sha256 of every local file already in `MANIFEST.csv`; uploader verifies after upload with `aws s3api head-object` size + sha256 metadata.
5. Decide which of the optional downloads (aggTrades BTC/ETH window, Bybit/OKX ticks, Tardis samples) run directly ON EC2 and write straight to S3 (no Mac disk).
6. Create IAM user/role with least privilege (S3 bucket, EC2 run/terminate with tag condition, instance profile for S3 read/write) - user action in console.

## Timeline (credits expire ~12-04; start only when the user says go)
- Day 0 (e.g. 12-01): create bucket, upload raw (~21 GB; time depends on home upload speed - estimate before start; if slow, upload only crypto 1m klines + metrics first and run those items first), upload code tarball, budgets, one smoke job on a small spot instance (<$0.5).
- Day 1-2: item batches in parallel (S1, S2, S4, S5, S7); merge ledger daily.
- Day 2-3: S3 (pairs), S6 (ML), tick study if data allows; phase-2 downloads on EC2.
- Day 3: S8 cost re-check of winners, Z final pooled correction and single holdout touch, report.
- Day 3-4: teardown + audit, download results (<1 GB), delete bucket, confirm zero resources.
If December start leaves < 5 days before expiry, cut items in this order: S9, S6, S3, S5; keep S1, S2, S4, S7, S8, Z.

## Out of scope / known risks
- Binance API IPs can be blocked from AWS; `data.binance.vision` is a static bucket and should work (verify with the smoke job).
- Large single-file bursts (aggTrades month ~3 GB CSV) must be stream-converted on EC2, not downloaded to Mac.
- Results are statistics on selected candidates: the final pooled correction (Z) is binding; no "winner" claim without forward test.
