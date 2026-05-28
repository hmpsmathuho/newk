"""Best Value Bet Analyzer — CLI entrypoint.

Usage:
    python main.py --input 1.mhtml
    python main.py --input 1.mhtml --output results/match.json --top 15
    python main.py --input-dir . --output-dir results/

Implements the SPEC.md pipeline:
  Input MHTML  ->  Parser  ->  Odds Normalizer
                                    |
                                    v
                       Probability Model (Poisson + Dixon-Coles)
                                    |
                                    v
                       Value Bet Ranker (devig + edge + Kelly)
                                    |
                                    v
                       Output: Best Bets (terminal / JSON / CSV)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List

# Allow running from anywhere
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.parser.mhtml_parser import decode_mhtml, parse_match_meta_from_url
from src.parser.odds_extractor import extract_match_meta, extract_markets, market_count
from src.model.poisson import compute_probabilities
from src.value.edge_calculator import evaluate
from src.value.ranker import rank_by_edge, rank_all_for_review, stake_from_kelly
from src.output.exporter import format_terminal, to_json, to_csv


# ----------------------------------------------------------------------
# Default config (mirrors config.yaml; used if PyYAML not available)
# ----------------------------------------------------------------------
DEFAULT_CONFIG = {
    "model": {
        "dixon_coles_rho": -0.10,
        "poisson_max_goals": 10,
    },
    "value": {
        "min_edge": 0.02,
        "remove_margin": True,
        "odds_min": 1.30,
        "odds_max": 6.50,
        "per_market_thresholds": {
            "Under 3.5":     {"model_min": 0.65, "gap_min_pp": 4.0},
            "Under 2.5":     {"model_min": 0.70, "gap_min_pp": 5.0},
            "Under 1.5":     {"model_min": 0.65, "gap_min_pp": 5.0},
            "Over 0.5":      {"model_min": 0.85, "gap_min_pp": 4.0},
            "Over 1.5":      {"model_min": 0.65, "gap_min_pp": 4.0},
            "Over 2.5":      {"model_min": 0.55, "gap_min_pp": 4.0},
            "Over 3.5":      {"model_min": 0.45, "gap_min_pp": 4.0},
            "BTTS Yes":      {"model_min": 0.55, "gap_min_pp": 4.0},
            "BTTS No":       {"model_min": 0.55, "gap_min_pp": 4.0},
            "Home Win":      {"model_min": 0.45, "gap_min_pp": 4.0},
            "Draw":          {"model_min": 0.25, "gap_min_pp": 4.0},
            "Away Win":      {"model_min": 0.40, "gap_min_pp": 4.0},
            "DC Home/Draw":  {"model_min": 0.65, "gap_min_pp": 4.0},
            "DC Home/Away":  {"model_min": 0.65, "gap_min_pp": 4.0},
            "DC Draw/Away":  {"model_min": 0.55, "gap_min_pp": 4.0},
            "AH Home":       {"model_min": 0.55, "gap_min_pp": 4.0},
            "AH Away":       {"model_min": 0.50, "gap_min_pp": 4.0},
            "HT Under 1.5":  {"model_min": 0.60, "gap_min_pp": 4.0},
            "HT Over 0.5":   {"model_min": 0.70, "gap_min_pp": 4.0},
        },
    },
    "staking": {
        "method": "kelly",
        "kelly_fraction": 0.25,
        "max_stake_pct": 0.05,
    },
    "output": {
        "top": 10,
        "show_blocked": True,
    },
}


def load_config(path: str | None) -> dict:
    if not path or not os.path.exists(path):
        return DEFAULT_CONFIG
    try:
        import yaml  # noqa
        with open(path) as f:
            return yaml.safe_load(f)
    except ImportError:
        # Fallback: try JSON
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return DEFAULT_CONFIG


# ----------------------------------------------------------------------
# Single-file analysis
# ----------------------------------------------------------------------
def analyze_file(path: str, config: dict, top: int = 10, show_blocked: bool = True) -> dict:
    decoded = decode_mhtml(path)
    url_meta = parse_match_meta_from_url(decoded.get("url", ""))
    match_meta = extract_match_meta(decoded["plain_text"], url_meta)
    if url_meta and url_meta.get("league_slug"):
        match_meta["league"] = " ".join(w.capitalize() for w in url_meta["league_slug"].split("-"))

    markets = extract_markets(decoded["plain_text"])
    n_selections = market_count(markets)

    # Apply min_edge override
    if config.get("value", {}).get("min_edge") is None:
        config.setdefault("value", {})["min_edge"] = 0.02

    probs_result = compute_probabilities(
        markets,
        rho=config.get("model", {}).get("dixon_coles_rho", -0.10),
        max_g=config.get("model", {}).get("poisson_max_goals", 10),
    )

    legs = evaluate(markets, probs_result["probs"], config)
    picks = rank_by_edge(legs, top=top)
    blocked_top = [l for l in legs if not l["passed"]]
    blocked_top.sort(key=lambda x: -x["edge"])

    terminal_out = format_terminal(
        match_meta,
        {"lambda_home": probs_result["lambda_home"],
         "lambda_away": probs_result["lambda_away"],
         "total_lambda": probs_result["total_lambda"]},
        picks,
        blocked_top if show_blocked else None,
    )
    json_out = to_json(match_meta,
                       {"lambda_home": probs_result["lambda_home"],
                        "lambda_away": probs_result["lambda_away"],
                        "total_lambda": probs_result["total_lambda"]},
                       picks, legs)

    return {
        "file": path,
        "match_meta": match_meta,
        "n_markets": len(markets),
        "n_selections": n_selections,
        "lambdas": {
            "lambda_home": probs_result["lambda_home"],
            "lambda_away": probs_result["lambda_away"],
            "total_lambda": probs_result["total_lambda"],
        },
        "picks": picks,
        "all_legs": legs,
        "terminal_output": terminal_out,
        "json_output": json_out,
    }


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="Best Value Bet Analyzer")
    p.add_argument("--input", help="Path to .mhtml or .mobi file")
    p.add_argument("--input-dir", help="Directory containing .mhtml/.mobi files")
    p.add_argument("--output", help="JSON file for single-file mode")
    p.add_argument("--output-dir", help="Output directory for batch mode")
    p.add_argument("--config", default="config.yaml", help="Path to config YAML")
    p.add_argument("--top", type=int, default=10, help="Top N picks per match")
    p.add_argument("--min-edge", type=float, help="Min edge floor (overrides config)")
    p.add_argument("--stake-method", choices=["kelly", "flat", "none"], default="none")
    p.add_argument("--no-blocked", action="store_true", help="Don't show BLOCKED markets")
    args = p.parse_args()

    if not args.input and not args.input_dir:
        p.error("Either --input or --input-dir is required")

    config = load_config(args.config)
    if args.min_edge is not None:
        config.setdefault("value", {})["min_edge"] = args.min_edge

    show_blocked = not args.no_blocked

    if args.input:
        result = analyze_file(args.input, config, top=args.top, show_blocked=show_blocked)
        print(result["terminal_output"])
        if args.output:
            os.makedirs(os.path.dirname(args.output), exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result["json_output"], f, indent=2, ensure_ascii=False)
            print(f"\n[saved] {args.output}")
    else:
        # Batch
        files = []
        for fn in sorted(os.listdir(args.input_dir)):
            if fn.endswith(".mhtml") or fn.endswith(".mobi"):
                files.append(os.path.join(args.input_dir, fn))
        all_results = []
        for fpath in files:
            try:
                r = analyze_file(fpath, config, top=args.top, show_blocked=show_blocked)
                print(r["terminal_output"])
                print()
                all_results.append(r["json_output"])
            except Exception as e:
                print(f"[ERR] {fpath}: {e}")
        if args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)
            agg_path = os.path.join(args.output_dir, "all_matches.json")
            with open(agg_path, "w", encoding="utf-8") as f:
                json.dump(all_results, f, indent=2, ensure_ascii=False)
            print(f"\n[saved] {agg_path}")


if __name__ == "__main__":
    main()
