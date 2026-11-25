"""Build bounded KR listing snapshots and delisting OHLCV. Network is used only when run by the owner."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

import pandas as pd

CUTOFF = date(2026, 5, 31)
ROOT = Path('/Users/user/CODE/Coin_Trade/trading_data/external/kr_pit')
MEMBERSHIP_COLUMNS = ['market', 'symbol', 'alive_from', 'alive_through', 'source', 'source_asof']


def month_ends(start=date(2000, 1, 1), end=CUTOFF):
    result = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        first_next = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
        month_end = first_next - timedelta(days=1)
        if month_end >= start and month_end <= end:
            result.append(month_end)
        year, month = first_next.year, first_next.month
    if not result or result[-1] != end:
        result.append(end)
    return result


def retry(call: Callable, attempts=4, delay=1.0, sleep=time.sleep):
    error = None
    for n in range(attempts):
        try:
            return call()
        except Exception as exc:
            error = exc
            if n + 1 < attempts:
                sleep(delay * (n + 1))
    raise RuntimeError(f'요청 실패 ({attempts}회): {error}') from error


def _date(value):
    if pd.isna(value):
        return None
    return pd.Timestamp(value).date()


def _load_clients():
    import FinanceDataReader as fdr
    from pykrx import stock
    return fdr, stock


def fetch_delistings(fdr, sleep=time.sleep):
    frame = retry(lambda: fdr.StockListing('KRX-DELISTING'))
    if frame is None or frame.empty:
        raise ValueError('상폐 목록이 비어 있음')
    frame = frame.copy()
    # FDR schema names are normalized without assuming a specific column case.
    frame.columns = [str(c).strip() for c in frame.columns]
    aliases = {c.lower(): c for c in frame.columns}
    code_col = next((aliases[k] for k in ('symbol', 'code', '종목코드') if k in aliases), None)
    date_col = next((aliases[k] for k in ('delistingdate', 'delisting_date', '상장폐지일') if k in aliases), None)
    listing_col = next((aliases[k] for k in ('listingdate', 'listing_date', '상장일') if k in aliases), None)
    if not code_col or not date_col:
        raise ValueError(f'상폐 목록 필수 열 누락: {list(frame.columns)}')
    frame['code'] = frame[code_col].astype(str).str.extract(r'(\d{6})', expand=False)
    def parse_day(value):
        try:
            return datetime.fromisoformat(str(value)[:10]).date()
        except (ValueError, TypeError):
            return None
    frame['delisting_date'] = [parse_day(x) for x in frame[date_col]]
    frame['listing_date'] = [parse_day(x) for x in frame[listing_col]] if listing_col else None
    frame = frame[frame.code.notna() & frame.delisting_date.notna()]
    frame = frame[frame.delisting_date <= CUTOFF]
    frame['instrument_key'] = frame.apply(lambda r: f"{r.code}:{r.listing_date.isoformat() if pd.notna(r.listing_date) else 'unknown'}", axis=1)
    frame['source'] = 'FinanceDataReader KRX-DELISTING'
    return frame.reset_index(drop=True)


def _is_merger(row):
    text = ' '.join(str(row.get(k, '')) for k in row.index).lower()
    return any(term in text for term in ('합병', 'merger', '흡수', '주식교환', '이전상장'))


def fetch_delisted_prices(delistings, stock, sleep=time.sleep, rate_seconds=0.35, min_rows=2, chunk_dir=None):
    pieces, meta = [], []
    for row in delistings.to_dict('records'):
        chunk = Path(chunk_dir) / f"{hashlib.sha256(row['instrument_key'].encode()).hexdigest()}.parquet" if chunk_dir else None
        if chunk and chunk.exists():
            cached = pd.read_parquet(chunk)
            pieces.append(cached)
            meta.append({**row, 'status': 'ok_cached', 'rows': len(cached), 'merger_delisting': bool(cached.merger_delisting.iloc[0])})
            continue
        listing = row.get('listing_date')
        end = row['delisting_date']
        start = listing if isinstance(listing, date) else date(max(1980, end.year - 30), 1, 1)
        start = max(start, date(1900, 1, 1))
        if start > end or end > CUTOFF:
            continue
        sleep(rate_seconds)
        frame = retry(lambda: stock.get_market_ohlcv_by_date(start.strftime('%Y%m%d'), end.strftime('%Y%m%d'), row['code']))
        if frame is None or frame.empty or len(frame) < min_rows:
            meta.append({**row, 'status': 'empty_or_too_short', 'rows': 0 if frame is None else len(frame), 'merger_delisting': _is_merger(pd.Series(row))})
            continue
        frame = frame.copy().reset_index()
        frame.columns = [str(c).lower() for c in frame.columns]
        dtcol = next((c for c in frame.columns if c in ('날짜', 'date', 'index')), frame.columns[0])
        def parse_day(value):
            try:
                return datetime.fromisoformat(str(value)[:10]).date()
            except (ValueError, TypeError):
                return None
        frame['date'] = [parse_day(x) for x in frame[dtcol]]
        frame = frame[frame.date.notna() & (frame.date <= CUTOFF)]
        if len(frame) < min_rows:
            meta.append({**row, 'status': 'empty_or_too_short', 'rows': len(frame), 'merger_delisting': _is_merger(pd.Series(row))})
            continue
        frame['instrument_key'] = row['instrument_key']
        frame['code'] = row['code']
        frame['listing_date'] = listing
        frame['delisting_date'] = end
        frame['merger_delisting'] = _is_merger(pd.Series(row))
        frame['source'] = 'pykrx get_market_ohlcv_by_date'
        if chunk:
            chunk.parent.mkdir(parents=True, exist_ok=True)
            frame.to_parquet(chunk, index=False, compression='zstd')
        pieces.append(frame)
        meta.append({**row, 'status': 'ok', 'rows': len(frame), 'merger_delisting': _is_merger(pd.Series(row))})
    return (pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()), pd.DataFrame(meta)


def fetch_membership(stock, dates, sleep=time.sleep, rate_seconds=0.35, snapshot_dir=None):
    # Snapshot intervals only establish observed presence. They do not prove exact IPO/delisting dates.
    seen = {}
    for market in ('KOSPI', 'KOSDAQ'):
        for day in dates:
            snap = Path(snapshot_dir) / f'{day.isoformat()}_{market}.csv' if snapshot_dir else None
            if snap and snap.exists():
                tickers = pd.read_csv(snap, dtype=str).symbol.tolist()
            else:
                sleep(rate_seconds)
                tickers = retry(lambda: stock.get_market_ticker_list(day.strftime('%Y%m%d'), market))
            if tickers is None:
                raise ValueError(f'{market} {day} 스냅샷이 없음')
            if snap:
                snap.parent.mkdir(parents=True, exist_ok=True)
                pd.DataFrame({'symbol': list(map(str, tickers))}).to_csv(snap, index=False)
            for ticker in map(str, tickers):
                code = ticker.zfill(6)
                key = (market, code)
                seen.setdefault(key, []).append(day)
    out = []
    for (market, code), observed in sorted(seen.items()):
        observed.sort()
        groups = [[observed[0]]]
        for day in observed[1:]:
            if (day - groups[-1][-1]).days > 45:
                groups.append([day])
            else:
                groups[-1].append(day)
        for group in groups:
            out.append({'market': market, 'symbol': code, 'alive_from': group[0].isoformat(),
                        'alive_through': group[-1].isoformat(), 'source': 'pykrx get_market_ticker_list month-end snapshots; gaps >45d split',
                        'source_asof': group[-1].isoformat()})
    return pd.DataFrame(out, columns=MEMBERSHIP_COLUMNS)


def write_table(frame, path):
    if frame.empty:
        raise ValueError(f'빈 결과 저장 거부: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == '.parquet':
        frame.to_parquet(path, index=False, compression='zstd')
    else:
        frame.to_csv(path, index=False)


def update_manifest(root):
    rows = []
    for path in sorted(p for p in root.rglob('*') if p.is_file() and p.name != 'MANIFEST_sha256.csv'):
        try:
            count = len(pd.read_parquet(path)) if path.suffix == '.parquet' else max(0, sum(1 for _ in path.open(encoding='utf-8')) - 1)
        except Exception:
            continue
        rows.append({'path': str(path.relative_to(root)), 'rows': count, 'bytes': path.stat().st_size,
                     'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    with (root / 'MANIFEST_sha256.csv').open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=['path', 'rows', 'bytes', 'sha256'])
        writer.writeheader(); writer.writerows(rows)


def run(out=ROOT, sleep=time.sleep, rate_seconds=0.35):
    fdr, stock = _load_clients()
    out.mkdir(parents=True, exist_ok=True)
    membership_path = out / 'membership.csv'
    # Resume by reusing a previously completed monthly snapshot file.
    dates = month_ends()
    membership = fetch_membership(stock, dates, sleep, rate_seconds, out / 'snapshots')
    write_table(membership, membership_path)
    delistings = fetch_delistings(fdr, sleep)
    write_table(delistings, out / 'delistings.csv')
    prices, coverage = fetch_delisted_prices(delistings, stock, sleep, rate_seconds,
                                             chunk_dir=out / 'delisted_chunks')
    if not prices.empty:
        write_table(prices, out / 'delisted_ohlcv.parquet')
    if not coverage.empty:
        write_table(coverage, out / 'delisted_price_coverage.csv')
    update_manifest(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT)
    parser.add_argument('--rate-seconds', type=float, default=0.35)
    args = parser.parse_args()
    run(args.out, rate_seconds=args.rate_seconds)

if __name__ == '__main__':
    main()
