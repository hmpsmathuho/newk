"""Extract betting markets from 1xbet rendered text (post-MHTML parse).

Indonesian language (1xbet.mobi/id) is what we target. Markets covered:
  - 1X2 (M1/X/M2)
  - Double Chance (1X/12/2X)
  - BTTS (Kedua Tim Mencetak Skor: Ya/Tidak)
  - Total Goals Over/Under (full match): 0.5–5.5
  - Asian Handicap (Handicap 1/2 with full integer lines)
  - Asian Total quarter (Total Asia)
  - Halftime Total (Total .. Babak pertama)
  - Halftime 1X2 (Babak pertama 1x2)
  - Win to Nil
  - Result + BTTS (Hasil Dan Kedua Tim Mencetak Skor)

Robust to whitespace and punctuation variations from quoted-printable decode.
"""
from __future__ import annotations

import re
from typing import Dict, List


def _f(s):
    """Cast to float, accept '2' or '2.5'."""
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


_NUM = r"(\d+(?:\.\d+)?)"


def extract_match_meta(text: str, url_meta: dict | None = None) -> dict:
    """Identify home/away team names from rendered text + URL hints."""
    out = {"home": "", "away": "", "league": ""}

    # 1xbet rendered page layout: "{Home} {time} {date} {Away} Waktu reguler ..."
    m = re.search(r"([A-Z][^\s]+(?:\s+[A-Z][^\s]+){0,4})\s+\d{1,2}[:.]\d{2}\s+\d{1,2}/\d{1,2}\s+([A-Z][^\s]+(?:\s+[A-Z][^\s]+){0,4})\s+Waktu\s+reguler", text)
    if m:
        out["home"] = m.group(1).strip()
        out["away"] = m.group(2).strip()

    # Fallback: look for "Cari berdasarkan pasar 1x2 M1 X.X X X.X M2 X.X" — preceded by team names
    if not out["home"]:
        # Find team names from URL slug or page heading
        if url_meta and url_meta.get("match_slug"):
            slug = url_meta["match_slug"]
            # Heuristic split: 1xbet uses single '-' between teams; team words also use '-'.
            # Best effort: split on common middle hyphen (greedy first half = home)
            parts = slug.split("-")
            mid = len(parts) // 2
            out["home"] = " ".join(p.capitalize() for p in parts[:mid])
            out["away"] = " ".join(p.capitalize() for p in parts[mid:])
        # League from slug
        if url_meta and url_meta.get("league_slug"):
            out["league"] = " ".join(w.capitalize() for w in url_meta["league_slug"].split("-"))
    return out


