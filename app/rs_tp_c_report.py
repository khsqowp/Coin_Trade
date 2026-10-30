"""Builds tables + prereg-rule verdicts from results.json -> docs/research/tp_loop/C/tables.md, verdicts.json"""
import json, sys
sys.dont_write_bytecode = True
import numpy as np
D = "docs/research/tp_loop/C/"
r = json.load(open(D + "results.json"))
HEAD = ["A1", "A2", "A3", "A4", "A5", "A6", "B1", "B2", "R1", "R2", "C1", "C2"]
DESC = {"A1": "A 롱+숏 z3", "A2": "A 롱 z3", "A3": "A 숏 z3", "A4": "A 롱+숏 z2.5", "A5": "A 롱+숏 z4", "A6": "ADV 역방향 z3",
        "B1": "순위감쇠 m4", "B2": "순위감쇠 m2", "R1": "리밸 1일", "R2": "리밸 2일", "C1": "A1+트림", "C2": "B1+트림"}


def verdict(bn, n):
    c = r[bn]["cfg"][n]; res = r["RESEARCH"]["cfg"][n]
    pl = c.get("placebo")
    plc_ok = True if pl is None else (pl["hazard_pass"] and pl.get("shift_pass", True))
    crit = dict(IS=c["d_IS"] > 0, OOS=c["d_OOS"] > 0, regimes=c["regimes_improved"] >= 5, subsets=c["subset_pos"] >= 7,
                placebo=plc_ok, cost2x=c["d_2x"] > 0, neighbors=c["neigh_stable"], boot=c["boot_ci_bonf"][0] > 0,
                research=res["d_full"] > 0)
    helps = all(crit.values())
    hurts = c["d_IS"] < 0 and c["d_OOS"] < 0 and c["subset_pos"] <= 3 and c["regimes_improved"] <= 1
    return ("helps" if helps else "hurts" if hurts else "noise"), crit


