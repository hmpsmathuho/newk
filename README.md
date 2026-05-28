# Best Value Bet Analyzer

Implementasi sistem analisis value bet dari `SPEC.md`. Input file `.mhtml`
hasil simpan halaman 1xbet.mobi → output daftar value bet ranked by edge.

## Quick Start

```bash
# Single match
python3 main.py --input 1.mhtml --top 10

# All match files in directory, save aggregate JSON
python3 main.py --input-dir . --output-dir results --top 10

# Hide blocked markets (cleaner output)
python3 main.py --input-dir . --no-blocked
```

## What it does

1. **Parser** (`src/parser/`) — decode MHTML, extract markets via regex
   (1X2, DC, BTTS, Total Goals, Asian Handicap full + quarter, Total Asia
   quarter, Halftime totals, HT 1X2, Team Totals).
2. **Model** (`src/model/poisson.py`) — derive λ_total from devigged
   Over/Under 2.5 odds, split into home/away via 1X2 grid search,
   compute every market probability via Poisson + Dixon-Coles ρ=-0.10.
3. **Value calculator** (`src/value/edge_calculator.py`) — for each
   selection: devig margin, compute edge & Kelly, apply per-market gate
   (model_min + gap_min from config) and Fade-Short-Odds rule.
4. **Ranker** (`src/value/ranker.py`) — sort passed legs by edge,
   compute quarter-Kelly stake.
5. **Output** (`src/output/exporter.py`) — terminal table + JSON.

## Project Structure

```
.
├── SPEC.md                        # Original specification
├── README.md                      # This file
├── config.yaml                    # Per-market gate thresholds, Kelly fraction
├── requirements.txt               # (stdlib-only; PyYAML optional)
├── main.py                        # CLI entrypoint
├── src/
│   ├── parser/
│   │   ├── mhtml_parser.py        # MHTML → text
│   │   └── odds_extractor.py      # text → markets dict (regex)
│   ├── model/
│   │   └── poisson.py             # λ-from-market + DC + grid → probs
│   ├── value/
│   │   ├── edge_calculator.py     # devig + edge + gate
│   │   └── ranker.py              # sort + Kelly
│   └── output/
│       └── exporter.py            # terminal / JSON / CSV
├── data/
│   ├── input/                     # (optional; can read from CWD)
│   └── cache/                     # external API cache (unused for now)
├── results/
│   ├── all_matches.json
│   ├── full_terminal.txt
│   └── REPORT.md
└── *.mhtml / *.mobi               # match files
```

## Latest Run Results

See `results/REPORT.md` for full analysis. Summary:
- 7 input files processed
- 4 value bets identified (top edge: +13.4%)
- 3 sit-out (no edge); 1 file is history slip (no match data)

## Limitations

- **No external data** (form/injury/motivation) yet — pure odds-internal.
  SPEC sections 4 & 5 (External Data API, Elo) not implemented.
- **No backtest validation** — edge claims are theoretical based on
  Poisson model assumptions.
- **EPL-style markets only** — parser tested on 1xbet.mobi/id Indonesian
  layout. Other languages/bookmakers need parser tweaks.
- **Recency-weighted form, injury impact, motivation** — currently no-op
  in `compute_probabilities()`. Add via `adjustments.py` when data
  source is wired.

## Disclaimer

Model probabilistik. Value bet ≠ guaranteed win. Selalu manage bankroll.
Lihat `SPEC.md` section 10.
