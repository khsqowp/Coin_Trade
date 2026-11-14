import hashlib
import json

import pytest

from fixtures_ablation import FIXED, PRIOR_DEFECT, TWO_EFFECTIVE
from test_risk import good_audit, good_bt
from tp import deploy


def sha(code):
    return hashlib.sha256(code.encode()).hexdigest()


def make_run(root, code=FIXED, verdict="PASS", dead=(), symbol="BTC/USDT", gate="ALLOW_DRY_RUN", abl_status="ok", bt_hash=None):
    rd = root / "runs" / "run-t1"
    (rd / "work").mkdir(parents=True)
    (rd / "work" / "strategy.py").write_text(code)
    audit = good_audit()
    audit["verdict"] = verdict
    (rd / "04_auditor.json").write_text(json.dumps({"output": audit}))
    bt = good_bt()
    bt["symbol"], bt["strategy_sha256"] = symbol, bt_hash or sha(code)
    (rd / "03_backtest.json").write_text(json.dumps(bt))
    abl = {"status": abl_status, "rules": [], "dead_rules": list(dead), "weak_rules": [], "effective_rules": ["a"],
           "undeclared_hypothesis_rules": [], "thresholds": {"weak_diff_frac": 0.005}, "strategy_sha256": sha(code)}
    (rd / "03b_ablation.json").write_text(json.dumps(abl))
    (rd / "05_risk_gate.json").write_text(json.dumps({"decision": gate}))
    (rd / "03_engineer_final.json").write_text(json.dumps({"hypothesis_id": "H1"}))
    return rd


@pytest.fixture
def dirs(tmp_path):
    s, c = tmp_path / "strategies", tmp_path / "candidates"
    s.mkdir(), c.mkdir()
    (s / "DryRunStrategy.py").write_text("# existing\n")
    return s, c


def test_static_check_accepts_reference_strategies():
    for src in (FIXED, PRIOR_DEFECT, TWO_EFFECTIVE):
        assert deploy.static_check(src) == []


@pytest.mark.parametrize("code", [
    "import os\ndef generate_signals(df):\n    return df\n",
    "import pandas as pd\nimport requests\n",
    "import pandas as pd\nopen('/etc/passwd')\n",
    "import pandas as pd\ndef f(df):\n    return eval('1')\n",
    "import pandas as pd\ndef f(df):\n    return pd.read_csv('http://x/y.csv')\n",
    "import pandas as pd\ndef f(df):\n    return df.to_pickle('x')\n",
    "import pandas as pd\ndef f(df):\n    return ().__class__.__bases__\n",
    "import pandas as pd\nx = pd.Series([1]).sum()\n",                 # top-level call
    "import pandas as pd\nclass A:\n    pass\n",
    "import pandas as pd\nprint('side effect')\n",
    "import pandas as pd\ndef f(df):\n    return getattr(df, 'x')\n",
    "def f(:\n",
])
def test_static_check_rejects(code):
    assert deploy.static_check(code) != []


def test_export_happy_path_and_idempotence(tmp_path, dirs):
    s, c = dirs
    rd = make_run(tmp_path)
    res = deploy.export_candidate(rd, s, c, host_root="/home/x/trading")
    assert res["exported"], res
    cand = res["candidate"]
    f = s / (cand["class"] + ".py")
    assert f.exists() and (s / (cand["class"] + ".config.json")).exists()
    src = f.read_text()
    compile(src, str(f), "exec")                                  # syntactically valid, not executed
    assert "class %s(IStrategy)" % cand["class"] in src and 'timeframe = "1d"' in src and "can_short = False" in src
    ov = json.loads((s / (cand["class"] + ".config.json")).read_text())
    assert ov["dry_run"] is True and ov["exchange"]["pair_whitelist"] == ["BTC/USDT"]
    assert not any(k in json.dumps(ov).lower() for k in ("key", "secret", "token", "password"))
    assert (s / "DryRunStrategy.py").read_text() == "# existing\n"          # untouched
    bk = c / cand["backup_dir"]
    assert (bk / "DryRunStrategy.py").exists()                              # backup taken
    comp = (c / cand["id"] / "compose.override.yml").read_text()
    assert "--strategy " + cand["class"] in comp and "tradesv3_" + cand["id"] in comp
    assert "docker compose" in cand["swap_command"] and "--force-recreate" in cand["swap_command"]
    assert cand["status"] == "candidate_registered" and "owner" in cand["note"]
    assert json.loads((c / "registry.json").read_text())[0]["id"] == cand["id"]
    # second call must not overwrite or duplicate
    res2 = deploy.export_candidate(rd, s, c)
    assert not res2["exported"] and res2["reasons"] == ["ALREADY_REGISTERED"]
    assert len(json.loads((c / "registry.json").read_text())) == 1


def test_name_collision_is_refused(tmp_path, dirs):
    s, c = dirs
    rd = make_run(tmp_path)
    ok, _, ctx = deploy.check_eligibility(rd)
    assert ok
    (s / ("TPC_BTCUSDT_H1_%s.py" % ctx["sha"][:8])).write_text("# someone else's file\n")
    res = deploy.export_candidate(rd, s, c)
    assert not res["exported"] and res["reasons"][0].startswith("NAME_COLLISION")
    assert (s / ("TPC_BTCUSDT_H1_%s.py" % ctx["sha"][:8])).read_text() == "# someone else's file\n"


@pytest.mark.parametrize("kw,needle", [
    ({"verdict": "FAIL"}, "AUDIT_NOT_PASS"),
    ({"verdict": "INCONCLUSIVE"}, "AUDIT_NOT_PASS"),
    ({"dead": ["atr_trailing_exit"]}, "DEAD_RULE"),
    ({"abl_status": "no_rules"}, "ABLATION_UNAVAILABLE"),
    ({"gate": "BLOCK"}, "GATE_FILE_NOT_ALLOW"),
    ({"symbol": "005930"}, "SYMBOL_NOT_WHITELISTED"),
    ({"bt_hash": "0" * 64}, "EVIDENCE_HASH_MISMATCH"),
])
def test_ineligible_runs_export_nothing(tmp_path, dirs, kw, needle):
    s, c = dirs
    rd = make_run(tmp_path, **kw)
    res = deploy.export_candidate(rd, s, c)
    assert not res["exported"]
    assert any(needle in r for r in res["reasons"]), res["reasons"]
    assert sorted(p.name for p in s.iterdir()) == ["DryRunStrategy.py"]
    assert not (c / "registry.json").exists()


def test_unsafe_code_is_refused_even_if_gate_says_allow(tmp_path, dirs):
    s, c = dirs
    bad = FIXED + "\nimport os\n"
    rd = make_run(tmp_path, code=bad)
    res = deploy.export_candidate(rd, s, c)
    assert not res["exported"] and any(r.startswith("CODE_CHECK") for r in res["reasons"])


def test_code_changed_after_evidence_is_refused(tmp_path, dirs):
    s, c = dirs
    rd = make_run(tmp_path)
    (rd / "work" / "strategy.py").write_text(FIXED + "\n# edited after backtest\n")
    res = deploy.export_candidate(rd, s, c)
    assert not res["exported"] and any("EVIDENCE_HASH_MISMATCH" in r for r in res["reasons"])
