#!/usr/bin/env python3
"""Phase 3 Poisson + Phase 4 filter."""
import json
import math


def poisson_pmf(k, lam):
    return math.exp(-lam) * lam**k / math.factorial(k)


def poisson_cdf(k, lam):
    return sum(poisson_pmf(i, lam) for i in range(k + 1))


def total_goals_prob(line, lh, la):
    """P(over line) given total goals ~ Poisson(lh+la). Lines are .5 typically."""
    lam = lh + la
    floor = int(line)  # for .5 lines, P(over X.5) = 1 - P(<= X)
    p_under = poisson_cdf(floor, lam)
    return p_under, 1 - p_under  # (under, over)


def btts_prob(lh, la):
    p_h_zero = math.exp(-lh)
    p_a_zero = math.exp(-la)
    p_yes = (1 - p_h_zero) * (1 - p_a_zero)
    return p_yes, 1 - p_yes  # (yes, no)


def grid_1x2(lh, la, max_goals=10):
    """Return P(home win), P(draw), P(away win)."""
    ph, pd, pa = 0.0, 0.0, 0.0
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            p = poisson_pmf(h, lh) * poisson_pmf(a, la)
            if h > a: ph += p
            elif h == a: pd += p
            else: pa += p
    return ph, pd, pa


def evaluate_leg(model_p, odds):
    implied = 1 / odds
    value = model_p * odds - 1
    gap_ppt = (model_p - implied) * 100
    kelly = (model_p * odds - 1) / (odds - 1) if odds > 1 else 0
    return {
        "model_p": model_p, "odds": odds, "implied": implied,
        "value_pct": value * 100, "gap_ppt": gap_ppt, "kelly_pct": kelly * 100
    }


def gate_pass(leg):
    return (leg["model_p"] >= 0.65 and leg["value_pct"] >= 4.0
            and leg["gap_ppt"] >= 4.0 and 1.30 <= leg["odds"] <= 2.50
            and leg["kelly_pct"] >= 2.0)


# ============================================================
# Team form inputs (estimated from web search)
# Format: per-team "for" goals/match and "against" goals/match
# Adjusted for context (motivation, injuries, rotation, fatigue)
# ============================================================

# Final-day EPL fixtures, 24 May 2026. Special context:
# - Arsenal already champions, heavy rotation expected
# - Burnley + Wolves already relegated — both "spent"
# - Brighton fighting for Europa Conference League slot
# - Man Utd safe at 3rd, Carrick first match as permanent manager
# - West Ham must-win for relegation survival, Leeds safe & checked out
# - Liverpool needs draw for CL5, Brentford safe; Salah/Robertson farewell
# - Crystal Palace has Europa Conference final ahead, may rotate