V = {bn: {n: verdict(bn, n) for n in HEAD} for bn in ("LIVE", "RESEARCH")}
json.dump({bn: {n: dict(verdict=v[0], crit=v[1]) for n, v in d.items()} for bn, d in V.items()}, open(D + "verdicts.json", "w"), indent=1, default=bool)
L = []
f = lambda x, p=2: "n/a" if x is None else f"{x:.{p}f}"
for bn in ("LIVE", "RESEARCH"):
    R = r[bn]; v0 = R["V0"]
    L.append(f"\n### {bn} 구성: 요약 (전구간 2022-01-01~2026-10-09, 3위상 평균; 괄호=최악위상)\n")
    L.append("| ID | 설정 | Calmar | CAGR% | 종가MDD% | kill/위상 | 회전율(x/년) | 수수료드래그%/년 | 청산/년(롱,숏) | ΔCalmar | 최악위상Δ |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    L.append(f"| V0 | 기준 | {f(v0['calmar'])} ({f(v0['calmar_worst'])}) | {v0['cagr']*100:.1f} ({v0['cagr_worst']*100:.1f}) | {v0['mdd']*100:.1f} ({v0['mdd_worst']*100:.1f}) | {v0['kills']:.1f} | {v0['turnover']:.0f} | {v0['fee_drag']*100:.1f} | 0,0 | - | - |")
    for n in HEAD:
        c = R["cfg"][n]; s = c["summary"]
        L.append(f"| {n} | {DESC[n]} | {f(s['calmar'])} ({f(s['calmar_worst'])}) | {s['cagr']*100:.1f} ({s['cagr_worst']*100:.1f}) | {s['mdd']*100:.1f} ({s['mdd_worst']*100:.1f}) | {s['kills']:.1f} | {s['turnover']:.0f} | {s['fee_drag']*100:.1f} | {s['exL_yr']:.0f},{s['exS_yr']:.0f} | {c['d_full']:+.2f} | {c['worst_phase_delta']:+.2f} |")
    L.append(f"\n### {bn}: IS / OOS (ΔCalmar, CAGR V0->변형 %, 종가MDD V0->변형 %, 위상평균)\n")
    L.append("| ID | IS ΔCalmar | IS CAGR | IS MDD | OOS ΔCalmar | OOS CAGR | OOS MDD |")
    L.append("|---|---|---|---|---|---|---|")
    for n in HEAD:
        c = R["cfg"][n]
        L.append(f"| {n} | {c['d_IS']:+.2f} | {c['cagr_IS'][0]*100:.0f}->{c['cagr_IS'][1]*100:.0f} | {c['mdd_IS'][0]*100:.0f}->{c['mdd_IS'][1]*100:.0f} | {c['d_OOS']:+.2f} | {c['cagr_OOS'][0]*100:.0f}->{c['cagr_OOS'][1]*100:.0f} | {c['mdd_OOS'][0]*100:.0f}->{c['mdd_OOS'][1]*100:.0f} |")
    L.append(f"\n### {bn}: 레짐별 Δ(로그수익 합, 변형-V0; +가 개선). 일수는 첫 행 기준\n")
    keys = ["bear", "chop", "bull", "lowvol", "midvol", "highvol"]
    rg0 = R["cfg"]["A1"]["regimes"]
    L.append("| ID | " + " | ".join(f"{k}({rg0[k]['days']}d)" for k in keys) + " | 개선수/6 |")
    L.append("|---|" + "---|" * 7)
    for n in HEAD:
        c = R["cfg"][n]
        L.append(f"| {n} | " + " | ".join(f"{c['regimes'][k]['dlog']:+.2f}" for k in keys) + f" | {c['regimes_improved']} |")
    L.append(f"\n### {bn}: 스트레스 창 (복리 수익 차이 변형-V0, %p; V0 수익 %)\n")
    sk = list(R["cfg"]["A1"]["stress"].keys())
    L.append("| ID | " + " | ".join(sk) + " |")
    L.append("|---|" + "---|" * len(sk))
    L.append("| V0 수익% | " + " | ".join(f"{R['cfg']['A1']['stress'][k]['v0']*100:.0f}" for k in sk) + " |")
    for n in HEAD:
        c = R["cfg"][n]
        L.append(f"| {n} | " + " | ".join(f"{c['stress'][k]['diff']*100:+.0f}" for k in sk) + " |")
    L.append(f"\n### {bn}: 위상별 ΔCalmar / 서브셋(30종목 x10) 개선 비율 / 2x 비용 ΔCalmar / 이웃(±25%) 전구간 ΔCalmar\n")
    L.append("| ID | 위상별Δ | 서브셋 개선 | 서브셋Δ 중앙값 | 2x비용 Δ | 이웃 (IS,OOS) | 이웃 안정 |")
    L.append("|---|---|---|---|---|---|---|")
    for n in HEAD:
        c = R["cfg"][n]
        nb = "; ".join(f"({x['d_IS']:+.2f},{x['d_OOS']:+.2f})" for x in c["neighbors"])
        L.append(f"| {n} | {', '.join(f'{x:+.2f}' for x in c['phase_delta'])} | {c['subset_pos']}/10 | {np.median(c['subset_d']):+.2f} | {c['d_2x']:+.2f} | {nb} | {'Y' if c['neigh_stable'] else 'N'} |")
    L.append(f"\n### {bn}: 플라시보 / 부트스트랩 (블록15일, 5000회; CI=Bonferroni 12, 양측 99.58%)\n")
    L.append("| ID | 실제Δ | 무작위청산 플라시보 평균/p95/경험p | 시프트 플라시보 평균/p95/경험p | 부트 점추정 | 95%CI | Bonf CI | p(단측) | Holm p |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for n in HEAD:
        c = R["cfg"][n]; p = c.get("placebo"); b = c["boot"]
        hp = "n/a" if p is None else f"{p['hazard_mean']:+.2f}/{p['hazard_p95']:+.2f}/{p['hazard_p']:.2f}"
        sp = "n/a" if (p is None or "shift_p" not in p) else f"{p['shift_mean']:+.2f}/{p['shift_p95']:+.2f}/{p['shift_p']:.2f}"
        L.append(f"| {n} | {c['d_full']:+.2f} | {hp} | {sp} | {b['point']:+.2f} | [{c['boot_ci95'][0]:+.2f},{c['boot_ci95'][1]:+.2f}] | [{c['boot_ci_bonf'][0]:+.2f},{c['boot_ci_bonf'][1]:+.2f}] | {b['p_one']:.3f} | {b['p_holm']:.3f} |")
    L.append(f"\n### {bn}: 판정 (사전등록 규칙 자동 적용)\n")
    L.append("| ID | 판정 | IS | OOS | 레짐>=5 | 서브셋>=7 | 플라시보 | 2x비용 | 이웃 | CI>0 | RESEARCH>0 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for n in HEAD:
        vv, cr = V[bn][n]
        L.append(f"| {n} | **{vv}** | " + " | ".join('Y' if cr[k] else 'N' for k in ["IS", "OOS", "regimes", "subsets", "placebo", "cost2x", "neighbors", "boot", "research"]) + " |")
# wide horizon info
L.append("\n### 정보용: 수익률 호라이즌 h=1,3 (넓은 이웃) 전구간 ΔCalmar\n")
for bn in ("LIVE", "RESEARCH"):
    for n in ("A1", "A2", "A3", "C1"):
        L.append(f"- {bn} {n}: h=1 {r[bn]['cfg'][n]['wide_h']['1']:+.2f}, h=2(기본) {r[bn]['cfg'][n]['d_full']:+.2f}, h=3 {r[bn]['cfg'][n]['wide_h']['3']:+.2f}")
# IS selection
L.append("\n### IS 전용 선택 (계열별 IS ΔCalmar 최대, 이후 OOS 확인)\n")
for bn in ("LIVE", "RESEARCH"):
    for fam, ids in (("A", ["A1", "A2", "A3", "A4", "A5"]), ("B", ["B1", "B2"]), ("R", ["R1", "R2"]), ("C", ["C1", "C2"])):
        best = max(ids, key=lambda k: r[bn]["cfg"][k]["d_IS"]); c = r[bn]["cfg"][best]
        L.append(f"- {bn} 계열{fam}: IS 선택 {best} (IS Δ {c['d_IS']:+.2f}) -> OOS Δ {c['d_OOS']:+.2f}, 전구간 {c['d_full']:+.2f}")
open(D + "tables.md", "w").write("\n".join(L) + "\n")
print("\n".join(L))
