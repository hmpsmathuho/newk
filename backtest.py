#!/usr/bin/env python3
"""Backtest Poisson model vs actual EPL 2025/26 results.

Workflow per match:
  1. Take all matches before this fixture's date (only past info available)
  2. Compute rolling form: last-N home GF/GA for home team (home games only),
                          last-N away GF/GA for away team (away games only)
  3. Build lambda using CLAUDE-style formula: λ_h = (avg_GF_home + avg_GA_away_seen_at_home_opp)/2
     (simplified: just use season-to-date avg for home/away splits)
  4. Predict P(U2.5), P(U3.5), P(BTTS No), P(home win)
  5. Compare to actual outcome
  6. Bucket predictions by probability and compute hit rate per bucket
"""
import csv
import math
from collections import defaultdict, deque
from datetime import datetime


def pmf(k, l): return math.exp(-l) * l ** k / math.factorial(k)
def cdf(k, l): return sum(pmf(i, l) for i in range(k + 1))


def parse_date(s):
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    raise ValueError(f"bad date {s}")


def load_matches(path):
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for x in r:
            try:
                d = parse_date(x["Date"])
                home = x["HomeTeam"].strip()
                away = x["AwayTeam"].strip()
                fh = int(x["FTHG"])
                fa = int(x["FTAG"])
            except (ValueError, KeyError):
                continue
            rows.append({"date": d, "home": home, "away": away, "fh": fh, "fa": fa,
                         "u25_odds": _f(x.get("Avg<2.5")), "o25_odds": _f(x.get("Avg>2.5"))})
    rows.sort(key=lambda r: r["date"])
    return rows


def _f(s):
    try: return float(s)
    except (TypeError, ValueError): return None


def run_backtest(rows, n_window=6, min_games=4, lambda_blend=1.0):
    """Run model on each fixture using only PAST data.

    n_window: rolling window length (matches looking back per side)
    min_games: minimum games of history required to make prediction (skip early MD)
    lambda_blend: 1.0 = pure form-derived λ; 0.0 = pure league avg
    """
    # State: per-team list of recent home games (GF, GA), away games (GF, GA)
    home_hist = defaultdict(lambda: deque(maxlen=n_window))  # tuples (gf, ga) for home games
    away_hist = defaultdict(lambda: deque(maxlen=n_window))
    # League-wide running averages (for fallback / blend baseline)
    all_home_gf = []
    all_home_ga = []

    predictions = []
    for m in rows:
        h, a = m["home"], m["away"]
        hh = home_hist[h]
        aa = away_hist[a]

        if len(hh) >= min_games and len(aa) >= min_games and all_home_gf:
            avg_home_gf = sum(gf for gf, _ in hh) / len(hh)
            avg_home_ga = sum(ga for _, ga in hh) / len(hh)
            avg_away_gf = sum(gf for gf, _ in aa) / len(aa)
            avg_away_ga = sum(ga for _, ga in aa) / len(aa)

            # League baseline (avg goals scored at home / away across all matches so far)
            league_home_gf = sum(all_home_gf) / len(all_home_gf)
            league_home_ga = sum(all_home_ga) / len(all_home_ga)  # = avg goals conceded by home (= avg goals away team scored)

            # Attack/defense strength relative to league
            home_atk = avg_home_gf / max(league_home_gf, 0.1)
            home_def = avg_home_ga / max(league_home_ga, 0.1)
            away_atk = avg_away_gf / max(league_home_ga, 0.1)  # away team's goals when away, vs avg goals away teams score
            away_def = avg_away_ga / max(league_home_gf, 0.1)

            # Expected lambdas
            lh_form = league_home_gf * home_atk * away_def
            la_form = league_home_ga * away_atk * home_def

            # Optional blend with raw league avg
            lh = lambda_blend * lh_form + (1 - lambda_blend) * league_home_gf
            la = lambda_blend * la_form + (1 - lambda_blend) * league_home_ga

            total = lh + la
            actual_total = m["fh"] + m["fa"]
            actual_btts = m["fh"] >= 1 and m["fa"] >= 1

            pred = {
                "date": m["date"], "home": h, "away": a,
                "fh": m["fh"], "fa": m["fa"], "actual_total": actual_total,
                "lh": lh, "la": la, "total_lambda": total,
                "p_u15": cdf(1, total), "p_u25": cdf(2, total),
                "p_u35": cdf(3, total), "p_u45": cdf(4, total),
                "p_btts_yes": (1 - math.exp(-lh)) * (1 - math.exp(-la)),
                "actual_u15": actual_total <= 1,
                "actual_u25": actual_total <= 2,
                "actual_u35": actual_total <= 3,
                "actual_u45": actual_total <= 4,
                "actual_btts": actual_btts,
                "u25_odds": m["u25_odds"], "o25_odds": m["o25_odds"],
            }
            predictions.append(pred)

        # Update history AFTER predicting
        hh.append((m["fh"], m["fa"]))
        aa.append((m["fa"], m["fh"]))
        all_home_gf.append(m["fh"])
        all_home_ga.append(m["fa"])

    return predictions


