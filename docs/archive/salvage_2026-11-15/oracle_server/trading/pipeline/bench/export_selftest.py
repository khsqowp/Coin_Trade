"""Self-test of the dry-run candidate path with SYNTHETIC passing evidence (no real run passes the gate).
Run in the offline role with a scratch dir mounted at /selftest (strategies + candidates + data export). Never touches
the real Freqtrade strategies dir or the real candidate registry."""
import json
import pathlib
import sys

sys.path.insert(0, "/app/src")
sys.path.insert(0, "/app/tests")
from fixtures_ablation import FIXED  # noqa: E402
from test_deploy import make_run  # noqa: E402
from tp import deploy, store  # noqa: E402

root = pathlib.Path("/selftest")
(root / "strategies").mkdir(exist_ok=True)
(root / "candidates").mkdir(exist_ok=True)
(root / "strategies" / "DryRunStrategy.py").write_text("# stand-in for the existing strategy\n")
rd = make_run(root / "fake", code=FIXED)
res = deploy.export_candidate(rd, root / "strategies", root / "candidates", host_root="/home/opc/trading")
print(json.dumps(res, indent=1)[:1500])
df = store.get_ohlcv("BTC/USDT", "1d").reset_index()
df = df.rename(columns={"ts": "date"})
df.to_csv(root / "btc.csv", index=False)
(root / "class.txt").write_text(res["candidate"]["class"] if res.get("exported") else "")
