"""Team form / context store (Section 5 — Elo + form-based adjustments).

Hand-curated context for matches with research data (web-search verified May 2026).
Multipliers applied to lambdas after market-implied derivation.

Lookup contract:
    ctx = lookup_team_context("Burnley", "Wolverhampton Wanderers", "EPL")
    -> {
        "home_lambda_adj": 0.95, "away_lambda_adj": 0.92,
        "rho_dc_override": -0.15,
        "notes": [...],
        "available": True/False, "source": "curated"|"cache"|"neutral",
    }

Multipliers are clamped in adjustments.py to ±20% so a single context entry
cannot move λ by more than that.
"""
from __future__ import annotations

import json
import os
from typing import Dict


CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "cache", "team_form.json",
)


# Curated facts from web research. Final-day EPL 2025/26 + Liga Irlandia 22 May.
DEFAULT_FORM_DB: Dict[tuple, dict] = {
    ("burnley", "wolverhampton wanderers"): {
        "home_lambda_adj": 0.95, "away_lambda_adj": 0.92,
        "rho_dc_override": -0.15,
        "notes": [
            "Both teams already relegated (Burnley 22 Apr, Wolves 20 Apr 2026).",
            "Dead-rubber final day with no stakes for either side.",
            "Wolves attack worst in PL (~26 GF/season); Burnley 6L of last 7.",
            "Tips.gg pre-match: 'neither side can buy a win, both spent.'",
        ],
    },
    ("brighton & hove albion", "manchester united"): {
        "home_lambda_adj": 0.95, "away_lambda_adj": 1.00,
        "rho_dc_override": None,
        "notes": [
            "Brighton fighting for Conference League slot.",
            "Man Utd: Sesko out (long-term injury).",
            "Casemiro confirmed retired/out (last appearance was prior week).",
            "All last 4 H2H matches were BTTS = Yes.",
        ],
    },
    ("west ham united", "leeds united"): {
        "home_lambda_adj": 1.05, "away_lambda_adj": 0.92,
        "rho_dc_override": None,
        "notes": [
            "West Ham must-win to escape relegation (depends on Spurs).",
            "Leeds safe at 14th — checked-out, 'toothless' (Guardian).",
            "Leeds out: Okafor (calf), Gudmundsson, Gruev (injury).",
            "WH home form last 7: W3 D3 L1.",
        ],
    },
    ("crystal palace", "arsenal"): {
        "home_lambda_adj": 0.85, "away_lambda_adj": 0.85,
        "rho_dc_override": None,
        "notes": [
            "Arsenal CHAMPIONS already (clinched 19 May vs Man City draw).",
            "HEAVY ROTATION expected: Raya, Rice, Saka, Havertz rested.",
            "Palace plays Conference League final 27 May vs Real Betis.",
            "Both sides protecting legs.",
        ],
    },
    ("liverpool", "brentford"): {
        "home_lambda_adj": 0.95, "away_lambda_adj": 0.95,
        "rho_dc_override": None,
        "notes": [
            "Salah & Robertson farewell at Anfield.",
            "Liverpool need >=1 point for CL5 qualification.",
            "Liverpool no clean sheet last 6 matches.",
            "Brentford safe at 9th — dead rubber.",
        ],
    },
    ("shelbourne", "waterford"): {
        "home_lambda_adj": 1.00, "away_lambda_adj": 0.95,
        "rho_dc_override": None,
        "notes": [
            "Shelbourne home, won last vs St Patrick's 1-0.",
            "Waterford 10th place, mid-table form mixed.",
        ],
    },
}


def _normalize(name: str) -> str:
    """Lowercase + map common short forms to canonical names."""
    if not name:
        return ""
    n = name.lower().strip()
    short_to_full = {
        "wolves": "wolverhampton wanderers",
        "wolverhampton": "wolverhampton wanderers",
        "man united": "manchester united",
        "man utd": "manchester united",
        "manchecter united": "manchester united",  # 1xbet typo seen in slip
        "brighton": "brighton & hove albion",
        "hove albion": "brighton & hove albion",
        "brighton and hove albion": "brighton & hove albion",
    }
    if n in short_to_full:
        n = short_to_full[n]
    return n.strip()


def _load_cache() -> dict:
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def lookup_team_context(home: str, away: str, league: str = "") -> dict:
    """Return context entry for a match. Falls back to neutral if not found."""
    h = _normalize(home)
    a = _normalize(away)

    if (h, a) in DEFAULT_FORM_DB:
        return {**DEFAULT_FORM_DB[(h, a)], "available": True, "source": "curated"}

    cache = _load_cache()
    cache_key = f"{h}|{a}"
    if cache_key in cache:
        return {**cache[cache_key], "available": True, "source": "cache"}

    return {
        "home_lambda_adj": 1.0,
        "away_lambda_adj": 1.0,
        "rho_dc_override": None,
        "notes": ["No curated form data; using neutral λ adjustments."],
        "available": False,
        "source": "neutral",
    }


def store_team_context(home: str, away: str, ctx: dict) -> None:
    """Persist a context entry for later reuse."""
    cache = _load_cache()
    cache[f"{_normalize(home)}|{_normalize(away)}"] = {
        k: v for k, v in ctx.items() if k not in ("available", "source")
    }
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
