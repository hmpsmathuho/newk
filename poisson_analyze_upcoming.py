#!/usr/bin/env python3
"""Phase 3-5 — Poisson + filter + parlay build for slate Sat 30/05/2026 WIB.

Form data sourced from upcoming/research_notes.md (web search per match).
"""
import json
import math


def poisson_pmf(k, lam):
    return math.exp(-lam) * lam**k / math.factorial(k)


def poisson_cdf(k, lam):
    return sum(poisson_pmf(i, lam) for i in range(k + 1))


def total_goals_prob(line_int, lh, la):
    lam = lh + la
    p_under = poisson_cdf(line_int, lam)
    return p_under, 1 - p_under


def btts_prob(lh, la):
    p_h_zero = math.exp(-lh)
    p_a_zero = math.exp(-la)
    p_yes = (1 - p_h_zero) * (1 - p_a_zero)
    return p_yes, 1 - p_yes


def grid_1x2(lh, la, max_goals=10):
    ph = pd = pa = 0.0
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            p = poisson_pmf(h, lh) * poisson_pmf(a, la)
            if h > a: ph += p
            elif h == a: pd += p
            else: pa += p
    return ph, pd, pa


def grid_supremacy(lh, la, max_goals=10):
    res = {}
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            d = h - a
            res[d] = res.get(d, 0.0) + poisson_pmf(h, lh) * poisson_pmf(a, la)
    return res


def evaluate(model_p, odds):
    implied = 1 / odds
    return {
        "model_p": model_p, "odds": odds, "implied": implied,
        "value_pct": (model_p * odds - 1) * 100,
        "gap_ppt": (model_p - implied) * 100,
        "kelly_pct": ((model_p * odds - 1) / (odds - 1) if odds > 1 else 0) * 100,
    }


def gate_pass(c):
    return (c["model_p"] >= 0.65 and c["value_pct"] >= 4.0
            and c["gap_ppt"] >= 4.0 and 1.30 <= c["odds"] <= 2.50
            and c["kelly_pct"] >= 2.0)


def fade_short_block(c):
    return c["odds"] <= 1.40 and c["gap_ppt"] >= 8.0


