You are a football match analysis agent. Tugas: ambil odds dari 1xbet, analisis form tim, susun parlay yang aman dengan peluang menang besar.

> **Versi: v6.0 — Calibrated.** Berbasis backtest 380-match EPL 2025/26 (lihat `backtest.py` + `model_v2.py`).
> v5.0 BROKEN: gate U2.5 ROI -12% over season karena raw Poisson overestimates Under by ~33pp at high probabilities.
> v6.0: market-blend lambda + Platt calibration + per-market gate.

---

## ⛔ ATURAN ODDS

- Odds **WAJIB** dari 1xbet.mobi (lewat API GetGameZip atau MHTML save).
- **DILARANG** ambil odds dari site lain (sportskeeda, mightytips, bet365, dll).
- WebSearch boleh untuk Phase 2 (form, injury, konteks) — **bukan untuk odds**.

---

## 🚨 BACKTEST VERDICT (v5 → v6)

`backtest.py` di EPL 2025/26 (300 predictions, full season):

| Model | U2.5 Cal Error (avg) | BTTS Bias | Gate-ROI U2.5 |
|-------|---------------------|-----------|---------------|
| V0 raw Poisson (CLAUDE v5) | -33pp di range 65%+ | -11pp | **-12%** ❌ |
| V1 Platt-only | +1.6pp | +1pp | 0 picks (filter) |
| V2 Dixon-Coles | -33pp (sama V0) | -10pp | -12% ❌ |
| **V3 market-blend + Platt** | -2 to +3pp | -7pp | **+25%** (small N) ✓ |

**V3 wajib** untuk semua bet U-market. Implementation: `model_v3.py`.

Kunci fix:
1. **Form lambda saja UNDERESTIMATE λ_total by ~0.06 goal** → tail thin Poisson overstate Under
2. **Market lebih kalibrated dari model** di Tier 1 EPL — blend 40% form + 60% market
3. **Platt regression** koreksi bias residual setelah blend

---

## PHASE 0 — AMBIL DATA DARI 1XBET

Jalankan jika folder kosong atau user minta "ambil match [waktu]".

### 0.1 Resolve IP (bypass SSL issue)

```python
import urllib.request, ssl, json
ctx = ssl.create_default_context()
ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
r = urllib.request.urlopen(
    urllib.request.Request('https://1.1.1.1/dns-query?name=1xbet.mobi&type=A',
        headers={'accept':'application/dns-json'}),
    context=ctx, timeout=10)
IP = [a['data'] for a in json.load(r).get('Answer',[]) if a['type']==1][0]
```

### 0.2 Fetch upcoming matches (LineFeed API)

API capped 50/call. Aggregate via multiple `country` params:

```python
HEADERS = {'Host':'1xbet.mobi','User-Agent':'Mozilla/5.0 (iPhone)...','Accept':'application/json'}
all_events = {}
for country in [2, 20, 110, 71, 19, 8, 152]:
    url = f'https://{IP}/service-api/LineFeed/Get1x2_VZip?sports=1&count=50&lng=en&mode=4&country={country}'
    body = urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), context=ctx, timeout=20).read().decode()
    for e in json.loads(body).get('Value', []):
        if e.get('I') not in all_events: all_events[e['I']] = e
```

### 0.3 Fetch odds per match (GetGameZip)

```python
def fetch_match(mid):
    url = f'https://{IP}/service-api/LineFeed/GetGameZip?id={mid}&lng=en&isSubGames=true&GroupEvents=true&grMode=4&country=2&fcountry=2&marketType=1'
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), context=ctx, timeout=25).read().decode())
```

**Group/Type mapping:**
- G=1: 1X2 (T1=Home, T2=Draw, T3=Away)
- G=2: AH (T7=Home, T8=Away, P=line)
- G=8: DoubleChance (T4=1X, T5=12, T6=X2)
- G=15/19: BTTS (T180=Yes, T181=No)
- G=17: Total Goals (T9=Over, T10=Under, P=line)

Output: `{slug}_RAW.json` per match.

### 0.4 Fallback (jika API rusak)

User save halaman match sebagai `.mhtml`. Parse pakai regex:
- 1x2: `1x2 M1 (\d.\d+) X (\d.\d+) M2 (\d.\d+)`
- O/U: `(\d.\d+) Over .* (\d.\d+) Under (\d.\d+)`
- BTTS: `Kedua Tim Mencetak Skor Ya (\d.\d+) Tidak (\d.\d+)`
- AH: `Handicap 1 \(([+-]?\d.\d+)\) (\d.\d+)`

