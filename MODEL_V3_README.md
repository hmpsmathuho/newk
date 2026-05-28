# Model V3 — Calibrated Production Model

## Why V3 (the rebuild story)

V5 of CLAUDE.md was based on raw Poisson with manual lambda adjustments. **It was broken.**

`backtest.py` ran the original model on 380-match EPL 2025/26 season (300 predictions after warmup). Results:

```
U2.5 calibration error by predicted bucket:
  65-70%   pred 68.0%   actual 42.9%   diff -25.1 pp
  70-75%   pred 72.4%   actual 31.2%   diff -41.1 pp
  75-80%   pred 77.7%   actual 56.2%   diff -21.5 pp
  80-90%   pred 83.9%   actual 36.8%   diff -47.1 pp

Gate simulation (model >= 65%, value >= 4%, gap >= 4pp):
  77 picks U2.5
  Avg model: 77.3%, actual hit: 44.2%, error -33.2 pp
  Flat-stake ROI: -12.17% over 77 bets
```

This explains the "selalu kalah Under 2.5" experience.

## What V3 fixes

`model_v2.py` compared 4 variants on held-out test set:

| Variant | U2.5 bias | BTTS bias | Verdict |
|---------|-----------|-----------|---------|
| V0 raw Poisson | +9.2pp | -11.2pp | broken |
| V1 Platt-only (linear calibration) | +1.6pp | +0.0pp | over-corrects, produces 0 picks |
| V2 Dixon-Coles (low-score correlation) | +9.2pp (same as V0) | -10.2pp | barely helps |
| **V3 market-blend + Platt** | +3.9pp | -7.0pp | **best balanced** |

Production model = `model_v3.py`:
- λ_total = 0.4 × form_lambda + 0.6 × market_implied_lambda (devig U/O 2.5)
- Apply Platt calibration per market
- Per-market gate (different threshold for U3.5, U2.5, BTTS)

## Per-market gate decisions

Based on V3 calibration tables:

| Market | Gate | Why |
|--------|------|-----|
| **U3.5** | 65% min, 4ppt gap | Calibrated near-perfect at 65-80% (test diff -3 to +3 pp) |
| **U2.5** | 75% min, 7ppt gap | Residual +3.9pp bias even after blend; need wide buffer |
| **BTTS Yes** | 65% min, 4ppt gap | OK at 60-65% range |
| BTTS No | **BLOCKED** | BTTS Yes systematically underestimated -7 to -11pp |
| 1X2 Home | **BLOCKED** | Out-of-sample: pred 73%, actual 40% (-33pp) |
| 1X2 Draw/Away | **BLOCKED** | Same — 1X2 raw Poisson uncalibrated |

## Files

- `backtest.py` — V0 baseline backtest, demonstrates broken model
- `model_v2.py` — Comparison of V0/V1/V2/V3 variants on held-out test
- `model_v3.py` — **Production model**. Includes `build_model()`, `evaluate_match()`, `gate_v3()`
- `backtest_v3.py` — Out-of-sample validation of V3 + per-market gate
- `E0_2526.csv` — EPL 2025/26 historical data (football-data.co.uk)
- `CLAUDE.md` — Updated agent instructions (v6.0)

## Usage

```python
from model_v3 import build_model, evaluate_match, gate_v3

# Train calibration (once per season)
model = build_model("E0_2526.csv")

# Evaluate a fixture
result = evaluate_match(model, "Liverpool", "Brentford",
    market={
        "u25": 2.56, "o25": 1.46, "u35": 1.734, "o35": 2.281,
        "btts_yes": 1.444, "btts_no": 2.611,
        "home_1x2": 1.929, "draw_1x2": 4.16, "away_1x2": 3.895,
    })

# Filter legs by gate
for leg in result["legs"]:
    ok, reason = gate_v3(leg)
    if ok:
        print(f"PICK: {leg['market']} @ {leg['odds']} (model {leg['model_p']*100:.1f}%, gap +{leg['gap_ppt']:.1f}pp)")
```

## Validation

Out-of-sample 190-match EPL test (`backtest_v3.py`):
- V3 + per-market gate on U2.5: **0 picks** (filter correctly identifies no edge)
- V0 baseline: 46 picks, ROI -7.76%
- V3 actively prevents losing trades

## Limitations

1. **V3 calibrated for EPL only.** Other leagues need own training data. Tier 3 (Vietnam 2nd Div, Kazakhstan, Ethiopia) calibration unknown — `gate_v3` thresholds may not transfer.
2. **Calibration drifts season-over-season.** Re-train at start of each season.
3. **U3.5 gate validated, U2.5 gate filters everything** — by design (V0 -12% ROI history), but means fewer betting opportunities.
4. **No 1X2 betting capability.** Future work: train 1X2 calibrator separately (current 1X2 raw is unreliable).
5. **Sample size for gate-ROI is small.** "+25% ROI" V3 single-fold result based on 3 picks — direction-confirming but not statistically conclusive. The strong evidence is in calibration error reduction, not single-fold ROI.
