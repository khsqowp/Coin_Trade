"""Run offline research: python -m app.rs_regime_run [--self-test-only]."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time
import numpy as np
import pandas as pd

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.rs_regime_lib import (Config, Engine, config_grid, diagnostic, load_cache,
                               metrics, neighbours, self_test)


TRAIN_END = '2024-06-30'
OOS_START = '2024-07-01'


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value


def table(title, rows, columns):
    print(f'\n### {title}\n')
    print('| ' + ' | '.join(columns) + ' |')
    print('| ' + ' | '.join('---' for _ in columns) + ' |')
    for row in rows:
        cells = []
        for key in columns:
            v = row.get(key)
            if isinstance(v, float):
                v = f'{v:.6f}'
            elif isinstance(v, dict):
                v = json.dumps(v, sort_keys=True)
            cells.append(str(v) if v is not None else 'NA')
        print('| ' + ' | '.join(cells) + ' |')


def split_metrics(daily):
    return {'TRAIN': metrics(daily.loc[:TRAIN_END]), 'OOS': metrics(daily.loc[OOS_START:]),
            'FULL': metrics(daily)}


def eligible(m):
    return m['days'] >= 180 and m['MDD'] is not None and m['MDD'] <= 0.25 and m['Calmar'] is not None


def score(m):
    return m['Calmar'] if eligible(m) else -float('inf')


def folds(engine, configs, baseline):
    rows = []
    for start, end in [('2023-01-01', '2023-12-31'), ('2024-01-01', '2024-12-31'), ('2025-01-01', None)]:
        cutoff = pd.Timestamp(start) - pd.Timedelta(days=1)
        best, best_score = None, -float('inf')
        for c in configs:
            daily = engine.run(c)['daily']
            train = metrics(daily.loc[:cutoff])
            s = score(train)
            if s > best_score:
                best, best_score = c, s
        test_base = baseline.loc[start:end]
        if best is None or test_base.empty:
            rows.append({'window': start, 'selected': None, 'reason': 'No eligible training config or no test observations'})
            continue
        selected = engine.run(best)['daily']
        rows.append({'window': start, 'selected': best.label(), 'train': metrics(selected.loc[:cutoff]),
                     'test': metrics(selected.loc[start:end]), 'baseline': metrics(test_base)})
    return rows


def robustness(engine, top, baseline_metrics):
    rows = []
    for entry in top:
        c = Config(**entry['config'])
        nearby = []
        for other in neighbours(c):
            m = split_metrics(engine.run(other)['daily'])
            nearby.append({'config': asdict(other), 'id': other.label(), **m})
        fractions = {}
        for part in ('FULL', 'OOS'):
            base = baseline_metrics[part]['Calmar']
            valid = [n[part]['Calmar'] for n in nearby if n[part]['Calmar'] is not None]
            fractions[part] = sum(v > base for v in valid) / len(valid) if valid and base is not None else None
        rows.append({'design': c.label(), 'neighbours': nearby, 'fraction_beating_baseline': fractions})
    return rows


def report(results):
    columns = ['CAGR', 'MDD', 'Calmar', 'Sharpe', 'worst_day', 'time_in_market', 'annual_turnover', 'rebalances_yr', 'flips_yr', 'days']
    table('Baseline (decimal returns; WITH funding is primary)',
          [{'variant': k, **v} for k, v in results['baseline'].items()], ['variant'] + columns)
    table('Baseline calendar years', [{'year': y, 'WITH': v, 'WITHOUT': results['baseline']['WITHOUT']['years'][y]}
                                      for y, v in results['baseline']['WITH']['years'].items()], ['year', 'WITH', 'WITHOUT'])
    table('Diagnostics: prior-close detector, expanding terciles', results['diagnostics'],
          ['detector', 'tercile', 'mean', 'Sharpe', 'n', 'year_signs'])
    rows = []
    for rank, entry in enumerate(results['top10'], 1):
        for part in ('TRAIN', 'OOS', 'FULL'):
            rows.append({'rank': rank, 'id': entry['id'], 'period': part, **entry[part]})
    table(f'Top 10 by TRAIN Calmar, TRAIN MDD <= 25%; {len(results["grid"])} configs tried', rows,
          ['rank', 'id', 'period'] + columns + ['years'])
    rows = []
    for fold in results['folds']:
        for variant in ('test', 'baseline'):
            rows.append({'window': fold['window'], 'selected': fold['selected'], 'variant': variant,
                         **fold.get(variant, {}), 'reason': fold.get('reason', '')})
    table('Expanding training folds', rows, ['window', 'selected', 'variant', 'CAGR', 'MDD', 'Calmar', 'Sharpe', 'reason'])
    rows = []
    for design in results['robustness']:
        for neighbour in design['neighbours']:
            rows.append({'design': design['design'], 'neighbour': neighbour['id'],
                         'FULL Calmar': neighbour['FULL']['Calmar'], 'FULL CAGR': neighbour['FULL']['CAGR'],
                         'OOS Calmar': neighbour['OOS']['Calmar'], 'OOS CAGR': neighbour['OOS']['CAGR']})
    table('Top 3 distinct designs: adjacent parameter neighbours', rows,
          ['design', 'neighbour', 'FULL Calmar', 'FULL CAGR', 'OOS Calmar', 'OOS CAGR'])
    table('Neighbour fractions beating baseline Calmar',
          [{'design': d['design'], **d['fraction_beating_baseline']} for d in results['robustness']], ['design', 'FULL', 'OOS'])
    table('Excluding calendar 2024 (365 observations/year annualization)', results['excluding_2024'], ['id'] + columns + ['years'])


def research(close, funding):
    engine = Engine(close, funding)
    baseline = engine.prepare()['daily']
    configs = config_grid(engine.features)
    grid = []
    started = time.perf_counter()
    for c in configs:
        grid.append({'id': c.label(), 'config': asdict(c), **split_metrics(engine.run(c)['daily'])})
    ranked = sorted(grid, key=lambda entry: score(entry['TRAIN']), reverse=True)
    top = [entry for entry in ranked if eligible(entry['TRAIN'])][:10]
    # Design = detector/action/direction, so near-identical thresholds do not consume all three slots.
    designs, seen = [], set()
    for entry in top + ranked:
        key = tuple(entry['config'][k] for k in ('detector', 'action', 'direction'))
        if eligible(entry['TRAIN']) and key not in seen:
            seen.add(key)
            designs.append(entry)
        if len(designs) == 3:
            break
    baseline_parts = split_metrics(baseline)
    excluding = [{'id': 'baseline', **metrics(baseline.loc[baseline.index.year != 2024])}]
    for entry in designs:
        daily = engine.run(Config(**entry['config']))['daily']
        excluding.append({'id': entry['id'], **metrics(daily.loc[daily.index.year != 2024])})
    return {'metadata': {'symbols': list(close.columns), 'data_start': str(close.index.min().date()),
                         'data_end': str(close.index.max().date()), 'configs_tried': len(grid),
                         'grid_seconds': time.perf_counter() - started,
                         'end_rule': 'Last cached date, with no artificial 2026 truncation',
                         'missing_return_rule': 'Missing asset returns are zero; prices are never filled',
                         'funding_rule': 'Missing funding is zero', 'cost_per_turnover': 0.001,
                         'rebalance_rule': 'Scheduled decision count, including flat schedules; first earning day follows first signal',
                         'selection_rule': 'TRAIN only, MDD <= .25, >=180 days; deterministic grid-order ties',
                         'partial_cache_warning': 'Available cached universe only; incomplete/unbalanced caches can bias results',
                         'lookback_rule': 'Flag selects alternate independently held R-day sleeve; regime change can change exposure off schedule'},
            'baseline': {'WITH': metrics(baseline), 'WITHOUT': metrics(baseline, 'without_funding')},
            'diagnostics': diagnostic(engine.features, baseline), 'grid': grid, 'top10': top,
            'folds': folds(engine, configs, baseline), 'robustness': robustness(engine, designs, baseline_parts),
            'excluding_2024': excluding}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, default=Path('.rs_cache'))
    parser.add_argument('--output', type=Path, default=Path('docs/research/_regime_results.json'))
    parser.add_argument('--self-test-only', action='store_true')
    args = parser.parse_args()
    checks = self_test()
    print('Self-test:', json.dumps(checks, sort_keys=True))
    if args.self_test_only:
        return
    close, funding, warnings = load_cache(args.cache)
    if close.empty or not (close.index >= pd.Timestamp('2022-01-01')).any():
        print('No cached backtest observations. No empirical results written. Run again as CSVs arrive.')
        return
    results = research(close, funding)
    results['self_test'], results['loader_warnings'] = checks, warnings
    results = clean(results)
    # NEW files only: never overwrite an earlier research artifact.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as handle:
        json.dump(results, handle, indent=2, allow_nan=False)
        handle.write('\n')
    report(results)
    print(f'\nComplete: {len(close.columns)} cached symbols; {len(results["grid"])} configurations; results: {args.output}')
    print('Research limitations: cached universe survivorship, missing prices treated as zero return, missing funding as zero, multiple grid comparisons.')


if __name__ == '__main__':
    main()