# ============================================================
# Match form/context derived from research_notes.md
# Lambdas built from per-match GF/GA averages with motivasi adjustments
# ============================================================
MATCHES = [
    {
        "id": "rosenborg-bodoglimt",
        "home": "Rosenborg", "away": "Bodo-Glimt", "league": "Norway Eliteserien",
        # Rosenborg home: 0.7 GF / 1.6 GA per match (10 game), bottom desperate
        # Bodo-Glimt away: 3 W in row, best defense in liga (9 GA all season ~0.9 GA/game)
        # Bodo strong attacking: +5%
        "lh_base": 0.85,  # avg(Rosenborg home GF=0.7, Bodo away GA=0.9) = 0.80
        "la_base": 1.85,  # avg(Bodo away GF=2.1 inflated by 3-0 wins, Rosenborg home GA=1.6)
        "adj_h": 0.95,    # -5% (Rosenborg can't score, demoralised)
        "adj_a": 1.05,    # +5% Bodo momentum
        "note": "Bodo-Glimt 3W beruntun, best defense liga. Rosenborg dasar klasemen.",
    },
    {
        "id": "brann-sarpsborg",
        "home": "Brann", "away": "Sarpsborg 08", "league": "Norway Eliteserien",
        # Brann: 1.9 GF / 1.5 GA per match, baru kalah 1-3 di Bodo
        # Sarpsborg mid-bottom (estimasi neutral)
        "lh_base": 1.65,  # avg(Brann home GF=1.9, Sarpsborg away GA=1.4)
        "la_base": 1.05,  # avg(Sarpsborg away GF=1.0, Brann home GA=1.1)
        "adj_h": 1.00,
        "adj_a": 0.95,
        "note": "Brann favourite home (1.737). Sarpsborg mid-table.",
    },
    {
        "id": "fredrikstad-ikstart",
        "home": "Fredrikstad", "away": "IK Start", "league": "Norway Eliteserien",
        # Fredrikstad: 1.5 GF / 1.8 GA per match. Home form W3/5
        # IK Start: lost 4 away straight, 1-4 to Bodo recent
        "lh_base": 1.55,  # Fredrikstad home GF + IK Start away GA
        "la_base": 1.00,  # IK Start away GF + Fredrikstad home GA
        "adj_h": 1.05,    # +5% home advantage strong
        "adj_a": 0.92,    # -8% IK Start road struggles
        "note": "Fredrikstad home favorite. IK Start lost 4 away straight.",
    },
    {
        "id": "orgryte-elfsborg",
        "home": "Orgryte", "away": "Elfsborg", "league": "Sweden Allsvenskan",
        # Orgryte: 0.9 GF / 2.3 GA per match (10 game), winless 5 (2 GF / 17 GA last 5!)
        # Elfsborg: 4th, established, strong form
        "lh_base": 0.95,  # Orgryte home GF + Elfsborg away GA
        "la_base": 1.95,  # Elfsborg away GF + Orgryte home GA (very high!)
        "adj_h": 0.90,    # -10% (form rating 13%, demoralised)
        "adj_a": 1.05,    # +5% Elfsborg momentum
        "note": "Orgryte winless 5, 17 GA in 5! Elfsborg 4th & in form.",
    },
    {
        "id": "nbe-ittihad",
        "home": "National Bank of Egypt", "away": "Al Ittihad Alexandria",
        "league": "Egypt Premier League",
        # NBE: 3rd reg-group, GD +4. Home record W4 D2 L1 last 7 (13 GF / 9 GA = 1.86 GF / 1.29 GA at home)
        # Al Ittihad weaker reg-group team
        "lh_base": 1.50,
        "la_base": 0.85,
        "adj_h": 0.95,    # -5% (relegation group fatigue end of season)
        "adj_a": 0.95,    # -5% (visiting team in dead-rubber-esque match)
        "note": "NBE 3rd reg-group, defensif solid. Possible dead-rubber lean.",
    },
    {
        "id": "monza-catanzaro",
        "home": "Monza 1912", "away": "Catanzaro 1929", "league": "Italy Serie B Playoff",
        # MONZA WON 2-0 IN FIRST LEG. This is RETURN LEG at home.
        # Monza unbeaten 17 home (13W 4D); only 1 home loss season
        # Catanzaro lost 2, winless 5 away
        # PLAYOFF CONTEXT: Monza only needs DRAW (or loss <3 goals) to advance
        # → Monza will be CAGEY/DEFENSIVE (won't push numbers up)
        # → Total goals expected LOW
        "lh_base": 1.30,  # adjusted for cagey home
        "la_base": 0.95,  # Catanzaro forced to attack but limited away
        "adj_h": 0.85,    # -15% Monza protecting lead, won't push
        "adj_a": 1.10,    # +10% Catanzaro forced to chase
        "note": "Monza 2-0 first leg lead → CAGEY home, just need not lose by 3+. Total goals LOW.",
    },
    {
        "id": "nice-saintetienne",
        "home": "OGC Nice", "away": "AS Saint-Etienne",
        "league": "France Ligue 1/2 Barrage",
        # FIRST LEG 0-0. Nice 16th L1 (relegation panic), drew 6/9. Avg 0.8 GF.
        # Saint-Etienne L2 promotion candidate.
        # Defensive both sides. "Cagey affair" expected.
        "lh_base": 1.10,  # Nice usually low-scoring, home
        "la_base": 0.90,  # SE away in L1 venue
        "adj_h": 0.85,    # -15% Nice cagey, defensive
        "adj_a": 0.85,    # -15% SE not stretching
        "note": "First leg 0-0. Cagey expected. Nice 0.8 GF/match. Defensive both.",
    },
    {
        "id": "dundalk-derry",
        "home": "Dundalk", "away": "Derry City",
        "league": "Ireland Premier League",
        # Dundalk: 1 W / 5 last, 7 GF in 5 still scoring
        # Derry: unbeaten 5 (draws), 5 GF in 5 low scoring recently
        "lh_base": 1.30,
        "la_base": 1.00,
        "adj_h": 1.00,
        "adj_a": 0.95,
        "note": "Tight. Dundalk slight home favorite. Derry 4 away draws straight.",
    },
    {
        "id": "shelbourne-galway",
        "home": "Shelbourne", "away": "Galway",
        "league": "Ireland Premier League",
        # Shelbourne: defending champ, unbeaten 6, 1.44 GF / 1.39 GA
        # Galway: 1.47 GF / 1.65 GA, away leaky
        "lh_base": 1.50,
        "la_base": 1.10,
        "adj_h": 1.00,
        "adj_a": 0.95,
        "note": "Shelbourne defending champion home favorite (1.71). Galway leaky away.",
    },
    {
        "id": "shamrock-stpats",
        "home": "Shamrock Rovers", "away": "St Patrick's Athletic",
        "league": "Ireland Premier League",
        # Shamrock leader, beaten St Pats 2x season (2-0 H, 1-0 A) - low scoring wins
        # But lost 2 home recently. St Pats 1 loss in 7 away.
        "lh_base": 1.40,
        "la_base": 1.10,
        "adj_h": 0.95,   # -5% recent home wobble
        "adj_a": 1.00,
        "note": "Dublin derby. Shamrock won both H2H this season. St Pats 4 straight away draws.",
    },
    {
        "id": "fram-breidablik",
        "home": "Fram", "away": "Breidablik UBK",
        "league": "Iceland Urvalsdeild",
        # Fram: 2.6 GF / 2.1 GA per match (10 game) — VERY high scoring
        # Breidablik: traditional top-3
        "lh_base": 2.00,
        "la_base": 1.80,
        "adj_h": 0.95,   # regress small sample
        "adj_a": 1.00,
        "note": "Both high-scoring. Total goals likely 4+. BTTS Yes implied 78%.",
    },
    {
        "id": "psg-arsenal",
        "home": "Paris Saint-Germain", "away": "Arsenal",
        "league": "UEFA Champions League FINAL",
        # PSG: 44 UCL goals season, beat Bayern. Hakimi back. Pacho/Mendes minor thigh.
        # Arsenal: defensive, 32% market.
        # Single-match final variance HIGH
        "lh_base": 1.65,
        "la_base": 1.30,
        "adj_h": 0.90,   # -10% final tightening
        "adj_a": 0.90,   # -10% Arsenal cagey
        "note": "UCL FINAL. High variance. Expect cagey, low-scoring per market.",
    },
]


