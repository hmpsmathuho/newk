#!/usr/bin/env python3
"""V3.1 extended: ALL 1xbet bet types parser + scorer + 1xbet-style output.

Calibrated markets (validated on EPL 2025/26 out-of-sample 190 matches):
  ✓ U2.5 / U3.5 / BTTS Yes / Home 1X2 / Away 1X2 / HT U1.5 / HT U2.5

Computed but uncalibrated (use cautiously):
  ⚠ Total Over (1.5/2.5/3.5/4.5)
  ⚠ Asian Handicap (full + quarter)
  ⚠ Team Total (Home/Away X.X)
  ⚠ Double Chance (uses calibrated 1X2)
  ⚠ Halftime markets
  ⚠ Win to Nil
  ⚠ Result + BTTS combo
  ⚠ Odd/Even total

Blocked (terbukti rugi atau impossible to model):
  ✗ BTTS No (-7 to -11pp underestimate)
  ✗ Correct Score (very high variance)
  ✗ Goalscorer (player-level)
  ✗ HT/FT combo (use HT U/O instead)
"""
import json
import math
import os
import sys
from collections import defaultdict, deque

# Allow import as both module and script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model_v3 as m3


# ============================================================
# 1xbet group/type registry
# Indonesian labels match what user sees on slip
# ============================================================
GROUP_NAMES_ID = {
    1: "1x2",
    2: "Handicap Asia",
    8: "Double Chance",
    14: "Total Genap/Ganjil",
    15: "Tim 1 Total / BTTS",
    17: "Total",
    18: "Total Babak Pertama",
    19: "Kedua Tim Mencetak Skor",
    62: "Tim Asia Total — Tim 1",
    73: "Win to Nil",
    75: "Hasil + BTTS",
    87: "Total Babak Pertama (alt)",
    88: "Tim Asia Total — Tim 2",
    99: "Total Asia (Quarter)",
    154: "Hasil Babak Pertama",
    8427: "Handicap Asia Quarter — Tim 1",
    8429: "Handicap Asia Quarter — Tim 2",
}


