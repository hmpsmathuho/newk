# 🎯 PARLAY ANALYSIS — EPL Matchday 38, 24 May 2026

> Sumber odds: 1xbet.mobi (parsed dari 5 file `.mhtml` saved 24/05/2026 21:43 SGT)
> Margin bookmaker rata-rata: ~1.55% (sangat tight, khas Tier 1 EPL)
> ⚠️ Konteks: ini matchday TERAKHIR EPL 2025-26. Final-day = motivasi chaos.

---

## Phase 1 — Odds Snapshot (key markets)

| Match | 1X2 (H/D/A) | BTTS Y/N | O2.5/U2.5 | O3.5/U3.5 |
|-------|-------------|----------|-----------|-----------|
| Burnley vs Wolves | 2.603 / 3.435 / 2.939 | 1.66 / 2.116 | 1.96 / **1.98** | 3.04 / **1.32** |
| Brighton vs Man Utd | 2.000 / 4.160 / 3.635 | 1.43 / 2.662 | 1.45 / 2.59 | 2.281 / **1.734** |
| West Ham vs Leeds | 1.692 / 4.400 / 5.070 | 1.615 / 2.189 | 1.67 / 2.402 | 2.43 / **1.48** |
| Crystal Palace vs Arsenal | 4.000 / 3.655 / 2.032 | 1.71 / 2.04 | 1.939 / 2.001 | 3.04 / 1.34 |
| Liverpool vs Brentford | 1.929 / 4.160 / 3.895 | 1.444 / 2.611 | 1.46 / 2.56 | 2.281 / **1.734** |

---

## Phase 2 — Konteks Tim (kunci pre-match)

| # | Match | Konteks Kritis |
|---|-------|----------------|
| 1 | Burnley vs Wolves | **Both already RELEGATED** (sejak April). Wolves attack TERLEMAH EPL (26 GF/37). Burnley 6L dari 7. "Neither side can buy a win, both spent". Pertarungan 19 vs 20. |
| 2 | Brighton vs Man Utd | Brighton fight Europa Conference (slot 8). MUN safe at 3rd, **missing Sesko/De Ligt/Ugarte**. Carrick first match as permanent. 4 H2H terakhir: BTTS Yes semua. |
| 3 | West Ham vs Leeds | West Ham **HARUS MENANG** untuk peluang lolos relegasi (tergantung Spurs). WH home form W3 D3 L1 last 7. Leeds safe at 14, "toothless" di away. |
| 4 | Palace vs Arsenal | Arsenal **CHAMPIONS sudah confirmed** — coronation match. **HEAVY ROTATION** (Raya/Rice/Saka/Havertz dirested). Palace ada Europa Conference final → juga proteksi pemain. |
| 5 | Liverpool vs Brentford | **Salah & Robertson farewell** Anfield. LFC butuh ≥1 poin untuk CL5. "Failed clean sheet last 6". Brentford safe at 9th, dead rubber. |

---

## Phase 3 — Poisson Model (λ + adjustment)

| Match | λ_home | λ_away | Total λ | Adjustment Reasoning |
|-------|--------|--------|---------|----------------------|
| Burnley-Wolves | 1.080 | 0.945 | 2.025 | base ~1.20/1.05 × 0.90 each (-10% relegated+spent) |
| Brighton-MUN | 1.340 | 1.421 | 2.661 | MUN -7% (3 starters absent + dead rubber) |
| West Ham-Leeds | 1.732 | 0.782 | 2.514 | WH +5% (must-win), Leeds -8% (toothless dead rubber) |
| Palace-Arsenal | 1.140 | 1.232 | 2.372 | Arsenal -15% (4 starters rested + celebration mode) |
| Liverpool-Brent | 1.500 | 1.330 | 2.830 | Brent -5% (safe), LFC neutral |

---

## Phase 4 — Filter Hasil (gate: model≥65%, value≥4%, gap≥4ppt, odds 1.30-2.50, kelly≥2%)

### ✅ LEGS YANG LOLOS

| # | Match | Pick | Odds | Model% | Value | Gap (ppt) | Kelly |
|---|-------|------|------|--------|-------|-----------|-------|
| 1 | Burnley vs Wolves | **U2.5** | 1.98 | 67.0% | +32.6% | +16.5 | 33.3% |
| 2 | Brighton vs Man Utd | **U3.5** | 1.734 | 72.3% | +25.3% | +14.6 | 34.5% |
| 3 | West Ham vs Leeds | **U3.5** | 1.48 | 75.4% | +11.7% | +7.9 | 24.3% |
| 4 | Liverpool vs Brentford | **U3.5** | 1.734 | 68.5% | +18.8% | +10.9 | 25.6% |

### ❌ BLOCK / NO-PASS

| Match | Considered | Reason |
|-------|------------|--------|
| Burnley-Wolves U3.5 @ 1.32 | model 85.3%, gap +9.5 | **HARD BLOCK** — Fade-Short-Odds rule (odds≤1.40 + gap≥8ppt) |
| Crystal Palace vs Arsenal | best=U3.5 1.34 model 78.4% | Gap +3.82 ppt — fails 4ppt threshold by 0.18ppt; sit out |

