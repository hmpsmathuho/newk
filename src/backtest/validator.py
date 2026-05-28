"""Backtest validation against known match results.

Workspace .mhtml files become the historical test set. Each file's odds are
parsed, the model produces value-bet picks, and we score those picks against
the actual full-time scores (sourced from web search, hard-coded below).

Outputs hit rate, per-market breakdown, flat-stake P/L, and calibration table.
"""
from __future__ import annotations

from typing import Dict, List


# Ground truth verified via web search (ESPN, Sky Sports, Guardian, NBC Sports)
GROUND_TRUTH: Dict[str, Dict] = {
    "1.mhtml": {
        "home": "Burnley", "away": "Wolverhampton Wanderers",
        "fh": 1, "fa": 1, "ht_h": 0, "ht_a": 1,
        "league": "England Premier League",
        "summary": "Burnley 1-1 Wolves (Flemming 47, Armstrong 5 PEN)",
    },
    "2.mhtml": {
        "home": "Brighton & Hove Albion", "away": "Manchester United",
        "fh": 0, "fa": 3, "ht_h": 0, "ht_a": 1,
        "league": "England Premier League",
        "summary": "Brighton 0-3 Man Utd (Bruno Fernandes record assists)",
    },
    "3.mhtml": {
        "home": "West Ham United", "away": "Leeds United",
        "fh": 3, "fa": 0, "ht_h": 0, "ht_a": 0,
        "league": "England Premier League",
        "summary": "West Ham 3-0 Leeds (Castellanos, Bowen, Wilson — 2nd half)",
    },
    "4.mhtml": {
        "home": "Crystal Palace", "away": "Arsenal",
        "fh": 1, "fa": 2, "ht_h": 0, "ht_a": 1,
        "league": "England Premier League",
        "summary": "Crystal Palace 1-2 Arsenal (Mateta 89; Arsenal champions celebration)",
    },
    "5.mhtml": {
        "home": "Liverpool", "away": "Brentford",
        "fh": 1, "fa": 1, "ht_h": 1, "ht_a": 0,
        "league": "England Premier League",
        "summary": "Liverpool 1-1 Brentford (Curtis Jones / Schade — Salah farewell)",
    },
    "Taruhan_Shelbourne_Waterford_22_05_2026_Republik_Irlandia_Liga_Premier.mobi": {
        "home": "Shelbourne", "away": "Waterford",
        "fh": None, "fa": None, "ht_h": None, "ht_a": None,
        "league": "Ireland Premier League",
        "summary": "Result not encoded (excluded from backtest)",
    },
}