# ============================================================
# Parser: 1xbet GetGameZip -> structured market dict
# ============================================================
def parse_market_from_raw(raw_value):
    """Take 1xbet GetGameZip Value, return structured info + flat market dict."""
    out = {
        "home": raw_value.get("O1", "") or raw_value.get("O1E", ""),
        "away": raw_value.get("O2", "") or raw_value.get("O2E", ""),
        "league": raw_value.get("L", ""),
        "start_unix": raw_value.get("S", 0),
        "markets": {},
    }
    events = list(raw_value.get("E", []) or [])
    for grp in (raw_value.get("GE", []) or []):
        for sub in (grp.get("E", []) or []):
            if isinstance(sub, list):
                events.extend(sub)
            elif isinstance(sub, dict):
                events.append(sub)

    by_gtp = {}
    for e in events:
        if not isinstance(e, dict):
            continue
        g, t, p, c = e.get("G"), e.get("T"), e.get("P"), e.get("C")
        if c is None:
            continue
        key = (g, t, p)
        if key not in by_gtp:
            by_gtp[key] = c

    M = out["markets"]

    # 1X2 (G=1)
    if (1, 1, None) in by_gtp: M["1X2_HOME"] = by_gtp[(1, 1, None)]
    if (1, 2, None) in by_gtp: M["1X2_DRAW"] = by_gtp[(1, 2, None)]
    if (1, 3, None) in by_gtp: M["1X2_AWAY"] = by_gtp[(1, 3, None)]

    # Double Chance (G=8)
    if (8, 4, None) in by_gtp: M["DC_1X"] = by_gtp[(8, 4, None)]
    if (8, 5, None) in by_gtp: M["DC_12"] = by_gtp[(8, 5, None)]
    if (8, 6, None) in by_gtp: M["DC_X2"] = by_gtp[(8, 6, None)]

    # Total Goals (G=17)
    for (g, t, p), c in by_gtp.items():
        if g == 17 and p is not None:
            if t == 9:    M[f"O{p}"] = c
            elif t == 10: M[f"U{p}"] = c

    # BTTS (G=19, T=180/181) — main
    if (19, 180, None) in by_gtp: M["BTTS_YES"] = by_gtp[(19, 180, None)]
    if (19, 181, None) in by_gtp: M["BTTS_NO"] = by_gtp[(19, 181, None)]

    # AH full (G=2, T=7 home / T=8 away)
    for (g, t, p), c in by_gtp.items():
        if g == 2 and p is not None:
            if t == 7: M[f"AH_HOME_{p:+.2f}"] = c
            elif t == 8: M[f"AH_AWAY_{p:+.2f}"] = c

    # AH quarter (G=8427 home, G=8429 away)
    for (g, t, p), c in by_gtp.items():
        if g == 8427 and p is not None:
            M[f"AHQ_HOME_{p:+.2f}"] = c
        elif g == 8429 and p is not None:
            M[f"AHQ_AWAY_{p:+.2f}"] = c

    # Team total (Home: G=15 with T=11/12 or G=62 T=13/14; Away: G=88 T=15/16 or T=749/750)
    for (g, t, p), c in by_gtp.items():
        if p is None: continue
        if g == 15 and t == 11:  M[f"TT_HOME_O{p}"] = c  # Home Total Over
        elif g == 15 and t == 12: M[f"TT_HOME_U{p}"] = c
        elif g == 62 and t == 13: M[f"TT_HOME_O{p}"] = c
        elif g == 62 and t == 14: M[f"TT_HOME_U{p}"] = c
        elif g == 88 and t == 15: M[f"TT_AWAY_O{p}"] = c
        elif g == 88 and t == 16: M[f"TT_AWAY_U{p}"] = c

    # Halftime totals (G=18 T=11/12, OR G=87 T=389/390)
    for (g, t, p), c in by_gtp.items():
        if p is None: continue
        if g == 18 and t == 11: M[f"HT_O{p}"] = c
        elif g == 18 and t == 12: M[f"HT_U{p}"] = c

    # Odd/Even total goals (G=14, T=182=Odd, T=183=Even)
    if (14, 182, None) in by_gtp: M["TOTAL_ODD"] = by_gtp[(14, 182, None)]
    if (14, 183, None) in by_gtp: M["TOTAL_EVEN"] = by_gtp[(14, 183, None)]

    # Win to Nil (G=73 T=654 home Yes, T=655 home No, T=656 away Yes, T=657 away No)
    if (73, 654, None) in by_gtp: M["HOME_WIN_TO_NIL_YES"] = by_gtp[(73, 654, None)]
    if (73, 655, None) in by_gtp: M["HOME_WIN_TO_NIL_NO"] = by_gtp[(73, 655, None)]
    if (73, 656, None) in by_gtp: M["AWAY_WIN_TO_NIL_YES"] = by_gtp[(73, 656, None)]
    if (73, 657, None) in by_gtp: M["AWAY_WIN_TO_NIL_NO"] = by_gtp[(73, 657, None)]

    # Half-Time 1X2 (G=154, T=475/476/477)
    if (154, 475, None) in by_gtp: M["HT_1X2_HOME"] = by_gtp[(154, 475, None)]
    if (154, 476, None) in by_gtp: M["HT_1X2_DRAW"] = by_gtp[(154, 476, None)]
    if (154, 477, None) in by_gtp: M["HT_1X2_AWAY"] = by_gtp[(154, 477, None)]

    # Result + BTTS (G=75)
    # T values: 651=H+Yes, 652=D+Yes, 653=A+Yes, 670/...=No
    if (75, 651, None) in by_gtp: M["HOME_AND_BTTS_YES"] = by_gtp[(75, 651, None)]
    if (75, 652, None) in by_gtp: M["DRAW_AND_BTTS_YES"] = by_gtp[(75, 652, None)]
    if (75, 653, None) in by_gtp: M["AWAY_AND_BTTS_YES"] = by_gtp[(75, 653, None)]

    return out