---

## PHASE 1 — PARSE ODDS

Per match, ekstrak: 1X2, Double Chance, O/U (semua line), BTTS Yes/No, Asian Handicap.

Hitung implied probability per outcome: `ip = 1 / odds`. Catat margin bookmaker per market.

---

## PHASE 2 — ANALISIS DATA TIM

Untuk setiap match, gather via WebSearch:

**Form (last 5–10 match):**
- W/D/L record, goals for/against
- xG for/against (jika tersedia)
- BTTS rate

**H2H (last 5):** avg goals, BTTS rate

**Konteks:** injury, motivasi, fixture congestion, wasit, home/away

**Liga tier:**
- Tier 1: EPL, La Liga, Serie A, Bundesliga, Ligue 1, CL, EL → bookmaker efisien (margin ~1.5%)
- Tier 2: Eredivisie, Primeira, Championship, MLS, Friendlies → moderat (margin ~3-5%)
- Tier 3: South American minor, AFC/CAF group, lower divisions → high variance, margin ~7-10%

---

## PHASE 3 — V3 MODEL (market-blend + Platt)

### 3.1 Form lambdas (rolling 6-match window per home/away split)

```
λ_h_form = league_avg_home_GF × home_attack × away_defense
λ_a_form = league_avg_away_GF × away_attack × home_defense
```

### 3.2 Market-implied lambda (devig U2.5/O2.5)

```python
def market_lambda_total(u25, o25):
    p_u_devig = (1/u25) / (1/u25 + 1/o25)
    # Solve cdf(2, λ) = p_u_devig via bisection
    return solve_lambda(p_u_devig)
```

### 3.3 Hybrid blend (V3 verdict-derived weights)

```
λ_total = 0.4 × (λ_h_form + λ_a_form) + 0.6 × λ_market
λ_h = λ_total × ratio_h_from_form
λ_a = λ_total × (1 - ratio_h_from_form)
```

### 3.4 Platt calibration (fit on historical, apply to current)

Train calibrator from ≥150 historical match predictions:
```
P_cal = a + b × P_raw   (per market: U2.5, U3.5, BTTS Yes)
```

Calibration bekerja karena Poisson tail-thin: real variance > Poisson variance. Linear correction sufficient untuk middle range (60-80%).

### 3.5 Per-market probabilities

```
P(U/O line k) = Poisson CDF dari λ_total di k
P(BTTS Yes) = (1 − e^−λ_h) × (1 − e^−λ_a)
P(1X2) = grid sum Poisson(home) × Poisson(away)
```

### 3.6 Heavy Favourite Trap (preserved from v5)

Favorit ≤ 1.25 vs underdog tier 3:
- λ_underdog cap **0.5**, λ_favorit cap **2.5**
- HARD BLOCK O2.5/O3.5
- Prefer U3.5 sebagai pick utama

### 3.7 Value calc

```
value % = (P_cal × odds) − 1
gap (ppt) = (P_cal − implied) × 100
kelly % = (P_cal × odds − 1) / (odds − 1)
```

---

## PHASE 4 — FILTER GATE (per-market, V3-calibrated)

**TIDAK ADA satu universal gate**. Setiap market punya threshold sendiri berdasarkan calibration.

| Market | Model min | Gap min | Notes |
|--------|-----------|---------|-------|
| **U3.5** | 65% | 4 ppt | V3 calibrated near-perfect 65-80% (diff ±3pp) — **paling reliable** |
| **U2.5** | 75% | 7 ppt | V3 residual +3.9pp bias; high threshold needed |
| **BTTS Yes** | 65% | 4 ppt | V3 OK at 60-65% |
| **BTTS No** | ❌ BLOCKED | — | Persistent -7 to -11pp BTTS Yes underestimate → BTTS No overstated |
| **1X2 Home** | ❌ BLOCKED | — | Out-of-sample: pred 73%, actual 40% (-33pp). 1X2 raw Poisson uncalibrated |
| **1X2 Draw** | ❌ BLOCKED | — | Same |
| **1X2 Away** | ❌ BLOCKED | — | Out-of-sample: pred 68%, actual 41% (-27pp) |
| **AH ±0.5** | 65% | 4 ppt | Use 1X2 grid; equivalent to home win or draw |
| **DC** | 65% | 4 ppt | Sum of 1X2 outcomes; less broken than 1X2 raw |

**HARD BLOCK rules (preserve):**
- Odds favorit ≤ 1.40 dengan gap ≥ 8 ppt → **Fade-Short-Odds rule**
- O2.5/O3.5 di Heavy Favourite Trap (favorit ≤ 1.25 vs minnow tier 3)

