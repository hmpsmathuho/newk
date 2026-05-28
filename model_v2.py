#!/usr/bin/env python3
"""Model rebuild — compare 4 variants on same EPL 2025/26 backtest.

V0: Original Poisson (baseline, BROKEN per backtest)
V1: Calibrated Poisson (Platt-style shrinkage + lambda inflation)
V2: Dixon-Coles bivariate (corrects low-score cells, fixes BTTS underestimate)
V3: Market-blend (0.4 * form_lambda + 0.6 * market_implied_lambda)

All four scored on SAME held-out test set (last 150 of 300 predictions).
"""
import csv
import math
from collections import defaultdict, deque
from datetime import datetime


def pmf(k, l): return math.exp(-l) * l ** k / math.factorial(k)
def cdf(k, l): return sum(pmf(i, l) for i in range(k + 1))


def dc_factor(h, a, lh, la, rho):
    if h == 0 and a == 0: return 1 - lh * la * rho
    if h == 0 and a == 1: return 1 + lh * rho
    if h == 1 and a == 0: return 1 + la * rho
    if h == 1 and a == 1: return 1 - rho
    return 1.0


def dc_under(threshold, lh, la, rho=-0.10, max_g=10):
    p = 0.0
    for h in range(max_g + 1):
        for a in range(max_g + 1):
            if h + a <= threshold:
                p += pmf(h, lh) * pmf(a, la) * dc_factor(h, a, lh, la, rho)
    return p


def dc_btts_yes(lh, la, rho=-0.10, max_g=10):
    p = 0.0
    for h in range(1, max_g + 1):
        for a in range(1, max_g + 1):
            p += pmf(h, lh) * pmf(a, la) * dc_factor(h, a, lh, la, rho)
    return p


def market_lambda_total(u25_odds, o25_odds):
    if not u25_odds or not o25_odds: return None
    ip_u = 1 / u25_odds
    ip_o = 1 / o25_odds
    margin = ip_u + ip_o
    p_u_devig = ip_u / margin
    lo, hi = 0.3, 7.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if cdf(2, mid) > p_u_devig:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def parse_date(s):
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try: return datetime.strptime(s, fmt)
        except ValueError: pass
    raise ValueError(f"bad date {s}")


def _f(s):
    try: return float(s)
    except (TypeError, ValueError): return None


def load_matches(path):
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for x in r:
            try:
                d = parse_date(x["Date"])
                fh = int(x["FTHG"]); fa = int(x["FTAG"])
            except (ValueError, KeyError):
                continue
            rows.append({
                "date": d, "home": x["HomeTeam"].strip(), "away": x["AwayTeam"].strip(),
                "fh": fh, "fa": fa,
                "u25_odds": _f(x.get("Avg<2.5")), "o25_odds": _f(x.get("Avg>2.5")),
            })
    rows.sort(key=lambda r: r["date"])
    return rows


def compute_predictions(rows, n_window=6, min_games=4):
    home_hist = defaultdict(lambda: deque(maxlen=n_window))
    away_hist = defaultdict(lambda: deque(maxlen=n_window))
    all_h_gf, all_h_ga = [], []

    for m in rows:
        h, a = m["home"], m["away"]
        hh, aa = home_hist[h], away_hist[a]

        if len(hh) >= min_games and len(aa) >= min_games and all_h_gf:
            avg_h_gf = sum(gf for gf, _ in hh) / len(hh)
            avg_h_ga = sum(ga for _, ga in hh) / len(hh)
            avg_a_gf = sum(gf for gf, _ in aa) / len(aa)
            avg_a_ga = sum(ga for _, ga in aa) / len(aa)

            league_h_gf = sum(all_h_gf) / len(all_h_gf)
            league_h_ga = sum(all_h_ga) / len(all_h_ga)

            home_atk = avg_h_gf / max(league_h_gf, 0.1)
            home_def = avg_h_ga / max(league_h_ga, 0.1)
            away_atk = avg_a_gf / max(league_h_ga, 0.1)
            away_def = avg_a_ga / max(league_h_gf, 0.1)

            lh_form = league_h_gf * home_atk * away_def
            la_form = league_h_ga * away_atk * home_def

            mkt_total = market_lambda_total(m["u25_odds"], m["o25_odds"])
            if mkt_total:
                form_total = lh_form + la_form
                blend_total = 0.4 * form_total + 0.6 * mkt_total
                ratio_h = lh_form / form_total if form_total > 0 else 0.55
                lh_v3 = blend_total * ratio_h
                la_v3 = blend_total * (1 - ratio_h)
            else:
                lh_v3, la_v3 = lh_form, la_form

            actual_total = m["fh"] + m["fa"]
            actual_btts = m["fh"] >= 1 and m["fa"] >= 1

            yield {
                "date": m["date"], "home": h, "away": a, "fh": m["fh"], "fa": m["fa"],
                "actual_total": actual_total, "actual_btts": actual_btts,
                "actual_u25": actual_total <= 2, "actual_u35": actual_total <= 3,
                "u25_odds": m["u25_odds"], "o25_odds": m["o25_odds"],
                "v0_lh": lh_form, "v0_la": la_form,
                "v0_p_u25": cdf(2, lh_form + la_form),
                "v0_p_u35": cdf(3, lh_form + la_form),
                "v0_p_btts": (1 - math.exp(-lh_form)) * (1 - math.exp(-la_form)),
                "v2_p_u25": dc_under(2, lh_form, la_form),
                "v2_p_u35": dc_under(3, lh_form, la_form),
                "v2_p_btts": dc_btts_yes(lh_form, la_form),
                "v3_p_u25": cdf(2, lh_v3 + la_v3),
                "v3_p_u35": cdf(3, lh_v3 + la_v3),
                "v3_p_btts": (1 - math.exp(-lh_v3)) * (1 - math.exp(-la_v3)),
                "v3_lh": lh_v3, "v3_la": la_v3,
            }

        hh.append((m["fh"], m["fa"]))
        aa.append((m["fa"], m["fh"]))
        all_h_gf.append(m["fh"])
        all_h_ga.append(m["fa"])