# ============================================================
# Compute probabilities for ALL markets
# ============================================================
def compute_market_probabilities(model, home, away, market_data):
    history = model["history"]
    cal = model["calibrator"]
    rho = model["rho"]
    ht_ratio = model["halftime_ratio"]

    lh_f, la_f = history.form_lambdas(home, away, min_games=model["min_games"])

    # Market blend with 0.4/0.6
    u25_odds = market_data.get("U2.5")
    o25_odds = market_data.get("O2.5")
    mkt_total = m3.market_lambda_total(u25_odds, o25_odds)

    if lh_f is None:
        # Fallback: no team history. Use market-implied lambda + 1X2 prior for split
        if mkt_total is None:
            return {"error": "no team history AND no market O/U 2.5",
                    "home_history": len(history.home_hist[home]),
                    "away_history": len(history.away_hist[away])}
        # Estimate home/away ratio from 1X2 odds if available
        h_odds = market_data.get("1X2_HOME")
        a_odds = market_data.get("1X2_AWAY")
        if h_odds and a_odds:
            ip_h, ip_a = 1 / h_odds, 1 / a_odds
            # Margin-aware ratio (skip draw): home favorit means lh > la
            if ip_h + ip_a > 0:
                ratio_h = ip_h / (ip_h + ip_a)
            else:
                ratio_h = 0.55
        else:
            ratio_h = 0.55
        # Constrain ratio to plausible range
        ratio_h = max(0.30, min(0.75, ratio_h))
        lh = mkt_total * ratio_h
        la = mkt_total * (1 - ratio_h)
        market_blended = "fallback_market_only"
        lh_f, la_f = lh, la  # reported back for transparency
    elif mkt_total:
        lh_m, la_m = m3.split_market_lambda(mkt_total, lh_f, la_f)
        lh, la = m3.hybrid_lambdas(lh_f, la_f, lh_m, la_m, alpha_form=0.4)
        market_blended = True
    else:
        lh, la = lh_f, la_f
        market_blended = False

    out = {
        "lambda_home_form": lh_f, "lambda_away_form": la_f,
        "lambda_home": lh, "lambda_away": la, "total_lambda": lh + la,
        "rho": rho, "market_blended": market_blended,
        "probs": {},
    }
    P = out["probs"]

    # Full grid for derived markets
    grid = m3.grid_with_dc(lh, la, rho)
    grid_ht = m3.grid_with_dc(lh * ht_ratio, la * ht_ratio, rho)

    # Total Under/Over (calibrated U2.5, U3.5; raw for others)
    for line_int, line_str in [(0, "0.5"), (1, "1.5"), (2, "2.5"), (3, "3.5"), (4, "4.5"), (5, "5.5"), (6, "6.5")]:
        p_under_raw = sum(grid[h][a] for h in range(11) for a in range(11) if h + a <= line_int)
        if line_str == "2.5":
            p_under = cal.apply("u25", p_under_raw)
        elif line_str == "3.5":
            p_under = cal.apply("u35", p_under_raw)
        else:
            p_under = p_under_raw
        P[f"U{line_str}"] = p_under
        P[f"O{line_str}"] = 1 - p_under

    # BTTS (calibrated)
    p_btts_yes_raw, _ = m3.grid_btts(lh, la, rho)
    P["BTTS_YES"] = cal.apply("btts_yes", p_btts_yes_raw)
    P["BTTS_NO"] = 1 - P["BTTS_YES"]

    # 1X2 (CALIBRATED in V3.1)
    ph_raw, pd_raw, pa_raw = m3.grid_1x2(lh, la, rho)
    ph_cal = cal.apply("home_1x2", ph_raw)
    pd_cal = cal.apply("draw_1x2", pd_raw)
    pa_cal = cal.apply("away_1x2", pa_raw)
    # Renormalize so sum = 1
    s = ph_cal + pd_cal + pa_cal
    if s > 0:
        ph_cal /= s; pd_cal /= s; pa_cal /= s
    P["1X2_HOME"] = ph_cal
    P["1X2_DRAW"] = pd_cal
    P["1X2_AWAY"] = pa_cal

    # Double Chance (sum of calibrated 1X2)
    P["DC_1X"] = ph_cal + pd_cal
    P["DC_12"] = ph_cal + pa_cal
    P["DC_X2"] = pd_cal + pa_cal

    # Asian Handicap full integer line (push possible)
    for k_int in range(-4, 5):
        k = float(k_int)
        line_str = f"{k:+.2f}"
        for prefix in ["AH_HOME", "AH_AWAY"]:
            p_cover = 0.0
            p_push = 0.0
            for h in range(11):
                for a in range(11):
                    p = grid[h][a]
                    margin = h - a if prefix == "AH_HOME" else a - h
                    # AH +k for selection: covers if margin > -k (or push if margin == -k)
                    if margin > -k: p_cover += p
                    elif margin == -k: p_push += p
            P[f"{prefix}_{line_str}"] = p_cover + 0.5 * p_push  # treat push as half

    # Asian Handicap quarter (no push, half-stake split)
    for k in [-2.25, -1.75, -1.25, -0.75, -0.25, 0.25, 0.75, 1.25, 1.75, 2.25]:
        line_str = f"{k:+.2f}"
        for prefix in ["AHQ_HOME", "AHQ_AWAY"]:
            p_cover = 0.0
            for h in range(11):
                for a in range(11):
                    p = grid[h][a]
                    margin = h - a if prefix == "AHQ_HOME" else a - h
                    if margin > -k:
                        p_cover += p
            P[f"{prefix}_{line_str}"] = p_cover

    # Team totals (Home/Away independent Poisson)
    for line_int, line_str in [(0, "0.5"), (1, "1.5"), (2, "2.5"), (3, "3.5")]:
        P[f"TT_HOME_U{line_str}"] = m3.cdf(line_int, lh)
        P[f"TT_HOME_O{line_str}"] = 1 - m3.cdf(line_int, lh)
        P[f"TT_AWAY_U{line_str}"] = m3.cdf(line_int, la)
        P[f"TT_AWAY_O{line_str}"] = 1 - m3.cdf(line_int, la)

    # Halftime totals (CALIBRATED for U1.5, U2.5)
    total_ht = (lh + la) * ht_ratio
    for line_int, line_str in [(0, "0.5"), (1, "1.5"), (2, "2.5")]:
        p_ht_under_raw = m3.cdf(line_int, total_ht)
        if line_str == "1.5":
            p_ht_under = cal.apply("ht_u15", p_ht_under_raw)
        elif line_str == "2.5":
            p_ht_under = cal.apply("ht_u25", p_ht_under_raw)
        else:
            p_ht_under = p_ht_under_raw
        P[f"HT_U{line_str}"] = p_ht_under
        P[f"HT_O{line_str}"] = 1 - p_ht_under

    # Halftime 1X2 (using ht-scaled lambda, NOT calibrated separately for 1X2-HT)
    ph_ht, pd_ht, pa_ht = m3.grid_1x2(lh * ht_ratio, la * ht_ratio, rho)
    P["HT_1X2_HOME"] = ph_ht
    P["HT_1X2_DRAW"] = pd_ht
    P["HT_1X2_AWAY"] = pa_ht

    # Odd/Even total
    p_odd = 0.0
    for h in range(11):
        for a in range(11):
            if (h + a) % 2 == 1:
                p_odd += grid[h][a]
    P["TOTAL_ODD"] = p_odd
    P["TOTAL_EVEN"] = 1 - p_odd

    # Win to Nil (Home wins AND away score = 0)
    p_h_wtn = sum(grid[h][0] for h in range(1, 11))
    p_a_wtn = sum(grid[0][a] for a in range(1, 11))
    P["HOME_WIN_TO_NIL_YES"] = p_h_wtn
    P["HOME_WIN_TO_NIL_NO"] = 1 - p_h_wtn
    P["AWAY_WIN_TO_NIL_YES"] = p_a_wtn
    P["AWAY_WIN_TO_NIL_NO"] = 1 - p_a_wtn

    # Result + BTTS combo (Home AND BTTS Yes; Draw AND BTTS Yes; Away AND BTTS Yes)
    p_h_btts_yes = sum(grid[h][a] for h in range(1, 11) for a in range(1, 11) if h > a)
    p_d_btts_yes = sum(grid[h][a] for h in range(1, 11) for a in range(1, 11) if h == a)
    p_a_btts_yes = sum(grid[h][a] for h in range(1, 11) for a in range(1, 11) if h < a)
    P["HOME_AND_BTTS_YES"] = p_h_btts_yes
    P["DRAW_AND_BTTS_YES"] = p_d_btts_yes
    P["AWAY_AND_BTTS_YES"] = p_a_btts_yes

    return out


