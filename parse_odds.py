#!/usr/bin/env python3
"""Parse 1xbet mhtml match files (Phase 1 fallback method)."""
import re
import quopri
import json
import os

MATCHES = {
    "1.mhtml": {"home": "Burnley", "away": "Wolverhampton Wanderers", "league": "EPL", "slug": "burnley-wolves"},
    "2.mhtml": {"home": "Brighton & Hove Albion", "away": "Manchester United", "league": "EPL", "slug": "brighton-manutd"},
    "3.mhtml": {"home": "West Ham United", "away": "Leeds United", "league": "EPL", "slug": "westham-leeds"},
    "4.mhtml": {"home": "Crystal Palace", "away": "Arsenal", "league": "EPL", "slug": "palace-arsenal"},
    "5.mhtml": {"home": "Liverpool", "away": "Brentford", "league": "EPL", "slug": "liverpool-brentford"},
}


def decode_mhtml(path):
    with open(path, "rb") as f:
        raw = f.read()
    decoded = quopri.decodestring(raw).decode("utf-8", "ignore")
    no_tags = re.sub(r"<[^>]+>", " ", decoded)
    cleaned = re.sub(r"\s+", " ", no_tags)
    return cleaned


def fnum(s):
    return float(s)


def extract_odds(text, home, away):
    out = {"home": home, "away": away}

    # 1X2: take FIRST occurrence (full match) — odds can be integer (e.g., "2") or decimal
    m = re.search(r"1x2\s+M1\s+(\d+(?:\.\d+)?)\s+X\s+(\d+(?:\.\d+)?)\s+M2\s+(\d+(?:\.\d+)?)", text)
    if m:
        out["1x2"] = {"home": fnum(m.group(1)), "draw": fnum(m.group(2)), "away": fnum(m.group(3))}

    # Double Chance (first occurrence): "1X X.XXX 12 X.XXX 2X X.XXX"
    m = re.search(r"Double Chance\s+1X\s+(\d+\.\d+)\s+12\s+(\d+\.\d+)\s+2X\s+(\d+\.\d+)", text)
    if m:
        out["dc"] = {"1X": fnum(m.group(1)), "12": fnum(m.group(2)), "X2": fnum(m.group(3))}

    # BTTS (first occurrence — full match)
    m = re.search(r"Kedua Tim Mencetak Skor\s+Ya\s+(\d+\.\d+)\s+Tidak\s+(\d+\.\d+)", text)
    if m:
        out["btts"] = {"yes": fnum(m.group(1)), "no": fnum(m.group(2))}

    # Total full match: from " Total " to next section break "Total Asia" / "Total 1" / "Babak" / "Handicap"
    totals = {}
    # Find segment after "Kedua Tim Mencetak Skor Ya X.XXX Tidak X.XXX ... Total ...". The first Total section
    # comes typically after BTTS section. Use literal " Total " as anchor (with surrounding spaces).
    seg = re.search(r"\sTotal\s+0\.5\s+Over\s+(.+?)(?:Total Asia|Handicap\s+1\s|Total 1\s|Babak)", text)
    if seg:
        body = "0.5 Over " + seg.group(1)
        for ln in re.finditer(r"(\d+(?:\.\d+)?)\s+Over\s+(\d+\.\d+)\s+\d+(?:\.\d+)?\s+Under\s+(\d+\.\d+)", body):
            line = ln.group(1)
            totals[f"O{line}"] = fnum(ln.group(2))
            totals[f"U{line}"] = fnum(ln.group(3))
    if totals:
        out["totals"] = totals

    # Total Asia (full match) - quarter lines
    totals_asia = {}
    seg = re.search(r"Total Asia\s+0\.75\s+Over\s+(.+?)(?:Handicap\s+1\s|Total 1\s|Babak|Tim\s+1\s+Total)", text)
    if seg:
        body = "0.75 Over " + seg.group(1)
        for ln in re.finditer(r"(\d+(?:\.\d+)?)\s+Over\s+(\d+\.\d+)\s+\d+(?:\.\d+)?\s+Under\s+(\d+\.\d+)", body):
            line = ln.group(1)
            totals_asia[f"O{line}"] = fnum(ln.group(2))
            totals_asia[f"U{line}"] = fnum(ln.group(3))
    if totals_asia:
        out["totals_asia"] = totals_asia

    # Asian Handicap full match (Handicap section first occurrence)
    ah = {"home": {}, "away": {}}
    seg = re.search(r"\sHandicap\s+1\s+\(([+-]?\d+(?:\.\d+)?)\)\s+(.+?)(?:Handicap Asia|Total 1\s|Babak|Tim\s+1\s+Total)", text)
    if seg:
        body = "1 (" + seg.group(1) + ") " + seg.group(2)
        # pairs: 1 (line) odd  2 (line) odd
        # iterate consecutive pairs
        for h in re.finditer(r"1\s+\(([+-]?\d+(?:\.\d+)?)\)\s+(\d+\.\d+)", body):
            ah["home"][h.group(1)] = fnum(h.group(2))
        for a in re.finditer(r"2\s+\(([+-]?\d+(?:\.\d+)?)\)\s+(\d+\.\d+)", body):
            ah["away"][a.group(1)] = fnum(a.group(2))
    if ah["home"] or ah["away"]:
        out["ah"] = ah

    # Handicap Asia (quarter lines for full match)
    ah_asia = {"home": {}, "away": {}}
    seg = re.search(r"Handicap Asia\s+1\s+\(([+-]?\d+(?:\.\d+)?)\)\s+(.+?)(?:Total 1\s|Babak|Tim\s+1\s+Total)", text)
    if seg:
        body = "1 (" + seg.group(1) + ") " + seg.group(2)
        for h in re.finditer(r"1\s+\(([+-]?\d+(?:\.\d+)?)\)\s+(\d+\.\d+)", body):
            ah_asia["home"][h.group(1)] = fnum(h.group(2))
        for a in re.finditer(r"2\s+\(([+-]?\d+(?:\.\d+)?)\)\s+(\d+\.\d+)", body):
            ah_asia["away"][a.group(1)] = fnum(a.group(2))
    if ah_asia["home"] or ah_asia["away"]:
        out["ah_asia"] = ah_asia

    return out