def calibration(preds, key_p, key_actual, bins=None):
    """For each prob bucket, compute mean predicted vs actual hit rate."""
    if bins is None:
        bins = [(0.0, 0.5), (0.5, 0.55), (0.55, 0.60), (0.60, 0.65), (0.65, 0.70),
                (0.70, 0.75), (0.75, 0.80), (0.80, 0.90), (0.90, 1.01)]
    out = []
    for lo, hi in bins:
        bucket = [p for p in preds if lo <= p[key_p] < hi]
        if not bucket:
            out.append((lo, hi, 0, None, None, None))
            continue
        n = len(bucket)
        mean_pred = sum(p[key_p] for p in bucket) / n
        actual_rate = sum(1 for p in bucket if p[key_actual]) / n
        diff = actual_rate - mean_pred
        out.append((lo, hi, n, mean_pred, actual_rate, diff))
    return out


def print_calibration(name, table):
    print(f"\n--- Calibration: {name} ---")
    print(f"{'Bucket':<14}{'N':>5}{'Mean pred':>12}{'Actual hit':>14}{'Diff':>10}")
    for lo, hi, n, mp, ar, d in table:
        if n == 0:
            print(f"{lo:.2f}-{hi:.2f}  {n:>5}    --          --         --")
        else:
            print(f"{lo:.2f}-{hi:.2f}  {n:>5}    {mp*100:>6.1f}%      {ar*100:>6.1f}%   {d*100:>+6.1f} pp")


def overall_stats(preds):
    print(f"\n=== Overall stats (N={len(preds)}) ===")
    avg_pred_total = sum(p["total_lambda"] for p in preds) / len(preds)
    avg_actual_total = sum(p["actual_total"] for p in preds) / len(preds)
    print(f"  Avg predicted total goals: {avg_pred_total:.3f}")
    print(f"  Avg actual total goals:    {avg_actual_total:.3f}")
    print(f"  Bias (actual - predicted): {avg_actual_total - avg_pred_total:+.3f}")

    for label, kp, ka in [("U2.5", "p_u25", "actual_u25"),
                          ("U3.5", "p_u35", "actual_u35"),
                          ("U1.5", "p_u15", "actual_u15"),
                          ("BTTS Yes", "p_btts_yes", "actual_btts")]:
        avg_p = sum(p[kp] for p in preds) / len(preds)
        actual = sum(1 for p in preds if p[ka]) / len(preds)
        print(f"  {label:<10} model={avg_p*100:.1f}%  actual={actual*100:.1f}%  diff={actual-avg_p:+.3%}")


def gate_simulation(preds):
    """Simulate the parlay gate: pick legs where model U2.5 >= 65% AND value >= 4% AND gap >= 4ppt."""
    print("\n=== Gate simulation: U2.5 picks per CLAUDE.md gate ===")
    picks = []
    for p in preds:
        if not p["u25_odds"]:
            continue
        model_p = p["p_u25"]
        odds = p["u25_odds"]
        implied = 1 / odds
        value = model_p * odds - 1
        gap = (model_p - implied) * 100
        if model_p >= 0.65 and value >= 0.04 and gap >= 4 and 1.30 <= odds <= 2.50:
            picks.append({**p, "model_p": model_p, "odds": odds, "value": value, "gap": gap})

    if not picks:
        print("  No legs pass gate.")
        return

    n = len(picks)
    won = sum(1 for x in picks if x["actual_u25"])
    avg_pred = sum(x["model_p"] for x in picks) / n
    actual_rate = won / n
    avg_odds = sum(x["odds"] for x in picks) / n
    roi = sum((x["odds"] - 1) if x["actual_u25"] else -1 for x in picks) / n

    print(f"  Picks (N={n}):")
    print(f"    Avg model probability: {avg_pred*100:.1f}%")
    print(f"    Actual U2.5 hit rate:  {actual_rate*100:.1f}%")
    print(f"    Calibration error:     {(actual_rate - avg_pred)*100:+.1f} pp")
    print(f"    Avg odds taken:        {avg_odds:.3f}")
    print(f"    Flat-stake ROI:        {roi*100:+.2f}%")
    print(f"    Profit/loss (flat 1u): {sum((x['odds'] - 1) if x['actual_u25'] else -1 for x in picks):+.2f} units over {n} bets")

    print("\n  By model-prob bucket:")
    for lo, hi in [(0.65, 0.70), (0.70, 0.75), (0.75, 0.80), (0.80, 1.01)]:
        b = [x for x in picks if lo <= x["model_p"] < hi]
        if not b: continue
        bw = sum(1 for x in b if x["actual_u25"])
        bn = len(b)
        bmp = sum(x["model_p"] for x in b) / bn
        bar = bw / bn
        broi = sum((x["odds"] - 1) if x["actual_u25"] else -1 for x in b) / bn
        print(f"    {lo:.2f}-{hi:.2f}: N={bn:3d}  pred={bmp*100:.1f}%  actual={bar*100:.1f}%  diff={(bar-bmp)*100:+.1f}pp  ROI={broi*100:+.1f}%")


def main():
    rows = load_matches("/projects/sandbox/newk/E0_2526.csv")
    print(f"Loaded {len(rows)} matches from {rows[0]['date'].date()} to {rows[-1]['date'].date()}")
    preds = run_backtest(rows, n_window=6, min_games=4)
    print(f"Predictions made (after warmup): {len(preds)}")

    overall_stats(preds)
    print_calibration("Under 2.5", calibration(preds, "p_u25", "actual_u25"))
    print_calibration("Under 3.5", calibration(preds, "p_u35", "actual_u35"))
    print_calibration("BTTS Yes", calibration(preds, "p_btts_yes", "actual_btts"))
    gate_simulation(preds)


if __name__ == "__main__":
    main()