# ============================================================
# Per-market gate rules
# ============================================================
GATE_RULES = {
    "U3.5":          {"model_min": 0.65, "gap_min": 4.0, "calibrated": True,  "allowed": True},
    "U2.5":          {"model_min": 0.75, "gap_min": 7.0, "calibrated": True,  "allowed": True},
    "U1.5":          {"model_min": 0.65, "gap_min": 5.0, "calibrated": False, "allowed": True},
    "U4.5":          {"model_min": 0.85, "gap_min": 4.0, "calibrated": False, "allowed": True},
    "O0.5":          {"model_min": 0.85, "gap_min": 4.0, "calibrated": False, "allowed": True},
    "O1.5":          {"model_min": 0.70, "gap_min": 5.0, "calibrated": False, "allowed": True},
    "O2.5":          {"model_min": 0.65, "gap_min": 5.0, "calibrated": False, "allowed": True},
    "O3.5":          {"model_min": 0.55, "gap_min": 6.0, "calibrated": False, "allowed": True},
    "BTTS_YES":      {"model_min": 0.65, "gap_min": 4.0, "calibrated": True,  "allowed": True},
    "BTTS_NO":       {"allowed": False, "reason": "BTTS Yes underestimated -7 to -11pp; BTTS No overstated"},
    "1X2_HOME":      {"model_min": 0.65, "gap_min": 5.0, "calibrated": True,  "allowed": True,
                      "note": "Calibrated V3.1; reliable at 65%+"},
    "1X2_DRAW":      {"model_min": 0.30, "gap_min": 5.0, "calibrated": True,  "allowed": True,
                      "note": "Draw rare so threshold lower"},
    "1X2_AWAY":      {"model_min": 0.65, "gap_min": 5.0, "calibrated": True,  "allowed": True,
                      "note": "Calibrated V3.1; reliable at 65%+"},
    "DC_1X":         {"model_min": 0.70, "gap_min": 5.0, "calibrated": False, "allowed": True,
                      "note": "Derived from calibrated 1X2 sum"},
    "DC_12":         {"model_min": 0.70, "gap_min": 5.0, "calibrated": False, "allowed": True,
                      "note": "Derived from calibrated 1X2 sum"},
    "DC_X2":         {"model_min": 0.70, "gap_min": 5.0, "calibrated": False, "allowed": True,
                      "note": "Derived from calibrated 1X2 sum"},
    "AH_*":          {"model_min": 0.65, "gap_min": 5.0, "calibrated": False, "allowed": True,
                      "note": "AH from grid + calibrated 1X2 boundary",
                      "epl_only": True},
    "AHQ_*":         {"model_min": 0.65, "gap_min": 5.0, "calibrated": False, "allowed": True,
                      "note": "AH quarter, half-stake split",
                      "epl_only": True},
    "TT_*":          {"model_min": 0.70, "gap_min": 5.0, "calibrated": False, "allowed": True,
                      "note": "Team-specific Poisson",
                      "epl_only": True},
    "HT_U1.5":       {"model_min": 0.65, "gap_min": 5.0, "calibrated": True,  "allowed": True},
    "HT_U2.5":       {"model_min": 0.80, "gap_min": 4.0, "calibrated": True,  "allowed": True},
    "HT_U0.5":       {"model_min": 0.65, "gap_min": 5.0, "calibrated": False, "allowed": True},
    "HT_O0.5":       {"model_min": 0.70, "gap_min": 5.0, "calibrated": False, "allowed": True},
    "HT_O1.5":       {"model_min": 0.55, "gap_min": 5.0, "calibrated": False, "allowed": True},
    "HT_O2.5":       {"model_min": 0.30, "gap_min": 5.0, "calibrated": False, "allowed": True},
    "HT_1X2_*":      {"model_min": 0.55, "gap_min": 5.0, "calibrated": False, "allowed": True,
                      "note": "Halftime 1X2 — uncalibrated"},
    "TOTAL_ODD":     {"model_min": 0.55, "gap_min": 4.0, "calibrated": False, "allowed": True,
                      "note": "Coin-flip event, edge thin"},
    "TOTAL_EVEN":    {"model_min": 0.55, "gap_min": 4.0, "calibrated": False, "allowed": True},
    "HOME_WIN_TO_NIL_YES": {"model_min": 0.55, "gap_min": 5.0, "calibrated": False, "allowed": True},
    "AWAY_WIN_TO_NIL_YES": {"model_min": 0.50, "gap_min": 5.0, "calibrated": False, "allowed": True},
    "HOME_WIN_TO_NIL_NO":  {"allowed": False, "reason": "BTTS-bias related; underestimates clean sheets"},
    "AWAY_WIN_TO_NIL_NO":  {"allowed": False, "reason": "BTTS-bias related"},
    "HOME_AND_BTTS_YES":   {"model_min": 0.40, "gap_min": 5.0, "calibrated": False, "allowed": True,
                            "note": "Result + BTTS combo"},
    "DRAW_AND_BTTS_YES":   {"model_min": 0.20, "gap_min": 5.0, "calibrated": False, "allowed": True},
    "AWAY_AND_BTTS_YES":   {"model_min": 0.40, "gap_min": 5.0, "calibrated": False, "allowed": True},
}


