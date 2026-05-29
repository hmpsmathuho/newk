#!/usr/bin/env python3
"""Final parlay assembly using SAFE-hierarchy selection per CLAUDE.md."""
import json

# Manual safe selection per CLAUDE.md hierarchy:
# 1. U3.5 > 2. U2.5 ≥65% > 3. BTTS No ≥65% > 4. AH ±0.5/±1.0 ≥65% > 5. DC ≥70%
PICKS = [
    {
        "n": 1,
        "match": "El Mokawloon vs Modern Sport",
        "league": "Egypt Premier League",
        "kickoff": "Fri 29/05 21:00 WIB",
        "pick": "BTTS No",
        "odds": 1.636,
        "model_p": 0.746,
        "value_pct": 22.1,
        "gap_ppt": 13.5,
        "kelly_pct": 34.7,
        "reason": "DEAD-RUBBER (kedua tim sudah aman; Pharco/Haras/Kahrbaa-Ismailia sudah dipastikan terdegradasi). Modern Sport last 6: 0.83 GF/0.5 GA, **83% U2.5**, profil ultra-defensif. Mokawloon last 6 4 dari 6 imbang. λ_h=0.63 / λ_a=0.78 → P(salah satu tim blank) = 74.7%."
    },
    {
        "n": 2,
        "match": "Naftan Novopolotsk vs Torpedo-BelAZ",
        "league": "Belarus Premier League",
        "kickoff": "Fri 29/05 22:00 WIB",
        "pick": "U3.5",
        "odds": 1.30,
        "model_p": 0.819,
        "value_pct": 6.5,
        "gap_ppt": 5.0,
        "kelly_pct": 21.8,
        "reason": "Naftan dasar klasemen 3 poin/9 game, **0/6 menang**, baru kalah 5-1 di Belshina (krisis bertahan). Torpedo away rata-rata ~1.1 GF / 1.0 GA. λ_total ≈ 2.20 → P(total ≤3) = 81.9%. Buffer paling lebar untuk parlay."
    },
    {
        "n": 3,
        "match": "Fergana State Univ vs Olimpik MobiUZ",
        "league": "Uzbekistan Pro League (2nd tier)",
        "kickoff": "Fri 29/05 19:00 WIB",
        "pick": "U2.75 Asian",
        "odds": 1.74,
        "model_p": 0.662,
        "value_pct": 15.3,
        "gap_ppt": 8.8,
        "kelly_pct": 20.6,
        "reason": "Pro Liga = tier 2 Uzbek (di bawah Superliga). FarDU 4 PL: 9 GF/4 GA tapi sample kecil → diregresi ke ~1.5 GF rumah. Olimpik baru turun dari Superliga, kongesti Cup, ~1.0 GF away. λ_total ≈ 2.45 → P(≤2) = 55.7%, P(=3) = 22.7%, eff_U2.75 = 0.557 + 0.5×0.227 = 67.1%. **CAVEAT: data tier-2 Uzbek tipis (soft market).**"
    },
    {
        "n": 4,
        "match": "ZED vs Kahrbaa Alasmalia",
        "league": "Egypt Premier League",
        "kickoff": "Fri 29/05 21:00 WIB",
        "pick": "DC 1X",
        "odds": 1.39,
        "model_p": 0.761,
        "value_pct": 5.8,
        "gap_ppt": 4.2,
        "kelly_pct": 14.8,
        "reason": "ZED 2nd di relegation group (sudah aman, 31 PL). Kahrbaa Ismailia **sudah resmi terdegradasi** (Ahram Online 22/05). ZED main di kandang, last 6 = 1.67 GF/match, statistik lebih agresif. Model 1X2 H/D/A = 50.7%/25.4%/23.9% → DC 1X = 76.1%. Pick paling konservatif untuk match ini (odds 1.39 = di batas FSO; gap 4.2pp < 8pp jadi tidak diblok)."
    },
    {
        "n": 5,
        "match": "Iran vs Republic of the Gambia",
        "league": "International Friendly (Antalya)",
        "kickoff": "Fri 29/05 22:30 WIB",
        "pick": "1 (Iran win)",
        "odds": 1.618,
        "model_p": 0.663,
        "value_pct": 7.3,
        "gap_ppt": 4.5,
        "kelly_pct": 13.6,
        "reason": "FIFA rank 21 vs 116 (gap 95). Iran 5-0 Costa Rica friendly terakhir, λ_h disesuaikan konservatif (excl. outliers): 1.89. Gambia λ_a 0.68 (kalah ke top-tier). Friendly tune-up untuk WC2026. **CAVEAT: friendly + rotasi babak 2 = variance tinggi**; gap +4.5pp tipis di gate."
    },
]


