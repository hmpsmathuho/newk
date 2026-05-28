#!/usr/bin/env python3
"""Production model v3 — market-blend Poisson with Platt calibration.

Backtest verdict (EPL 2025/26, 300 predictions):
  V0 raw Poisson: U2.5 bias +9.2pp, gate-ROI -12% over season ❌
  V1 Platt calibrated: bias +1.6pp ✓ but produces 0 picks (filter effect)
  V2 Dixon-Coles: identical to V0 for U2.5 ❌
  V3 Market-blend: bias +3.9pp ✓, gate-ROI +25% (small sample)
  V3 + V1 calibration: BEST balanced ✓

Usage:
  from model_v3 import build_model, evaluate_match
  m = build_model(history_csv="E0_2526.csv")
  result = evaluate_match(m, "Liverpool", "Brentford",
                          market={"u25": 2.56, "o25": 1.46, "btts_yes": 1.444})
"""
import csv
import math
import os
from collections import defaultdict, deque
from datetime import datetime


# ============================================================
# Core math primitives
# ============================================================
def pmf(k, l): return math.exp(-l) * l ** k / math.factorial(k)
def cdf(k, l): return sum(pmf(i, l) for i in range(k + 1))


def total_under(line_int, lam):
    """P(total goals <= line_int) for line=line_int+0.5."""
    return cdf(line_int, lam)


def btts_yes(lh, la):
    return (1 - math.exp(-lh)) * (1 - math.exp(-la))


def grid_1x2(lh, la, max_g=10):
    ph = pd = pa = 0.0
    for h in range(max_g + 1):
        for a in range(max_g + 1):
            p = pmf(h, lh) * pmf(a, la)
            if h > a: ph += p
            elif h == a: pd += p
            else: pa += p
    return ph, pd, pa


def market_lambda_total(u25_odds, o25_odds):
    """Reverse-engineer total lambda from market O/U 2.5 prices via devig."""
    if not u25_odds or not o25_odds: return None
    ip_u, ip_o = 1 / u25_odds, 1 / o25_odds
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


# ============================================================
# History tracker (for form-based λ_form)
# ============================================================
class HistoryStore:
    def __init__(self, n_window=6):
        self.n = n_window
        self.home_hist = defaultdict(lambda: deque(maxlen=n_window))
        self.away_hist = defaultdict(lambda: deque(maxlen=n_window))
        self.all_h_gf, self.all_h_ga = [], []

    def update(self, home, away, fh, fa):
        self.home_hist[home].append((fh, fa))
        self.away_hist[away].append((fa, fh))
        self.all_h_gf.append(fh)
        self.all_h_ga.append(fa)

    def form_lambdas(self, home, away, min_games=4):
        hh, aa = self.home_hist[home], self.away_hist[away]
        if len(hh) < min_games or len(aa) < min_games or not self.all_h_gf:
            return None, None
        avg_h_gf = sum(gf for gf, _ in hh) / len(hh)
        avg_h_ga = sum(ga for _, ga in hh) / len(hh)
        avg_a_gf = sum(gf for gf, _ in aa) / len(aa)
        avg_a_ga = sum(ga for _, ga in aa) / len(aa)
        lg_h_gf = sum(self.all_h_gf) / len(self.all_h_gf)
        lg_h_ga = sum(self.all_h_ga) / len(self.all_h_ga)
        home_atk = avg_h_gf / max(lg_h_gf, 0.1)
        home_def = avg_h_ga / max(lg_h_ga, 0.1)
        away_atk = avg_a_gf / max(lg_h_ga, 0.1)
        away_def = avg_a_ga / max(lg_h_gf, 0.1)
        lh = lg_h_gf * home_atk * away_def
        la = lg_h_ga * away_atk * home_def
        return lh, la