def find_rule(market_label):
    if market_label in GATE_RULES:
        return GATE_RULES[market_label]
    for prefix in ["AH_HOME", "AH_AWAY"]:
        if market_label.startswith(prefix):
            return GATE_RULES["AH_*"]
    for prefix in ["AHQ_HOME", "AHQ_AWAY"]:
        if market_label.startswith(prefix):
            return GATE_RULES["AHQ_*"]
    if market_label.startswith("TT_"):
        return GATE_RULES["TT_*"]
    if market_label.startswith("HT_1X2_"):
        return GATE_RULES["HT_1X2_*"]
    return None


def evaluate_all_markets(model, home, away, raw_value, *,
                         odds_min=1.30, odds_max=2.50, kelly_min=0.02, value_min=0.04):
    parsed = parse_market_from_raw(raw_value)
    market_data = parsed["markets"]
    probs_result = compute_market_probabilities(model, home, away, market_data)

    if "error" in probs_result:
        return {"error": probs_result["error"], "match_info": parsed}

    # Detect non-EPL: uncalibrated markets in non-EPL get tighter gates
    is_epl = "England. Premier League" in parsed["league"] or "Premier League" in parsed["league"] and "England" in parsed["league"]
    is_fallback = probs_result["market_blended"] == "fallback_market_only"

    P = probs_result["probs"]
    legs = []
    for label, odds in market_data.items():
        if label not in P:
            continue
        rule = find_rule(label)
        model_p = P[label]
        implied = 1 / odds
        value = model_p * odds - 1
        gap = (model_p - implied) * 100
        kelly = (model_p * odds - 1) / (odds - 1) if odds > 1 else 0
        leg = {
            "market": label, "odds": odds, "model_p": model_p,
            "implied_pct": implied * 100, "value_pct": value * 100,
            "gap_ppt": gap, "kelly_pct": kelly * 100,
            "rule": rule,
        }
        if rule is None:
            leg["pass"] = False
            leg["reason"] = f"unknown market"
        elif not rule.get("allowed", False):
            leg["pass"] = False
            leg["reason"] = "BLOCKED: " + rule.get("reason", "not allowed")
        elif rule.get("epl_only", False) and (is_fallback or not is_epl):
            leg["pass"] = False
            leg["reason"] = f"BLOCKED: {label} requires EPL history (uncalibrated for non-EPL)"
        elif not (odds_min <= odds <= odds_max):
            leg["pass"] = False
            leg["reason"] = f"odds {odds:.2f} out of [{odds_min}, {odds_max}]"
        elif model_p < rule.get("model_min", 0.65):
            leg["pass"] = False
            leg["reason"] = f"model {model_p*100:.1f}% < {rule['model_min']*100:.0f}%"
        elif gap < rule.get("gap_min", 4.0):
            leg["pass"] = False
            leg["reason"] = f"gap {gap:.1f}ppt < {rule['gap_min']}ppt"
        elif value < value_min:
            leg["pass"] = False
            leg["reason"] = f"value {value*100:.1f}% < {value_min*100:.0f}%"
        elif kelly < kelly_min:
            leg["pass"] = False
            leg["reason"] = f"kelly {kelly*100:.1f}% < {kelly_min*100:.0f}%"
        elif odds <= 1.40 and gap >= 8:
            leg["pass"] = False
            leg["reason"] = "Fade-Short-Odds rule"
        else:
            leg["pass"] = True
            leg["reason"] = "OK"
            if not rule.get("calibrated", False):
                leg["reason"] += " (uncalibrated — caution)"
        legs.append(leg)

    legs.sort(key=lambda x: (-(1 if x["pass"] else 0), -x["gap_ppt"]))
    return {
        "match_info": parsed,
        "is_epl": is_epl,
        "is_fallback": is_fallback,
        "lambda": {
            "home_form": probs_result["lambda_home_form"],
            "away_form": probs_result["lambda_away_form"],
            "home_blend": probs_result["lambda_home"],
            "away_blend": probs_result["lambda_away"],
            "total": probs_result["total_lambda"],
            "rho": probs_result["rho"],
        },
        "legs": legs,
        "passing_legs": [l for l in legs if l["pass"]],
    }


