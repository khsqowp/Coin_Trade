import json
from pathlib import Path

import pytest

from tp import library

LIB = Path("/app/strategy_library")


def have_lib():
    return (LIB / "entries").exists()


pytestmark = pytest.mark.skipif(not have_lib(), reason="strategy_library not mounted")


def test_entries_valid_and_sourced():
    es = library.load_all(LIB)
    assert len(es) >= 12
    for e in es:
        assert e["source"]["url"].startswith("https://github.com/")
        assert e["source"]["license"]
        assert e["source"].get("commit")
        assert e["pipeline_fit"]["single_asset_daily_long_flat"]
        for r in e["rules"]:
            assert set(r) == {"name", "kind", "description"}


def test_index_is_compact_and_matches_file():
    txt = library.index_text(LIB)
    assert len(txt) <= library.INDEX_MAX_CHARS
    assert txt.count("\n") + 1 == len(library.load_all(LIB))
    idx = json.loads((LIB / "index.json").read_text())
    assert idx == library.index_entries(library.load_all(LIB))


def test_card_capped_and_unknown_id_none():
    es = library.load_all(LIB)
    for e in es:
        c = library.card(e["id"], LIB)
        assert c.startswith("ID: " + e["id"]) and len(c) <= library.CARD_MAX_CHARS
    assert library.card("nope", LIB) is None
    assert library.MAX_LOOKUPS == 2


def test_card_strips_control_chars(tmp_path):
    (tmp_path / "entries").mkdir()
    e = json.loads((LIB / "entries" / "ct-ema-cross-swing.json").read_text())
    e["idea"] = "ok\x00\x1b[31m hidden"
    (tmp_path / "entries" / (e["id"] + ".json")).write_text(json.dumps(e))
    c = library.card(e["id"], tmp_path)
    assert "\x00" not in c and "\x1b" not in c


def test_no_secret_shaped_strings_in_library():
    import re
    pat = re.compile(r"(sk-[A-Za-z0-9_\-]{10,}|AIza[0-9A-Za-z_\-]{20,}|\b\d{6,}:[A-Za-z0-9_\-]{30,}|[A-Fa-f0-9]{48,})")
    for p in (LIB / "entries").glob("*.json"):
        t = p.read_text()
        # commit hashes are 40 hex chars: allowed; anything longer is suspicious
        assert not pat.search(t), p.name
