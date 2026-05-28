"""Best Value Bet Analyzer — CLI entrypoint (v1.1: + external + form + backtest).

Subcommands:
  analyze   Analyze .mhtml file(s) → ranked value bets
  live      Fetch upcoming matches from 1xbet API → analyze live odds
  backtest  Validate model on workspace .mhtml files vs known results

Usage:
    python main.py analyze --input 1.mhtml
    python main.py analyze --input-dir . --output-dir results/
    python main.py live --window-hours 24
    python main.py backtest --input-dir .
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.parser.mhtml_parser import decode_mhtml, parse_match_meta_from_url
from src.parser.odds_extractor import extract_match_meta, extract_markets, market_count
from src.model.poisson import compute_probabilities
from src.value.edge_calculator import evaluate
from src.value.ranker import rank_by_edge
from src.output.exporter import format_terminal, to_json
from src.external.team_form import lookup_team_context


DEFAULT_CONFIG = {
    "model": {"dixon_coles_rho": -0.10, "poisson_max_goals": 10},
    "value": {
        "min_edge": 0.02, "remove_margin": True,
        "odds_min": 1.30, "odds_max": 6.50,
        "per_market_thresholds": {
            "Under 3.5": {"model_min": 0.65, "gap_min_pp": 4.0},
            "Under 2.5": {"model_min": 0.70, "gap_min_pp": 5.0},
            "Under 1.5": {"model_min": 0.65, "gap_min_pp": 5.0},
            "Over 0.5":  {"model_min": 0.85, "gap_min_pp": 4.0},
            "Over 1.5":  {"model_min": 0.65, "gap_min_pp": 4.0},
            "Over 2.5":  {"model_min": 0.55, "gap_min_pp": 4.0},
            "Over 3.5":  {"model_min": 0.45, "gap_min_pp": 4.0},
            "BTTS Yes":  {"model_min": 0.55, "gap_min_pp": 4.0},
            "BTTS No":   {"model_min": 0.55, "gap_min_pp": 4.0},
            "Home Win":  {"model_min": 0.45, "gap_min_pp": 4.0},
            "Draw":      {"model_min": 0.25, "gap_min_pp": 4.0},
            "Away Win":  {"model_min": 0.40, "gap_min_pp": 4.0},
            "DC Home/Draw": {"model_min": 0.65, "gap_min_pp": 4.0},
            "DC Home/Away": {"model_min": 0.65, "gap_min_pp": 4.0},
            "DC Draw/Away": {"model_min": 0.55, "gap_min_pp": 4.0},
            "AH Home":   {"model_min": 0.55, "gap_min_pp": 4.0},
            "AH Away":   {"model_min": 0.50, "gap_min_pp": 4.0},
            "HT Under 1.5": {"model_min": 0.60, "gap_min_pp": 4.0},
            "HT Over 0.5":  {"model_min": 0.70, "gap_min_pp": 4.0},
        },
    },
    "staking": {"method": "kelly", "kelly_fraction": 0.25, "max_stake_pct": 0.05},
    "output": {"top": 10, "show_blocked": True},
}


def load_config(path: str | None) -> dict:
    if not path or not os.path.exists(path):
        return DEFAULT_CONFIG
    try:
        import yaml
        with open(path) as f:
            return yaml.safe_load(f)
    except ImportError:
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return DEFAULT_CONFIG


def _analyze(markets: dict, match_meta: dict, config: dict, top: int,
             show_blocked: bool) -> dict:
    team_ctx = lookup_team_context(
        match_meta.get("home", ""), match_meta.get("away", ""),
        match_meta.get("league", ""),
    )
    probs_result = compute_probabilities(
        markets,
        rho=config.get("model", {}).get("dixon_coles_rho", -0.10),
        max_g=config.get("model", {}).get("poisson_max_goals", 10),
        team_context=team_ctx,
    )
    legs = evaluate(markets, probs_result["probs"], config)
    picks = rank_by_edge(legs, top=top)
    blocked_top = sorted([l for l in legs if not l["passed"]], key=lambda x: -x["edge"])

    return {
        "match_meta": match_meta,
        "team_context": team_ctx,
        "probs_result": probs_result,
        "legs": legs,
        "picks": picks,
        "blocked_top": blocked_top if show_blocked else None,
        "n_markets": len(markets),
        "n_selections": market_count(markets),
    }


def _format_result_terminal(r: dict) -> str:
    lambdas = {
        "lambda_home": r["probs_result"]["lambda_home"],
        "lambda_away": r["probs_result"]["lambda_away"],
        "total_lambda": r["probs_result"]["total_lambda"],
    }
    out = format_terminal(r["match_meta"], lambdas, r["picks"], r["blocked_top"])
    if r["team_context"].get("available"):
        ctx_lines = ["", "  📋 CONTEXT (form/injury/motivation):"]
        for note in r["team_context"].get("notes", []):
            ctx_lines.append(f"     • {note}")
        ctx_lines.append(
            f"     λ adj — home: {r['team_context']['home_lambda_adj']:.2f}x, "
            f"away: {r['team_context']['away_lambda_adj']:.2f}x  "
            f"(source: {r['team_context'].get('source', '?')})"
        )
        out = out + "\n" + "\n".join(ctx_lines)
    return out


def _to_json(r: dict) -> dict:
    return to_json(
        r["match_meta"],
        {"lambda_home": r["probs_result"]["lambda_home"],
         "lambda_away": r["probs_result"]["lambda_away"],
         "total_lambda": r["probs_result"]["total_lambda"]},
        r["picks"], r["legs"],
    )


# ----------------------------------------------------------------------
# analyze
# ----------------------------------------------------------------------
def cmd_analyze(args):
    config = load_config(args.config)
    if args.min_edge is not None:
        config.setdefault("value", {})["min_edge"] = args.min_edge
    show_blocked = not args.no_blocked

    files = []
    if args.input:
        files = [args.input]
    else:
        for fn in sorted(os.listdir(args.input_dir)):
            if fn.endswith((".mhtml", ".mobi")):
                files.append(os.path.join(args.input_dir, fn))

    all_results = []
    from src.backtest.validator import GROUND_TRUTH
    for fpath in files:
        try:
            decoded = decode_mhtml(fpath)
            url_meta = parse_match_meta_from_url(decoded.get("url", ""))
            match_meta = extract_match_meta(decoded["plain_text"], url_meta)
            if url_meta and url_meta.get("league_slug"):
                match_meta["league"] = " ".join(w.capitalize() for w in url_meta["league_slug"].split("-"))

            base = os.path.basename(fpath)
            if base in GROUND_TRUTH:
                t = GROUND_TRUTH[base]
                match_meta["home"] = t["home"]
                match_meta["away"] = t["away"]
                match_meta["league"] = t["league"]

            markets = extract_markets(decoded["plain_text"])
            r = _analyze(markets, match_meta, config, args.top, show_blocked)
            r["file"] = fpath
            print(_format_result_terminal(r))
            print()
            all_results.append(r)
        except Exception as e:
            print(f"[ERR] {fpath}: {e}")

    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        out_path = os.path.join(args.output_dir, "all_matches.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump([_to_json(r) for r in all_results], f, indent=2, ensure_ascii=False)
        print(f"[saved] {out_path}")
    elif args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            payload = _to_json(all_results[0]) if len(all_results) == 1 else [_to_json(r) for r in all_results]
            json.dump(payload, f, indent=2, ensure_ascii=False)
        print(f"[saved] {args.output}")


# ----------------------------------------------------------------------
# live
# ----------------------------------------------------------------------
def cmd_live(args):
    from datetime import datetime, timezone
    from src.external.onexbet_client import (
        resolve_ip, fetch_upcoming, filter_serious_matches,
        fetch_match_odds, parse_apivalue_to_markets, fetch_meta_from_apivalue,
    )

    config = load_config(args.config)
    if args.min_edge is not None:
        config.setdefault("value", {})["min_edge"] = args.min_edge
    show_blocked = not args.no_blocked

    print("[live] Resolving 1xbet.mobi IP...")
    ip = resolve_ip()
    print(f"[live] IP: {ip}")

    print("[live] Fetching upcoming events...")
    now_utc = int(datetime.now(timezone.utc).timestamp())
    max_unix = now_utc + args.window_hours * 3600
    events = fetch_upcoming(ip)
    events = filter_serious_matches(events, min_unix=now_utc, max_unix=max_unix)
    print(f"[live] {len(events)} matches in next {args.window_hours}h after filtering")

    if args.max_matches and len(events) > args.max_matches:
        events = events[: args.max_matches]
        print(f"[live] limiting to first {args.max_matches} for analysis")

    all_results = []
    for ev in events:
        try:
            v = fetch_match_odds(ip, ev["I"])
            if not v:
                continue
            markets = parse_apivalue_to_markets(v)
            match_meta = fetch_meta_from_apivalue(v)
            r = _analyze(markets, match_meta, config, args.top, show_blocked)
            r["match_id"] = ev["I"]
            print(_format_result_terminal(r))
            print()
            all_results.append(r)
        except Exception as e:
            print(f"[ERR] match {ev.get('I')}: {e}")

    all_picks_flat = []
    for r in all_results:
        for p in r["picks"]:
            all_picks_flat.append({
                **p,
                "match": f"{r['match_meta']['home']} vs {r['match_meta']['away']}",
                "league": r["match_meta"]["league"],
                "kickoff_wib": r["match_meta"].get("kickoff_wib", ""),
            })
    all_picks_flat.sort(key=lambda x: -x["edge"])

    print("=" * 78)
    print(f"  TOP VALUE BETS ACROSS {len(all_results)} MATCHES (by edge)")
    print("=" * 78)
    if not all_picks_flat:
        print("  No value bets identified.")
    else:
        print(f"  {'#':<3}{'Match':<35}{'Pick':<22}{'Odds':>6}{'Edge':>7}{'KO':>17}")
        for i, p in enumerate(all_picks_flat[: args.top * 2], 1):
            print(f"  {i:<3}{p['match'][:34]:<35}{p['label'][:21]:<22}"
                  f"{p['odds']:>6.2f}{p['edge']*100:>+6.1f}%{p['kickoff_wib']:>17}")

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump({
                "n_matches": len(all_results),
                "top_picks": all_picks_flat[: args.top * 2],
                "matches": [_to_json(r) for r in all_results],
            }, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n[saved] {args.output}")


# ----------------------------------------------------------------------
# backtest
# ----------------------------------------------------------------------
def cmd_backtest(args):
    from src.backtest.validator import GROUND_TRUTH, backtest_picks, format_backtest_report

    config = load_config(args.config)
    if args.min_edge is not None:
        config.setdefault("value", {})["min_edge"] = args.min_edge

    files = []
    for fn in sorted(os.listdir(args.input_dir)):
        if fn.endswith((".mhtml", ".mobi")) and fn in GROUND_TRUTH:
            t = GROUND_TRUTH[fn]
            if t.get("fh") is not None:
                files.append(os.path.join(args.input_dir, fn))
    print(f"[backtest] {len(files)} files have ground-truth data")

    all_picks: List[dict] = []
    for fpath in files:
        base = os.path.basename(fpath)
        truth = GROUND_TRUTH[base]
        decoded = decode_mhtml(fpath)
        match_meta = {
            "home": truth["home"], "away": truth["away"], "league": truth["league"],
        }
        markets = extract_markets(decoded["plain_text"])
        r = _analyze(markets, match_meta, config, args.top, False)

        match_str = f"{truth['home']} vs {truth['away']}"
        for p in r["picks"]:
            all_picks.append({**p, "file": base, "match": match_str})

    print(f"[backtest] Evaluating {len(all_picks)} picks against ground truth...")
    result = backtest_picks(all_picks, GROUND_TRUTH)
    print()
    print(format_backtest_report(result))

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n[saved] {args.output}")


# ----------------------------------------------------------------------
# Argparse
# ----------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="Best Value Bet Analyzer (v1.1)")
    sub = p.add_subparsers(dest="command")

    p_an = sub.add_parser("analyze", help="Analyze .mhtml/.mobi files")
    p_an.add_argument("--input", help="Single file")
    p_an.add_argument("--input-dir", default=".", help="Directory with .mhtml/.mobi (default: cwd)")
    p_an.add_argument("--output", help="JSON output for single file")
    p_an.add_argument("--output-dir", help="Directory for batch JSON output")
    p_an.add_argument("--config", default="config.yaml")
    p_an.add_argument("--top", type=int, default=10)
    p_an.add_argument("--min-edge", type=float)
    p_an.add_argument("--no-blocked", action="store_true")
    p_an.set_defaults(func=cmd_analyze)

    p_lv = sub.add_parser("live", help="Fetch upcoming odds from 1xbet API and analyze")
    p_lv.add_argument("--window-hours", type=int, default=24)
    p_lv.add_argument("--max-matches", type=int, default=20)
    p_lv.add_argument("--config", default="config.yaml")
    p_lv.add_argument("--top", type=int, default=5)
    p_lv.add_argument("--min-edge", type=float)
    p_lv.add_argument("--no-blocked", action="store_true")
    p_lv.add_argument("--output", help="JSON output path")
    p_lv.set_defaults(func=cmd_live)

    p_bt = sub.add_parser("backtest", help="Validate model on .mhtml files vs known results")
    p_bt.add_argument("--input-dir", default=".")
    p_bt.add_argument("--config", default="config.yaml")
    p_bt.add_argument("--top", type=int, default=10)
    p_bt.add_argument("--min-edge", type=float)
    p_bt.add_argument("--output", help="JSON output path")
    p_bt.set_defaults(func=cmd_backtest)

    args = p.parse_args()
    if not args.command:
        p.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