# ============================================================
# Output formatter (1xbet-style Indonesian)
# ============================================================
def translate_market(label, info):
    home = info["home"]
    away = info["away"]
    match_str = f"{home} - {away}"
    if label.startswith("U") and "." in label:
        return f"Total Under ({label[1:]}): {match_str}"
    if label.startswith("O") and "." in label:
        return f"Total Over ({label[1:]}): {match_str}"
    if label == "BTTS_YES":
        return f"Kedua Tim Mencetak Skor — Ya: {match_str}"
    if label == "BTTS_NO":
        return f"Kedua Tim Mencetak Skor — Tidak: {match_str}"
    if label == "1X2_HOME":  return f"1x2: M1 ({home})"
    if label == "1X2_DRAW":  return f"1x2: X (Draw)"
    if label == "1X2_AWAY":  return f"1x2: M2 ({away})"
    if label == "DC_1X":     return f"Double Chance: 1X ({home}/Draw)"
    if label == "DC_12":     return f"Double Chance: 12 (no Draw)"
    if label == "DC_X2":     return f"Double Chance: X2 (Draw/{away})"
    if label.startswith("AH_HOME_"):
        return f"Handicap Asia: Handicap 1 ({label[len('AH_HOME_'):]}) — {home}"
    if label.startswith("AH_AWAY_"):
        return f"Handicap Asia: Handicap 2 ({label[len('AH_AWAY_'):]}) — {away}"
    if label.startswith("AHQ_HOME_"):
        return f"Handicap Asia (Q): Handicap 1 ({label[len('AHQ_HOME_'):]}) — {home}"
    if label.startswith("AHQ_AWAY_"):
        return f"Handicap Asia (Q): Handicap 2 ({label[len('AHQ_AWAY_'):]}) — {away}"
    if label.startswith("TT_HOME_O"): return f"Tim 1 Total Over ({label[len('TT_HOME_O'):]}): {home}"
    if label.startswith("TT_HOME_U"): return f"Tim 1 Total Under ({label[len('TT_HOME_U'):]}): {home}"
    if label.startswith("TT_AWAY_O"): return f"Tim 2 Total Over ({label[len('TT_AWAY_O'):]}): {away}"
    if label.startswith("TT_AWAY_U"): return f"Tim 2 Total Under ({label[len('TT_AWAY_U'):]}): {away}"
    if label.startswith("HT_U"):  return f"Total Babak Pertama Under ({label[len('HT_U'):]}): {match_str}"
    if label.startswith("HT_O"):  return f"Total Babak Pertama Over ({label[len('HT_O'):]}): {match_str}"
    if label == "HT_1X2_HOME": return f"1x2 Babak Pertama: M1 ({home})"
    if label == "HT_1X2_DRAW": return f"1x2 Babak Pertama: X (Draw)"
    if label == "HT_1X2_AWAY": return f"1x2 Babak Pertama: M2 ({away})"
    if label == "TOTAL_ODD":   return f"Total Genap/Ganjil — Ganjil: {match_str}"
    if label == "TOTAL_EVEN":  return f"Total Genap/Ganjil — Genap: {match_str}"
    if label == "HOME_WIN_TO_NIL_YES": return f"{home} Menang Tanpa Kebobolan — Ya"
    if label == "AWAY_WIN_TO_NIL_YES": return f"{away} Menang Tanpa Kebobolan — Ya"
    if label == "HOME_AND_BTTS_YES":   return f"Hasil + BTTS: {home} Menang & BTTS Ya"
    if label == "DRAW_AND_BTTS_YES":   return f"Hasil + BTTS: Seri & BTTS Ya"
    if label == "AWAY_AND_BTTS_YES":   return f"Hasil + BTTS: {away} Menang & BTTS Ya"
    return label