MATCHES = [
    {
        "id": "burnley-wolves",
        "home": "Burnley", "away": "Wolverhampton Wanderers", "league": "EPL",
        # Burnley season GF 38/GA 75; home form W2D6L10 → ~1.0 GF, ~1.9 GA at home
        # Wolves season GF 26/GA 67 → 0.68 GF, 1.76 GA
        "lh_base": 1.20,  # (1.0 + 1.76) / 2 → 1.38, lowered for relegated context
        "la_base": 1.05,  # (0.68 + 1.9) / 2 → 1.29, lowered for spent form
        "adj_h": 0.90,    # -10%: relegated, 6L from last 7
        "adj_a": 0.90,    # -10%: spent, just 3W all season, dead rubber
        "note": "Both relegated. Wolves worst attack EPL. Tips.gg: 'neither side can buy a win, both spent'."
    },
    {
        "id": "brighton-manutd",
        "home": "Brighton & Hove Albion", "away": "Manchester United", "league": "EPL",
        # Brighton 52GF/46GA → 1.37/1.21; home strong (9W/18)
        # Man Utd 69GF/50GA → 1.82/1.32; away patchy (1W/4)
        "lh_base": 1.34,  # (1.37 + 1.32) / 2 → 1.345, slight pos for Europa motivation
        "la_base": 1.42,  # (1.82 + 1.21) / 2 → 1.515, lowered: Sesko/De Ligt/Ugarte out, away patchy
        "adj_h": 1.00,    # Brighton fighting for Europe — full motivation
        "adj_a": 0.93,    # -7%: 3 key players out + dead-rubber
        "note": "Brighton fighting Europa Conference. MUN missing Sesko/De Ligt/Ugarte. Carrick 1st permanent match. 4 last H2H all BTTS."
    },
    {
        "id": "westham-leeds",
        "home": "West Ham United", "away": "Leeds United", "league": "EPL",
        # West Ham must-win mode, last 7 home W3D3L1
        # Leeds safe at 14, no pressure ('toothless' per Guardian)
        "lh_base": 1.65,  # West Ham home will press hard; combined ~1.55, +pos motivation
        "la_base": 0.85,  # Leeds away, checked out
        "adj_h": 1.05,    # +5% motivation: must win
        "adj_a": 0.92,    # -8%: dead rubber, "toothless" away
        "note": "West Ham must-win to stay up. Leeds safe at 14, dead rubber. WH home form W3D3L1 last 7."
    },
    {
        "id": "palace-arsenal",
        "home": "Crystal Palace", "away": "Arsenal", "league": "EPL",
        # Arsenal 71GF/27GA → 1.87/0.71 — but HEAVY ROTATION (Raya/Rice/Saka/Havertz rested)
        # Palace ~50GF/60GA → 1.32/1.58, but Europa final ahead
        "lh_base": 1.20,  # Palace home, but Arsenal defense usually elite
        "la_base": 1.45,  # Arsenal usual ~1.85 attack, but rotation lowers
        "adj_h": 0.95,    # -5%: Europa final ahead, may protect legs
        "adj_a": 0.85,    # -15%: HEAVY rotation, Saka/Rice/Havertz/Raya out, party mood
        "note": "Arsenal champions already. HEAVY ROTATION (Raya/Rice/Saka/Havertz rested). Palace Europa final ahead. Both sides protecting legs."
    },
    {
        "id": "liverpool-brentford",
        "home": "Liverpool", "away": "Brentford", "league": "EPL",
        # Liverpool 63GF/53GA → 1.66/1.39; "no clean sheet last 6"
        # Brentford 55GF/52GA → 1.45/1.37; safe at 9
        "lh_base": 1.50,  # (1.66 + 1.37) / 2 → 1.515
        "la_base": 1.40,  # (1.45 + 1.39) / 2 → 1.42
        "adj_h": 1.00,    # Salah/Robertson farewell — emotional but motivated
        "adj_a": 0.95,    # -5%: safe, dead rubber
        "note": "Salah/Robertson farewell at Anfield. Liverpool needs point for CL. Liverpool no clean sheet last 6. Brentford safe."
    },
]


