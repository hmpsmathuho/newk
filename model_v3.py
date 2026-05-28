#!/usr/bin/env python3
"""Production model v3.1 — adds 1X2 calibration, HT calibration, Dixon-Coles ρ, and grid scoring.

Calibrators trained:
  u25 / u35 / btts_yes  (existing)
  ht_u15 / ht_u25       (new — halftime)
  home_1x2 / draw_1x2 / away_1x2  (new — replaces previous BLOCK)
  dc_1x / dc_x2 / dc_12 (new — derived from calibrated 1X2)
  rho                   (new — Dixon-Coles low-score correlation, fitted via MLE on score grid)

Backtest verdict (EPL 2025/26):
  V0 raw Poisson:        bias U2.5 +9pp, ROI -12% [BROKEN]
  V3.0 mkt-blend+Platt:  bias U2.5 +3.9pp, BTTS Yes -7pp, 1X2 BLOCKED [GOOD]
  V3.1 + 1X2 calib + ρ:  TARGET — unblock 1X2 with calibrated probabilities
"""
import csv
import math
import os
from collections import defaultdict, deque
from datetime import datetime


# ============================================================
# Core math primitives
# ============================================================
def pmf(k, l): return math.exp(-l) * l ** k / math.factorial(k) if l > 0 else (1.0 if k == 0 else 0.0)
def cdf(k, l): return sum(pmf(i, l) for i in range(k + 1))


def total_under(line_int, lam):
    return cdf(line_int, lam)


def btts_yes(lh, la):
    return (1 - math.exp(-lh)) * (1 - math.exp(-la))


# Dixon-Coles low-score correlation factor
def dc_factor(h, a, lh, la, rho):
    if h == 0 and a == 0: return max(0.001, 1 - lh * la * rho)
    if h == 0 and a == 1: return max(0.001, 1 + lh * rho)
    if h == 1 and a == 0: return max(0.001, 1 + la * rho)
    if h == 1 and a == 1: return max(0.001, 1 - rho)
    return 1.0


def grid_with_dc(lh, la, rho=0.0, max_g=10):
    """Return full score-grid probabilities with optional DC correction."""
    grid = []
    total_p = 0.0
    for h in range(max_g + 1):
        row = []
        for a in range(max_g + 1):
            p = pmf(h, lh) * pmf(a, la) * dc_factor(h, a, lh, la, rho)
            row.append(p)
            total_p += p
        grid.append(row)
    # Normalize to sum to 1 (DC factor doesn't preserve total mass exactly)
    if total_p > 0:
        grid = [[p / total_p for p in row] for row in grid]
    return grid


def grid_1x2(lh, la, rho=0.0, max_g=10):
    grid = grid_with_dc(lh, la, rho, max_g)
    ph = pd = pa = 0.0
    for h in range(max_g + 1):
        for a in range(max_g + 1):
            p = grid[h][a]
            if h > a: ph += p
            elif h == a: pd += p
            else: pa += p
    return ph, pd, pa


def grid_btts(lh, la, rho=0.0, max_g=10):
    grid = grid_with_dc(lh, la, rho, max_g)
    p_yes = 0.0
    for h in range(1, max_g + 1):
        for a in range(1, max_g + 1):
            p_yes += grid[h][a]
    return p_yes, 1 - p_yes


def grid_total_under(line_int, lh, la, rho=0.0, max_g=10):
    grid = grid_with_dc(lh, la, rho, max_g)
    p = 0.0
    for h in range(max_g + 1):
        for a in range(max_g + 1):
            if h + a <= line_int:
                p += grid[h][a]
    return p


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