def format_output_1xbet_style(eval_result, max_legs=15, show_blocked=True):
    info = eval_result["match_info"]
    lam = eval_result["lambda"]

    lines = []
    lines.append("=" * 78)
    lines.append(f"  V3.1 ANALISIS — {info['home']} vs {info['away']}")
    lines.append(f"  Liga: {info['league']}")
    lines.append("=" * 78)
    lines.append(f"  λ_home={lam['home_blend']:.2f}  λ_away={lam['away_blend']:.2f}  total={lam['total']:.2f}  ρ_DC={lam['rho']}")
    lines.append("")

    passing = eval_result["passing_legs"]
    if not passing:
        lines.append("  ⚠ TIDAK ADA leg yang lolos gate. SIT OUT match ini.")
    else:
        lines.append(f"  ✅ {len(passing)} REKOMENDASI BET (urut by gap):")
        lines.append("")
        for i, leg in enumerate(passing[:max_legs], 1):
            cal = "✓ calibrated" if leg["rule"] and leg["rule"].get("calibrated") else "⚠ uncalibrated"
            lines.append(f"  {i}. {translate_market(leg['market'], info)}")
            lines.append(f"     Odds: {leg['odds']:.3f}  |  Model: {leg['model_p']*100:.1f}%  |  Gap: +{leg['gap_ppt']:.1f}pp  |  Kelly: {leg['kelly_pct']:.1f}%  [{cal}]")
            lines.append("")

    if show_blocked:
        blocked = [l for l in eval_result["legs"] if not l["pass"] and "BLOCKED" in l["reason"]]
        blocked.sort(key=lambda x: -x["gap_ppt"])
        if blocked:
            lines.append(f"  ❌ Top {min(5, len(blocked))} BLOCKED markets (jangan dipasang):")
            for leg in blocked[:5]:
                lines.append(f"     • {translate_market(leg['market'], info)}")
                lines.append(f"       odds={leg['odds']:.2f}  model={leg['model_p']*100:.1f}%  gap=+{leg['gap_ppt']:.1f}pp")
                lines.append(f"       └ {leg['reason']}")
    return "\n".join(lines)