---

## Phase 5 — Final Parlay (4 leg, BUKAN 5)

```
### 🎯 PARLAY 4-LEG — Minggu 24/05/2026 | EPL Matchday 38

| # | Match                   | Liga | Pick | Odds  | Model % | Value  | Gap   |
|---|-------------------------|------|------|-------|---------|--------|-------|
| 1 | Burnley vs Wolves       | EPL  | U2.5 | 1.98  | 67.0%   | +32.6% | +16.5 |
| 2 | Brighton vs Man Utd     | EPL  | U3.5 | 1.734 | 72.3%   | +25.3% | +14.6 |
| 3 | West Ham vs Leeds       | EPL  | U3.5 | 1.48  | 75.4%   | +11.7% |  +7.9 |
| 4 | Liverpool vs Brentford  | EPL  | U3.5 | 1.734 | 68.5%   | +18.8% | +10.9 |

──────────────────────────────────────────
Combined odds  : 8.811
Combined prob  : 25.02%
Break-even     : 11.35%
Theoretical EV : +120.4%
Edge over BE   : +13.67 ppt
Stake (rec.)   : 0.3-0.5 unit (DI BAWAH normal 0.5-1.0 karena correlated risk)
Potensi return : ~2.6-4.4 unit
──────────────────────────────────────────
```

### 🔑 Alasan per leg

1. **Burnley vs Wolves U2.5** — Both sides relegated, no stakes. Wolves attack terlemah EPL (0.68 GF/match), Burnley spent 6L/7. Bahkan tanpa adjustment motivasi, total λ < 2.5 sangat realistic. Catatan: model 67% hanya tipis di atas gate 65% — leg paling tipis. (Pilih U2.5 bukan U3.5 karena U3.5 kena Fade-Short-Odds rule.)

2. **Brighton vs Man Utd U3.5** — Total λ 2.66, P(≤3) = 72.3%. MUN missing 3 starters, Brighton home tapi defense moderat. Market price U3.5 1.734 = 57.7% implied; gap +14.6 ppt = best value play. Walaupun H2H BTTS-heavy, BTTS ≠ banyak gol.

3. **West Ham vs Leeds U3.5** — West Ham must-win akan tekan tapi finishing terbatas (38 GF musim ini, dari Leeds yang "toothless" away). Total λ 2.51, P(≤3) 75.4%. Leg paling solid secara probability.

4. **Liverpool vs Brentford U3.5** — Highest λ di parlay (2.83) tapi tetap di bawah 4 goals threshold. Liverpool inkonsisten (19 losses semua kompetisi, no clean sheet last 6) tapi Brentford safe = tak agresif. Emotional farewell match cenderung slow tempo babak 1, late goals.

---

## ⚠️ DISCLOSURE / FLAGS

1. **Diversifikasi liga FAIL** — semua 4 leg dari EPL. CLAUDE.md mensyaratkan minimum 3 liga berbeda. Karena user hanya menyediakan 5 file EPL, ini unavoidable. **Konsekuensi**: leg-leg ini tidak fully anti-correlated.

2. **Direction-correlation FAIL** — semua 4 leg adalah "Under" di gameweek yang sama. Jika EPL final-day ternyata high-scoring (efek "no defensive intensity"), multiple leg bisa kalah bersamaan.

3. **Burnley-Wolves U2.5 borderline** — model 67% hanya tipis di atas gate 65%. Market price 50/50 (1.96/1.98). Edge +16.5 ppt looks suspicious di Tier 1 EPL dengan margin 1.5%. Mungkin bookmaker right dan model salah. Pertimbangkan **drop leg ini** untuk 3-leg lebih aman:

```
Alternatif konservatif 3-leg (drop leg #1):
Combined odds: 1.734 × 1.48 × 1.734 = 4.451
Combined prob: 0.723 × 0.754 × 0.685 = 37.34%
Break-even: 22.46%
EV: +66.2%
```

4. **Crystal Palace-Arsenal sit out** — closest leg (U3.5) gagal gate 4ppt by hair-thin 0.18ppt. Per prinsip "sit out > paksa-bet", saya keluarkan dari parlay. Adding it would make parlay +18.5% riskier without commensurate value.

5. **Stake recommendation 0.3-0.5 unit** (di bawah normal CLAUDE 0.5-1.0) karena correlated direction (semua Under) + diversifikasi gagal.

---

## Markets yang DIPERTIMBANGKAN tapi ditolak

- **AH (full-line) integer**: tidak diparlaykan karena push behavior susah dimodel di parlay context
- **AH ±0.25/±0.75 Asian quarter**: skipped — split-stake mechanics tidak clean untuk parlay
- **BTTS No** di Burnley-Wolves: model 59.6% < 65% gate
- **DC X2** Brighton-MUN: model 62.6% < 65% gate
- **Home win 1X2** West Ham: model 60% < 65% gate
