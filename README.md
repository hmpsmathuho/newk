# Best Value Bet Analyzer

Implementasi sistem analisis value bet dari `SPEC.md`.  
Input file `.mhtml` / `.mobi` hasil simpan halaman 1xbet.mobi → output daftar value bet ranked by edge.  
Plus subcommand `live` untuk fetch langsung dari 1xbet API, dan `backtest` untuk validate model vs hasil aktual.

## Quick Start

```bash
# Analyze single match file
python3 main.py analyze --input 1.mhtml --top 10

# Batch analyze all .mhtml/.mobi files in directory
python3 main.py analyze --input-dir . --output-dir results --no-blocked

# Fetch upcoming matches from 1xbet API and analyze (next 24 hours)
python3 main.py live --window-hours 24 --max-matches 20

# Backtest: validate model on workspace .mhtml vs known results
python3 main.py backtest --input-dir . --output results/backtest.json
```

## Architecture (per SPEC.md)

```
┌──────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Input MHTML │ ──▶ │  Parser & Norm  │ ──▶ │  Odds Markets   │
└──────────────┘     └─────────────────┘     └─────────────────┘
        │                                              │
   ┌────┴────┐                                         │
   │  Live   │                                         │
   │ 1xbet   │                                         │
   │   API   │                                         │
   └─────────┘                                         │
                            ┌────────────────────┐    │
                            │ External Form API  │ ◀──┘
                            │   (team_form.py)   │
                            └────────────────────┘
                                     │
                                     ▼
                       ┌─────────────────────────────┐
                       │  Probability Model           │
                       │  (Poisson + Dixon-Coles      │
                       │   + form λ-adjustment)       │
                       └─────────────────────────────┘
                                     │
                                     ▼
                       ┌─────────────────────────────┐
                       │  Value Bet Ranker           │
                       │  (devig + edge + Kelly      │
                       │   + per-market gate)        │
                       └─────────────────────────────┘
                                     │
                                     ▼
                              Best Bets Output

```

## SPEC compliance

| Section | Implementation | File(s) |
|---------|----------------|---------|
| 3. Input MHTML | ✅ | `src/parser/mhtml_parser.py`, `odds_extractor.py` |
| 4. External Data API | ✅ via 1xbet LineFeed | `src/external/onexbet_client.py` |
| 5. Form & Elo adjustments | ✅ via curated DB + ±20% cap | `src/external/team_form.py`, `src/model/adjustments.py` |
| 5. Poisson + DC model | ✅ | `src/model/poisson.py` |
| 6. Output (best bets) | ✅ JSON + terminal + CSV | `src/output/exporter.py` |
| 7. Project structure | ✅ | (see below) |
| 8. CLI parameters | ✅ | `main.py` |
| 9. config.yaml | ✅ | `config.yaml` |
| 10. Disclaimers | ✅ | this README + `results/REPORT.md` |
| **+ Validation** | ✅ Backtest vs hasil aktual | `src/backtest/validator.py` |

## Project Structure

```
.
├── SPEC.md                          # Original specification
├── README.md                        # This file
├── config.yaml                      # Per-market gate thresholds, Kelly fraction
├── requirements.txt
├── main.py                          # CLI entrypoint (subcommands)
├── src/
│   ├── parser/
│   │   ├── mhtml_parser.py          # MHTML → text
│   │   └── odds_extractor.py        # text → markets dict
│   ├── external/
│   │   ├── onexbet_client.py        # 1xbet LineFeed API
│   │   └── team_form.py             # form/injury context store
│   ├── model/
│   │   ├── poisson.py               # λ derivation, DC, grid → probs
│   │   └── adjustments.py           # form multipliers (±20% cap)
│   ├── value/
│   │   ├── edge_calculator.py       # devig + edge + per-market gate
│   │   └── ranker.py                # sort + Kelly stake
│   ├── output/
│   │   └── exporter.py              # terminal / JSON / CSV
│   └── backtest/
│       └── validator.py             # ground-truth scoring
├── data/
│   ├── input/
│   └── cache/                       # team_form.json cache
├── results/
│   ├── REPORT.md                    # Full run report
│   ├── all_matches.json
│   ├── backtest.json
│   ├── live.json
│   └── *_terminal.txt
└── *.mhtml / *.mobi                 # match files
```

## Key Results

Lihat `results/REPORT.md` untuk full breakdown. Ringkasan:

- **Backtest 9 picks @ EPL Matchweek 38:** 7W / 2L / 0P, **+50.89% ROI**
- **AH Quarter (+0.25) sweep:** 4/4 winners
- **Form context** memberi +5 picks tambahan vs baseline
- **Live API:** functional di Finland/Estonian liga (caveat: high variance)

## Limitations

- Form DB hand-curated untuk 6 match — perlu otomasi untuk produksi
- 9-pick backtest **bukan** sample size produksi (variance besar)
- Liga Tier 3+ uncalibrated form → model mostly neutral untuk match non-EPL
- AH Quarter winner pattern bisa lucky variance — re-test di matchday lain

## Usage Tips

1. **Selalu cek context output** — kalau "source: neutral", artinya tidak ada curated form data
2. **Jangan parlay 5-leg** — variance kill walaupun edge positive
3. **Stake Kelly/4** capped 5% bankroll (default config)
4. **Verify lineup resmi** ~1 jam sebelum kickoff sebelum bet

## Disclaimer

Model probabilistik. Edge ≠ guaranteed win. Bet bertanggung jawab.  
Lihat `SPEC.md` section 10 untuk lebih detail.
