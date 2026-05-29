# 🎯 PARLAY 5-LEG — Jumat 29 Mei 2026 | Window 19:00-22:30 WIB

> **Sumber odds**: 1xbet.mobi via service-api `LineFeed/GetGameZip` (29/05/2026 ~12:00 WIB).
> **Margin bookmaker**: rata-rata ~3-5% (mid-tier liga).
> **Konteks slate**: 2 dead-rubber Egypt PL relegation final round, 1 tier-2 China SL match (skip-no-pass), 1 Belarus mid-season, 1 friendly intl, 1 Uzbek tier-2.

## Phase 1 — Odds Snapshot (key markets, 5 match terpilih)

| Match | 1X2 (H/D/A) | BTTS Y/N | O/U 2.5 | O/U 3.5 |
|-------|-------------|----------|---------|---------|
| El Mokawloon vs Modern Sport | 2.43/2.61/3.28 | 2.11/1.636 | 2.56/1.4 | 4.8/1.114 |
| Naftan Novopolotsk vs Torpedo-BelAZ | 5.44/4.2/1.55 | 1.87/1.833 | 1.85/1.92 | 2.99/1.3 |
| Fergana State Univ vs Olimpik MobiUZ | 1.67/3.64/4.38 | 1.71/1.983 | 1.76/1.93 | 2.83/1.33 |
| ZED vs Kahrbaa Alasmalia | 2.52/3.05/2.59 | 1.87/1.816 | 2.19/1.6 | 3.92/1.176 |
| Iran vs Republic of the Gambia | 1.618/4.06/6.39 | 2.05/1.686 | 2.111/1.829 | 3.34/1.24 |

## Phase 2 — Konteks Tim (kunci pre-match)

| # | Match | Konteks Kritis |
|---|-------|----------------|
| 1 | El Mokawloon vs Modern Sport | **FINAL ROUND, both safe** (Pharco/Haras/Kahrbaa-Ismailia sudah turun). Modern Sport last 6: **83% U2.5**, 1.33 total gol/match. H2H 5 game terakhir: 2-2/1-1/0-0/1-0/1-1 (avg 1.4 gol). Profil paling defensif di slate. |
| 2 | Naftan Novopolotsk vs Torpedo-BelAZ | Belarus VL Round 10. Naftan **dasar klasemen 3 PL/9**, 0/6 menang last 6, 0.6 GF/match musim, baru kalah 5-1 di Belshina. Torpedo 5th-7th, 2-0 vs FC Minsk minggu lalu. Real stakes mid-season. |
| 3 | Fergana State Univ vs Olimpik MobiUZ | Uzbek Pro Liga (tier-2) early-season. FarDU 4 PL unbeaten (9 GF/4 GA). Olimpik baru turun dari Superliga, juggling Uzbek Cup. **Soft market: data tier-2 tipis**. |
| 4 | ZED vs Kahrbaa Alasmalia | **FINAL ROUND, dead-rubber + Kahrbaa sudah terdegradasi** (Ahram 22/05). ZED 2nd reg-group, aman. ZED last 6 1.67 GF/match, 83% BTTS. H2H avg 1.6 gol. |
| 5 | Iran vs Republic of the Gambia | Friendly Antalya, persiapan WC2026. Iran rank 21 vs Gambia 116. Iran 5-0 Costa Rica last out. Azmoun out, Taremi headline, deadline 26-man squad 1 Juni → **rotasi babak 2 expected**. Tidak pernah ketemu sebelumnya. |

## Phase 3 — Poisson Model (λ + adjustment)

| Match | λ_home | λ_away | Total λ | Adjustment Reasoning |
|-------|--------|--------|---------|----------------------|
| El Mokawloon vs Modern Sport | 0.63 | 0.78 | 1.41 | Both -10% (dead-rubber, intensity drop) |
| Naftan Novopolotsk vs Torpedo-BelAZ | 0.78 | 1.42 | 2.20 | Naftan -8% defensive crisis post 5-1; Torpedo +5% momentum |
| Fergana State Univ vs Olimpik MobiUZ | 1.50 | 0.95 | 2.45 | Olimpik -5% Cup congestion; FarDU regressed dari sample 4 game |
| ZED vs Kahrbaa Alasmalia | 1.56 | 0.98 | 2.54 | ZED -5% safe coasting; Kahrbaa -8% relegated already |
| Iran vs Republic of the Gambia | 1.89 | 0.68 | 2.57 | Both -10% friendly mode + rotation. λ Iran KONSERVATIF (excl 5-0 CR + 7-0 Seychelles outliers) |

## Phase 4 — Filter Hasil

Gate: model ≥ 65%, value ≥ 4%, gap ≥ 4 ppt, odds 1.30-2.50, Kelly ≥ 2%, no Fade-Short-Odds block.

### ✅ LEG TERPILIH (safe-hierarchy: U3.5 > U2.5 > BTTS-No > AH ± > DC)

