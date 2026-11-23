"""Build a lightweight KR point-in-time membership CSV without price data."""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime
from pathlib import Path

CUTOFF = date(2026, 5, 31)
DEFAULT_DELISTING = Path('/Users/user/CODE/trading_data/external/kr_pit/delisting_list.csv')
DEFAULT_OUTPUT = Path('~/CODE/trading_data/cache/orderblock/equity_membership_kr.csv').expanduser()
MEMBERSHIP_COLUMNS = ['market', 'symbol', 'alive_from', 'alive_through', 'source', 'source_asof', 'status']
STATUS = 'PIT_MEMBERSHIP_ONLY'


def parse_date(value: str | None, field: str) -> date | None:
    """Parse an ISO-like date cell; blank cells return None."""
    value = (value or '').strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError as exc:
        raise ValueError(f'invalid {field}: {value!r}') from exc


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f'CSV header missing: {path}')
        return [{(key or '').strip(): (value or '').strip() for key, value in row.items()}
                for row in reader]


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def validate_intervals(rows: list[dict[str, str]]) -> None:
    """Fail if any membership interval starts after it ends."""
    invalid = []
    for row in rows:
        start = parse_date(row.get('alive_from'), 'alive_from')
        end = parse_date(row.get('alive_through'), 'alive_through')
        if not start or not end or start > end:
            invalid.append(row)
    if invalid:
        raise ValueError(f'alive_from <= alive_through check FAIL: {len(invalid)} invalid membership row(s)')


def build(delisting_path: Path, output_path: Path, current_path: Path | None = None,
          today: date | None = None) -> dict[str, int]:
    """Create membership and auxiliary exclusion reports from local CSV files."""
    asof = (today or date.today()).isoformat()
    delisting_rows = read_rows(delisting_path)
    current_rows = read_rows(current_path) if current_path else []
    missing, duplicate_groups = [], {}
    for row in delisting_rows:
        symbol = row.get('Symbol', '').strip()
        if not parse_date(row.get('ListingDate'), 'ListingDate'):
            missing.append({'symbol': symbol, 'reason': 'missing ListingDate'})
            continue
        duplicate_groups.setdefault(symbol, []).append(row)
    duplicate_symbols = {symbol for symbol, rows in duplicate_groups.items() if symbol and len(rows) > 1}
    delisted = []
    for symbol, rows in duplicate_groups.items():
        if symbol:
            for row in rows:
                listing = parse_date(row.get('ListingDate'), 'ListingDate')
                delisting = parse_date(row.get('DelistingDate'), 'DelistingDate')
                if not listing or not delisting:
                    raise ValueError(f'missing listing/delisting date for {symbol}')
                delisted.append({'market': row.get('Market', '').strip(), 'symbol': symbol,
                                 'alive_from': listing.isoformat(), 'alive_through': delisting.isoformat(),
                                 'source': 'FDR KRX-DELISTING', 'source_asof': asof,
                                 'status': STATUS, '_start': listing, '_end': delisting})

    current, excluded_after_cutoff = [], []
    for row in current_rows:
        required = ('market', 'symbol', 'listing_date')
        if any(not row.get(key, '').strip() for key in required):
            raise ValueError(f'current-listing row requires market,symbol,listing_date: {row}')
        listing = parse_date(row['listing_date'], 'listing_date')
        if not listing:
            raise ValueError(f'missing listing_date for {row["symbol"]}')
        if listing > CUTOFF:
            excluded_after_cutoff.append({'symbol': row['symbol'], 'market': row['market'],
                                          'listing_date': listing.isoformat(),
                                          'reason': 'listing_date after 2026-05-31 cutoff'})
            continue
        current.append({'market': row['market'], 'symbol': row['symbol'],
                        'alive_from': listing.isoformat(), 'alive_through': CUTOFF.isoformat(),
                        'source': row.get('source', '').strip() or 'current-listing CSV',
                        'source_asof': asof, 'status': STATUS, '_start': listing, '_end': CUTOFF})

    conflicts, rejected_current = [], set()
    rejected_delisted = {index for index, row in enumerate(delisted)
                         if row['symbol'] in duplicate_symbols}
    for d_index, drow in enumerate(delisted):
        for c_index, crow in enumerate(current):
            if drow['symbol'] != crow['symbol']:
                continue
            if drow['_start'] <= crow['_end'] and crow['_start'] <= drow['_end']:
                rejected_delisted.add(d_index)
                rejected_current.add(c_index)
                conflicts.append({'symbol': drow['symbol'], 'reason': 'overlapping delisted/current listing intervals',
                                  'delisted_market': drow['market'], 'delisted_alive_from': drow['alive_from'],
                                  'delisted_alive_through': drow['alive_through'],
                                  'current_market': crow['market'], 'current_alive_from': crow['alive_from'],
                                  'current_alive_through': crow['alive_through']})
    for symbol in sorted(duplicate_symbols):
        conflicts.append({'symbol': symbol, 'reason': 'duplicate Symbol in delisting_list.csv',
                          'delisted_market': '', 'delisted_alive_from': '', 'delisted_alive_through': '',
                          'current_market': '', 'current_alive_from': '', 'current_alive_through': ''})

    output = [row for index, row in enumerate(delisted) if index not in rejected_delisted]
    output.extend(row for index, row in enumerate(current) if index not in rejected_current)
    validate_intervals(output)
    for row in output:
        row.pop('_start', None)
        row.pop('_end', None)
    write_csv(output_path, MEMBERSHIP_COLUMNS, output)
    write_csv(output_path.with_name('excluded_after_cutoff.csv'),
              ['symbol', 'market', 'listing_date', 'reason'], excluded_after_cutoff)
    write_csv(output_path.with_name('excluded_missing_listing_date.csv'), ['symbol', 'reason'], missing)
    if conflicts:
        write_csv(output_path.with_name('conflicts.csv'),
                  ['symbol', 'reason', 'delisted_market', 'delisted_alive_from', 'delisted_alive_through',
                   'current_market', 'current_alive_from', 'current_alive_through'], conflicts)
    elif current_path:
        write_csv(output_path.with_name('conflicts.csv'),
                  ['symbol', 'reason', 'delisted_market', 'delisted_alive_from', 'delisted_alive_through',
                   'current_market', 'current_alive_from', 'current_alive_through'], [])
    return {'membership_rows': len(output), 'excluded_missing_listing_date': len(missing),
            'excluded_after_cutoff': len(excluded_after_cutoff),
            'duplicate_symbols': len(duplicate_symbols), 'overlap_conflicts': len(conflicts) - len(duplicate_symbols)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delisting-list', type=Path, default=DEFAULT_DELISTING)
    parser.add_argument('--current-listing', type=Path)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    counts = build(args.delisting_list, args.output, args.current_listing)
    print(f'membership rows: {counts["membership_rows"]}')
    print(f'excluded current listings after cutoff: {counts["excluded_after_cutoff"]}')
    print('alive_from <= alive_through check: PASS')
    print(f'excluded missing ListingDate: {counts["excluded_missing_listing_date"]}')
    print(f'duplicate delisting symbols: {counts["duplicate_symbols"]}')
    print(f'overlap conflicts: {counts["overlap_conflicts"]}')
    if not args.current_listing:
        print('Note: current-listing symbols are not included; only delisting_list.csv rows were processed.')


if __name__ == '__main__':
    main()