def analyze_match(m, odds_data):
    o = odds_data[m["id"]]
    lh = m["lh_base"] * m["adj_h"]
    la = m["la_base"] * m["adj_a"]
    total_lam = lh + la

    print(f"\n{'='*88}")
    print(f"  {m['home']} vs {m['away']} ({m['league']})")
    print(f"{'='*88}")
    print(f"  Context: {m['note']}")
    print(f"  λ_home={lh:.3f}  λ_away={la:.3f}  total_λ={total_lam:.3f}")

    # Compute model probabilities
    pu05, po05 = total_goals_prob(0.5, lh, la)
    pu15, po15 = total_goals_prob(1.5, lh, la)
    pu25, po25 = total_goals_prob(2.5, lh, la)
    pu35, po35 = total_goals_prob(3.5, lh, la)
    pu45, po45 = total_goals_prob(4.5, lh, la)
    p_btts_yes, p_btts_no = btts_prob(lh, la)
    ph, pd, pa = grid_1x2(lh, la)

    print(f"  Model: 1X2 H/D/A = {ph:.3f}/{pd:.3f}/{pa:.3f}")
    print(f"  Model: BTTS Y/N = {p_btts_yes:.3f}/{p_btts_no:.3f}")
    print(f"  Model: U/O 1.5={pu15:.3f}/{po15:.3f} | U/O 2.5={pu25:.3f}/{po25:.3f} | U/O 3.5={pu35:.3f}/{po35:.3f}")

    candidates = []

    def add(market, model_p, odds, label):
        if odds is None: return
        leg = evaluate_leg(model_p, odds)
        leg.update({"market": market, "label": label, "match": f"{m['home']} vs {m['away']}", "match_id": m["id"]})
        candidates.append(leg)

    # 1X2
    if "1x2" in o:
        add("1X2", ph, o["1x2"]["home"], "Home win")
        add("1X2", pd, o["1x2"]["draw"], "Draw")
        add("1X2", pa, o["1x2"]["away"], "Away win")

    # DC
    if "dc" in o:
        add("DC", ph + pd, o["dc"]["1X"], "1X (Home or Draw)")
        add("DC", ph + pa, o["dc"]["12"], "12 (no draw)")
        add("DC", pd + pa, o["dc"]["X2"], "X2 (Draw or Away)")

    # BTTS
    if "btts" in o:
        add("BTTS", p_btts_yes, o["btts"]["yes"], "BTTS Yes")
        add("BTTS", p_btts_no, o["btts"]["no"], "BTTS No")

    # Totals
    if "totals" in o:
        t = o["totals"]
        if "U1.5" in t: add("Total", pu15, t["U1.5"], "U1.5")
        if "O1.5" in t: add("Total", po15, t["O1.5"], "O1.5")
        if "U2.5" in t: add("Total", pu25, t["U2.5"], "U2.5")
        if "O2.5" in t: add("Total", po25, t["O2.5"], "O2.5")
        if "U3.5" in t: add("Total", pu35, t["U3.5"], "U3.5")
        if "O3.5" in t: add("Total", po35, t["O3.5"], "O3.5")
        if "U4.5" in t: add("Total", pu45, t["U4.5"], "U4.5")

    # AH (full-line +0.5/-0.5/+1/-1 from "ah_asia" mid-line; we use ah_asia for clean half-lines)
    if "ah_asia" in o:
        # half-lines: home ±0.25, ±0.75 etc. Compute half-line as average of two adj integer lines or simpler model
        # For Asian +0.5 = home covers if home wins or draws
        # P(home AH +0.5) = ph + pd (same as DC 1X for +0.5 line)
        # P(home AH -0.5) = ph (same as 1X2 home win)
        # We use full-line ah for ±0.5 AH which exists in 'ah' dict at +1/-1 etc.
        pass

    if "ah" in o:
        # 'ah' contains integer-line AH. Map to model:
        # Home AH 0 (push on draw): P(home win) / (1 - P(draw))
        # Home AH +1 (lose by ≤1 OK, win=full): P(home win) + P(draw) + P(home lose by 1)
        # We'll model only: home AH 0, home AH +1, away AH 0, away AH +1
        # For AH 0 "draw no bet": effective prob = ph / (ph + pa) treating draw as void
        # But for parlay, AH 0 = win+push, so prob_win = ph, prob_push = pd, effective = ph + 0.5*pd? In parlay leg
        # 1xbet treats AH 0 as: home wins → win, draw → stake refund (push), home loses → lose
        # In parlay context, push reduces leg out — hard to compute. Skip AH 0.
        # AH +1 home: home wins→full win, draw→full win, home loses by 1→push, lose by 2+→lose
        # AH -1 home: home wins by 2+→full, by 1→push, draw or away win→lose
        # For parlay, only count "win" outcomes; treat push as half-loss conservative
        # Simpler: skip integer AH for parlay. Only use ±0.5 if we can derive.
        pass

    # Print candidates and check gates
    print(f"\n  {'Market':<10}{'Pick':<25}{'Odds':>8}{'Model%':>9}{'Implied%':>10}{'Value%':>9}{'Gap pp':>9}{'Kelly%':>8}  Pass")
    candidates.sort(key=lambda x: -x["gap_ppt"])
    passing = []
    for c in candidates:
        ok = gate_pass(c)
        flag = "✓" if ok else " "
        print(f"  {c['market']:<10}{c['label']:<25}{c['odds']:>8.3f}{c['model_p']*100:>8.1f}%{c['implied']*100:>9.1f}%{c['value_pct']:>+8.1f}%{c['gap_ppt']:>+8.1f}{c['kelly_pct']:>+7.1f}%  {flag}")
        if ok:
            passing.append(c)

    return passing


def main():
    with open("/projects/sandbox/newk/all_odds.json") as f:
        odds_data = json.load(f)

    all_passing = []
    for m in MATCHES:
        passing = analyze_match(m, odds_data)
        all_passing.extend(passing)

    print(f"\n\n{'='*88}\n  PHASE 4 SUMMARY: Legs that pass ALL gates\n{'='*88}")
    print(f"  {'Match':<46}{'Pick':<22}{'Odds':>7}{'Model%':>9}{'Value%':>8}{'Gap':>7}")
    for c in all_passing:
        m = c["match"][:45]
        print(f"  {m:<46}{c['label']:<22}{c['odds']:>7.2f}{c['model_p']*100:>8.1f}%{c['value_pct']:>+7.1f}%{c['gap_ppt']:>+6.1f}")

    with open("/projects/sandbox/newk/passing_legs.json", "w") as f:
        json.dump(all_passing, f, indent=2)


if __name__ == "__main__":
    main()