def analyze_match(m, odds):
    o = odds[m["id"]]
    lh = m["lh_base"] * m["adj_h"]
    la = m["la_base"] * m["adj_a"]

    print(f"\n{'='*100}")
    print(f"  {m['home']}  vs  {m['away']}   ({m['league']})")
    print(f"{'='*100}")
    print(f"  Context: {m['note']}")
    print(f"  λ_home={lh:.3f}   λ_away={la:.3f}   total_λ={lh+la:.3f}")

    pu05, po05 = total_goals_prob(0, lh, la)
    pu15, po15 = total_goals_prob(1, lh, la)
    pu25, po25 = total_goals_prob(2, lh, la)
    pu35, po35 = total_goals_prob(3, lh, la)
    pu45, po45 = total_goals_prob(4, lh, la)
    p_btts_y, p_btts_n = btts_prob(lh, la)
    ph, pd, pa = grid_1x2(lh, la)
    sup = grid_supremacy(lh, la)

    print(f"  Model 1X2 H/D/A = {ph*100:>5.1f}% / {pd*100:>5.1f}% / {pa*100:>5.1f}%")
    print(f"  Model BTTS Y/N  = {p_btts_y*100:>5.1f}% / {p_btts_n*100:>5.1f}%")
    print(f"  Totals U/O 1.5={pu15*100:.0f}/{po15*100:.0f}  2.5={pu25*100:.0f}/{po25*100:.0f}  "
          f"3.5={pu35*100:.0f}/{po35*100:.0f}  4.5={pu45*100:.0f}/{po45*100:.0f}")

    cands = []

    def add(market, mp, c, label):
        if c is None: return
        e = evaluate(mp, c)
        e.update({"market": market, "label": label,
                  "match": f"{m['home']} vs {m['away']}", "match_id": m["id"]})
        cands.append(e)

    # 1X2
    if "1x2" in o:
        add("1X2", ph, o["1x2"]["home"], "Home win")
        add("1X2", pd, o["1x2"]["draw"], "Draw")
        add("1X2", pa, o["1x2"]["away"], "Away win")
    # DC
    if "dc" in o:
        add("DC", ph + pd, o["dc"]["1X"], "1X")
        add("DC", ph + pa, o["dc"]["12"], "12 (no draw)")
        add("DC", pd + pa, o["dc"]["X2"], "X2")
    # BTTS
    if "btts" in o:
        add("BTTS", p_btts_y, o["btts"]["yes"], "BTTS Yes")
        add("BTTS", p_btts_n, o["btts"]["no"], "BTTS No")
    # Totals integer
    if "totals" in o:
        t = o["totals"]
        for ln, p_under, p_over in [(1.5, pu15, po15), (2.5, pu25, po25),
                                     (3.5, pu35, po35), (4.5, pu45, po45)]:
            if f"O{ln}" in t: add("Total", p_over, t[f"O{ln}"], f"O{ln}")
            if f"U{ln}" in t: add("Total", p_under, t[f"U{ln}"], f"U{ln}")
    # Totals Asia (quarter lines) — corrected formula
    if "totals_asia" in o:
        t = o["totals_asia"]
        for line_q in [1.25, 1.75, 2.25, 2.75, 3.25, 3.75]:
            frac = round(line_q - int(line_q), 2)
            if abs(frac - 0.25) < 0.01:
                fl = int(line_q)
            elif abs(frac - 0.75) < 0.01:
                fl = int(line_q) + 1
            else:
                continue
            p_eq = poisson_pmf(fl, lh + la)
            p_over = 1 - poisson_cdf(fl, lh + la)
            p_under = poisson_cdf(fl, lh + la) - p_eq
            if f"O{line_q}" in t:
                add("TotalAsian", p_over + 0.5 * p_eq, t[f"O{line_q}"], f"O{line_q} Asian")
            if f"U{line_q}" in t:
                add("TotalAsian", p_under + 0.5 * p_eq, t[f"U{line_q}"], f"U{line_q} Asian")
    # AH Asia (quarter lines) — corrected formula
    if "ah_asia" in o:
        ahA = o["ah_asia"]
        for ln_str, c in (ahA.get("home") or {}).items():
            ln = float(ln_str)
            def home_ah_prob(line):
                if line == 0:
                    return ph + 0.5 * pd
                pw = sum(p for d, p in sup.items() if d > -line + 1e-9)
                push = sup.get(int(-line), 0.0) if (-line == int(-line)) else 0.0
                return pw + 0.5 * push
            if abs(ln - round(ln)) < 0.1:
                continue  # integer
            frac = ln - math.floor(ln) if ln >= 0 else math.ceil(ln) - ln
            if abs(frac - 0.5) < 0.01:
                eff_p = home_ah_prob(ln)
                add("AH-Home", eff_p, c, f"AH {ln:+.1f} {m['home'][:14]}")
            elif abs(frac - 0.25) < 0.01:
                eff_p = 0.5 * home_ah_prob(ln - 0.25) + 0.5 * home_ah_prob(ln + 0.25)
                add("AH-Home", eff_p, c, f"AH {ln:+.2f} {m['home'][:14]}")
            elif abs(frac - 0.75) < 0.01:
                eff_p = 0.5 * home_ah_prob(ln - 0.25) + 0.5 * home_ah_prob(ln + 0.25)
                add("AH-Home", eff_p, c, f"AH {ln:+.2f} {m['home'][:14]}")
        for ln_str, c in (ahA.get("away") or {}).items():
            ln = float(ln_str)
            def away_ah_prob(line):
                if line == 0:
                    return pa + 0.5 * pd
                pw = sum(p for d, p in sup.items() if d < line - 1e-9)
                push = sup.get(int(line), 0.0) if (line == int(line)) else 0.0
                return pw + 0.5 * push
            if abs(ln - round(ln)) < 0.1:
                continue
            frac = ln - math.floor(ln) if ln >= 0 else math.ceil(ln) - ln
            if abs(frac - 0.5) < 0.01:
                eff_p = away_ah_prob(ln)
                add("AH-Away", eff_p, c, f"AH {ln:+.1f} {m['away'][:14]}")
            elif abs(frac - 0.25) < 0.01:
                eff_p = 0.5 * away_ah_prob(ln - 0.25) + 0.5 * away_ah_prob(ln + 0.25)
                add("AH-Away", eff_p, c, f"AH {ln:+.2f} {m['away'][:14]}")
            elif abs(frac - 0.75) < 0.01:
                eff_p = 0.5 * away_ah_prob(ln - 0.25) + 0.5 * away_ah_prob(ln + 0.25)
                add("AH-Away", eff_p, c, f"AH {ln:+.2f} {m['away'][:14]}")

    cands.sort(key=lambda x: -x["gap_ppt"])
    print(f"\n  {'Market':<12}{'Pick':<26}{'Odds':>7}{'Mod%':>8}{'Imp%':>8}{'Val%':>8}{'Gap':>7}{'Kelly':>9}  Pass")
    passing = []
    for c in cands:
        ok = gate_pass(c) and not fade_short_block(c)
        block = " (FSO)" if fade_short_block(c) else ""
        flag = "✓" if ok else " "
        if c["model_p"] < 0.4 and c["gap_ppt"] < -2: continue
        print(f"  {c['market']:<12}{c['label']:<26}{c['odds']:>7.3f}{c['model_p']*100:>7.1f}%{c['implied']*100:>7.1f}%{c['value_pct']:>+7.1f}%{c['gap_ppt']:>+6.1f}{c['kelly_pct']:>+8.1f}%  {flag}{block}")
        if ok:
            passing.append(c)
    return passing


def main():
    odds = json.load(open("/projects/sandbox/newk/upcoming/all_odds_upcoming.json"))
    all_passing = []
    for m in MATCHES:
        if m["id"] not in odds:
            print(f"\n[!] No odds for {m['id']} — skip")
            continue
        passing = analyze_match(m, odds)
        all_passing.extend(passing)

    print(f"\n\n{'#'*100}")
    print("# PHASE 4 — Legs that pass all gates")
    print(f"{'#'*100}")
    print(f"  {'Match':<55}{'Pick':<26}{'Odds':>7}{'Mod%':>7}{'Val%':>7}{'Gap':>6}")
    by_match = {}
    for c in all_passing:
        by_match.setdefault(c["match_id"], []).append(c)
        m = c["match"][:54]
        print(f"  {m:<55}{c['label']:<26}{c['odds']:>7.3f}{c['model_p']*100:>6.1f}%{c['value_pct']:>+6.1f}%{c['gap_ppt']:>+5.1f}")

    with open("/projects/sandbox/newk/upcoming/passing_legs_upcoming.json", "w") as fh:
        json.dump(all_passing, fh, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
