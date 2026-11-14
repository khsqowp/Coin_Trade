"""Post-hoc A3 matched random-portfolio diagnostic. Offline; writes results_null.json only."""
import json
from pathlib import Path
import numpy as np
import bt2

KR = Path('/app/kr')
TRIALS = [
    'V1_XS_MOM12_1', 'V2_XS_MOM12_1_MF', 'V3_XS_MOM60_REPL',
    'V4_XS_52WH', 'V5_XS_LOWVOL', 'V6_XS_MOM_LOWVOL',
    'V7_TS_DONCHIAN_70_25', 'V8_EV_VOLSPIKE20', 'V9_XS_STREV_W'
]
SLOTS = {'V7_TS_DONCHIAN_70_25', 'V8_EV_VOLSPIKE20'}


def active_sharpe(nav, b1, start, end):
    a = nav.loc[start:end, 'ret']
    b = b1['ret'].reindex(a.index).fillna(0.0)
    return float(bt2.metrics.sharpe_annual((a - b).to_numpy(), bt2.PPY))


def rand_full(P, sig, name, rng):
    """Keep each decision date, cash state and target count; randomize names within the registered pool."""
    out = {}
    for t, target in sig.items():
        k = len(target)
        if not k:
            out[t] = {}
            continue
        pool = np.where(P.elig3[t])[0] if name == 'V3_XS_MOM60_REPL' else bt2.u500(P, t)
        if k > len(pool):
            k = len(pool)
        chosen = rng.choice(pool, size=k, replace=False) if k else []
        weight = next(iter(target.values()))
        out[t] = {int(a): float(weight) for a in chosen}
    return out


def slot_membership_by_signal(P, sig):
    """Mirror V7/V8's latest-month-end U500 membership state for every signal date."""
    month_ends = bt2.month_end_idx(P.cal)
    active, pools = set(), {}
    for t in range(P.t0 - 260, len(P.cal)):
        if t in month_ends or not active:
            active = set(bt2.u500(P, t).tolist())
        if t in sig:
            pools[t] = sorted(active)
    return pools


def rand_slots(P, sig, name, rng, pools):
    """Keep slot event timing/weights and randomize entrants from the active month-end U500."""
    out, held = {}, set()
    for t in sorted(sig):
        changes = sig[t]
        ch = {}
        exits = [a for a, w in changes.items() if w <= 0]
        # Match the number and date of observed exits, but close randomly-held null names.
        exit_names = []
        if exits and held:
            exit_names = rng.choice(np.asarray(sorted(held), dtype=int), size=min(len(exits), len(held)), replace=False).tolist()
        for a in exit_names:
            held.remove(int(a)); ch[int(a)] = 0.0
        entries = [float(w) for w in changes.values() if w > 0]
        if entries:
            pool = [int(a) for a in pools.get(t, []) if int(a) not in held]
            take = min(len(entries), len(pool))
            if take:
                chosen = rng.choice(np.asarray(pool, dtype=int), size=take, replace=False)
                for a, w in zip(chosen, entries[:take]):
                    held.add(int(a)); ch[int(a)] = w
        if ch:
            out[t] = ch
    return out


def main():
    mainres = json.loads((KR / 'results_main.json').read_text())
    P = bt2.load_panel()
    F = bt2.feats(P)
    B1 = bt2.b1_nav(P)
    T = bt2.trials_build(P, F)
    draws_full, draws_slots = 200, 100
    results = {}
    for ix, name in enumerate(TRIALS):
        sig, mode = T[name]
        real_nav, _ = bt2.simulate(P, sig, mode=mode)
        real = {
            'IS': active_sharpe(real_nav, B1, bt2.START, bt2.IS_END),
            'OOS': active_sharpe(real_nav, B1, bt2.OOS_START, bt2.END),
        }
        draws = draws_slots if name in SLOTS else draws_full
        rng = np.random.default_rng(20261105 + ix)
        slot_pools = slot_membership_by_signal(P, sig) if name in SLOTS else None
        sims = {'IS': [], 'OOS': []}
        for j in range(draws):
            rsig = rand_slots(P, sig, name, rng, slot_pools) if name in SLOTS else rand_full(P, sig, name, rng)
            nav, _ = bt2.simulate(P, rsig, mode=mode)
            for period, a, b in (('IS', bt2.START, bt2.IS_END), ('OOS', bt2.OOS_START, bt2.END)):
                sims[period].append(active_sharpe(nav, B1, a, b))
            if (j + 1) % 25 == 0:
                print(name, 'draw', j + 1, '/', draws, flush=True)
        item = {'draws': draws, 'seed': 20261105 + ix, 'selection_count': 0,
                'real_active_sharpe': real, 'p': {}, 'null_median': {}, 'null_p95': {}}
        for period in ('IS', 'OOS'):
            vals = sims[period]
            item['p'][period] = round((1 + sum(x >= real[period] for x in vals)) / (1 + draws), 6)
            item['null_median'][period] = round(float(np.median(vals)), 4)
            item['null_p95'][period] = round(float(np.percentile(vals, 95)), 4)
        results[name] = item
        print(name, item, flush=True)
    ps = [results[n]['p']['OOS'] for n in TRIALS]
    m = len(ps)
    order = np.argsort(ps)
    q = np.empty(m, float); prev = 1.0
    for rank in range(m, 0, -1):
        k = order[rank - 1]
        prev = min(prev, ps[k] * m / rank)
        q[k] = prev
    for k, name in enumerate(TRIALS):
        results[name]['bonferroni_OOS'] = round(min(1.0, ps[k] * m), 6)
        results[name]['bh_q_OOS'] = round(float(q[k]), 6)
    payload = {'diagnostic': 'post-hoc Addendum A3; selection_count=0', 'metric': 'annualized Sharpe of daily strategy returns minus B1 daily returns',
               'draws_non_slot': draws_full, 'draws_slot': draws_slots, 'trials': results,
               'is_pick_from_main': mainres['is_pick'], 'correction_family': TRIALS}
    (KR / 'results_null.json').write_text(json.dumps(payload, indent=2))
    print('WROTE results_null.json', flush=True)


if __name__ == '__main__':
    main()