def evaluate_pick(market_key: str, fh: int, fa: int,
                  ht_h: int | None = None, ht_a: int | None = None) -> str | None:
    """Return 'WIN' / 'LOSS' / 'PUSH' / None (unknown market)."""
    if fh is None or fa is None:
        return None
    ft = fh + fa
    btts = fh >= 1 and fa >= 1

    if market_key == "1X2: Home Win": return "WIN" if fh > fa else "LOSS"
    if market_key == "1X2: Draw":     return "WIN" if fh == fa else "LOSS"
    if market_key == "1X2: Away Win": return "WIN" if fh < fa else "LOSS"

    if market_key == "DC: Home/Draw": return "WIN" if fh >= fa else "LOSS"
    if market_key == "DC: Home/Away": return "WIN" if fh != fa else "LOSS"
    if market_key == "DC: Draw/Away": return "WIN" if fh <= fa else "LOSS"

    if market_key == "BTTS: Yes": return "WIN" if btts else "LOSS"
    if market_key == "BTTS: No":  return "WIN" if not btts else "LOSS"

    if market_key.startswith("Totals: "):
        rest = market_key[len("Totals: "):]
        side, line_s = rest.split(" ", 1)
        line = float(line_s)
        if side == "Over":  return "WIN" if ft > line else "LOSS"
        if side == "Under": return "WIN" if ft < line else "LOSS"

    if market_key.startswith("Totals Asia: "):
        rest = market_key[len("Totals Asia: "):]
        side, line_s = rest.split(" ", 1)
        line = float(line_s)
        if side == "Over":  return "WIN" if ft > line else "LOSS"
        if side == "Under": return "WIN" if ft < line else "LOSS"

    if market_key.startswith("AH: Home (") or market_key.startswith("AH: Away ("):
        side = "Home" if "Home" in market_key else "Away"
        line = float(market_key.split("(")[1].rstrip(")"))
        margin = (fh - fa) if side == "Home" else (fa - fh)
        if margin > -line: return "WIN"
        if margin == -line: return "PUSH"
        return "LOSS"

    if market_key.startswith("AH Q: Home (") or market_key.startswith("AH Q: Away ("):
        side = "Home" if "Home" in market_key else "Away"
        line = float(market_key.split("(")[1].rstrip(")"))
        margin = (fh - fa) if side == "Home" else (fa - fh)
        return "WIN" if margin > -line else "LOSS"

    if ht_h is not None and ht_a is not None:
        ht_total = ht_h + ht_a
        if market_key.startswith("HT Totals: "):
            rest = market_key[len("HT Totals: "):]
            side, line_s = rest.split(" ", 1)
            line = float(line_s)
            if side == "Over":  return "WIN" if ht_total > line else "LOSS"
            if side == "Under": return "WIN" if ht_total < line else "LOSS"
        if market_key == "HT 1X2: Home Win": return "WIN" if ht_h > ht_a else "LOSS"
        if market_key == "HT 1X2: Draw":     return "WIN" if ht_h == ht_a else "LOSS"
        if market_key == "HT 1X2: Away Win": return "WIN" if ht_h < ht_a else "LOSS"

    if market_key.startswith("Team Home: "):
        rest = market_key[len("Team Home: "):]
        side, line_s = rest.split(" ", 1)
        line = float(line_s)
        if side == "Over":  return "WIN" if fh > line else "LOSS"
        if side == "Under": return "WIN" if fh < line else "LOSS"
    if market_key.startswith("Team Away: "):
        rest = market_key[len("Team Away: "):]
        side, line_s = rest.split(" ", 1)
        line = float(line_s)
        if side == "Over":  return "WIN" if fa > line else "LOSS"
        if side == "Under": return "WIN" if fa < line else "LOSS"

    return None