# ============================================================
# Dixon-Coles rho fitting via simple grid search on log-likelihood
# ============================================================
def fit_dc_rho(predictions_with_lambdas, max_g=8):
    """Find rho that maximizes log-likelihood of observed score grid.

    Each item must have: lh, la, fh (actual home goals), fa (actual away goals).
    """
    best_rho = 0.0
    best_ll = -1e18
    for rho in [-0.20, -0.15, -0.10, -0.05, -0.025, 0.0, 0.025, 0.05, 0.10]:
        ll = 0.0
        ok = True
        for p in predictions_with_lambdas:
            lh, la = p["lh"], p["la"]
            fh, fa = p["fh"], p["fa"]
            if fh > max_g or fa > max_g:
                continue
            grid = grid_with_dc(lh, la, rho, max_g)
            prob = grid[fh][fa] if fh < len(grid) and fa < len(grid[fh]) else 0
            if prob <= 0:
                ok = False
                break
            ll += math.log(prob)
        if ok and ll > best_ll:
            best_ll = ll
            best_rho = rho
    return best_rho


# ============================================================
# V3 hybrid lambda
# ============================================================
def hybrid_lambdas(lh_form, la_form, lh_market, la_market, alpha_form=0.4):
    if lh_market is None or la_market is None:
        return lh_form, la_form
    lh = alpha_form * lh_form + (1 - alpha_form) * lh_market
    la = alpha_form * la_form + (1 - alpha_form) * la_market
    return lh, la


def split_market_lambda(market_total, lh_form, la_form):
    form_total = lh_form + la_form
    if form_total <= 0:
        return market_total * 0.55, market_total * 0.45
    ratio_h = lh_form / form_total
    return market_total * ratio_h, market_total * (1 - ratio_h)


# ============================================================
# CSV loader
# ============================================================
def parse_date(s):
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try: return datetime.strptime(s, fmt)
        except ValueError: pass
    raise ValueError(f"bad date {s}")


def _f(s):
    try: return float(s)
    except (TypeError, ValueError): return None


def load_csv(path):
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for x in r:
            try:
                d = parse_date(x["Date"])
                fh = int(x["FTHG"])
                fa = int(x["FTAG"])
                hh = int(x.get("HTHG", 0) or 0)
                ha = int(x.get("HTAG", 0) or 0)
            except (ValueError, KeyError):
                continue
            rows.append({
                "date": d, "home": x["HomeTeam"].strip(), "away": x["AwayTeam"].strip(),
                "fh": fh, "fa": fa, "hh": hh, "ha": ha,
                "ftr": x.get("FTR", ""),
                "u25_odds": _f(x.get("Avg<2.5")),
                "o25_odds": _f(x.get("Avg>2.5")),
                "h_odds": _f(x.get("AvgH")),
                "d_odds": _f(x.get("AvgD")),
                "a_odds": _f(x.get("AvgA")),
            })
    rows.sort(key=lambda r: r["date"])
    return rows