def fit_calibration(train_preds, p_key, actual_key):
    xs = [p[p_key] for p in train_preds]
    ys = [1 if p[actual_key] else 0 for p in train_preds]
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    den = sum((xs[i] - mx) ** 2 for i in range(n))
    if den < 1e-9: return 0, 1
    b = num / den
    a = my - b * mx
    return a, b


def apply_calibration(p, a, b):
    out = a + b * p
    return max(0.001, min(0.999, out))


def calibration_table(preds, p_key, actual_key, label):
    bins = [(0, 0.5), (0.5, 0.6), (0.6, 0.65), (0.65, 0.70),
            (0.70, 0.75), (0.75, 0.80), (0.80, 0.90), (0.90, 1.01)]
    print(f"\n  {label}")
    print(f"    {'Bucket':<13}{'N':>5}{'Pred':>10}{'Actual':>10}{'Diff':>10}")
    for lo, hi in bins:
        b = [p for p in preds if lo <= p[p_key] < hi]
        if not b: continue
        n = len(b)
        mp = sum(p[p_key] for p in b) / n
        ar = sum(1 for p in b if p[actual_key]) / n
        d = ar - mp
        flag = " " if abs(d) < 0.05 else ("!" if abs(d) < 0.15 else "X")
        print(f"    {lo:.2f}-{hi:.2f}  {n:>5}   {mp*100:>6.1f}%   {ar*100:>6.1f}%   {d*100:>+5.1f}pp {flag}")


def gate_roi(preds, p_key, odds_key, actual_key, label, model_min=0.65, value_min=0.04, gap_min=4.0):
    picks = []
    for p in preds:
        if not p[odds_key]: continue
        mp, o = p[p_key], p[odds_key]
        if not (1.30 <= o <= 2.50): continue
        if mp < model_min: continue
        value = mp * o - 1
        gap = (mp - 1 / o) * 100
        if value < value_min or gap < gap_min: continue
        picks.append({"mp": mp, "odds": o, "won": p[actual_key]})

    n = len(picks)
    if n == 0:
        print(f"    {label:<35} 0 picks")
        return
    won = sum(1 for x in picks if x["won"])
    avg_p = sum(x["mp"] for x in picks) / n
    actual = won / n
    roi = sum((x["odds"] - 1) if x["won"] else -1 for x in picks) / n
    pl = sum((x["odds"] - 1) if x["won"] else -1 for x in picks)
    print(f"    {label:<35} N={n:3d}  pred={avg_p*100:5.1f}%  actual={actual*100:5.1f}%  err={(actual-avg_p)*100:+6.1f}pp  ROI={roi*100:+6.2f}%  P/L={pl:+6.2f}u")