def main():
    combined_odds = 1.0
    combined_prob = 1.0
    for p in PICKS:
        combined_odds *= p["odds"]
        combined_prob *= p["model_p"]
    be = 1 / combined_odds
    ev = combined_prob * combined_odds - 1

    out = []
    out.append("# 🎯 PARLAY 5-LEG — Jumat 29 Mei 2026 | Window 19:00-22:30 WIB\n")
    out.append("> **Sumber odds**: 1xbet.mobi via service-api `LineFeed/GetGameZip` (29/05/2026 ~12:00 WIB).\n"
               "> **Margin bookmaker**: rata-rata ~3-5% (mid-tier liga).\n"
               "> **Konteks slate**: 2 dead-rubber Egypt PL relegation final round, 1 tier-2 China SL match (skip-no-pass), 1 Belarus mid-season, 1 friendly intl, 1 Uzbek tier-2.\n")

    out.append("## Phase 1 — Odds Snapshot (key markets, 5 match terpilih)\n")
    out.append("| Match | 1X2 (H/D/A) | BTTS Y/N | O/U 2.5 | O/U 3.5 |")
    out.append("|-------|-------------|----------|---------|---------|")
    odds_data = json.load(open("/projects/sandbox/newk/upcoming/all_odds_upcoming.json"))
    slug_map = {
        "El Mokawloon vs Modern Sport": "mokawloon-modernsport",
        "Naftan Novopolotsk vs Torpedo-BelAZ": "naftan-torpedobelaz",
        "Fergana State Univ vs Olimpik MobiUZ": "fergana-olimpik",
        "ZED vs Kahrbaa Alasmalia": "zed-kahrbaa",
        "Iran vs Republic of the Gambia": "iran-gambia",
    }
    for p in PICKS:
        slug = slug_map[p["match"]]
        o = odds_data[slug]
        x = o["1x2"]
        b = o.get("btts", {})
        t = o.get("totals", {})
        out.append(f"| {p['match']} | {x['home']}/{x['draw']}/{x['away']} | "
                   f"{b.get('yes','-')}/{b.get('no','-')} | "
                   f"{t.get('O2.5','-')}/{t.get('U2.5','-')} | "
                   f"{t.get('O3.5','-')}/{t.get('U3.5','-')} |")
    out.append("")

    out.append("## Phase 2 — Konteks Tim (kunci pre-match)\n")
    out.append("| # | Match | Konteks Kritis |")
    out.append("|---|-------|----------------|")
    contexts = {
        "El Mokawloon vs Modern Sport": "**FINAL ROUND, both safe** (Pharco/Haras/Kahrbaa-Ismailia sudah turun). Modern Sport last 6: **83% U2.5**, 1.33 total gol/match. H2H 5 game terakhir: 2-2/1-1/0-0/1-0/1-1 (avg 1.4 gol). Profil paling defensif di slate.",
        "Naftan Novopolotsk vs Torpedo-BelAZ": "Belarus VL Round 10. Naftan **dasar klasemen 3 PL/9**, 0/6 menang last 6, 0.6 GF/match musim, baru kalah 5-1 di Belshina. Torpedo 5th-7th, 2-0 vs FC Minsk minggu lalu. Real stakes mid-season.",
        "Fergana State Univ vs Olimpik MobiUZ": "Uzbek Pro Liga (tier-2) early-season. FarDU 4 PL unbeaten (9 GF/4 GA). Olimpik baru turun dari Superliga, juggling Uzbek Cup. **Soft market: data tier-2 tipis**.",
        "ZED vs Kahrbaa Alasmalia": "**FINAL ROUND, dead-rubber + Kahrbaa sudah terdegradasi** (Ahram 22/05). ZED 2nd reg-group, aman. ZED last 6 1.67 GF/match, 83% BTTS. H2H avg 1.6 gol.",
        "Iran vs Republic of the Gambia": "Friendly Antalya, persiapan WC2026. Iran rank 21 vs Gambia 116. Iran 5-0 Costa Rica last out. Azmoun out, Taremi headline, deadline 26-man squad 1 Juni → **rotasi babak 2 expected**. Tidak pernah ketemu sebelumnya.",
    }
    for i, p in enumerate(PICKS, 1):
        out.append(f"| {i} | {p['match']} | {contexts[p['match']]} |")
    out.append("")

    out.append("## Phase 3 — Poisson Model (λ + adjustment)\n")
    out.append("| Match | λ_home | λ_away | Total λ | Adjustment Reasoning |")
    out.append("|-------|--------|--------|---------|----------------------|")
    lambdas = {
        "El Mokawloon vs Modern Sport": (0.63, 0.78, "Both -10% (dead-rubber, intensity drop)"),
        "Naftan Novopolotsk vs Torpedo-BelAZ": (0.78, 1.42, "Naftan -8% defensive crisis post 5-1; Torpedo +5% momentum"),
        "Fergana State Univ vs Olimpik MobiUZ": (1.50, 0.95, "Olimpik -5% Cup congestion; FarDU regressed dari sample 4 game"),
        "ZED vs Kahrbaa Alasmalia": (1.56, 0.98, "ZED -5% safe coasting; Kahrbaa -8% relegated already"),
        "Iran vs Republic of the Gambia": (1.89, 0.68, "Both -10% friendly mode + rotation. λ Iran KONSERVATIF (excl 5-0 CR + 7-0 Seychelles outliers)"),
    }
    for p in PICKS:
        lh, la, adj = lambdas[p["match"]]
        out.append(f"| {p['match']} | {lh:.2f} | {la:.2f} | {lh+la:.2f} | {adj} |")
    out.append("")

    out.append("## Phase 4 — Filter Hasil\n")
    out.append("Gate: model ≥ 65%, value ≥ 4%, gap ≥ 4 ppt, odds 1.30-2.50, Kelly ≥ 2%, no Fade-Short-Odds block.\n")
    out.append("### ✅ LEG TERPILIH (safe-hierarchy: U3.5 > U2.5 > BTTS-No > AH ± > DC)\n")
    out.append("| # | Match | Pick | Odds | Model% | Value | Gap (ppt) | Kelly |")
    out.append("|---|-------|------|------|--------|-------|-----------|-------|")
    for p in PICKS:
        out.append(f"| {p['n']} | {p['match']} | **{p['pick']}** | {p['odds']:.3f} | "
                   f"{p['model_p']*100:.1f}% | +{p['value_pct']:.1f}% | "
                   f"+{p['gap_ppt']:.1f} | {p['kelly_pct']:.1f}% |")
    out.append("")

    out.append("### ❌ MATCH/PICK YANG DI-SKIP\n")
    out.append("| Match/Pick | Alasan |")
    out.append("|------------|--------|")
    out.append("| Liaoning Tieren vs Shanghai Port (China SL) | Tidak ada leg lolos gate setelah Poisson lebih ketat. Total goals ~ market price. AH Port -0.75/-1.25 awalnya tampak +EV tapi setelah perbaikan formula AH Asian, model converge ke market (gap ≈0). Sit out. |")
    out.append("| Mokawloon U2.5 @ 1.40 | **HARD BLOCK Fade-Short-Odds**: odds ≤1.40 + gap +11.6 ≥ 8 → market kemungkinan benar. |")
    out.append("| Iran-Gambia O2.5 @ 2.111 | Setelah λ konservatif (excl outliers), model 47.3% ≈ market 47.4%. Gap ~0. Tidak ada edge. |")
    out.append("| Iran-Gambia BTTS Yes @ 2.05 | λ_gambia 0.68 → P(BTTS Yes)=41.7% vs market 48.8%. Gap NEGATIF. |")
    out.append("| Naftan AH -1.25 Torpedo @ 2.184 | Awalnya tampak 90% (bug formula AH-Away). Setelah fix → model ~33%. Tidak edge. |")
    out.append("| Andorra-Iraq, SA-Nicaragua, Terdu-Aral | Tier-3 minnow + Heavy-Favourite-Trap risk; tidak diteliti dalam Phase 2. Skip per prinsip CLAUDE. |")
    out.append("")

    out.append("## Phase 5 — Final Parlay\n")
    out.append("```")
    out.append("### 🎯 PARLAY 5-LEG — Jumat 29/05/2026 | Window 19:00-22:30 WIB\n")
    out.append("| # | Match                                    | Liga             | Pick              | Odds  | Model % | Value  | Gap   |")
    out.append("|---|------------------------------------------|------------------|-------------------|-------|---------|--------|-------|")
    for p in PICKS:
        match_short = p["match"][:40]
        league_short = p["league"][:16]
        out.append(f"| {p['n']} | {match_short:<40} | {league_short:<16} | {p['pick']:<17} | {p['odds']:.3f} | "
                   f"{p['model_p']*100:.1f}%   | +{p['value_pct']:.1f}% | +{p['gap_ppt']:.1f} |")
    out.append("")
    out.append("──────────────────────────────────────────────")
    out.append(f"Combined odds  : {combined_odds:.3f}")
    out.append(f"Combined prob  : {combined_prob*100:.2f}%")
    out.append(f"Break-even     : {be*100:.2f}%")
    out.append(f"Theoretical EV : +{ev*100:.1f}%")
    out.append(f"Edge over BE   : +{(combined_prob-be)*100:.2f} ppt")
    out.append("Stake (rec.)   : 0.3-0.5 unit (di bawah normal 0.5-1.0; lihat disclosure)")
    out.append(f"Potensi return : ~{combined_odds * 0.3:.2f}-{combined_odds * 0.5:.2f} unit")
    out.append("──────────────────────────────────────────────")
    out.append("```")
    out.append("")

    out.append("### 🔑 Alasan per Leg\n")
    for p in PICKS:
        out.append(f"**{p['n']}. {p['match']} — {p['pick']} @ {p['odds']:.3f}**  ")
        out.append(f"{p['reason']}\n")

    out.append("---\n")
    out.append("## ⚠️ DISCLOSURE / FLAGS\n")
    out.append("1. **Diversifikasi liga**: 4 liga unik (Egypt PL ×2, Belarus PL, Uzbek Pro L, Friendly Intl). CLAUDE mensyaratkan ≥3 liga — passes (4 ≥ 3). 2 leg dari Egypt PL (Mokawloon + ZED) di slot Cairo waktu yang sama (21:00 WIB) — minor regional weather/refree correlation risk.")
    out.append("")
    out.append("2. **Direction-mix**: 1 BTTS-No, 2 Under (U3.5 + U2.75 Asian), 1 DC 1X (result-based), 1 1X2 home — direction TIDAK sepenuhnya searah (mix Under + Result), anti-correlation OK.")
    out.append("")
    out.append("3. **Leg #5 Iran win 1X2**: gap +4.5pp **tipis** (tepat di gate 4pp). Friendly + WC-prep rotation babak 2 = variance lebih tinggi dari liga reguler. Per CLAUDE, friendlies tier-3 high-variance. Pertimbangkan **drop leg ini** untuk 4-leg lebih aman:")
    out.append("   ```")
    out.append("   Alternatif konservatif 4-leg (drop leg #5):")
    p4 = [p for p in PICKS if p["n"] != 5]
    co4 = 1.0; cp4 = 1.0
    for p in p4:
        co4 *= p["odds"]; cp4 *= p["model_p"]
    out.append(f"   Combined odds: {co4:.3f}")
    out.append(f"   Combined prob: {cp4*100:.2f}%")
    out.append(f"   Break-even: {1/co4*100:.2f}%")
    out.append(f"   EV: +{(cp4*co4-1)*100:.1f}%")
    out.append("   ```")
    out.append("")
    out.append("4. **Leg #3 Fergana U2.75 Asian (Uzbek tier-2)**: data quality LOWEST di slate. Sample form FarDU 4 game (regressed). Soft market = bookmaker bisa salah harga DAN model bisa salah. Treat as marginal.")
    out.append("")
    out.append("5. **Leg #2 Naftan U3.5**: odds 1.30 = batas bawah gate. Sebenarnya safest leg by model (81.9%) tapi value tipis (+5pp gap). Risk: Torpedo blowout 0-4 (P≈18%). Naftan baru kalah 5-1 minggu lalu — defensive crisis bisa berlanjut. Mempertimbangkan **U2.5 alternatif** (model 62%, gap +10) — gagal gate 65%.")
    out.append("")
    out.append("6. **Stake recommendation 0.3-0.5 unit** (di bawah normal CLAUDE 0.5-1.0) karena:")
    out.append("   - 2 leg dari Egypt PL (regional correlation)")
    out.append("   - 1 leg friendly (variance tinggi)")
    out.append("   - 1 leg soft Uzbek tier-2 market")
    out.append("   - 2 leg di odds boundary (1.30 dan 1.39)")
    out.append("")

    out.append("## 🐛 Bug Fixes Selama Analisis\n")
    out.append("Selama implementasi, ditemukan & diperbaiki 2 bug di Poisson script:")
    out.append("1. **Asian Total .75-line formula**: `fl=int(line)` ditambah +1 untuk .75 (e.g., O1.75 floor=2, bukan 1). Sebelum perbaikan, O1.75/U1.75 di-overestimate.")
    out.append("2. **AH Asian Away kondisi**: `d < -line - 1e-9` salah (warisan dari home formula); benar `d < line - 1e-9` karena `line` di T8 sudah dari sudut pandang away. Sebelum perbaikan, AH Away -0.75/-1.25 model berlebihan (e.g., Naftan AH -1.25 Torpedo di-show 90% padahal real ~33%).")
    out.append("")

    out.append("## Markets yang DIPERTIMBANGKAN tapi ditolak\n")
    out.append("- **Naftan U2.75 Asian @ 1.681** (model 72.1%, gap +12.6) — bigger value tapi tighter buffer dari U3.5; pilih U3.5 untuk safety.")
    out.append("- **Mokawloon U1.75 Asian @ 1.989** (model 70.9%, gap +20.6) — bigger value tapi sangat tight (≤1 goal full, =2 half-push); BTTS No lebih binary dan robust ke '0-2'/'2-0'.")
    out.append("- **Mokawloon U2.5 @ 1.40** (model 83%, gap +11.6) — HARD BLOCK Fade-Short-Odds rule (odds ≤1.40 + gap ≥8pp).")
    out.append("- **AH integer (line=0, ±1)** — di-skip karena push behavior susah dimodel di parlay.")
    out.append("- **AH ekstrem (±1.5+, ±2.5)** — buffer terlalu sempit / variance tinggi.")
    out.append("")

    text = "\n".join(out)
    out_path = "/projects/sandbox/newk/PARLAY_OUTPUT_29MAY.md"
    with open(out_path, "w") as f:
        f.write(text)
    print(f"\n[*] Wrote {out_path}\n")
    print(text)


if __name__ == "__main__":
    main()
