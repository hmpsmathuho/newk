"""1xbet.mobi LineFeed API client (Section 4 — External Data Source).

Resolves IP via Cloudflare DoH (geo-block bypass), aggregates upcoming
events across multiple country params (API caps at 50/call), and fetches
full odds (200+ markets) per match via GetGameZip. Output schema matches
src.parser.odds_extractor.extract_markets so the downstream pipeline is reused.
"""
from __future__ import annotations

import json
import ssl
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Dict, List


_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

_HEADERS = {
    "Host": "1xbet.mobi",
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
        "Mobile/15E148 Safari/604.1"
    ),
    "Accept": "application/json",
}


def resolve_ip(host: str = "1xbet.mobi", doh: str = "https://1.1.1.1/dns-query") -> str:
    """Resolve hostname via DNS-over-HTTPS (Cloudflare)."""
    req = urllib.request.Request(
        f"{doh}?name={host}&type=A",
        headers={"accept": "application/dns-json"},
    )
    r = urllib.request.urlopen(req, context=_CTX, timeout=10)
    data = json.load(r)
    answers = [a["data"] for a in data.get("Answer", []) if a.get("type") == 1]
    if not answers:
        raise RuntimeError(f"DNS resolve failed for {host}")
    return answers[0]


def fetch_upcoming(ip: str, country_codes: List[int] | None = None,
                   sport_id: int = 1, count: int = 50,
                   timeout: int = 25) -> List[dict]:
    """Aggregate upcoming events across multiple country params.

    API caps response at 50 events. We hit several country-coded endpoints
    and dedupe by event ID to assemble a fuller picture.
    """
    if country_codes is None:
        country_codes = [2, 20, 110, 71, 19, 8, 152, 145]

    seen: Dict[int, dict] = {}
    base = f"sports={sport_id}&count={count}&lng=en&mode=4"
    variants = [base, base + "&top=true"] + [f"{base}&country={c}" for c in country_codes]
    for variant in variants:
        url = f"https://{ip}/service-api/LineFeed/Get1x2_VZip?{variant}"
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            body = urllib.request.urlopen(req, context=_CTX, timeout=timeout).read().decode("utf-8", "ignore")
            data = json.loads(body)
        except Exception:
            continue
        for ev in data.get("Value", []) or []:
            mid = ev.get("I")
            if mid and mid not in seen:
                seen[mid] = ev
    out = list(seen.values())
    out.sort(key=lambda e: e.get("S", 0))
    return out


def filter_serious_matches(events: List[dict],
                           min_unix: int | None = None,
                           max_unix: int | None = None) -> List[dict]:
    """Drop placeholder, youth, women, futsal, virtual matches."""
    bad_substrings = (
        "U21", "U23", "U19", "U17", "Youth", "Reserve", "Women",
        "6x6", "II", "III", "Mini Euro", "Virtual", "ESports",
    )

    def is_real(e: dict) -> bool:
        h = (e.get("O1") or "").strip()
        a = (e.get("O2") or "").strip()
        L = e.get("L", "")
        if h == "Home" and a == "Away":
            return False
        for s in bad_substrings:
            if s in h or s in a or s in L:
                return False
        if min_unix is not None and e.get("S", 0) < min_unix:
            return False
        if max_unix is not None and e.get("S", 0) > max_unix:
            return False
        return True

    return [e for e in events if is_real(e)]


def fetch_match_odds(ip: str, match_id: int, timeout: int = 25) -> dict | None:
    """Fetch full odds (200+ markets) for a single match via GetGameZip."""
    url = (
        f"https://{ip}/service-api/LineFeed/GetGameZip"
        f"?id={match_id}&lng=en&isSubGames=true&GroupEvents=true"
        f"&grMode=4&country=2&fcountry=2&marketType=1"
    )
    req = urllib.request.Request(url, headers=_HEADERS)
    body = urllib.request.urlopen(req, context=_CTX, timeout=timeout).read().decode("utf-8", "ignore")
    data = json.loads(body)
    v = data.get("Value")
    return v if isinstance(v, dict) else None


