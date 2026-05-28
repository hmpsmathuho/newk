# Model V3.1 — Production Calibrated Model + Extended Markets

## Story

V5 of CLAUDE.md → BROKEN raw Poisson, U2.5 ROI -12% over season.
V3.0 (model_v3.py) → market-blend + Platt fixed U2.5/U3.5/BTTS Yes, but BLOCKED 1X2.
**V3.1 (now)** → unlocks 1X2 via Platt calibration + Dixon-Coles ρ + supports 20+ bet types.

## Backtest verdict

`backtest.py` (V0 raw Poisson, full EPL 2025/26):
```
U2.5 calibration error by predicted bucket:
  65-70%: -25.1 pp     70-75%: -41.1 pp
  75-80%: -21.5 pp     80-90%: -47.1 pp

Gate sim: 77 picks U2.5, ROI -12.17%
```

`model_v2.py` variant comparison on held-out:

| Model | U2.5 bias | BTTS bias | 1X2 cal | ROI gate |
|-------|-----------|-----------|---------|---------|
| V0 raw | +9.2pp | -11.2pp | -33pp | -12% |
| V1 Platt-only | +1.6pp | +0pp | — | 0 picks |
| V2 Dixon-Coles | +9.2pp | -10.2pp | — | -12% (sama V0) |
| **V3 mkt-blend+Platt** | +3.9pp | -7pp | BLOCKED | +25% (small N) |
| **V3.1 + ρ + 1X2 calib** | +3.9pp | -7pp | ±5pp at 65%+ | TBD on next season |

## V3.1 architecture

```
form λ (rolling 6-match)              \
                                        → 0.4 × form + 0.6 × market = λ
market-implied λ (devig U/O 2.5)      /
                                       
λ → Dixon-Coles ρ adjustment → score grid → market probabilities → Platt calibration
                                                              ↓
                                                      Per-market gate
                                                              ↓
                                                      Pass / Block decision
```

## Calibrators (V3.1 trained on EPL 2025/26, 300 preds)

```
u25:       a=0.470, b=-0.056   (negative slope = corrects raw overestimate)
u35:       a=0.585, b=+0.172
btts_yes:  a=0.502, b=+0.140
home_1x2:  a=0.178, b=+0.562   (NEW V3.1)
draw_1x2:  a=0.339, b=-0.224   (NEW V3.1)
away_1x2:  a=0.172, b=+0.398   (NEW V3.1)
ht_u15:    a=0.756, b=-0.172   (NEW V3.1)
ht_u25:    a=1.109, b=-0.258   (NEW V3.1)
```

Dixon-Coles ρ = -0.15 (fitted via grid-search MLE). Empirical HT/FT ratio = 0.445.

## Per-market gate (V3.1)

See CLAUDE.md Phase 4 table. Key:
- ✓ Calibrated reliable: U3.5 (65%), U2.5 (75%), BTTS Yes (65%), 1X2 (65%), HT U1.5/2.5
- ⚠ Uncalibrated cautious: AH, AHQ, Team Totals — **EPL only**
- ❌ BLOCKED: BTTS No, Win-to-Nil No

## Bet types supported

20+ types matching 1xbet history slip:

| Indonesian (1xbet) | Code | Status |
|--------------------|------|--------|
| Total Under (X.X) | U{line} | ✓ calibrated |
| Total Over (X.X) | O{line} | ⚠ uncal |
| 1x2: M1/X/M2 | 1X2_HOME/DRAW/AWAY | ✓ calibrated V3.1 |
| Double Chance: 1X/12/X2 | DC_1X/12/X2 | ⚠ derived |
| Kedua Tim Mencetak — Ya | BTTS_YES | ✓ calibrated |
| Kedua Tim Mencetak — Tidak | BTTS_NO | ❌ BLOCKED |
| Handicap Asia (full) | AH_HOME/AWAY_{line} | ⚠ EPL-only |
| Handicap Asia (Quarter) | AHQ_HOME/AWAY_{line} | ⚠ EPL-only |
| Tim 1/2 Total Over/Under | TT_HOME/AWAY_O/U{line} | ⚠ EPL-only |
| Total Babak Pertama (HT) | HT_O/U{line} | ✓ calibrated |
| 1x2 Babak Pertama | HT_1X2_HOME/DRAW/AWAY | ⚠ uncal |
| Total Genap/Ganjil | TOTAL_ODD/EVEN | ⚠ uncal |
| Win to Nil — Ya | HOME/AWAY_WIN_TO_NIL_YES | ⚠ uncal |
| Hasil + BTTS | HOME/DRAW/AWAY_AND_BTTS_YES | ⚠ uncal |

## Test Results

**EPL 5 mhtml (calibrated history):**
- 5 matches → 6 passing legs
- 2 calibrated U3.5 picks (Brighton, Liverpool)
- 4 uncalibrated AH/DC picks (with warning)
- 2 sit-out matches (West Ham, Palace) — gate honest no-edge

**Non-EPL 15 RAW (fallback mode):**
- 15 matches → 0 passing legs
- All AH/AHQ/TT correctly BLOCKED (no calibration available)
- Honest "sit out" output

## Usage

```python
import model_v3 as m3
import model_v3_extended as m3e

# Train (once per season)
model = m3.build_model("E0_2526.csv")

# Evaluate (with raw 1xbet GetGameZip Value dict)
result = m3e.evaluate_all_markets(model, "Liverpool", "Brentford", raw_value)

# Output 1xbet-style
print(m3e.format_output_1xbet_style(result, max_legs=10, show_blocked=True))

# Or programmatic access
for leg in result["passing_legs"]:
    print(f"{leg['market']}: {leg['odds']} @ {leg['model_p']*100:.1f}% (gap +{leg['gap_ppt']:.1f}pp)")
```

## Limitations

1. **EPL-trained only.** Non-EPL legs (AH, AHQ, TT) blocked by gate. Need per-league CSV training.
2. **HT 1X2 uncalibrated** — uses naive ht_ratio scaling. Calibrate next.
3. **Player-level markets unsupported** — Goalscorer, Time of First Goal, Booking range.
4. **Correct Score** — too high variance, blocked.
5. **Re-train per season** — calibration drifts.

## Files

- `model_v3.py` — Core (build_model, evaluate_match, gate_v3)
- `model_v3_extended.py` — Extended (parse_market_from_raw, evaluate_all_markets, format_output_1xbet_style)
- `backtest.py` — V0 baseline backtest
- `backtest_v3.py` — V3 out-of-sample validation
- `model_v2.py` — Variant comparison (V0/V1/V2/V3)
- `parse_odds.py` — MHTML fallback parser
- `phase0_fetch.py` / `phase0_match_odds.py` — Phase 0 API helpers
- `E0_2526.csv` — EPL 2025/26 training data