def main():
    base = "/projects/sandbox/newk"
    results = {}
    for fname, meta in MATCHES.items():
        path = os.path.join(base, fname)
        text = decode_mhtml(path)
        with open(os.path.join(base, f"{meta['slug']}_text.txt"), "w") as f:
            f.write(text)
        odds = extract_odds(text, meta["home"], meta["away"])
        odds["league"] = meta["league"]
        results[meta["slug"]] = odds
    with open(os.path.join(base, "all_odds.json"), "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    # Print summary
    for slug, o in results.items():
        print(f"\n=== {o['home']} vs {o['away']} ===")
        if "1x2" in o:
            print(f"  1X2: H={o['1x2']['home']} D={o['1x2']['draw']} A={o['1x2']['away']}")
        if "dc" in o:
            print(f"  DC : 1X={o['dc']['1X']} 12={o['dc']['12']} X2={o['dc']['X2']}")
        if "btts" in o:
            print(f"  BTTS: Yes={o['btts']['yes']} No={o['btts']['no']}")
        if "totals" in o:
            for k in ["O1.5","U1.5","O2.5","U2.5","O3.5","U3.5","O4.5","U4.5"]:
                if k in o["totals"]: print(f"  {k}={o['totals'][k]}", end="  ")
            print()
        if "ah" in o:
            print(f"  AH home: {o['ah']['home']}")
            print(f"  AH away: {o['ah']['away']}")
        if "ah_asia" in o:
            print(f"  AH-asia home: {o['ah_asia']['home']}")
            print(f"  AH-asia away: {o['ah_asia']['away']}")


if __name__ == "__main__":
    main()
