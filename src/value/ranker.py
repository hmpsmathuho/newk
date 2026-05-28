"""Rank legs and apply correlation/diversity filters."""
from __future__ import annotations
from typing import List


def rank_by_edge(legs: List[dict], top: int = 10) -> List[dict]:
    """Sort by edge descending, return top N picks that passed gate."""
    passed = [l for l in legs if l["passed"]]
    passed.sort(key=lambda x: -x["edge"])
    return passed[:top]


def rank_all_for_review(legs: List[dict], top: int = 20) -> List[dict]:
    """Sort all legs (passed + blocked) by edge for human review."""
    s = sorted(legs, key=lambda x: -x["edge"])
    return s[:top]


def stake_from_kelly(model_p: float, odds: float, bankroll: float = 1.0,
                     fraction: float = 0.25, max_pct: float = 0.05) -> float:
    """Quarter-Kelly stake clamped to max_pct of bankroll.

    Returns stake in same units as bankroll (e.g. 1.0 unit input -> 0.025 means 2.5% of bankroll).
    """
    if odds <= 1.0:
        return 0.0
    kelly_full = (model_p * odds - 1) / (odds - 1)
    if kelly_full <= 0:
        return 0.0
    stake_pct = kelly_full * fraction
    stake_pct = min(stake_pct, max_pct)
    return max(0.0, stake_pct * bankroll)