def parse_apivalue_to_markets(value: dict) -> dict:
    """Convert 1xbet GetGameZip Value (G/T/P/C events) into the standard
    markets dict consumed by downstream evaluators."""
    events: List[dict] = list(value.get("E", []) or [])
    for grp in value.get("GE", []) or []:
        for sub in grp.get("E", []) or []:
            if isinstance(sub, list):
                events.extend(sub)
            elif isinstance(sub, dict):
                events.append(sub)

    by_gtp: Dict[tuple, float] = {}
    for e in events:
        if not isinstance(e, dict):
            continue
        g, t, p, c = e.get("G"), e.get("T"), e.get("P"), e.get("C")
        if c is None:
            continue
        key = (g, t, p)
        if key not in by_gtp:
            by_gtp[key] = c

    M: dict = {}

    h = by_gtp.get((1, 1, None))
    d = by_gtp.get((1, 2, None))
    a = by_gtp.get((1, 3, None))
    if h and d and a:
        M["1X2"] = {"Home": h, "Draw": d, "Away": a}

    if all((8, t, None) in by_gtp for t in (4, 5, 6)):
        M["DC"] = {"1X": by_gtp[(8, 4, None)],
                   "12": by_gtp[(8, 5, None)],
                   "X2": by_gtp[(8, 6, None)]}

    btts_y = by_gtp.get((19, 180, None)) or by_gtp.get((15, 180, None))
    btts_n = by_gtp.get((19, 181, None)) or by_gtp.get((15, 181, None))
    if btts_y and btts_n:
        M["BTTS"] = {"Yes": btts_y, "No": btts_n}

    totals: Dict[str, float] = {}
    for (g, t, p), c in by_gtp.items():
        if g == 17 and p is not None:
            if t == 9: totals[f"Over {p}"] = c
            elif t == 10: totals[f"Under {p}"] = c
    if totals:
        M["Totals"] = totals

    ta: Dict[str, float] = {}
    for (g, t, p), c in by_gtp.items():
        if g == 99 and p is not None:
            if t == 3827: ta[f"Over {p}"] = c
            elif t == 3828: ta[f"Under {p}"] = c
    if ta:
        M["Totals Asia"] = ta

    ah_h: Dict[str, float] = {}
    ah_a: Dict[str, float] = {}
    for (g, t, p), c in by_gtp.items():
        if g == 2 and p is not None:
            if t == 7: ah_h[f"{p:+g}"] = c
            elif t == 8: ah_a[f"{p:+g}"] = c
    if ah_h or ah_a:
        M["AH"] = {"Home": ah_h, "Away": ah_a}

    ahq_h: Dict[str, float] = {}
    ahq_a: Dict[str, float] = {}
    for (g, t, p), c in by_gtp.items():
        if g == 8427 and p is not None:
            ahq_h[f"{p:+g}"] = c
        elif g == 8429 and p is not None:
            ahq_a[f"{p:+g}"] = c
    if ahq_h or ahq_a:
        M["AH Quarter"] = {"Home": ahq_h, "Away": ahq_a}

    ht: Dict[str, float] = {}
    for (g, t, p), c in by_gtp.items():
        if g == 18 and p is not None:
            if t == 11: ht[f"Over {p}"] = c
            elif t == 12: ht[f"Under {p}"] = c
    if ht:
        M["HT Totals"] = ht

    ht_h = by_gtp.get((154, 475, None))
    ht_d = by_gtp.get((154, 476, None))
    ht_a = by_gtp.get((154, 477, None))
    if ht_h and ht_d and ht_a:
        M["HT 1X2"] = {"Home": ht_h, "Draw": ht_d, "Away": ht_a}

    tth: Dict[str, float] = {}
    for (g, t, p), c in by_gtp.items():
        if p is None:
            continue
        if (g == 15 and t == 11) or (g == 62 and t == 13):
            tth[f"Over {p}"] = c
        elif (g == 15 and t == 12) or (g == 62 and t == 14):
            tth[f"Under {p}"] = c
    if tth:
        M["Team Total Home"] = tth

    tta: Dict[str, float] = {}
    for (g, t, p), c in by_gtp.items():
        if p is None:
            continue
        if g == 88 and t in (15, 749):
            tta[f"Over {p}"] = c
        elif g == 88 and t in (16, 750):
            tta[f"Under {p}"] = c
    if tta:
        M["Team Total Away"] = tta

    return M


def fetch_meta_from_apivalue(value: dict) -> dict:
    """Extract match meta (home/away/league/kickoff) from API Value."""
    return {
        "home": value.get("O1") or value.get("O1E") or "",
        "away": value.get("O2") or value.get("O2E") or "",
        "league": value.get("L", ""),
        "kickoff_unix": value.get("S", 0),
        "kickoff_wib": (
            datetime.fromtimestamp(value.get("S", 0), tz=timezone(timedelta(hours=7))).strftime("%Y-%m-%d %H:%M")
            if value.get("S")
            else ""
        ),
        "match_id": value.get("I"),
    }