def backtest_picks(picks: List[dict], file_to_truth: Dict[str, dict]) -> dict:
    """Score picks against ground truth. Returns aggregate metrics."""
    rows = []
    for p in picks:
        truth = file_to_truth.get(p["file"])
        if not truth or truth["fh"] is None:
            rows.append({**p, "outcome": None})
            continue
        outcome = evaluate_pick(
            p["market_key"], truth["fh"], truth["fa"],
            truth.get("ht_h"), truth.get("ht_a"),
        )
        rows.append({**p, "outcome": outcome})

    evaluable = [r for r in rows if r["outcome"] in ("WIN", "LOSS", "PUSH")]
    wins = [r for r in evaluable if r["outcome"] == "WIN"]
    losses = [r for r in evaluable if r["outcome"] == "LOSS"]
    pushes = [r for r in evaluable if r["outcome"] == "PUSH"]

    flat_pl = sum((r["odds"] - 1) for r in wins) - len(losses)
    n_decided = len(wins) + len(losses)
    hit_rate = (len(wins) / n_decided) if n_decided else 0.0
    roi = (flat_pl / n_decided) if n_decided else 0.0

    def market_category(mk: str) -> str:
        if mk.startswith("Totals: "): return "Totals"
        if mk.startswith("Totals Asia: "): return "Totals Asia"
        if mk.startswith("AH: "): return "AH (full)"
        if mk.startswith("AH Q: "): return "AH (quarter)"
        if mk.startswith("BTTS"): return "BTTS"
        if mk.startswith("1X2"): return "1X2"
        if mk.startswith("DC"): return "DC"
        if mk.startswith("HT"): return "HT"
        if mk.startswith("Team Home") or mk.startswith("Team Away"): return "Team Total"
        return "Other"

    per_market: Dict[str, dict] = {}
    for r in evaluable:
        cat = market_category(r["market_key"])
        if cat not in per_market:
            per_market[cat] = {"n": 0, "win": 0, "loss": 0, "push": 0, "pl": 0.0}
        per_market[cat]["n"] += 1
        per_market[cat][r["outcome"].lower()] += 1
        if r["outcome"] == "WIN":
            per_market[cat]["pl"] += r["odds"] - 1
        elif r["outcome"] == "LOSS":
            per_market[cat]["pl"] -= 1

    buckets = [(0.0, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]
    calibration = []
    for lo, hi in buckets:
        bucket_rows = [r for r in evaluable if r["outcome"] != "PUSH"
                       and lo <= r.get("model_p", 0) < hi]
        if not bucket_rows:
            continue
        n = len(bucket_rows)
        avg_pred = sum(r["model_p"] for r in bucket_rows) / n
        actual = sum(1 for r in bucket_rows if r["outcome"] == "WIN") / n
        calibration.append({
            "bucket": f"{lo:.2f}-{hi:.2f}", "n": n,
            "avg_predicted": round(avg_pred, 4),
            "actual_hit_rate": round(actual, 4),
            "diff_pp": round((actual - avg_pred) * 100, 2),
        })

    return {
        "n_picks_total": len(rows),
        "n_evaluable": len(evaluable),
        "n_win": len(wins),
        "n_loss": len(losses),
        "n_push": len(pushes),
        "n_unknown": len(rows) - len(evaluable),
        "hit_rate": round(hit_rate, 4),
        "flat_pl_units": round(flat_pl, 4),
        "roi_pct": round(roi * 100, 2),
        "per_market": per_market,
        "calibration": calibration,
        "rows": rows,
    }


def format_backtest_report(result: dict) -> str:
    L = []
    L.append("=" * 78)
    L.append("  BACKTEST VALIDATION — workspace .mhtml as test set")
    L.append("=" * 78)
    L.append(f"  Total picks:    {result['n_picks_total']}")
    L.append(f"  Evaluable:      {result['n_evaluable']}")
    L.append(f"  W / L / P:      {result['n_win']} / {result['n_loss']} / {result['n_push']}")
    L.append(f"  Hit rate:       {result['hit_rate']*100:.1f}% (excluding pushes)")
    L.append(f"  Flat-stake P/L: {result['flat_pl_units']:+.2f} units (1u per pick)")
    L.append(f"  ROI:            {result['roi_pct']:+.2f}%")

    if result["per_market"]:
        L.append("")
        L.append("  PER-MARKET BREAKDOWN:")
        L.append(f"  {'Market':<18}{'N':>4}{'W':>4}{'L':>4}{'P':>4}{'Hit%':>8}{'P/L':>9}")
        L.append(f"  {'-'*55}")
        for cat, s in sorted(result["per_market"].items(), key=lambda x: -x[1]["pl"]):
            decided = s["win"] + s["loss"]
            hit = (s["win"] / decided * 100) if decided else 0
            L.append(f"  {cat:<18}{s['n']:>4}{s['win']:>4}{s['loss']:>4}{s['push']:>4}"
                     f"{hit:>7.1f}%{s['pl']:>+8.2f}")

    if result["calibration"]:
        L.append("")
        L.append("  CALIBRATION (predicted vs actual):")
        L.append(f"  {'Bucket':<14}{'N':>4}{'Predicted':>12}{'Actual':>10}{'Diff':>9}")
        for c in result["calibration"]:
            L.append(f"  {c['bucket']:<14}{c['n']:>4}{c['avg_predicted']*100:>11.1f}%"
                     f"{c['actual_hit_rate']*100:>9.1f}%{c['diff_pp']:>+8.1f}pp")

    L.append("")
    L.append("  PER-PICK DETAIL:")
    L.append(f"  {'#':<3}{'Match':<32}{'Pick':<22}{'Odds':>6}{'P_riil':>8}{'Result':>8}{'P/L':>7}")
    L.append(f"  {'-'*86}")
    for i, r in enumerate(result["rows"], 1):
        outcome = r["outcome"] or "?"
        if outcome == "WIN":  pl = f"{r['odds'] - 1:+.2f}"
        elif outcome == "LOSS": pl = "-1.00"
        elif outcome == "PUSH": pl = "0.00"
        else: pl = "?"
        match = r.get("match", "?")[:31]
        label = r.get("label", r.get("market_key", ""))[:21]
        L.append(f"  {i:<3}{match:<32}{label:<22}{r['odds']:>6.2f}"
                 f"{r.get('model_p', 0)*100:>7.1f}%{outcome:>8}{pl:>7}")

    return "\n".join(L)
