import copy
import json
import pytest
from schema import validate_decision, extract_json


def valid():
    return {
        "actions": [
            {
                "type": "open",
                "symbol": "BTCUSDT",
                "side": "long",
                "size_pct_equity": 10,
                "leverage": 3,
                "stop_loss": 98.0,
                "rationale": "Trend",
            }
        ],
        "notes": "Watch",
    }


def test_valid_and_close_modify():
    assert validate_decision(valid())[0]
    assert validate_decision(
        {
            "actions": [
                {"type": "close", "symbol": "BTCUSDT", "rationale": ""},
                {
                    "type": "modify",
                    "symbol": "ETHUSDT",
                    "take_profit": 120,
                    "rationale": "",
                },
            ],
            "notes": "",
        }
    )[0]


@pytest.mark.parametrize(
    "key,value",
    [
        ("stop_loss", None),
        ("stop_loss", float("nan")),
        ("stop_loss", float("inf")),
        ("stop_loss", True),
        ("stop_loss", "98"),
        ("stop_loss", -1),
        ("size_pct_equity", 101),
        ("size_pct_equity", False),
        ("size_pct_equity", 0),
        ("leverage", 2.0),
        ("leverage", True),
        ("leverage", 0),
        ("side", "buy"),
        ("rationale", "x" * 1001),
        ("symbol", None),
        ("type", "buy"),
    ],
)
def test_invalid_action(key, value):
    d = valid()
    d["actions"][0][key] = value
    ok, errors, normalized = validate_decision(d)
    assert not ok and errors and normalized["actions"] == []


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_stop",
        "extra_action",
        "extra_top",
        "no_notes",
        "many",
        "notes_length",
        "summary_length",
        "no_type",
        "actions_type",
        "modify_empty",
    ],
)
def test_reject_whole(mutation):
    d = valid()
    if mutation == "missing_stop":
        del d["actions"][0]["stop_loss"]
    elif mutation == "extra_action":
        d["actions"][0]["foo"] = 1
    elif mutation == "extra_top":
        d["foo"] = 1
    elif mutation == "no_notes":
        del d["notes"]
    elif mutation == "many":
        d["actions"] *= 11
    elif mutation == "notes_length":
        d["notes"] = "x" * 4001
    elif mutation == "summary_length":
        d["summary"] = "x" * 501
    elif mutation == "no_type":
        del d["actions"][0]["type"]
    elif mutation == "actions_type":
        d["actions"] = {}
    elif mutation == "modify_empty":
        d["actions"] = [{"type": "modify", "symbol": "BTCUSDT", "rationale": ""}]
    assert not validate_decision(d)[0]


def test_extraction():
    text = json.dumps(valid())
    assert extract_json("```json\n" + text + "\n```") == valid()
    assert extract_json("Explanation\n" + text + "\nend") == valid()
    assert extract_json(text + text) == valid()
    assert extract_json(text + "{}") is None
    assert extract_json("nothing") is None
    assert extract_json("[" + text + "]") is None
    assert extract_json("{bad " + text) is None
    assert not validate_decision([])[0]