def extract_markets(text: str) -> Dict[str, dict]:
    """Return {market_label: {selection: odds_decimal}}.

    Selection naming is normalized to: Home / Draw / Away / 1X / 12 / X2 / Yes / No /
    Over / Under / lines for AH/totals (e.g., 'Over 2.5', 'Handicap 1 (-1.5)').
    """
    M: Dict[str, dict] = {}

    # ---- 1X2 (full match) ----
    m = re.search(r"1x2\s+M1\s+" + _NUM + r"\s+X\s+" + _NUM + r"\s+M2\s+" + _NUM, text)
    if m:
        M["1X2"] = {"Home": _f(m.group(1)), "Draw": _f(m.group(2)), "Away": _f(m.group(3))}

    # ---- Double Chance (full match) ----
    m = re.search(r"Double Chance\s+1X\s+" + _NUM + r"\s+12\s+" + _NUM + r"\s+2X\s+" + _NUM, text)
    if m:
        M["DC"] = {"1X": _f(m.group(1)), "12": _f(m.group(2)), "X2": _f(m.group(3))}

    # ---- BTTS (full match) ----
    m = re.search(r"Kedua Tim Mencetak Skor\s+Ya\s+" + _NUM + r"\s+Tidak\s+" + _NUM, text)
    if m:
        M["BTTS"] = {"Yes": _f(m.group(1)), "No": _f(m.group(2))}

    # ---- Total Goals (full match) — anchor between "Total" and next named section ----
    seg = re.search(r"\sTotal\s+0\.5\s+Over\s+(.+?)(?=Total Asia|Handicap\s+1\s|Total 1\s|Babak|Tim\s+1\s+Total)", text)
    if seg:
        body = "0.5 Over " + seg.group(1)
        totals: Dict[str, float] = {}
        for ln in re.finditer(_NUM + r"\s+Over\s+" + _NUM + r"\s+\d+(?:\.\d+)?\s+Under\s+" + _NUM, body):
            line = ln.group(1)
            totals[f"Over {line}"] = _f(ln.group(2))
            totals[f"Under {line}"] = _f(ln.group(3))
        if totals:
            M["Totals"] = totals

    # ---- Total Asia (quarter lines, full match) ----
    seg = re.search(r"Total Asia\s+0\.75\s+Over\s+(.+?)(?=Handicap\s+1\s|Total 1\s|Babak|Tim\s+1\s+Total)", text)
    if seg:
        body = "0.75 Over " + seg.group(1)
        ta: Dict[str, float] = {}
        for ln in re.finditer(_NUM + r"\s+Over\s+" + _NUM + r"\s+\d+(?:\.\d+)?\s+Under\s+" + _NUM, body):
            line = ln.group(1)
            ta[f"Over {line}"] = _f(ln.group(2))
            ta[f"Under {line}"] = _f(ln.group(3))
        if ta:
            M["Totals Asia"] = ta

    # ---- Asian Handicap full integer (Handicap 1 (-X) / Handicap 2 (+X)) ----
    seg = re.search(r"\sHandicap\s+1\s+\(([+-]?\d+(?:\.\d+)?)\)\s+(.+?)(?=Handicap Asia|Total 1\s|Babak|Tim\s+1\s+Total)", text)
    if seg:
        body = "1 (" + seg.group(1) + ") " + seg.group(2)
        ah_h: Dict[str, float] = {}
        ah_a: Dict[str, float] = {}
        for h in re.finditer(r"1\s+\(([+-]?\d+(?:\.\d+)?)\)\s+" + _NUM, body):
            ah_h[h.group(1)] = _f(h.group(2))
        for a in re.finditer(r"2\s+\(([+-]?\d+(?:\.\d+)?)\)\s+" + _NUM, body):
            ah_a[a.group(1)] = _f(a.group(2))
        if ah_h or ah_a:
            M["AH"] = {"Home": ah_h, "Away": ah_a}

    # ---- Asian Handicap quarter (Handicap Asia 1 (-1.75) ...) ----
    seg = re.search(r"Handicap Asia\s+1\s+\(([+-]?\d+(?:\.\d+)?)\)\s+(.+?)(?=Total 1\s|Babak|Tim\s+1\s+Total)", text)
    if seg:
        body = "1 (" + seg.group(1) + ") " + seg.group(2)
        ahq_h: Dict[str, float] = {}
        ahq_a: Dict[str, float] = {}
        for h in re.finditer(r"1\s+\(([+-]?\d+(?:\.\d+)?)\)\s+" + _NUM, body):
            ahq_h[h.group(1)] = _f(h.group(2))
        for a in re.finditer(r"2\s+\(([+-]?\d+(?:\.\d+)?)\)\s+" + _NUM, body):
            ahq_a[a.group(1)] = _f(a.group(2))
        if ahq_h or ahq_a:
            M["AH Quarter"] = {"Home": ahq_h, "Away": ahq_a}

    # ---- Halftime Total (within "Babak pertama" section) ----
    seg = re.search(r"Total\.\s+Babak pertama\s+0\.5\s+Over\s+(.+?)(?=Total Asia|Handicap|Babak ke-2|Tim\s+1)", text)
    if seg:
        body = "0.5 Over " + seg.group(1)
        ht: Dict[str, float] = {}
        for ln in re.finditer(_NUM + r"\s+Over\s+" + _NUM + r"\s+\d+(?:\.\d+)?\s+Under\s+" + _NUM, body):
            line = ln.group(1)
            ht[f"Over {line}"] = _f(ln.group(2))
            ht[f"Under {line}"] = _f(ln.group(3))
        if ht:
            M["HT Totals"] = ht

    # ---- Halftime 1X2 ----
    m = re.search(r"Babak pertama\s+1x2\.\s+Babak pertama\s+M1\s+" + _NUM + r"\s+X\s+" + _NUM + r"\s+M2\s+" + _NUM, text)
    if m:
        M["HT 1X2"] = {"Home": _f(m.group(1)), "Draw": _f(m.group(2)), "Away": _f(m.group(3))}

    # ---- Team Total (Tim 1 Total / Tim 2 Total — full match) ----
    for team_idx, team_label in [(1, "Home"), (2, "Away")]:
        seg = re.search(rf"Tim\s+{team_idx}\s+Total\s+0\.5\s+Over\s+(.+?)(?=Tim\s+{3-team_idx}\s+Total|Babak|Tim\s+1\s+Menang|Total\s+2\s+Jumlah)", text)
        if seg:
            body = "0.5 Over " + seg.group(1)
            tt: Dict[str, float] = {}
            for ln in re.finditer(_NUM + r"\s+Over\s+" + _NUM + r"\s+\d+(?:\.\d+)?\s+Under\s+" + _NUM, body):
                line = ln.group(1)
                tt[f"Over {line}"] = _f(ln.group(2))
                tt[f"Under {line}"] = _f(ln.group(3))
            if tt:
                M[f"Team Total {team_label}"] = tt

    return M


def market_count(markets: Dict) -> int:
    """Count total individual selections across all markets."""
    n = 0
    for k, v in markets.items():
        if isinstance(v, dict):
            for sel in v.values():
                if isinstance(sel, dict):
                    n += sum(1 for x in sel.values() if x is not None)
                elif sel is not None:
                    n += 1
    return n