def main():
    rows = load_matches("/projects/sandbox/newk/E0_2526.csv")
    preds = list(compute_predictions(rows, n_window=6, min_games=4))
    print(f"Loaded {len(rows)} matches -> {len(preds)} predictions (after warmup)")

    half = len(preds) // 2
    train, test = preds[:half], preds[half:]
    print(f"Train: {len(train)}  Test: {len(test)} (all models scored on test)")

    a25, b25 = fit_calibration(train, "v0_p_u25", "actual_u25")
    a35, b35 = fit_calibration(train, "v0_p_u35", "actual_u35")
    abt, bbt = fit_calibration(train, "v0_p_btts", "actual_btts")
    print(f"\nV1 calibration fit (linear P_cal = a + b*P_raw) on train:")
    print(f"  U2.5: a={a25:.3f}, b={b25:.3f}")
    print(f"  U3.5: a={a35:.3f}, b={b35:.3f}")
    print(f"  BTTS: a={abt:.3f}, b={bbt:.3f}")

    for p in test:
        p["v1_p_u25"] = apply_calibration(p["v0_p_u25"], a25, b25)
        p["v1_p_u35"] = apply_calibration(p["v0_p_u35"], a35, b35)
        p["v1_p_btts"] = apply_calibration(p["v0_p_btts"], abt, bbt)

    print("\n" + "=" * 78)
    print(f"CALIBRATION TABLES (held-out test, N={len(test)})")
    print("=" * 78)

    print("\n--- U2.5 ---")
    calibration_table(test, "v0_p_u25", "actual_u25", "V0 Original Poisson")
    calibration_table(test, "v1_p_u25", "actual_u25", "V1 Calibrated (Platt)")
    calibration_table(test, "v2_p_u25", "actual_u25", "V2 Dixon-Coles")
    calibration_table(test, "v3_p_u25", "actual_u25", "V3 Market-blend (0.4 form + 0.6 mkt)")

    print("\n--- U3.5 ---")
    calibration_table(test, "v0_p_u35", "actual_u35", "V0 Original Poisson")
    calibration_table(test, "v1_p_u35", "actual_u35", "V1 Calibrated")
    calibration_table(test, "v2_p_u35", "actual_u35", "V2 Dixon-Coles")
    calibration_table(test, "v3_p_u35", "actual_u35", "V3 Market-blend")

    print("\n--- BTTS Yes ---")
    calibration_table(test, "v0_p_btts", "actual_btts", "V0 Original Poisson")
    calibration_table(test, "v1_p_btts", "actual_btts", "V1 Calibrated")
    calibration_table(test, "v2_p_btts", "actual_btts", "V2 Dixon-Coles")
    calibration_table(test, "v3_p_btts", "actual_btts", "V3 Market-blend")

    print("\n" + "=" * 78)
    print("GATE-ROI (CLAUDE thresholds: model>=65%, value>=4%, gap>=4ppt, odds 1.30-2.50)")
    print("=" * 78)
    print("\n  Market: U2.5")
    gate_roi(test, "v0_p_u25", "u25_odds", "actual_u25", "V0 Original Poisson")
    gate_roi(test, "v1_p_u25", "u25_odds", "actual_u25", "V1 Calibrated")
    gate_roi(test, "v2_p_u25", "u25_odds", "actual_u25", "V2 Dixon-Coles")
    gate_roi(test, "v3_p_u25", "u25_odds", "actual_u25", "V3 Market-blend")

    print("\n  Market: U2.5 (STRICTER gate: model>=75%, gap>=7ppt)")
    for p_key, label in [("v0_p_u25", "V0"), ("v1_p_u25", "V1"), ("v2_p_u25", "V2"), ("v3_p_u25", "V3")]:
        gate_roi(test, p_key, "u25_odds", "actual_u25", label, model_min=0.75, gap_min=7.0)

    print("\n" + "=" * 78)
    print("MEAN BIAS (model avg - actual rate) on test set")
    print("=" * 78)
    for variant, kp, ka in [("V0 U2.5", "v0_p_u25", "actual_u25"),
                             ("V1 U2.5", "v1_p_u25", "actual_u25"),
                             ("V2 U2.5", "v2_p_u25", "actual_u25"),
                             ("V3 U2.5", "v3_p_u25", "actual_u25"),
                             ("V0 BTTS", "v0_p_btts", "actual_btts"),
                             ("V2 BTTS", "v2_p_btts", "actual_btts"),
                             ("V3 BTTS", "v3_p_btts", "actual_btts")]:
        ap = sum(p[kp] for p in test) / len(test)
        aa = sum(1 for p in test if p[ka]) / len(test)
        print(f"  {variant}: model_avg={ap*100:.1f}%  actual={aa*100:.1f}%  bias={(ap-aa)*100:+5.1f}pp")


if __name__ == "__main__":
    main()
