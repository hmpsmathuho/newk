"""λ-adjustment layer applied AFTER market-implied lambdas are derived.

Implements SPEC.md Section 5: form/injury/motivation as multiplicative factors
on the lambdas. Multipliers are CAPPED to [0.80, 1.20] so a single context
entry cannot move λ by more than ±20% — defensive against stale or wrong data.
"""
from __future__ import annotations

from typing import Tuple


_CAP_MIN = 0.80
_CAP_MAX = 1.20


def apply_form_adjustment(lambda_home: float, lambda_away: float,
                          team_context: dict) -> Tuple[float, float]:
    """Apply multipliers to home/away lambdas, clamped to [0.80, 1.20]."""
    home_adj = team_context.get("home_lambda_adj", 1.0) if team_context else 1.0
    away_adj = team_context.get("away_lambda_adj", 1.0) if team_context else 1.0
    home_adj = max(_CAP_MIN, min(_CAP_MAX, home_adj))
    away_adj = max(_CAP_MIN, min(_CAP_MAX, away_adj))
    return lambda_home * home_adj, lambda_away * away_adj


def get_rho_override(team_context: dict, default: float = -0.10) -> float:
    """Return ρ_DC override if specified in context, else default."""
    if team_context and team_context.get("rho_dc_override") is not None:
        rho = team_context["rho_dc_override"]
        return max(-0.30, min(0.10, rho))
    return default
