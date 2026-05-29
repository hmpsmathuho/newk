#!/usr/bin/env python3
"""Phase 1 — parse 1xbet GetGameZip JSON into clean odds dict.

Group/Type mapping (1xbet standard):
- G=1 1X2:        T1=Home, T2=Draw, T3=Away
- G=8 DoubleChance: T4=1X, T5=12, T6=X2
- G=2 AH integer: T7=Home(P=line), T8=Away(P=line)  [P null -> 0]
- G=2854 AH Asia quarter: T3829=Home(P=line), T3830=Away(P=line)
- G=17 Total integer: T9=Over(P=line), T10=Under(P=line)
- G=99 Total Asia quarter: T3827=Over(P=line), T3828=Under(P=line)
- G=19/15: BTTS (T180=Yes, T181=No) — actually G=19 is BTTS in modern feed
"""
import json
import os
import glob
from collections import defaultdict


def parse_event_groups(value):
    """Return dict of (G, T, P) -> coefficient by walking GE list-of-list-of-dict."""
    out = defaultdict(dict)
    for grp in value.get("GE", []):
        for ev_block in grp.get("E", []) or []:
            if not isinstance(ev_block, list):
                continue
            for entry in ev_block:
                if not isinstance(entry, dict):
                    continue
                G = entry.get("G")
                T = entry.get("T")
                P = entry.get("P")
                C = entry.get("C")
                if C is None or T is None or G is None:
                    continue
                key = (G, T)
                out[key][P] = float(C)
    return out


def extract_markets(value):
    """Convert GetGameZip Value to flat market dict."""
    g = parse_event_groups(value)

    out = {
        "home": value.get("O1"),
        "away": value.get("O2"),
        "league": value.get("L"),
        "start_ts": value.get("S"),
        "match_id": value.get("I"),
    }

    # 1X2 (G=1)
    h = g.get((1, 1), {}).get(None)
    d = g.get((1, 2), {}).get(None)
    a = g.get((1, 3), {}).get(None)
    if h and d and a:
        out["1x2"] = {"home": h, "draw": d, "away": a}

    # Double Chance (G=8)
    if (8, 4) in g and (8, 5) in g and (8, 6) in g:
        out["dc"] = {"1X": g[(8, 4)].get(None), "12": g[(8, 5)].get(None), "X2": g[(8, 6)].get(None)}

    # BTTS (G=19; T180=Yes, T181=No)
    yes = g.get((19, 180), {}).get(None)
    no = g.get((19, 181), {}).get(None)
    if yes and no:
        out["btts"] = {"yes": yes, "no": no}
    else:
        # fallback G=15 ITA might not be BTTS; skip
        pass

    # Total integer (G=17): T9 Over, T10 Under
    totals = {}
    for line, c in (g.get((17, 9)) or {}).items():
        if line is None: continue
        totals[f"O{line}"] = c
    for line, c in (g.get((17, 10)) or {}).items():
        if line is None: continue
        totals[f"U{line}"] = c
    if totals:
        out["totals"] = totals

    # Total Asia (G=99): T3827 Over, T3828 Under (quarter lines)
    totals_asia = {}
    for line, c in (g.get((99, 3827)) or {}).items():
        if line is None: continue
        totals_asia[f"O{line}"] = c
    for line, c in (g.get((99, 3828)) or {}).items():
        if line is None: continue
        totals_asia[f"U{line}"] = c
    if totals_asia:
        out["totals_asia"] = totals_asia

    # AH integer (G=2): T7 home, T8 away (P=handicap line, None=0)
    ah = {"home": {}, "away": {}}
    for line, c in (g.get((2, 7)) or {}).items():
        ln = "0" if line is None else str(line)
        ah["home"][ln] = c
    for line, c in (g.get((2, 8)) or {}).items():
        ln = "0" if line is None else str(line)
        ah["away"][ln] = c
    if ah["home"] or ah["away"]:
        out["ah"] = ah

    # AH Asia (G=2854): T3829 home, T3830 away (quarter lines)
    ah_asia = {"home": {}, "away": {}}
    for line, c in (g.get((2854, 3829)) or {}).items():
        if line is None: continue
        ah_asia["home"][str(line)] = c
    for line, c in (g.get((2854, 3830)) or {}).items():
        if line is None: continue
        ah_asia["away"][str(line)] = c
    if ah_asia["home"] or ah_asia["away"]:
        out["ah_asia"] = ah_asia

    return out


def main():
    src_dir = "/projects/sandbox/newk/upcoming"
    files = sorted(glob.glob(os.path.join(src_dir, "*_RAW.json")))
    all_odds = {}
    for f in files:
        slug = os.path.basename(f).replace("_RAW.json", "")
        d = json.load(open(f))
        o = extract_markets(d.get("Value", {}))
        all_odds[slug] = o
        print(f"\n=== {o['home']} vs {o['away']} ({o['league']}) [slug={slug}] ===")
        if "1x2" in o:
            print(f"  1X2: H={o['1x2']['home']} D={o['1x2']['draw']} A={o['1x2']['away']}")
        if "dc" in o:
            print(f"  DC : 1X={o['dc']['1X']} 12={o['dc']['12']} X2={o['dc']['X2']}")
        if "btts" in o:
            print(f"  BTTS: Yes={o['btts']['yes']} No={o['btts']['no']}")
        if "totals" in o:
            t = o["totals"]
            for k in ["O1.5","U1.5","O2.5","U2.5","O3.5","U3.5","O4.5","U4.5"]:
                if k in t:
                    print(f"  {k}={t[k]}", end="  ")
            print()
        if "totals_asia" in o:
            t = o["totals_asia"]
            interesting = sorted(t.keys(), key=lambda x: float(x[1:]))
            shown = [k for k in interesting if k.startswith(("O","U")) and 1.0<=float(k[1:])<=4.0]
            print(f"  Total Asia: " + " ".join(f"{k}={t[k]}" for k in shown[:14]))
        if "ah" in o:
            ah = o["ah"]
            print(f"  AH home: " + " ".join(f"{ln}@{c}" for ln, c in sorted(ah['home'].items(), key=lambda x: float(x[0]))))
            print(f"  AH away: " + " ".join(f"{ln}@{c}" for ln, c in sorted(ah['away'].items(), key=lambda x: float(x[0]))))
    out_path = "/projects/sandbox/newk/upcoming/all_odds_upcoming.json"
    with open(out_path, "w") as fh:
        json.dump(all_odds, fh, indent=2, ensure_ascii=False)
    print(f"\n[*] Wrote {out_path}")


if __name__ == "__main__":
    main()