# ============================================================
# Public API: build_model & evaluate_match
# ============================================================
def build_model(history_csv, n_window=6, min_games=4):
    """Train ALL calibrators (U2.5, U3.5, BTTS, 1X2, HT) + DC rho on historical CSV."""
    rows = load_csv(history_csv)
    history = HistoryStore(n_window=n_window)
    train_preds = []
    halftime_ratios = []

    for m in rows:
        lh_f, la_f = history.form_lambdas(m["home"], m["away"], min_games=min_games)
        if lh_f is not None:
            mkt_total = market_lambda_total(m["u25_odds"], m["o25_odds"])
            if mkt_total:
                lh_m, la_m = split_market_lambda(mkt_total, lh_f, la_f)
                lh, la = hybrid_lambdas(lh_f, la_f, lh_m, la_m)
            else:
                lh, la = lh_f, la_f

            ft = m["fh"] + m["fa"]
            ht = m["hh"] + m["ha"]
            train_preds.append({
                "lh": lh, "la": la, "fh": m["fh"], "fa": m["fa"],
                "hh": m["hh"], "ha": m["ha"],
                "raw_p_u25": cdf(2, lh + la),
                "raw_p_u35": cdf(3, lh + la),
                "raw_p_btts": btts_yes(lh, la),
                "raw_p_home": grid_1x2(lh, la, rho=0.0)[0],
                "raw_p_draw": grid_1x2(lh, la, rho=0.0)[1],
                "raw_p_away": grid_1x2(lh, la, rho=0.0)[2],
                "raw_p_ht_u15": cdf(1, (lh + la) * 0.433),  # use empirical ratio
                "raw_p_ht_u25": cdf(2, (lh + la) * 0.433),
                "actual_u25": ft <= 2,
                "actual_u35": ft <= 3,
                "actual_btts": m["fh"] >= 1 and m["fa"] >= 1,
                "actual_home": m["fh"] > m["fa"],
                "actual_draw": m["fh"] == m["fa"],
                "actual_away": m["fh"] < m["fa"],
                "actual_ht_u15": ht <= 1,
                "actual_ht_u25": ht <= 2,
            })
            if ft > 0:
                halftime_ratios.append(ht / max(ft, 1))
        history.update(m["home"], m["away"], m["fh"], m["fa"])

    # Fit DC rho
    rho = fit_dc_rho(train_preds[:300])  # use up to 300 for speed
    # Re-compute calibration features WITH rho (only 1X2 and BTTS care about it)
    for p in train_preds:
        ph, pd, pa = grid_1x2(p["lh"], p["la"], rho)
        p["raw_p_home"] = ph
        p["raw_p_draw"] = pd
        p["raw_p_away"] = pa
        p_btts_y, _ = grid_btts(p["lh"], p["la"], rho)
        p["raw_p_btts"] = p_btts_y

    cal = PlattCalibrator()
    cal.fit("u25", train_preds, "raw_p_u25", "actual_u25")
    cal.fit("u35", train_preds, "raw_p_u35", "actual_u35")
    cal.fit("btts_yes", train_preds, "raw_p_btts", "actual_btts")
    cal.fit("ht_u15", train_preds, "raw_p_ht_u15", "actual_ht_u15")
    cal.fit("ht_u25", train_preds, "raw_p_ht_u25", "actual_ht_u25")
    cal.fit("home_1x2", train_preds, "raw_p_home", "actual_home")
    cal.fit("draw_1x2", train_preds, "raw_p_draw", "actual_draw")
    cal.fit("away_1x2", train_preds, "raw_p_away", "actual_away")

    halftime_ratio = sum(halftime_ratios) / len(halftime_ratios) if halftime_ratios else 0.433

    return {
        "history": history,
        "calibrator": cal,
        "rho": rho,
        "halftime_ratio": halftime_ratio,
        "train_size": len(train_preds),
        "n_window": n_window,
        "min_games": min_games,
    }


