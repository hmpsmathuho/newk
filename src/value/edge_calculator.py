"""Compute edge / value / Kelly for each (market, selection) pair.

A selection passes the gate if:
  - odds in [odds_min, odds_max]
  - model_p >= per_market_threshold.model_min (or default)
  - gap (model_p - implied_devig_p) >= per_market_threshold.gap_min_pp / 100
  - edge >= min_edge
  - Fade-Short-Odds rule: NOT (odds <= 1.40 AND gap >= 8pp)
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from src.model.poisson import devig


def _market_to_label(market_key: str, selection: str) -> str | None:
    """Map our internal probability key (e.g. 'Totals: Over 2.5') to the
    standardized label used in config thresholds (e.g. 'Over 2.5')."""
    label_map = {
        "1X2: Home Win": "Home Win",
        "1X2: Draw": "Draw",
        "1X2: Away Win": "Away Win",
        "BTTS: Yes": "BTTS Yes",
        "BTTS: No": "BTTS No",
        "DC: Home/Draw": "DC Home/Draw",
        "DC: Home/Away": "DC Home/Away",
        "DC: Draw/Away": "DC Draw/Away",
    }
    if market_key in label_map:
        return label_map[market_key]
    if market_key.startswith("Totals:"):
        # "Totals: Over 2.5" -> "Over 2.5"
        return market_key.split(": ", 1)[1]
    if market_key.startswith("Totals Asia:"):
        return market_key.split(": ", 1)[1]
    if market_key.startswith("AH: Home"):
        return "AH Home"
    if market_key.startswith("AH: Away"):
        return "AH Away"
    if market_key.startswith("AH Q: Home"):
        return "AH Home"
    if market_key.startswith("AH Q: Away"):
        return "AH Away"
    if market_key.startswith("Team Home:"):
        return None  # no specific gate; will fall through to default
    if market_key.startswith("Team Away:"):
        return None
    if market_key.startswith("HT Totals: Under 1.5"):
        return "HT Under 1.5"
    if market_key.startswith("HT Totals: Over 0.5"):
        return "HT Over 0.5"
    return None


def _build_market_index(odds_markets: dict, probs: dict) -> List[Tuple[str, str, float, float]]:
    """Yield (market_key_in_probs, display_label, odds, model_p) for each selection.

    odds_markets: from odds_extractor (nested dict)
    probs: from compute_probabilities['probs']
    """
    legs: List[Tuple[str, str, float, float]] = []

    # 1X2
    if "1X2" in odds_markets:
        for sel in ["Home", "Draw", "Away"]:
            o = odds_markets["1X2"].get(sel)
            mp = probs.get(f"1X2: {sel} Win" if sel != "Draw" else "1X2: Draw")
            if o and mp is not None:
                legs.append((f"1X2: {sel} Win" if sel != "Draw" else "1X2: Draw", f"1X2 — {sel}", o, mp))

    # DC
    if "DC" in odds_markets:
        dc_map = {"1X": ("DC: Home/Draw", "DC — Home/Draw (1X)"),
                  "12": ("DC: Home/Away", "DC — Home/Away (12)"),
                  "X2": ("DC: Draw/Away", "DC — Draw/Away (X2)")}
        for sel, (probkey, label) in dc_map.items():
            o = odds_markets["DC"].get(sel)
            mp = probs.get(probkey)
            if o and mp is not None:
                legs.append((probkey, label, o, mp))

    # BTTS
    if "BTTS" in odds_markets:
        for sel, label in [("Yes", "BTTS — Yes"), ("No", "BTTS — No")]:
            o = odds_markets["BTTS"].get(sel)
            mp = probs.get(f"BTTS: {sel}")
            if o and mp is not None:
                legs.append((f"BTTS: {sel}", label, o, mp))

    # Totals
    if "Totals" in odds_markets:
        for sel, o in odds_markets["Totals"].items():
            probkey = f"Totals: {sel}"
            mp = probs.get(probkey)
            if o and mp is not None:
                legs.append((probkey, f"Total — {sel}", o, mp))

    # Totals Asia
    if "Totals Asia" in odds_markets:
        for sel, o in odds_markets["Totals Asia"].items():
            probkey = f"Totals Asia: {sel}"
            mp = probs.get(probkey)
            if o and mp is not None:
                legs.append((probkey, f"Total Asia — {sel}", o, mp))

    # AH (full integer)
    if "AH" in odds_markets:
        for side, side_label in [("Home", "AH Home"), ("Away", "AH Away")]:
            for line, o in odds_markets["AH"].get(side, {}).items():
                # line is a string like "-1.5" or "+1"
                try:
                    line_f = float(line)
                except ValueError:
                    continue
                probkey = f"AH: {side} ({line_f:+g})"
                mp = probs.get(probkey)
                if o and mp is not None:
                    legs.append((probkey, f"{side_label} ({line_f:+g})", o, mp))

    # AH Quarter
    if "AH Quarter" in odds_markets:
        for side, side_label in [("Home", "AH Home"), ("Away", "AH Away")]:
            for line, o in odds_markets["AH Quarter"].get(side, {}).items():
                try:
                    line_f = float(line)
                except ValueError:
                    continue
                probkey = f"AH Q: {side} ({line_f:+g})"
                mp = probs.get(probkey)
                if o and mp is not None:
                    legs.append((probkey, f"{side_label} (Q) ({line_f:+g})", o, mp))

    # HT Totals
    if "HT Totals" in odds_markets:
        for sel, o in odds_markets["HT Totals"].items():
            probkey = f"HT Totals: {sel}"
            mp = probs.get(probkey)
            if o and mp is not None:
                legs.append((probkey, f"HT Total — {sel}", o, mp))

    # HT 1X2
    if "HT 1X2" in odds_markets:
        for sel in ["Home", "Draw", "Away"]:
            o = odds_markets["HT 1X2"].get(sel)
            probkey = f"HT 1X2: {sel} Win" if sel != "Draw" else "HT 1X2: Draw"
            mp = probs.get(probkey)
            if o and mp is not None:
                legs.append((probkey, f"HT 1X2 — {sel}", o, mp))

    # Team Totals
    for team_label, internal in [("Team Total Home", "Team Home"), ("Team Total Away", "Team Away")]:
        if team_label in odds_markets:
            for sel, o in odds_markets[team_label].items():
                probkey = f"{internal}: {sel}"
                mp = probs.get(probkey)
                if o and mp is not None:
                    legs.append((probkey, f"{team_label} — {sel}", o, mp))

    return legs


def evaluate(odds_markets: dict, probs: dict, config: dict) -> List[dict]:
    """Build leg list with edge/value/gate evaluation."""
    results = []
    legs = _build_market_index(odds_markets, probs)

    val_cfg = config.get("value", {})
    odds_min = val_cfg.get("odds_min", 1.30)
    odds_max = val_cfg.get("odds_max", 6.50)
    min_edge = val_cfg.get("min_edge", 0.02)
    remove_margin = val_cfg.get("remove_margin", True)
    per_market = val_cfg.get("per_market_thresholds", {})
    default_gate = {"model_min": 0.50, "gap_min_pp": 4.0}

    # Pre-compute devigged implied probabilities per market
    devig_cache: Dict[str, Dict[str, float]] = {}
    if remove_margin:
        if "1X2" in odds_markets:
            devig_cache["1X2"] = devig(odds_markets["1X2"])
        if "DC" in odds_markets:
            devig_cache["DC"] = devig(odds_markets["DC"])
        if "BTTS" in odds_markets:
            devig_cache["BTTS"] = devig(odds_markets["BTTS"])

    for probkey, label, odds, model_p in legs:
        implied_raw = 1.0 / odds
        # Devig where we have the full opposing pair (3-way 1X2 or 2-way Y/N)
        implied_devig = implied_raw
        if remove_margin:
            if probkey.startswith("1X2:") and "1X2" in devig_cache:
                sel = probkey.split(": ")[1].replace(" Win", "")
                if sel in devig_cache["1X2"]:
                    implied_devig = devig_cache["1X2"][sel]
            elif probkey.startswith("BTTS:"):
                sel = probkey.split(": ")[1]
                if "BTTS" in devig_cache and sel in devig_cache["BTTS"]:
                    implied_devig = devig_cache["BTTS"][sel]
            # For O/U and AH lines, devig pair-by-pair if both sides present
            elif probkey.startswith("Totals:") and ":" in probkey:
                parts = probkey.split(": ", 1)[1]  # e.g. "Over 2.5"
                opp = parts.replace("Over", "Under") if parts.startswith("Over") else parts.replace("Under", "Over")
                if "Totals" in odds_markets:
                    opp_odds = odds_markets["Totals"].get(opp)
                    if opp_odds:
                        s = 1.0 / odds + 1.0 / opp_odds
                        if s > 0: implied_devig = (1.0 / odds) / s

        edge = model_p * odds - 1
        ev = edge  # alias
        gap = model_p - implied_devig  # in 0..1
        gap_pp = gap * 100
        kelly_full = (model_p * odds - 1) / (odds - 1) if odds > 1 else 0
        kelly_q = kelly_full * config.get("staking", {}).get("kelly_fraction", 0.25)

        # Gate evaluation
        market_label = _market_to_label(probkey, label)
        gate = per_market.get(market_label, default_gate) if market_label else default_gate
        passed = True
        reason = "OK"

        if not (odds_min <= odds <= odds_max):
            passed = False
            reason = f"odds {odds:.2f} out of [{odds_min}, {odds_max}]"
        elif model_p < gate["model_min"]:
            passed = False
            reason = f"model {model_p*100:.1f}% < {gate['model_min']*100:.0f}% gate"
        elif gap_pp < gate["gap_min_pp"]:
            passed = False
            reason = f"gap {gap_pp:+.1f}pp < {gate['gap_min_pp']}pp gate"
        elif edge < min_edge:
            passed = False
            reason = f"edge {edge*100:+.1f}% < {min_edge*100:.0f}% floor"
        elif odds <= 1.40 and gap_pp >= 8:
            passed = False
            reason = "Fade-Short-Odds rule (odds ≤1.40 AND gap ≥8pp)"

        results.append({
            "market_key": probkey,
            "label": label,
            "odds": odds,
            "implied_raw": implied_raw,
            "implied_devig": implied_devig,
            "model_p": model_p,
            "edge": edge,
            "ev": ev,
            "gap_pp": gap_pp,
            "kelly_full_pct": kelly_full * 100,
            "kelly_quarter_pct": kelly_q * 100,
            "passed": passed,
            "reason": reason,
        })
    return results