# ============================================================
# Main
# ============================================================
def main():
    base = os.path.dirname(os.path.abspath(__file__))
    print("Building V3.1 model from EPL 2025/26...")
    model = m3.build_model(os.path.join(base, "E0_2526.csv"))
    print(f"  Train: {model['train_size']} preds, ρ={model['rho']}, HT_ratio={model['halftime_ratio']:.3f}")
    print()

    # Test 1: synthetic Liverpool-Brentford from MD38
    print("\n" + "#" * 78)
    print("# TEST 1: Liverpool vs Brentford (synthetic from MD38)")
    print("#" * 78)
    synth = {
        "O1": "Liverpool", "O2": "Brentford", "L": "England. Premier League",
        "S": 1779645000,
        "GE": [
            {"G": 1, "GS": 1, "E": [
                [{"G": 1, "T": 1, "C": 1.929}],
                [{"G": 1, "T": 2, "C": 4.16}],
                [{"G": 1, "T": 3, "C": 3.895}],
            ]},
            {"G": 8, "GS": 2, "E": [
                [{"G": 8, "T": 4, "C": 1.30}],
                [{"G": 8, "T": 5, "C": 1.273}],
                [{"G": 8, "T": 6, "C": 1.972}],
            ]},
            {"G": 17, "GS": 4, "E": [
                [{"G": 17, "T": 9, "P": 0.5, "C": 1.013}, {"G": 17, "T": 9, "P": 1.5, "C": 1.103},
                 {"G": 17, "T": 9, "P": 2.5, "C": 1.46}, {"G": 17, "T": 9, "P": 3.5, "C": 2.281},
                 {"G": 17, "T": 9, "P": 4.5, "C": 3.62}],
                [{"G": 17, "T": 10, "P": 0.5, "C": 12.0}, {"G": 17, "T": 10, "P": 1.5, "C": 5.2},
                 {"G": 17, "T": 10, "P": 2.5, "C": 2.56}, {"G": 17, "T": 10, "P": 3.5, "C": 1.734},
                 {"G": 17, "T": 10, "P": 4.5, "C": 1.25}],
            ]},
            {"G": 19, "GS": 21, "E": [
                [{"G": 19, "T": 180, "C": 1.444}],
                [{"G": 19, "T": 181, "C": 2.611}],
            ]},
            {"G": 2, "GS": 3, "E": [
                [{"G": 2, "T": 7, "P": -1.0, "C": 2.5}, {"G": 2, "T": 7, "P": 0.0, "C": 1.494},
                 {"G": 2, "T": 7, "P": 1.0, "C": 1.066}],
                [{"G": 2, "T": 8, "P": 1.0, "C": 1.533}, {"G": 2, "T": 8, "P": 0.0, "C": 2.892},
                 {"G": 2, "T": 8, "P": -1.0, "C": 6.45}],
            ]},
        ],
    }
    result = evaluate_all_markets(model, "Liverpool", "Brentford", synth)
    if "error" in result:
        print(f"ERROR: {result['error']}")
    else:
        print(format_output_1xbet_style(result))


if __name__ == "__main__":
    main()