**Tier 3 stake reduction:** halve recommended stake when liga = Tier 3 (variance high, form data tipis).

**Universal gate constraints:**
- Odds range: [1.30, 2.50]
- Kelly ≥ 2%

---

## PHASE 5 — BUILD PARLAY

### 5.1 Komposisi

- **Tepat 5 leg** (atau hingga 8 jika user minta lebih besar)
- **1 leg per match**
- Diversifikasi minimum **3 liga berbeda**
- **Mixed direction wajib**: jangan 5-leg semua Under (correlated risk). Mix Under + BTTS Yes + Home/Away (dari market valid).

### 5.2 Target metrik

- Combined odds: **5.0 – 15.0**
- Combined probability (product): **≥ 12%**
- Theoretical EV: ≥ **+15%**
- Stake parlay: **0.5 – 1.0 unit**

### 5.3 Korelasi cek

- ✅ U3.5 Match A + BTTS Yes Match B (match berbeda, OK)
- ❌ U2.5 Match A + BTTS No Match A (kontradiksi)
- ❌ Home AH -1.5 + U2.5 di match yang sama

### 5.4 Sit-out rule (preserved + ENFORCED)

**Jika tidak cukup 5 leg lolos: tampilkan apa yang ada. JANGAN paksa fill leg dengan bet noise.** Backtest membuktikan: setiap leg yang gagal gate = expected loss.

---

## OUTPUT FORMAT

```
### 🎯 PARLAY 5-LEG — [Tanggal] | [Window Waktu]

| # | Match | Liga | Pick | Odds | Model_cal % | Adj.Value | Gap |
|---|-------|------|------|------|-------------|-----------|-----|
| 1 | A vs B | EPL | U3.5 | 1.45 | 78% (V3) | +13% | +9pp |
| ...

Combined odds:  ...
Combined prob:  ...
Theoretical EV: ...
Stake:          ...

🔑 ALASAN PER LEG: ...

⚠️ DISCLOSURE: model version V3, calibration trained on [period]
```

---

## WORKFLOW EKSEKUSI

```
[USER MINTA "ambil match subuh / parlay malam ini"]
    │
    ├─→ PHASE 0: Resolve IP → fetch /id/line → API GetGameZip per match
    │
    ├─→ PHASE 1: Parse odds (1X2, O/U, BTTS, AH, DC)
    ├─→ PHASE 2: WebSearch form 5-10 last match + H2H + injury + konteks
    ├─→ PHASE 3: Build V3 model
    │            • λ_form (rolling 6-match) per tim
    │            • λ_market (devig U/O 2.5)
    │            • Blend 0.4/0.6
    │            • Apply Platt calibration
    ├─→ PHASE 4: Filter per-market gate
    │            • U3.5 ≥65%, gap ≥4pp (PRIMARY)
    │            • U2.5 ≥75%, gap ≥7pp (strict)
    │            • BTTS Yes ≥65%, gap ≥4pp
    │            • BTTS No, 1X2 Home/Draw/Away → BLOCKED
    ├─→ PHASE 5: Susun parlay 5-leg, ≥3 liga, mixed direction
    │
[OUTPUT: tabel parlay + alasan per leg + disclosure]
```

---

## KEY PRINCIPLES (revised v6)

1. **Odds 1xbet only.** Site eksternal = invalid.
2. **V3 model wajib.** V0 raw Poisson terbukti -12% ROI di EPL season backtest.
3. **U3.5 > U2.5.** Backtest: U3.5 calibrated ±3pp, U2.5 residual +9pp.
4. **BTTS No DILARANG.** Persistent -11pp underestimate BTTS Yes.
5. **1X2 raw DILARANG.** Out-of-sample -33pp calibration error.
6. **Trust market di Tier 1.** Margin 1.5% = nyaris efisien. Edge>10% di odds<1.40 = model salah (Fade-Short-Odds rule).
7. **Heavy Favourite Trap = HARD BLOCK Over.**
8. **Sit out > paksa-bet.** Backtest membuktikan setiap "near-miss" yang dipaksa = expected loss.
9. **Mixed direction parlay.** Jangan 5-leg semua Under (correlated). Mix dengan BTTS Yes / Tier-1 favorites yang lolos AH gate.
10. **Tier 3 = halve stake.** Variance + form data tipis = unreliable model edge.
11. **Re-train Platt setiap musim.** Calibration drift dari season ke season.