# ============================================================
# Calibration (Platt: P_cal = a + b * P_raw)
# ============================================================
class PlattCalibrator:
    def __init__(self):
        self.a = {}
        self.b = {}

    def fit(self, market_label, predictions, p_key, actual_key):
        xs = [p[p_key] for p in predictions]
        ys = [1 if p[actual_key] else 0 for p in predictions]
        n = len(xs)
        if n < 30:
            self.a[market_label] = 0
            self.b[market_label] = 1
            return
        mx = sum(xs) / n
        my = sum(ys) / n
        num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
        den = sum((xs[i] - mx) ** 2 for i in range(n))
        if den < 1e-9:
            self.a[market_label] = my
            self.b[market_label] = 0
        else:
            b = num / den
            a = my - b * mx
            self.a[market_label] = a
            self.b[market_label] = b

    def apply(self, market_label, p_raw):
        a = self.a.get(market_label, 0)
        b = self.b.get(market_label, 1)
        out = a + b * p_raw
        return max(0.001, min(0.999, out))

    def to_dict(self):
        return {"a": dict(self.a), "b": dict(self.b)}

    @classmethod
    def from_dict(cls, d):
        c = cls()
        c.a = dict(d.get("a", {}))
        c.b = dict(d.get("b", {}))
        return c


# ============================================================
# V3 hybrid lambda
# ============================================================
def hybrid_lambdas(lh_form, la_form, lh_market, la_market, alpha_form=0.4):
    """V3: blend form-derived λ with market-implied λ."""
    if lh_market is None or la_market is None:
        return lh_form, la_form
    lh = alpha_form * lh_form + (1 - alpha_form) * lh_market
    la = alpha_form * la_form + (1 - alpha_form) * la_market
    return lh, la


def split_market_lambda(market_total, lh_form, la_form):
    """Split market total into home/away using form ratio."""
    form_total = lh_form + la_form
    if form_total <= 0:
        return market_total * 0.55, market_total * 0.45  # default home advantage
    ratio_h = lh_form / form_total
    return market_total * ratio_h, market_total * (1 - ratio_h)


# ============================================================
# Public API: build and evaluate
# ============================================================
def parse_date(s):
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try: return datetime.strptime(s, fmt)
        except ValueError: pass
    raise ValueError(f"bad date {s}")


def _f(s):
    try: return float(s)
    except (TypeError, ValueError): return None


