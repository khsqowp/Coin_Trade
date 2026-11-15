from datetime import date, timedelta
from pathlib import Path

from scripts.research.equity_kr_failed_breakdown_probe import (
    failed_breakdown_signal,
    load_before_cutoff,
    net_long,
    run,
)


def test_failed_breakdown_requires_intraday_low_below_prior_floor_and_close_reclaim():
    prior = [100.0] * 19 + [95.0]
    assert failed_breakdown_signal(prior, 94.99, 95.01)
    assert not failed_breakdown_signal(prior, 95.0, 95.01)
    assert not failed_breakdown_signal(prior, 94.99, 95.0)
    assert not failed_breakdown_signal(prior[:-1], 90.0, 110.0)


def test_stock_fee_model_charges_tax_only_on_stock_exit():
    stock = net_long(100.0, 100.0, 0.001, etf=False)
    etf = net_long(100.0, 100.0, 0.001, etf=True)
    assert stock < etf < 0


def test_cutoff_row_prices_are_not_parsed(tmp_path: Path):
    source = tmp_path / "KR_069500.csv"
    source.write_text(
        "timestamp,Open,High,Low,Close,Volume\n"
        "2024-11-11 00:00:00+00:00,100,102,99,101,1000\n"
        "2024-11-12 00:00:00+00:00,not-a-price,not-a-price,not-a-price,not-a-price,not-volume\n",
        encoding="utf-8",
    )
    rows, digest = load_before_cutoff(source)
    assert len(rows) == 1
    assert rows[next(iter(rows))]["close"] == 101
    assert len(digest) == 64


def test_run_executes_one_causal_nonoverlapping_trade_on_tiny_cache(tmp_path: Path):
    dates = []
    current = date(2024, 10, 1)
    while len(dates) < 30:
        if current.weekday() < 5:
            dates.append(current)
        current += timedelta(days=1)

    for symbol in ("069500", "005930"):
        lines = ["timestamp,Open,High,Low,Close,Volume"]
        for i, day in enumerate(dates):
            if i < 20:
                values = (101, 102, 100, 101, 1000)
            elif i == 20:
                values = (101, 103, 99, 101, 2000)
            else:
                values = (101, 103, 101, 102, 1000)
            lines.append(f"{day.isoformat()} 00:00:00+00:00," +
                         ",".join(map(str, values)))
        (tmp_path / f"KR_{symbol}.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = run(tmp_path)
    assert result["universe"] == ["005930"]
    assert result["events"] == 1
    assert result["counts_by_symbol"]["005930"]["signals"] == 1
    assert result["counts_by_symbol"]["005930"]["trades"] == 1
    assert result["metrics"]["base_net_trade_return"]["n"] == 1