def evaluate_match(model, home, away, market):
    """Evaluate one match. Returns calibrated probabilities for ALL markets supported."""
    history = model["history"]
    cal = model["calibrator"]
    rho = model["rho"]
    ht_ratio = model["halftime_ratio"]

    lh_f, la_f = history.form_lambdas(home, away, min_games=model["min_games"])
    if lh_f is None:
        return {"error": "insufficient history",
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

    grid_full = grid_with_dc(lh, la, rho)
    lh_ht, la_ht = lh * ht_ratio, la * ht_ratio
    grid_ht = grid_with_dc(lh_ht, la_ht, rho)

    raw_total = lh + la
    raw = {
        "p_u05": cdf(0, raw_total), "p_o05": 1 - cdf(0, raw_total),
        "p_u15": cdf(1, raw_total), "p_o15": 1 - cdf(1, raw_total),
        "p_u25": cdf(2, raw_total), "p_o25": 1 - cdf(2, raw_total),
        "p_u35": cdf(3, raw_total), "p_o35": 1 - cdf(3, raw_total),
        "p_u45": cdf(4, raw_total), "p_o45": 1 - cdf(4, raw_total),
    }
    p_btts_yes_raw, _ = grid_btts(lh, la, rho)
    raw["p_btts_yes"] = p_btts_yes_raw
    raw["p_btts_no"] = 1 - p_btts_yes_raw
    ph, pd, pa = grid_1x2(lh, la, rho)
    raw["p_home"], raw["p_draw"], raw["p_away"] = ph, pd, pa

    cal_p = {
        "p_u25": cal.apply("u25", raw["p_u25"]),
        "p_u35": cal.apply("u35", raw["p_u35"]),
        "p_btts_yes": cal.apply("btts_yes", raw["p_btts_yes"]),
        "p_home": cal.apply("home_1x2", raw["p_home"]),
        "p_draw": cal.apply("draw_1x2", raw["p_draw"]),
        "p_away": cal.apply("away_1x2", raw["p_away"]),
        "p_ht_u15": cal.apply("ht_u15", cdf(1, lh_ht + la_ht)),
        "p_ht_u25": cal.apply("ht_u25", cdf(2, lh_ht + la_ht)),
    }
    cal_p["p_btts_no"] = 1 - cal_p["p_btts_yes"]
    cal_p["p_dc_1x"] = cal_p["p_home"] + cal_p["p_draw"]
    cal_p["p_dc_12"] = cal_p["p_home"] + cal_p["p_away"]
    cal_p["p_dc_x2"] = cal_p["p_draw"] + cal_p["p_away"]
    cal_p["p_ht_o15"] = 1 - cal_p["p_ht_u15"]
    cal_p["p_ht_o25"] = 1 - cal_p["p_ht_u25"]

    out = {
        "home": home, "away": away,
        "lambda_home_form": lh_f, "lambda_away_form": la_f,
        "lambda_home_blend": lh, "lambda_away_blend": la,
        "market_blended": market_blended,
        "rho": rho,
        "raw": raw,
        "calibrated": cal_p,
        "grid_full": grid_full,
        "grid_ht": grid_ht,
    }
    return out


# ============================================================
# Per-market thresholds
# ============================================================
GATE_THRESHOLDS = {
    # market -> (model_min, gap_min)
    "U3.5":      (0.65, 4.0),
    "U2.5":      (0.75, 7.0),
    "U1.5":      (0.65, 5.0),
    "U4.5":      (0.85, 4.0),
    "O0.5":      (0.85, 4.0),
    "O1.5":      (0.70, 5.0),
    "O2.5":      (0.65, 5.0),
    "O3.5":      (0.55, 6.0),
    "BTTS Yes":  (0.65, 4.0),
    "Home":      (0.55, 5.0),
    "Draw":      (0.30, 5.0),
    "Away":      (0.50, 5.0),
    "DC 1X":     (0.70, 4.0),
    "DC X2":     (0.70, 4.0),
    "DC 12":     (0.70, 4.0),
    "HT U1.5":   (0.65, 5.0),
    "HT U2.5":   (0.80, 4.0),
    "HT O1.5":   (0.55, 5.0),
}

BLOCKED_MARKETS = {
    "BTTS No": "BTTS Yes systematically underestimated -7 to -11pp -> BTTS No overstated; do not bet",
}


def gate_v3(leg, *, value_min=0.04, odds_min=1.30, odds_max=2.50, kelly_min=0.02):
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
    if leg["odds"] <= 1.40 and leg["gap_ppt"] >= 8:
        return False, "Fade-Short-Odds rule"
    return True, "OK"


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base, "E0_2526.csv")
    print(f"Building V3.1 model from {csv_path}...")
    model = build_model(csv_path)
    print(f"  Train size: {model['train_size']} predictions")
    print(f"  Halftime ratio (empirical): {model['halftime_ratio']:.3f}")
    print(f"  Dixon-Coles rho: {model['rho']}")
    print(f"  Calibration coefficients (a + b * P_raw):")
    cal = model["calibrator"]
    for k in ["u25", "u35", "btts_yes", "home_1x2", "draw_1x2", "away_1x2", "ht_u15", "ht_u25"]:
        print(f"    {k:<12} a={cal.a.get(k,0):.3f}  b={cal.b.get(k,0):.3f}")


if __name__ == "__main__":
    main()