def build_model(history_csv, n_window=6, min_games=4):
    """Train calibration on historical CSV (football-data.co.uk format)."""
    rows = []
    with open(history_csv, encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for x in r:
            try:
                d = parse_date(x["Date"])
                fh = int(x["FTHG"])
                fa = int(x["FTAG"])
            except (ValueError, KeyError):
                continue
            rows.append({"date": d, "home": x["HomeTeam"].strip(), "away": x["AwayTeam"].strip(),
                         "fh": fh, "fa": fa,
                         "u25_odds": _f(x.get("Avg<2.5")), "o25_odds": _f(x.get("Avg>2.5"))})
    rows.sort(key=lambda r: r["date"])

    history = HistoryStore(n_window=n_window)
    train_preds = []
    for m in rows:
        lh_f, la_f = history.form_lambdas(m["home"], m["away"], min_games=min_games)
        if lh_f is not None:
            mkt_total = market_lambda_total(m["u25_odds"], m["o25_odds"])
            if mkt_total:
                lh_m, la_m = split_market_lambda(mkt_total, lh_f, la_f)
            else:
                lh_m = la_m = None
            lh, la = hybrid_lambdas(lh_f, la_f, lh_m, la_m, alpha_form=0.4)
            actual_total = m["fh"] + m["fa"]
            train_preds.append({
                "raw_p_u25": cdf(2, lh + la),
                "raw_p_u35": cdf(3, lh + la),
                "raw_p_btts": btts_yes(lh, la),
                "actual_u25": actual_total <= 2,
                "actual_u35": actual_total <= 3,
                "actual_btts": m["fh"] >= 1 and m["fa"] >= 1,
            })
        history.update(m["home"], m["away"], m["fh"], m["fa"])

    cal = PlattCalibrator()
    cal.fit("u25", train_preds, "raw_p_u25", "actual_u25")
    cal.fit("u35", train_preds, "raw_p_u35", "actual_u35")
    cal.fit("btts_yes", train_preds, "raw_p_btts", "actual_btts")

    return {
        "history": history,
        "calibrator": cal,
        "train_size": len(train_preds),
        "n_window": n_window,
        "min_games": min_games,
    }


def evaluate_match(model, home, away, market):
    """Evaluate one match with V3 model.

    market: dict with keys {u25, o25, btts_yes, btts_no, u35, o35, ...} (decimal odds)
    Returns dict with calibrated probabilities and per-market value/gap.
    """
    history = model["history"]
    cal = model["calibrator"]

    lh_f, la_f = history.form_lambdas(home, away, min_games=model["min_games"])
    if lh_f is None:
        return {"error": "insufficient history for form lambdas",
                "home_history_len": len(history.home_hist[home]),
                "away_history_len": len(history.away_hist[away])}

    mkt_total = market_lambda_total(market.get("u25"), market.get("o25"))
    if mkt_total:
        lh_m, la_m = split_market_lambda(mkt_total, lh_f, la_f)
        lh, la = hybrid_lambdas(lh_f, la_f, lh_m, la_m, alpha_form=0.4)
        market_blended = True
    else:
        lh, la = lh_f, la_f
        market_blended = False

    raw = {
        "p_u15": cdf(1, lh + la),
        "p_u25": cdf(2, lh + la),
        "p_u35": cdf(3, lh + la),
        "p_u45": cdf(4, lh + la),
        "p_btts_yes": btts_yes(lh, la),
    }
    raw["p_btts_no"] = 1 - raw["p_btts_yes"]
    ph, pd, pa = grid_1x2(lh, la)
    raw["p_home"] = ph
    raw["p_draw"] = pd
    raw["p_away"] = pa

    cal_p = {
        "p_u25": cal.apply("u25", raw["p_u25"]),
        "p_u35": cal.apply("u35", raw["p_u35"]),
        "p_btts_yes": cal.apply("btts_yes", raw["p_btts_yes"]),
    }
    cal_p["p_btts_no"] = 1 - cal_p["p_btts_yes"]

    out = {
        "home": home, "away": away,
        "lambda_home_form": lh_f, "lambda_away_form": la_f,
        "lambda_home_blend": lh, "lambda_away_blend": la,
        "market_blended": market_blended,
        "raw": raw,
        "calibrated": cal_p,
    }

    legs = []
    market_pairs = [
        ("U2.5", "u25", cal_p["p_u25"], "calibrated"),
        ("U3.5", "u35", cal_p["p_u35"], "calibrated"),
        ("BTTS Yes", "btts_yes", cal_p["p_btts_yes"], "calibrated"),
        ("BTTS No", "btts_no", cal_p["p_btts_no"], "calibrated"),
        ("Home", "home_1x2", ph, "raw_1x2"),
        ("Draw", "draw_1x2", pd, "raw_1x2"),
        ("Away", "away_1x2", pa, "raw_1x2"),
    ]
    for label, key, p_used, source in market_pairs:
        odds = market.get(key)
        if not odds: continue
        implied = 1 / odds
        value = p_used * odds - 1
        gap = (p_used - implied) * 100
        kelly = (p_used * odds - 1) / (odds - 1) if odds > 1 else 0
        legs.append({
            "market": label, "odds": odds, "model_p": p_used, "source": source,
            "implied_pct": implied * 100, "value_pct": value * 100,
            "gap_ppt": gap, "kelly_pct": kelly * 100,
        })
    out["legs"] = legs
    return out


# ============================================================
# Updated gate per backtest findings
# ============================================================
# Per-market thresholds (derived from V3 calibration table on EPL 2025/26 test set)
GATE_THRESHOLDS = {
    # market -> (model_min, gap_min)
    "U3.5":      (0.65, 4.0),   # V3 U3.5 calibrated near-perfect at 65-80% (diff -0.1 to +3.6 pp)
    "U2.5":      (0.75, 7.0),   # V3 U2.5 still has +3.9pp residual bias; high threshold needed
    "BTTS Yes":  (0.65, 4.0),   # V3 BTTS calibrated reasonably at 60-65%
}

BLOCKED_MARKETS = {
    "BTTS No": "BTTS Yes systematically underestimated -7 to -11pp -> BTTS No overstated; do not bet",
    "Home":    "1X2 raw Poisson uncalibrated; out-of-sample: pred 73%, actual 40% (-33pp). Don't bet.",
    "Draw":    "1X2 raw Poisson uncalibrated; do not bet.",
    "Away":    "1X2 raw Poisson uncalibrated; out-of-sample: pred 68%, actual 41% (-27pp). Don't bet.",
}


def gate_v3(leg, *, value_min=0.04, odds_min=1.30, odds_max=2.50, kelly_min=0.02):
    """V3 production gate, per-market thresholds derived from backtest.

    Justification (backtest 300 EPL preds, EPL 2025/26):
      V0 raw 65% gate: avg cal error -33pp, ROI -12% over season ❌
      V3 (market blend + Platt) at per-market thresholds: cal error <5pp ✓

    Per-market gate decisions:
      U2.5: 75% min, 7ppt gap (V3 still residual +3.9pp bias)
      U3.5: 65% min, 4ppt gap (V3 calibrated near-perfect)
      BTTS No: BLOCKED (persistent -11pp BTTS Yes underestimate -> overstates BTTS No)
    """
    market = leg["market"]
    if market in BLOCKED_MARKETS:
        return False, f"BLOCKED: {BLOCKED_MARKETS[market]}"

    th = GATE_THRESHOLDS.get(market, (0.75, 7.0))
    model_min, gap_min = th

    if leg["model_p"] < model_min:
        return False, f"model {leg['model_p']*100:.1f}% < {model_min*100:.0f}% ({market} gate)"
    if leg["value_pct"] / 100 < value_min:
        return False, f"value {leg['value_pct']:.1f}% < {value_min*100:.0f}%"
    if leg["gap_ppt"] < gap_min:
        return False, f"gap {leg['gap_ppt']:.1f}ppt < {gap_min}ppt ({market} gate)"
    if not (odds_min <= leg["odds"] <= odds_max):
        return False, f"odds {leg['odds']:.2f} out of [{odds_min},{odds_max}]"
    if leg["kelly_pct"] / 100 < kelly_min:
        return False, f"kelly {leg['kelly_pct']:.1f}% < {kelly_min*100:.0f}%"
    # Fade-Short-Odds (CLAUDE rule, kept)
    if leg["odds"] <= 1.40 and leg["gap_ppt"] >= 8:
        return False, "Fade-Short-Odds rule"
    return True, "OK"


def main():
    """Demo: build model from EPL CSV and evaluate Liverpool-Brentford."""
    base = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base, "E0_2526.csv")
    print(f"Building model from {csv_path}...")
    model = build_model(csv_path)
    print(f"  Train size: {model['train_size']} predictions")
    print(f"  Calibration U2.5: P_cal = {model['calibrator'].a['u25']:.3f} + {model['calibrator'].b['u25']:.3f} * P_raw")
    print(f"  Calibration U3.5: P_cal = {model['calibrator'].a['u35']:.3f} + {model['calibrator'].b['u35']:.3f} * P_raw")
    print(f"  Calibration BTTS: P_cal = {model['calibrator'].a['btts_yes']:.3f} + {model['calibrator'].b['btts_yes']:.3f} * P_raw")

    # Sanity check: evaluate Liverpool-Brentford from MD38 file (24/05/2026)
    print("\n--- Demo: Liverpool vs Brentford (final-day MD38) ---")
    market = {
        "u25": 2.56, "o25": 1.46, "u35": 1.734, "o35": 2.281,
        "btts_yes": 1.444, "btts_no": 2.611,
        "home_1x2": 1.929, "draw_1x2": 4.16, "away_1x2": 3.895,
    }
    r = evaluate_match(model, "Liverpool", "Brentford", market)
    if "error" in r:
        print(f"  ERR: {r['error']}")
        return
    print(f"  λ_form: H={r['lambda_home_form']:.2f} A={r['lambda_away_form']:.2f}")
    print(f"  λ_blend: H={r['lambda_home_blend']:.2f} A={r['lambda_away_blend']:.2f}  (market blended: {r['market_blended']})")
    print(f"  P_calibrated U2.5={r['calibrated']['p_u25']*100:.1f}%  U3.5={r['calibrated']['p_u35']*100:.1f}%  BTTS Yes={r['calibrated']['p_btts_yes']*100:.1f}%")
    print(f"\n  {'Market':<10}{'Odds':>7}{'Model%':>9}{'Value%':>8}{'Gap':>7}{'Kelly%':>8}  Pass?  Reason")
    for leg in r["legs"]:
        ok, reason = gate_v3(leg)
        flag = "✓" if ok else " "
        print(f"  {leg['market']:<10}{leg['odds']:>7.3f}{leg['model_p']*100:>8.1f}%{leg['value_pct']:>+7.1f}%{leg['gap_ppt']:>+6.1f}{leg['kelly_pct']:>+7.1f}%  {flag}      {reason}")


if __name__ == "__main__":
    main()
