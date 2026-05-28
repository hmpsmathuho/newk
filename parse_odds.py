#!/usr/bin/env python3
"""Parse 1xbet mhtml match files (Phase 1 fallback method)."""
import re
import quopri


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
    m = re.search(r"1x2\s+M1\s+(\d+(?:\.\d+)?)\s+X\s+(\d+(?:\.\d+)?)\s+M2\s+(\d+(?:\.\d+)?)", text)
    if m:
        out["1x2"] = {"home": fnum(m.group(1)), "draw": fnum(m.group(2)), "away": fnum(m.group(3))}
    m = re.search(r"Double Chance\s+1X\s+(\d+\.\d+)\s+12\s+(\d+\.\d+)\s+2X\s+(\d+\.\d+)", text)
    if m:
        out["dc"] = {"1X": fnum(m.group(1)), "12": fnum(m.group(2)), "X2": fnum(m.group(3))}
    m = re.search(r"Kedua Tim Mencetak Skor\s+Ya\s+(\d+\.\d+)\s+Tidak\s+(\d+\.\d+)", text)
    if m:
        out["btts"] = {"yes": fnum(m.group(1)), "no": fnum(m.group(2))}
    totals = {}
    seg = re.search(r"\sTotal\s+0\.5\s+Over\s+(.+?)(?:Total Asia|Handicap\s+1\s|Total 1\s|Babak)", text)
    if seg:
        body = "0.5 Over " + seg.group(1)
        for ln in re.finditer(r"(\d+(?:\.\d+)?)\s+Over\s+(\d+\.\d+)\s+\d+(?:\.\d+)?\s+Under\s+(\d+\.\d+)", body):
            line = ln.group(1)
            totals[f"O{line}"] = fnum(ln.group(2))
            totals[f"U{line}"] = fnum(ln.group(3))
    if totals:
        out["totals"] = totals
    ah = {"home": {}, "away": {}}
    seg = re.search(r"\sHandicap\s+1\s+\(([+-]?\d+(?:\.\d+)?)\)\s+(.+?)(?:Handicap Asia|Total 1\s|Babak|Tim\s+1\s+Total)", text)
    if seg:
        body = "1 (" + seg.group(1) + ") " + seg.group(2)
        for h in re.finditer(r"1\s+\(([+-]?\d+(?:\.\d+)?)\)\s+(\d+\.\d+)", body):
            ah["home"][h.group(1)] = fnum(h.group(2))
        for a in re.finditer(r"2\s+\(([+-]?\d+(?:\.\d+)?)\)\s+(\d+\.\d+)", body):
            ah["away"][a.group(1)] = fnum(a.group(2))
    if ah["home"] or ah["away"]:
        out["ah"] = ah
    return out
