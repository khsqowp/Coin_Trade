from urllib.parse import urlparse, parse_qs

import pandas as pd

import data


def _row(open_ms, close_ms, price):
    return [open_ms, str(price), str(price + 1), str(price - 1), str(price), "12.5",
            close_ms, "0", 1, "0", "0", "0"]


def test_download_paginates_and_keeps_ohlcv_schema(monkeypatch):
    calls = []
    start = 1_700_000_000_000

    def fake_fetch(url):
        q = parse_qs(urlparse(url).query)
        calls.append((url, int(q['startTime'][0])))
        if len(calls) == 1:
            return [_row(start, start + data.MS['1h'] - 1, 100)]
        return []

    monkeypatch.setattr(data, '_fetch_json', fake_fetch)
    monkeypatch.setattr(data.time, 'sleep', lambda *_: None)
    # Fixed clock ensures returned candles are complete.
    from datetime import datetime, timezone
    monkeypatch.setattr(data, 'datetime', type('Clock', (), {'now': staticmethod(lambda tz: datetime.fromtimestamp((start + 3 * data.MS['1h']) / 1000, tz=timezone.utc)), 'fromtimestamp': datetime.fromtimestamp}))
    result = data.download('ABCUSDT', '1h', start=pd.to_datetime(start, unit='ms', utc=True).strftime('%Y-%m-%d'), end='2024-01-01', sleep=0)
    assert result.columns.tolist() == ['open', 'high', 'low', 'close', 'volume']
    assert len(calls) >= 2
    assert calls[0][0].startswith(data.SPOT_URL + '?')
    assert calls[1][1] == start + data.MS['1h']


def test_futures_earliest_uses_zero_start_and_paginates(monkeypatch):
    calls = []
    first = 1_700_000_000_000

    def fake_fetch(url):
        q = parse_qs(urlparse(url).query)
        calls.append((url, int(q['startTime'][0])))
        if len(calls) == 1:
            return [_row(first, first + data.MS['1h'] - 1, 100)]
        return []

    monkeypatch.setattr(data, '_fetch_json', fake_fetch)
    monkeypatch.setattr(data.time, 'sleep', lambda *_: None)
    from datetime import datetime, timezone
    monkeypatch.setattr(data, 'datetime', type('Clock', (), {'now': staticmethod(lambda tz: datetime.fromtimestamp((first + 3 * data.MS['1h']) / 1000, tz=timezone.utc)), 'fromtimestamp': datetime.fromtimestamp}))
    result = data.download('NEWUSDT', '1h', 'earliest', end='2024-01-01', sleep=0, market='futures')
    assert calls[0][0].startswith(data.FUTURES_URL + '?')
    assert calls[0][1] == 0
    assert calls[1][1] == first + data.MS['1h']
    assert result.volume.iloc[0] == 12.5


def test_spot_daily_pagination_uses_one_day_step(monkeypatch):
    calls = []
    first = 1_700_006_400_000

    def fake_fetch(url):
        q = parse_qs(urlparse(url).query)
        calls.append((q['interval'][0], int(q['startTime'][0])))
        if len(calls) == 1:
            return [_row(first, first + data.MS['1d'] - 1, 100)]
        return []

    monkeypatch.setattr(data, '_fetch_json', fake_fetch)
    monkeypatch.setattr(data.time, 'sleep', lambda *_: None)
    from datetime import datetime, timezone
    monkeypatch.setattr(data, 'datetime', type('Clock', (), {
        'now': staticmethod(lambda tz: datetime.fromtimestamp((first + 3 * data.MS['1d']) / 1000, tz=timezone.utc)),
        'fromtimestamp': datetime.fromtimestamp,
    }))
    result = data.download('ABCUSDT', '1d', start='2023-11-15', end='2024-01-01', sleep=0)

    assert calls == [('1d', data._ms('2023-11-15')), ('1d', first + data.MS['1d'])]
    assert len(result) == 1
    assert result.index[0] == pd.to_datetime(first, unit='ms', utc=True)


def test_daily_gap_check_accepts_consecutive_candles():
    index = pd.date_range('2024-01-01', periods=3, freq='D', tz='UTC', name='open_time')
    frame = pd.DataFrame(index=index)

    assert data.check_data(frame, '1d') == []


def test_report_only_emits_first_date_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(data, 'BASE', tmp_path)
    outdir = tmp_path / 'data'
    outdir.mkdir()
    target = outdir / 'TESTSUMMARY_1h.parquet'
    frame = pd.DataFrame({'open': [1.], 'high': [2.], 'low': [0.], 'close': [1.], 'volume': [5.]},
                         index=pd.DatetimeIndex(['2024-01-02T00:00:00Z'], name='open_time'))
    frame.to_parquet(target)
    report = tmp_path / 'report.csv'
    first_dates = tmp_path / 'first.csv'
    monkeypatch.setattr('sys.argv', ['data.py', '--symbols', 'TESTSUMMARY', '--timeframes', '1h',
                                     '--report-only', '--out', str(report), '--first-dates-out', str(first_dates)])
    data.main()
    summary = pd.read_csv(first_dates)
    assert summary.to_dict('records') == [{'symbol': 'TESTSUMMARY', 'first_date': '2024-01-02T00:00:00+00:00'}]
    target.unlink()
