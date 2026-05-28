# Best Value Bet Analyzer — Report v1.1

Hasil run dari 3 subcommand sesuai SPEC.md sections 4, 5, dan validation.

---

## 1. `analyze` — value bets dengan form/injury context

`python3 main.py analyze --input-dir . --output-dir results --no-blocked`

**Match files diproses (7 file):**
- 5 EPL `.mhtml` (Matchweek 38, 24 May 2026)
- Liga Irlandia `.mobi` (Shelbourne vs Waterford, 22 May)
- `1xBet.mhtml` (history slip — bukan match, masuk SIT OUT)

**9 value bets diidentifikasi** (vs 4 picks sebelum form context):

| Match | Pick | Odds | P_riil | Edge | Source |
|-------|------|------|--------|------|--------|
| Crystal Palace vs Arsenal | Total Asia Under 2.25 | 2.30 | 59.6% | **+37.3%** | Arsenal heavy rotation |
| Crystal Palace vs Arsenal | Total Asia Under 2.75 | 1.80 | 69.8% | **+25.5%** | Champions, Palace Conf final |
| Burnley vs Wolves | Total Asia Under 2.25 | 2.29 | 54.1% | **+23.8%** | Both relegated, dead rubber |
| Brighton vs Man Utd | AH Away (Q) +0.25 | 2.22 | 53.3% | **+18.3%** | Sesko/Casemiro out |
| Liverpool vs Brentford | AH Away (Q) +0.25 | 2.33 | 50.5% | **+17.5%** | Salah farewell, no clean sheets |
| Burnley vs Wolves | Total Asia Under 2.75 | 1.78 | 64.8% | **+15.4%** | (form-adjusted -10% lambdas) |
| Crystal Palace vs Arsenal | Total Asia Under 3.25 | 1.41 | 79.9% | **+13.0%** | (rotation lowers λ to 2.71) |
| Burnley vs Wolves | AH Away (Q) +0.25 | 1.78 | 62.0% | **+10.2%** | (Wolves +0.25 cushion) |
| West Ham vs Leeds | AH Home (Q) -0.75 | 1.77 | 61.8% | **+9.4%** | WH must-win, Leeds toothless |

Form context source: `src/external/team_form.py` — multipliers di-cap ke ±20% via `src/model/adjustments.py`.

---

## 2. `live` — analyze upcoming dari 1xbet API

`python3 main.py live --window-hours 12 --max-matches 8 --top 5`

**Implementasi `src/external/onexbet_client.py`:**
- DNS-over-HTTPS resolve ke 83.147.204.86 (Cloudflare DoH)
- Aggregate 50/call × multiple country params
- `parse_apivalue_to_markets()` convert API JSON → schema yang sama dengan parser MHTML

**Run pada 8 match upcoming (Finland Div 4 + Estonian league):**
- Top edge: **+180.6%** (Metso vs Vaajakoski 2, Team Total Home Over)
- Top picks dominasi Team Total markets di liga rendah (high λ, market less efficient)

⚠️ **Caveat penting:** liga Tier-3 amateur (Finland Div 4) punya:
- Margin bookmaker tinggi (5–8% vs ~1.5% di EPL)
- Variance besar
- Form data tipis di curated DB — fallback ke neutral 1.0x

Edge claims di liga ini lebih spekulatif dari EPL — perlu hati-hati.

---

## 3. `backtest` — validate model vs hasil aktual

`python3 main.py backtest --input-dir . --top 10`

**Test set:** 5 EPL `.mhtml`, hasil aktual diketahui dari ESPN/Sky Sports/Guardian.

```
Total picks:    9
Evaluable:      9
W / L / P:      7 / 2 / 0
Hit rate:       77.8% (excluding pushes)
Flat-stake P/L: +4.58 units (1u per pick)
ROI:            +50.89%
```

### Per-market breakdown

| Market | N | W | L | Hit% | P/L |
|--------|---|---|---|------|-----|
| AH (quarter) | 4 | 4 | 0 | **100%** | +4.10 |
| Totals Asia | 5 | 3 | 2 | 60% | +0.48 |

