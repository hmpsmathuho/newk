"""Poisson + Dixon-Coles probability model.

The model derives lambdas (expected goals per side) from the bookmaker's
Over/Under 2.5 odds (devigged), then computes consistent probabilities for
EVERY market in the input. By using the market's own implied total goals,
we avoid the calibration disasters of an uninformed-prior Poisson model
and remain consistent with the market's overall expectation.

The "edge" we extract comes from the fact that within a match, the
bookmaker's prices for different markets (1X2, AH lines, BTTS, half-time
totals, etc.) are NOT always perfectly self-consistent. The Poisson model
exposes those internal inconsistencies and treats them as the value signal.
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple


# ----------------------------------------------------------------------
# Core math
# ----------------------------------------------------------------------
def pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * lam ** k / math.factorial(k)


def cdf(k: int, lam: float) -> float:
    return sum(pmf(i, lam) for i in range(k + 1))


def dc_factor(h: int, a: int, lh: float, la: float, rho: float) -> float:
    """Dixon-Coles low-score correction factor."""
    if h == 0 and a == 0: return max(0.001, 1 - lh * la * rho)
    if h == 0 and a == 1: return max(0.001, 1 + lh * rho)
    if h == 1 and a == 0: return max(0.001, 1 + la * rho)
    if h == 1 and a == 1: return max(0.001, 1 - rho)
    return 1.0


def grid(lh: float, la: float, rho: float = -0.10, max_g: int = 10) -> List[List[float]]:
    """Full P(home=h, away=a) grid up to max_g goals each side, normalized."""
    g = [[pmf(h, lh) * pmf(a, la) * dc_factor(h, a, lh, la, rho)
          for a in range(max_g + 1)] for h in range(max_g + 1)]
    total = sum(sum(row) for row in g)
    if total > 0:
        g = [[c / total for c in row] for row in g]
    return g


# ----------------------------------------------------------------------
# Devig
# ----------------------------------------------------------------------
def devig(odds_dict: Dict[str, float]) -> Dict[str, float]:
    """Remove bookmaker overround. Returns {selection: probability}."""
    if not odds_dict:
        return {}
    inverses = {k: 1.0 / v for k, v in odds_dict.items() if v and v > 1.0}
    if not inverses:
        return {}
    margin = sum(inverses.values())
    if margin <= 0:
        return {}
    return {k: v / margin for k, v in inverses.items()}


def market_lambda_total(over25_odds: float | None, under25_odds: float | None) -> float | None:
    """Reverse-engineer total lambda from market O/U 2.5."""
    if not over25_odds or not under25_odds:
        return None
    p_under_devig = (1.0 / under25_odds) / (1.0 / under25_odds + 1.0 / over25_odds)
    lo, hi = 0.3, 7.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if cdf(2, mid) > p_under_devig:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def split_lambda_by_1x2(total: float, x12_odds: Dict[str, float] | None) -> Tuple[float, float]:
    """Split total lambda into home/away using 1X2 devigged probabilities.

    Method: solve for ratio rho_h such that the resulting Poisson grid yields
    P(home win) ≈ devigged_p_home. We use a simple approximation:
        ratio_h = sqrt(P_home / (P_home + P_away)) when P_draw is moderate.
    Then constrain ratio_h to [0.30, 0.75] to avoid pathological cases.
    """
    if not x12_odds or "Home" not in x12_odds or "Away" not in x12_odds:
        # Default: home advantage
        return total * 0.55, total * 0.45
    devigged = devig(x12_odds)
    p_h = devigged.get("Home", 0.45)
    p_a = devigged.get("Away", 0.30)
    # Better split via grid search: find ratio_h that produces matching P(home win) under Poisson
    best_ratio, best_err = 0.55, 1e9
    for r in range(20, 81):  # ratio_h from 0.20 to 0.80
        rho_h = r / 100.0
        lh = total * rho_h
        la = total * (1 - rho_h)
        ph_pa_pd = _grid_1x2(lh, la)
        err = (ph_pa_pd[0] - p_h) ** 2 + (ph_pa_pd[2] - p_a) ** 2
        if err < best_err:
            best_err = err
            best_ratio = rho_h
    return total * best_ratio, total * (1 - best_ratio)


def _grid_1x2(lh: float, la: float, rho: float = -0.10, max_g: int = 8) -> Tuple[float, float, float]:
    """Helper: P(home win), P(draw), P(away win) without normalization concerns."""
    ph = pd = pa = 0.0
    for h in range(max_g + 1):
        for a in range(max_g + 1):
            p = pmf(h, lh) * pmf(a, la) * dc_factor(h, a, lh, la, rho)
            if h > a: ph += p
            elif h == a: pd += p
            else: pa += p
    s = ph + pd + pa
    if s > 0: return ph / s, pd / s, pa / s
    return 0.45, 0.27, 0.28


# ----------------------------------------------------------------------
# Per-market probability computation
# ----------------------------------------------------------------------
def compute_probabilities(markets: Dict[str, dict],
                          rho: float = -0.10,
                          ht_ratio: float = 0.45,
                          max_g: int = 10) -> dict:
    """Given markets dict (from odds_extractor), compute per-selection P_real.

    Returns:
      {
        "lambda_home": ..., "lambda_away": ...,
        "probs": {
            "1X2: Home": 0.42, "1X2: Draw": 0.27, "1X2: Away": 0.31,
            "Totals: Over 2.5": 0.55, ...
        }
      }
    """
    out = {"lambda_home": None, "lambda_away": None, "probs": {}, "total_lambda": None}

    # Step 1: derive lambdas from O/U 2.5
    totals = markets.get("Totals", {}) or {}
    o25 = totals.get("Over 2.5")
    u25 = totals.get("Under 2.5")
    total_lam = market_lambda_total(o25, u25)
    if total_lam is None:
        # Fallback: try other lines (Over/Under 1.5 if 2.5 missing)
        for line_str, line_int in [(1.5, 1), (3.5, 3)]:
            o = totals.get(f"Over {line_str}")
            u = totals.get(f"Under {line_str}")
            if o and u:
                p_under_devig = (1.0 / u) / (1.0 / u + 1.0 / o)
                lo, hi = 0.3, 7.0
                for _ in range(60):
                    mid = (lo + hi) / 2
                    if cdf(line_int, mid) > p_under_devig:
                        lo = mid
                    else:
                        hi = mid
                total_lam = (lo + hi) / 2
                break
    if total_lam is None:
        # Last resort: assume league average ~2.6
        total_lam = 2.6

    out["total_lambda"] = total_lam

    # Step 2: split into home/away using 1X2 odds
    x12 = markets.get("1X2")
    lh, la = split_lambda_by_1x2(total_lam, x12)
    out["lambda_home"] = lh
    out["lambda_away"] = la

    # Step 3: build full grid
    g = grid(lh, la, rho, max_g)
    g_ht = grid(lh * ht_ratio, la * ht_ratio, rho, max_g)

    P = out["probs"]

    # 1X2 (full match)
    ph = sum(g[h][a] for h in range(max_g + 1) for a in range(max_g + 1) if h > a)
    pd = sum(g[h][a] for h in range(max_g + 1) for a in range(max_g + 1) if h == a)
    pa = sum(g[h][a] for h in range(max_g + 1) for a in range(max_g + 1) if h < a)
    P["1X2: Home Win"] = ph
    P["1X2: Draw"] = pd
    P["1X2: Away Win"] = pa

    # Double Chance
    P["DC: Home/Draw"] = ph + pd  # 1X
    P["DC: Home/Away"] = ph + pa  # 12
    P["DC: Draw/Away"] = pd + pa  # X2

    # BTTS
    p_btts_yes = sum(g[h][a] for h in range(1, max_g + 1) for a in range(1, max_g + 1))
    P["BTTS: Yes"] = p_btts_yes
    P["BTTS: No"] = 1 - p_btts_yes

    # Total Goals (full)
    for line in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
        line_int = int(line)
        p_under = sum(g[h][a] for h in range(max_g + 1) for a in range(max_g + 1) if h + a <= line_int)
        P[f"Totals: Under {line}"] = p_under
        P[f"Totals: Over {line}"] = 1 - p_under

    # Asian Total (quarter) — at .25 line, half stake on .0 and half on .5
    # We just compute as standard line (no split) since it's an aggregate
    for line in [0.75, 1.25, 1.75, 2.25, 2.75, 3.25, 3.75]:
        # P(over X.25) = average of P(over X.0) and P(over X.5)
        floor_int = int(line - 0.25)
        ceil_int = int(line + 0.25)
        p_over_floor = sum(g[h][a] for h in range(max_g + 1) for a in range(max_g + 1) if h + a > floor_int)
        p_over_ceil = sum(g[h][a] for h in range(max_g + 1) for a in range(max_g + 1) if h + a > ceil_int)
        # P(over X.25 line, AH-style) ≈ avg
        P[f"Totals Asia: Over {line}"] = (p_over_floor + p_over_ceil) / 2
        P[f"Totals Asia: Under {line}"] = 1 - P[f"Totals Asia: Over {line}"]

    # Asian Handicap (full integer lines, push possible)
    for k_int in range(-4, 5):
        k = float(k_int)
        for prefix, sign in [("AH: Home", +1), ("AH: Away", -1)]:
            p_cover = 0.0
            p_push = 0.0
            for h in range(max_g + 1):
                for a in range(max_g + 1):
                    margin = (h - a) * sign
                    if margin > -k: p_cover += g[h][a]
                    elif margin == -k: p_push += g[h][a]
            P[f"{prefix} ({k:+g})"] = p_cover + 0.5 * p_push  # treat push as half-win

    # Asian Handicap quarter (no push, half-stake split on .25 / .75)
    for k in [-2.25, -1.75, -1.25, -0.75, -0.25, 0.25, 0.75, 1.25, 1.75, 2.25]:
        for prefix, sign in [("AH Q: Home", +1), ("AH Q: Away", -1)]:
            p_cover = 0.0
            for h in range(max_g + 1):
                for a in range(max_g + 1):
                    margin = (h - a) * sign
                    if margin > -k:
                        p_cover += g[h][a]
            P[f"{prefix} ({k:+g})"] = p_cover

    # Team totals (Home/Away independent)
    for line in [0.5, 1.5, 2.5, 3.5]:
        line_int = int(line)
        ph_under = cdf(line_int, lh)
        pa_under = cdf(line_int, la)
        P[f"Team Home: Under {line}"] = ph_under
        P[f"Team Home: Over {line}"] = 1 - ph_under
        P[f"Team Away: Under {line}"] = pa_under
        P[f"Team Away: Over {line}"] = 1 - pa_under

    # Halftime Totals
    for line in [0.5, 1.5, 2.5]:
        line_int = int(line)
        p_under = sum(g_ht[h][a] for h in range(max_g + 1) for a in range(max_g + 1) if h + a <= line_int)
        P[f"HT Totals: Under {line}"] = p_under
        P[f"HT Totals: Over {line}"] = 1 - p_under

    # Halftime 1X2
    ph_ht = sum(g_ht[h][a] for h in range(max_g + 1) for a in range(max_g + 1) if h > a)
    pd_ht = sum(g_ht[h][a] for h in range(max_g + 1) for a in range(max_g + 1) if h == a)
    pa_ht = sum(g_ht[h][a] for h in range(max_g + 1) for a in range(max_g + 1) if h < a)
    P["HT 1X2: Home Win"] = ph_ht
    P["HT 1X2: Draw"] = pd_ht
    P["HT 1X2: Away Win"] = pa_ht

    return out
