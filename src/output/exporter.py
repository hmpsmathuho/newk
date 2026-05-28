"""Output formatters: terminal (1xbet-style), JSON, CSV."""
from __future__ import annotations
import json
import csv
from typing import List, Dict


def format_terminal(match_meta: dict, lambdas: dict, picks: List[dict],
                    blocked_top: List[dict] | None = None) -> str:
    lines = []
    lines.append("=" * 78)
    home = match_meta.get("home", "?")
    away = match_meta.get("away", "?")
    league = match_meta.get("league", "?")
    lines.append(f"  PERTANDINGAN: {home} vs {away}")
    lines.append(f"  Liga: {league}")
    lines.append("=" * 78)
    lh = lambdas.get("lambda_home")
    la = lambdas.get("lambda_away")
    tot = lambdas.get("total_lambda")
    if lh is not None:
        lines.append(f"  Model: λ_home={lh:.2f}  λ_away={la:.2f}  total_λ={tot:.2f}")
    lines.append("")

    if not picks:
        lines.append("  ⚠ TIDAK ADA value bet yang lolos gate.")
        lines.append("  Rekomendasi: SIT OUT match ini.")
    else:
        lines.append(f"  ✅ {len(picks)} VALUE BET (urut by edge):")
        lines.append("")
        lines.append(f"  {'#':<3}{'MARKET — SELEKSI':<42}{'ODDS':>6}{'IMP%':>7}{'P_RIIL':>8}{'EDGE':>7}{'KELLY/4':>9}")
        lines.append(f"  {'-'*78}")
        for i, p in enumerate(picks, 1):
            lines.append(
                f"  {i:<3}{p['label'][:41]:<42}{p['odds']:>6.2f}{p['implied_devig']*100:>6.1f}%"
                f"{p['model_p']*100:>7.1f}%{p['edge']*100:>+6.1f}%{p['kelly_quarter_pct']:>+8.2f}%"
            )

    if blocked_top:
        lines.append("")
        lines.append(f"  ❌ Top {min(5, len(blocked_top))} BLOCKED (jangan dipasang — model overestimate atau gate fail):")
        for b in blocked_top[:5]:
            lines.append(f"     • {b['label'][:50]:<52} odds={b['odds']:.2f} model={b['model_p']*100:.1f}% edge={b['edge']*100:+.1f}%")
            lines.append(f"       └ {b['reason']}")

    return "\n".join(lines)


def to_json(match_meta: dict, lambdas: dict, picks: List[dict], all_legs: List[dict]) -> dict:
    return {
        "match": match_meta,
        "model": {
            "lambda_home": lambdas.get("lambda_home"),
            "lambda_away": lambdas.get("lambda_away"),
            "total_lambda": lambdas.get("total_lambda"),
        },
        "picks": [_clean_leg(p) for p in picks],
        "all_legs_count": len(all_legs),
        "passed_count": sum(1 for l in all_legs if l["passed"]),
        "blocked_count": sum(1 for l in all_legs if not l["passed"]),
    }


def to_csv(rows: List[dict], path: str) -> None:
    if not rows:
        return
    keys = ["match", "league", "label", "odds", "implied_devig_pct", "model_p_pct",
            "edge_pct", "gap_pp", "kelly_quarter_pct", "passed", "reason"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in keys})


def _clean_leg(p: dict) -> dict:
    return {
        "market_key": p["market_key"],
        "label": p["label"],
        "odds": round(p["odds"], 4),
        "implied_devig": round(p["implied_devig"], 4),
        "model_p": round(p["model_p"], 4),
        "edge": round(p["edge"], 4),
        "gap_pp": round(p["gap_pp"], 2),
        "kelly_full_pct": round(p["kelly_full_pct"], 2),
        "kelly_quarter_pct": round(p["kelly_quarter_pct"], 2),
        "passed": p["passed"],
        "reason": p["reason"],
    }