**AH Quarter sweep 4-0**:
- Burnley AH Away +0.25 ✓ (1-1 → +0.25 cover)
- Brighton AH Away +0.25 ✓ (Man Utd 3-0 → cover)
- West Ham AH Home -0.75 ✓ (3-0 → cover)
- Liverpool AH Away +0.25 ✓ (Brentford 1-1 → +0.25 cover)

**Totals Asia 3-2**:
- Burnley Under 2.25 ✓ (1-1 = 2 < 2.25)
- Burnley Under 2.75 ✓ (1-1 = 2 < 2.75)
- Crystal Palace Under 3.25 ✓ (1-2 = 3 < 3.25)
- Crystal Palace Under 2.25 ✗ (1-2 = 3 > 2.25)
- Crystal Palace Under 2.75 ✗ (1-2 = 3 > 2.75)

### Calibration

| Bucket | N | Predicted | Actual | Diff |
|--------|---|-----------|--------|------|
| 0.50–0.60 | 4 | 54.4% | 75.0% | +20.6pp |
| 0.60–0.70 | 4 | 64.6% | 75.0% | +10.4pp |
| 0.70–0.80 | 1 | 79.9% | 100.0% | +20.1pp |

Model **underestimates** aktual hit rate by ~10–20pp — implementasinya terlalu konservatif. Sample size kecil (9 picks) tapi direction konsisten: model honest, tidak overstate. Itu kebalikan dari V0 raw Poisson di session sebelumnya yang **overstate by -33pp**.

---

## 4. Lessons & Caveats

### Yang berhasil
- ✅ **Backtest +50.89% ROI** dengan 7/9 hit rate di EPL MD38 — jauh lebih baik dari V0 raw Poisson sesi sebelumnya (-12% ROI)
- ✅ Form context (Section 5) memberi **+5 picks tambahan** vs run tanpa context — context membuat model lebih bisa identify edge yang sebelumnya tertutup baseline λ
- ✅ AH Quarter (+0.25) consistent winner — ini di mana market 1xbet least efficient
- ✅ Live API client (Section 4) functional — bisa fetch 200+ markets per match

### Yang perlu validate ulang
- Sample size 9 picks **tidak cukup** untuk klaim ROI sustainable
- Form context curated only untuk 6 match — perlu otomatisasi via API atau scraping
- AH Quarter sweep 4-0 mungkin **lucky variance** — perlu test di matchday lain
- Calibration positive bias (+10-20pp) artinya model conservative, **tapi belum verified di sample besar**

### Yang harus dilakukan kalau pakai production
1. **Train calibrators** seperti yang dilakukan di session sebelumnya, dari historical CSV per liga
2. **Otomatisasi form data** via API (api-football $19/mo) atau scraping (BeautifulSoup + caching)
3. **Re-test backtest** setiap matchday baru, track rolling ROI 50-100 picks
4. **Stake disiplin** — Kelly/4 capped 5% bankroll, jangan gabung jadi parlay 5-leg (variance kill)

---

## Files

| File | Purpose |
|------|---------|
| `results/all_matches.json` | Per-match analyze JSON output |
| `results/backtest.json` | Backtest detail per pick |
| `results/live.json` | Live API analyze snapshot |
| `results/analyze_terminal.txt` | Human-readable analyze output |
| `results/backtest_terminal.txt` | Human-readable backtest report |
| `results/live_terminal.txt` | Human-readable live snapshot |
| `data/cache/team_form.json` | Cache untuk form context (akan auto-populate kalau pakai `store_team_context()`) |

---

## Disclaimer

Model probabilistik. Backtest 9 picks **bukan** sample size produksi.  
Edge claim adalah **theoretical EV** berdasarkan asumsi Poisson + Dixon-Coles + form adjustments.  
Selalu verify lineup resmi 1 jam sebelum kickoff. Manage bankroll disiplin.