| # | Match | Pick | Odds | Model% | Value | Gap (ppt) | Kelly |
|---|-------|------|------|--------|-------|-----------|-------|
| 1 | El Mokawloon vs Modern Sport | **BTTS No** | 1.636 | 74.6% | +22.1% | +13.5 | 34.7% |
| 2 | Naftan Novopolotsk vs Torpedo-BelAZ | **U3.5** | 1.300 | 81.9% | +6.5% | +5.0 | 21.8% |
| 3 | Fergana State Univ vs Olimpik MobiUZ | **U2.75 Asian** | 1.740 | 66.2% | +15.3% | +8.8 | 20.6% |
| 4 | ZED vs Kahrbaa Alasmalia | **DC 1X** | 1.390 | 76.1% | +5.8% | +4.2 | 14.8% |
| 5 | Iran vs Republic of the Gambia | **1 (Iran win)** | 1.618 | 66.3% | +7.3% | +4.5 | 13.6% |

### ❌ MATCH/PICK YANG DI-SKIP

| Match/Pick | Alasan |
|------------|--------|
| Liaoning Tieren vs Shanghai Port (China SL) | Tidak ada leg lolos gate setelah Poisson lebih ketat. Total goals ~ market price. AH Port -0.75/-1.25 awalnya tampak +EV tapi setelah perbaikan formula AH Asian, model converge ke market (gap ≈0). Sit out. |
| Mokawloon U2.5 @ 1.40 | **HARD BLOCK Fade-Short-Odds**: odds ≤1.40 + gap +11.6 ≥ 8 → market kemungkinan benar. |
| Iran-Gambia O2.5 @ 2.111 | Setelah λ konservatif (excl outliers), model 47.3% ≈ market 47.4%. Gap ~0. Tidak ada edge. |
| Iran-Gambia BTTS Yes @ 2.05 | λ_gambia 0.68 → P(BTTS Yes)=41.7% vs market 48.8%. Gap NEGATIF. |
| Naftan AH -1.25 Torpedo @ 2.184 | Awalnya tampak 90% (bug formula AH-Away). Setelah fix → model ~33%. Tidak edge. |
| Andorra-Iraq, SA-Nicaragua, Terdu-Aral | Tier-3 minnow + Heavy-Favourite-Trap risk; tidak diteliti dalam Phase 2. Skip per prinsip CLAUDE. |

## Phase 5 — Final Parlay

```
### 🎯 PARLAY 5-LEG — Jumat 29/05/2026 | Window 19:00-22:30 WIB

| # | Match                                    | Liga             | Pick              | Odds  | Model % | Value  | Gap   |
|---|------------------------------------------|------------------|-------------------|-------|---------|--------|-------|
| 1 | El Mokawloon vs Modern Sport             | Egypt Premier Le | BTTS No           | 1.636 | 74.6%   | +22.1% | +13.5 |
| 2 | Naftan Novopolotsk vs Torpedo-BelAZ      | Belarus Premier  | U3.5              | 1.300 | 81.9%   | +6.5% | +5.0 |
| 3 | Fergana State Univ vs Olimpik MobiUZ     | Uzbekistan Pro L | U2.75 Asian       | 1.740 | 66.2%   | +15.3% | +8.8 |
| 4 | ZED vs Kahrbaa Alasmalia                 | Egypt Premier Le | DC 1X             | 1.390 | 76.1%   | +5.8% | +4.2 |
| 5 | Iran vs Republic of the Gambia           | International Fr | 1 (Iran win)      | 1.618 | 66.3%   | +7.3% | +4.5 |

──────────────────────────────────────────────
Combined odds  : 8.323
Combined prob  : 20.41%
Break-even     : 12.02%
Theoretical EV : +69.8%
Edge over BE   : +8.39 ppt
Stake (rec.)   : 0.3-0.5 unit (di bawah normal 0.5-1.0; lihat disclosure)
Potensi return : ~2.50-4.16 unit
──────────────────────────────────────────────
```

### 🔑 Alasan per Leg

**1. El Mokawloon vs Modern Sport — BTTS No @ 1.636**  
DEAD-RUBBER (kedua tim sudah aman; Pharco/Haras/Kahrbaa-Ismailia sudah dipastikan terdegradasi). Modern Sport last 6: 0.83 GF/0.5 GA, **83% U2.5**, profil ultra-defensif. Mokawloon last 6 4 dari 6 imbang. λ_h=0.63 / λ_a=0.78 → P(salah satu tim blank) = 74.7%.

**2. Naftan Novopolotsk vs Torpedo-BelAZ — U3.5 @ 1.300**  
Naftan dasar klasemen 3 poin/9 game, **0/6 menang**, baru kalah 5-1 di Belshina (krisis bertahan). Torpedo away rata-rata ~1.1 GF / 1.0 GA. λ_total ≈ 2.20 → P(total ≤3) = 81.9%. Buffer paling lebar untuk parlay.

**3. Fergana State Univ vs Olimpik MobiUZ — U2.75 Asian @ 1.740**  
Pro Liga = tier 2 Uzbek (di bawah Superliga). FarDU 4 PL: 9 GF/4 GA tapi sample kecil → diregresi ke ~1.5 GF rumah. Olimpik baru turun dari Superliga, kongesti Cup, ~1.0 GF away. λ_total ≈ 2.45 → P(≤2) = 55.7%, P(=3) = 22.7%, eff_U2.75 = 0.557 + 0.5×0.227 = 67.1%. **CAVEAT: data tier-2 Uzbek tipis (soft market).**

