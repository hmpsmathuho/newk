#!/usr/bin/env python3
"""Backtest V3 (production model) with proper time-split + per-market gate.

Uses model_v3.build_model on first half, evaluates on held-out second half.
Tracks gate-ROI per market and per probability bucket.
"""
import csv
import os
from datetime import datetime
from collections import defaultdict, deque
import math

import model_v3 as m3


def parse_date(s):
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try: return datetime.strptime(s, fmt)
        except ValueError: pass
    raise ValueError(f"bad date {s}")


def _f(s):
    try: return float(s)
    except (TypeError, ValueError): return None


def load(path):
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
                "btts_yes_odds": None,  # not in CSV by default; gate-test will skip BTTS
                "h_odds": _f(x.get("AvgH")), "d_odds": _f(x.get("AvgD")), "a_odds": _f(x.get("AvgA")),
            })
    rows.sort(key=lambda r: r["date"])
    return rows


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    rows = load(os.path.join(base, "E0_2526.csv"))
    print(f"Loaded {len(rows)} matches")

    # Split: train on first 50% chronologically, test on last 50%
    split_idx = len(rows) // 2
    train_rows = rows[:split_idx]
    test_rows = rows[split_idx:]

    # Build model on train period only
    print(f"Building model on first {len(train_rows)} matches...")

    # Replicate build but only over train data
    history = m3.HistoryStore(n_window=6)
    train_preds = []
    for m in train_rows:
        lh_f, la_f = history.form_lambdas(m["home"], m["away"], min_games=4)
        if lh_f is not None:
            mkt_total = m3.market_lambda_total(m["u25_odds"], m["o25_odds"])
            if mkt_total:
                lh_m, la_m = m3.split_market_lambda(mkt_total, lh_f, la_f)
                lh, la = m3.hybrid_lambdas(lh_f, la_f, lh_m, la_m)
            else:
                lh, la = lh_f, la_f
            actual_total = m["fh"] + m["fa"]
            train_preds.append({
                "raw_p_u25": m3.cdf(2, lh + la),
                "raw_p_u35": m3.cdf(3, lh + la),
                "raw_p_btts": m3.btts_yes(lh, la),
                "actual_u25": actual_total <= 2,
                "actual_u35": actual_total <= 3,
                "actual_btts": m["fh"] >= 1 and m["fa"] >= 1,
            })
        history.update(m["home"], m["away"], m["fh"], m["fa"])

    cal = m3.PlattCalibrator()
    cal.fit("u25", train_preds, "raw_p_u25", "actual_u25")
    cal.fit("u35", train_preds, "raw_p_u35", "actual_u35")
    cal.fit("btts_yes", train_preds, "raw_p_btts", "actual_btts")
    print(f"  Train preds: {len(train_preds)}")
    print(f"  Cal U2.5: a={cal.a['u25']:.3f} b={cal.b['u25']:.3f}")
    print(f"  Cal U3.5: a={cal.a['u35']:.3f} b={cal.b['u35']:.3f}")
    print(f"  Cal BTTS: a={cal.a['btts_yes']:.3f} b={cal.b['btts_yes']:.3f}")

    # Test on out-of-sample test rows
    print(f"\nTest on next {len(test_rows)} matches (out-of-sample)...")
    test_results = []
    for m in test_rows:
        lh_f, la_f = history.form_lambdas(m["home"], m["away"], min_games=4)
        if lh_f is None:
            history.update(m["home"], m["away"], m["fh"], m["fa"])
            continue
        mkt_total = m3.market_lambda_total(m["u25_odds"], m["o25_odds"])
        if mkt_total:
            lh_m, la_m = m3.split_market_lambda(mkt_total, lh_f, la_f)
            lh, la = m3.hybrid_lambdas(lh_f, la_f, lh_m, la_m)
        else:
            lh, la = lh_f, la_f
        actual_total = m["fh"] + m["fa"]
        ph, pd, pa = m3.grid_1x2(lh, la)
        result = {
            "home": m["home"], "away": m["away"], "fh": m["fh"], "fa": m["fa"],
            "actual_u25": actual_total <= 2,
            "actual_u35": actual_total <= 3,
            "actual_btts": m["fh"] >= 1 and m["fa"] >= 1,
            "actual_home": m["fh"] > m["fa"],
            "actual_draw": m["fh"] == m["fa"],
            "actual_away": m["fa"] > m["fh"],
            "p_u25": cal.apply("u25", m3.cdf(2, lh + la)),
            "p_u35": cal.apply("u35", m3.cdf(3, lh + la)),
            "p_btts_yes": cal.apply("btts_yes", m3.btts_yes(lh, la)),
            "p_home": ph, "p_draw": pd, "p_away": pa,
            "u25_odds": m["u25_odds"], "o25_odds": m["o25_odds"],
            "h_odds": m["h_odds"], "d_odds": m["d_odds"], "a_odds": m["a_odds"],
        }
        test_results.append(result)
        history.update(m["home"], m["away"], m["fh"], m["fa"])

    print(f"  Test predictions: {len(test_results)}")

    print("\n" + "=" * 78)
    print("V3 OUT-OF-SAMPLE GATE-ROI (per-market)")
    print("=" * 78)

    def run_gate(market_label, p_key, odds_key, actual_key):
        picks = []
        skipped = 0
        for r in test_results:
            o = r[odds_key]
            if not o: continue
            mp = r[p_key]
            leg = {
                "market": market_label,
                "model_p": mp, "odds": o,
                "value_pct": (mp * o - 1) * 100,
                "gap_ppt": (mp - 1 / o) * 100,
                "kelly_pct": (mp * o - 1) / (o - 1) * 100 if o > 1 else 0,
            }
            ok, reason = m3.gate_v3(leg)
            if not ok: continue
            picks.append({"mp": mp, "odds": o, "won": r[actual_key]})

        if not picks:
            print(f"  {market_label:<10}: 0 picks pass gate")
            return
        n = len(picks)
        won = sum(1 for x in picks if x["won"])
        avg_p = sum(x["mp"] for x in picks) / n
        actual_rate = won / n
        roi = sum((x["odds"] - 1) if x["won"] else -1 for x in picks) / n
        pl = sum((x["odds"] - 1) if x["won"] else -1 for x in picks)
        print(f"  {market_label:<10}: N={n:3d}  pred={avg_p*100:5.1f}%  actual={actual_rate*100:5.1f}%  err={(actual_rate-avg_p)*100:+5.1f}pp  ROI={roi*100:+6.2f}%  P/L={pl:+6.2f}u")

    run_gate("U2.5", "p_u25", "u25_odds", "actual_u25")
    # NOTE: football-data CSV lacks O3.5/U3.5 odds. We approximate via market-implied
    # by reverse-engineering U3.5 odds from O2.5/U2.5 lambda. Skipped properly here.
    print(f"  U3.5      : skipped (CSV lacks O3.5/U3.5 odds)")
    run_gate("Home", "p_home", "h_odds", "actual_home")
    run_gate("Draw", "p_draw", "d_odds", "actual_draw")
    run_gate("Away", "p_away", "a_odds", "actual_away")

    # Compare with V0 (raw, no calibration, old gate model_min=0.65 gap_min=4)
    print("\n" + "=" * 78)
    print("BASELINE V0 (raw Poisson, original CLAUDE gate) — same out-of-sample period")
    print("=" * 78)

    v0_picks = []
    for r in test_results:
        # Reconstruct raw p_u25 from form λ alone (no market blend, no calibration)
        # We'll cheat slightly: use the raw_p_u25 we'd compute from lh, la — but we already overwrote
        # For fairness, recompute using form_lambdas only
        pass

    # Redo with form-only lambdas
    history2 = m3.HistoryStore(n_window=6)
    for m in train_rows + test_rows[:0]:
        history2.update(m["home"], m["away"], m["fh"], m["fa"])
    # Replay through both train+test, only predict in test phase using form-only
    history2 = m3.HistoryStore(n_window=6)
    in_test = False
    test_idx_start = len(train_rows)
    for i, m in enumerate(rows):
        if i == test_idx_start:
            in_test = True
        if in_test:
            lh_f, la_f = history2.form_lambdas(m["home"], m["away"], min_games=4)
            if lh_f is None:
                history2.update(m["home"], m["away"], m["fh"], m["fa"]); continue
            actual_total = m["fh"] + m["fa"]
            p_u25 = m3.cdf(2, lh_f + la_f)
            o = m["u25_odds"]
            if o and 1.30 <= o <= 2.50:
                value = p_u25 * o - 1
                gap = (p_u25 - 1 / o) * 100
                kelly = (p_u25 * o - 1) / (o - 1)
                if p_u25 >= 0.65 and value >= 0.04 and gap >= 4 and kelly >= 0.02:
                    v0_picks.append({"mp": p_u25, "odds": o, "won": actual_total <= 2})
        history2.update(m["home"], m["away"], m["fh"], m["fa"])

    n = len(v0_picks)
    if n:
        won = sum(1 for x in v0_picks if x["won"])
        avg_p = sum(x["mp"] for x in v0_picks) / n
        actual_rate = won / n
        roi = sum((x["odds"] - 1) if x["won"] else -1 for x in v0_picks) / n
        pl = sum((x["odds"] - 1) if x["won"] else -1 for x in v0_picks)
        print(f"  V0 U2.5  : N={n:3d}  pred={avg_p*100:5.1f}%  actual={actual_rate*100:5.1f}%  err={(actual_rate-avg_p)*100:+5.1f}pp  ROI={roi*100:+6.2f}%  P/L={pl:+6.2f}u")
    else:
        print(f"  V0 U2.5  : 0 picks")


if __name__ == "__main__":
    main()