**4. ZED vs Kahrbaa Alasmalia — DC 1X @ 1.390**  
ZED 2nd di relegation group (sudah aman, 31 PL). Kahrbaa Ismailia **sudah resmi terdegradasi** (Ahram Online 22/05). ZED main di kandang, last 6 = 1.67 GF/match, statistik lebih agresif. Model 1X2 H/D/A = 50.7%/25.4%/23.9% → DC 1X = 76.1%. Pick paling konservatif untuk match ini (odds 1.39 = di batas FSO; gap 4.2pp < 8pp jadi tidak diblok).

**5. Iran vs Republic of the Gambia — 1 (Iran win) @ 1.618**  
FIFA rank 21 vs 116 (gap 95). Iran 5-0 Costa Rica friendly terakhir, λ_h disesuaikan konservatif (excl. outliers): 1.89. Gambia λ_a 0.68 (kalah ke top-tier). Friendly tune-up untuk WC2026. **CAVEAT: friendly + rotasi babak 2 = variance tinggi**; gap +4.5pp tipis di gate.

---

## ⚠️ DISCLOSURE / FLAGS

1. **Diversifikasi liga**: 4 liga unik (Egypt PL ×2, Belarus PL, Uzbek Pro L, Friendly Intl). CLAUDE mensyaratkan ≥3 liga — passes (4 ≥ 3). 2 leg dari Egypt PL (Mokawloon + ZED) di slot Cairo waktu yang sama (21:00 WIB) — minor regional weather/refree correlation risk.

2. **Direction-mix**: 1 BTTS-No, 2 Under (U3.5 + U2.75 Asian), 1 DC 1X (result-based), 1 1X2 home — direction TIDAK sepenuhnya searah (mix Under + Result), anti-correlation OK.

3. **Leg #5 Iran win 1X2**: gap +4.5pp **tipis** (tepat di gate 4pp). Friendly + WC-prep rotation babak 2 = variance lebih tinggi dari liga reguler. Per CLAUDE, friendlies tier-3 high-variance. Pertimbangkan **drop leg ini** untuk 4-leg lebih aman:
   ```
   Alternatif konservatif 4-leg (drop leg #5):
   Combined odds: 5.144
   Combined prob: 30.78%
   Break-even: 19.44%
   EV: +58.3%
   ```

4. **Leg #3 Fergana U2.75 Asian (Uzbek tier-2)**: data quality LOWEST di slate. Sample form FarDU 4 game (regressed). Soft market = bookmaker bisa salah harga DAN model bisa salah. Treat as marginal.

5. **Leg #2 Naftan U3.5**: odds 1.30 = batas bawah gate. Sebenarnya safest leg by model (81.9%) tapi value tipis (+5pp gap). Risk: Torpedo blowout 0-4 (P≈18%). Naftan baru kalah 5-1 minggu lalu — defensive crisis bisa berlanjut. Mempertimbangkan **U2.5 alternatif** (model 62%, gap +10) — gagal gate 65%.

6. **Stake recommendation 0.3-0.5 unit** (di bawah normal CLAUDE 0.5-1.0) karena:
   - 2 leg dari Egypt PL (regional correlation)
   - 1 leg friendly (variance tinggi)
   - 1 leg soft Uzbek tier-2 market
   - 2 leg di odds boundary (1.30 dan 1.39)

## 🐛 Bug Fixes Selama Analisis

Selama implementasi, ditemukan & diperbaiki 2 bug di Poisson script:
1. **Asian Total .75-line formula**: `fl=int(line)` ditambah +1 untuk .75 (e.g., O1.75 floor=2, bukan 1). Sebelum perbaikan, O1.75/U1.75 di-overestimate.
2. **AH Asian Away kondisi**: `d < -line - 1e-9` salah (warisan dari home formula); benar `d < line - 1e-9` karena `line` di T8 sudah dari sudut pandang away. Sebelum perbaikan, AH Away -0.75/-1.25 model berlebihan (e.g., Naftan AH -1.25 Torpedo di-show 90% padahal real ~33%).

## Markets yang DIPERTIMBANGKAN tapi ditolak

- **Naftan U2.75 Asian @ 1.681** (model 72.1%, gap +12.6) — bigger value tapi tighter buffer dari U3.5; pilih U3.5 untuk safety.
- **Mokawloon U1.75 Asian @ 1.989** (model 70.9%, gap +20.6) — bigger value tapi sangat tight (≤1 goal full, =2 half-push); BTTS No lebih binary dan robust ke '0-2'/'2-0'.
- **Mokawloon U2.5 @ 1.40** (model 83%, gap +11.6) — HARD BLOCK Fade-Short-Odds rule (odds ≤1.40 + gap ≥8pp).
- **AH integer (line=0, ±1)** — di-skip karena push behavior susah dimodel di parlay.
- **AH ekstrem (±1.5+, ±2.5)** — buffer terlalu sempit / variance tinggi.
