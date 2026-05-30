#!/usr/bin/env python3
"""Fetch ALL football matches today+tomorrow (WIB) from 1xbet service-api,
parse odds, write to Excel.

Strategy:
1. GetChampsZip → list all 320 football champs (leagues)
2. Per champ → Get1x2_VZip?champs=<LI> → up to 50 events with embedded odds
3. Dedupe by event ID, filter to window (now → end of tomorrow WIB)
4. Parse markets from E + AE arrays
5. Write Excel: Sheet1 = match summary, Sheet2 = full markets long-format
"""
import urllib.request
import ssl
import json
import time
import os
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

# --- HTTP setup ---
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
      "Mobile/15E148 Safari/604.1")
HOST = "1xbet.mobi"
IP = "83.147.204.86"


def http_get(path, retry=3):
    for i in range(retry):
        try:
            req = urllib.request.Request(
                f"https://{IP}{path}",
                headers={"Host": HOST, "User-Agent": UA, "Accept": "application/json,*/*"},
            )
            return urllib.request.urlopen(req, context=ctx, timeout=25).read().decode("utf-8", "ignore")
        except Exception as e:
            if i == retry - 1:
                raise
            time.sleep(0.6)


def get_json(path, retry=3):
    return json.loads(http_get(path, retry=retry))


# --- Group/Type → market label mapping ---
# Based on reverse-engineered 1xbet schema
G_LABELS = {
    1: "1X2",
    2: "AH",
    8: "DC",
    15: "ITT_Home",
    17: "OU",
    19: "BTTS",
    20: "CS",
    62: "ITT_Away",
    99: "OU_Asian",
    136: "Result+Total",
    2854: "AH_Asian",
    11412: "1stHalf_1X2_BTTS",
    8427: "AH_Home_Asian",
    8429: "AH_Away_Asian",
    8863: "Result+Total_full",
}

T_LABELS = {  # for outcome within group
    1: "Home", 2: "Draw", 3: "Away",
    4: "1X", 5: "12", 6: "X2",
    7: "AH_Home", 8: "AH_Away",
    9: "Over", 10: "Under",
    11: "ITT_Home_O", 12: "ITT_Home_U",
    13: "ITT_Away_O", 14: "ITT_Away_U",
    180: "BTTS_Yes", 181: "BTTS_No",
    3827: "OU_Asian_Over", 3828: "OU_Asian_Under",
    3829: "AH_Asian_Home", 3830: "AH_Asian_Away",
}


def parse_event_odds(ev):
    """Extract key markets from event entry (E array + AE array)."""
    odds = {}
    # Combine E (main) + AE (additional) entries
    entries = list(ev.get("E", []))
    for ae in ev.get("AE", []):
        if isinstance(ae, dict):
            entries.extend(ae.get("ME", []) or [])

    # Build dict (G, T, P or None) → C
    bucket = {}
    for e in entries:
        if not isinstance(e, dict):
            continue
        G, T, P, C = e.get("G"), e.get("T"), e.get("P"), e.get("C")
        if C is None or T is None or G is None:
            continue
        bucket[(G, T, P)] = float(C)

    # Helper to fetch
    def b(G, T, P=None):
        return bucket.get((G, T, P))

    # 1X2 (G=1)
    odds["1X2_H"] = b(1, 1)
    odds["1X2_D"] = b(1, 2)
    odds["1X2_A"] = b(1, 3)

    # Double Chance (G=8)
    odds["DC_1X"] = b(8, 4)
    odds["DC_12"] = b(8, 5)
    odds["DC_X2"] = b(8, 6)

    # BTTS (G=19)
    odds["BTTS_Yes"] = b(19, 180)
    odds["BTTS_No"] = b(19, 181)

    # Total goals integer (G=17)
    for ln in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
        odds[f"O{ln}"] = b(17, 9, ln)
        odds[f"U{ln}"] = b(17, 10, ln)

    # Total Asian quarter (G=99)
    for ln in [1.25, 1.75, 2.25, 2.75, 3.25, 3.75]:
        odds[f"O{ln}_A"] = b(99, 3827, ln)
        odds[f"U{ln}_A"] = b(99, 3828, ln)

    # AH integer (G=2). Capture key lines only.
    for ln in [-2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2]:
        odds[f"AH_H_{ln:+}"] = b(2, 7, ln if ln != 0 else None)
        odds[f"AH_A_{ln:+}"] = b(2, 8, ln if ln != 0 else None)

    # AH Asian quarter (G=2854)
    for ln in [-1.75, -1.25, -0.75, -0.25, 0.25, 0.75, 1.25, 1.75]:
        odds[f"AHa_H_{ln:+}"] = b(2854, 3829, ln)
        odds[f"AHa_A_{ln:+}"] = b(2854, 3830, ln)

    # Individual Total Home (G=15) / Away (G=62) — key lines
    for ln in [0.5, 1.5, 2.5]:
        odds[f"ITT_H_O{ln}"] = b(15, 11, ln)
        odds[f"ITT_H_U{ln}"] = b(15, 12, ln)
        odds[f"ITT_A_O{ln}"] = b(62, 13, ln)
        odds[f"ITT_A_U{ln}"] = b(62, 14, ln)

    return odds


def build_match_row(ev, odds):
    """Combine event metadata + odds into one Excel row."""
    s = ev.get("S")
    if s:
        utc = datetime.fromtimestamp(s, tz=timezone.utc)
        wib = utc + timedelta(hours=7)
    else:
        wib = utc = None
    wp = ev.get("WP") or {}
    return {
        "ID": ev.get("I"),
        "Kickoff_WIB": wib.strftime("%a %d/%m %H:%M") if wib else "",
        "UTC_TS": s,
        "Country": ev.get("CN", "") or "",
        "League": ev.get("L", "") or "",
        "Home": ev.get("O1", "") or "",
        "Away": ev.get("O2", "") or "",
        "WP_H": wp.get("P1"),
        "WP_X": wp.get("PX"),
        "WP_A": wp.get("P2"),
        **odds,
    }


def fetch_champs():
    j = get_json("/service-api/LineFeed/GetChampsZip?sport=1&lng=en&tz=7")
    return j.get("Value") or []


def fetch_champ_events(champ_id):
    path = f"/service-api/LineFeed/Get1x2_VZip?champs={champ_id}&count=200&lng=en&tz=7&mode=4"
    j = get_json(path)
    return j.get("Value") or []


def main():
    # --- Window definition: today + tomorrow (WIB) ---
    now_utc = datetime.now(timezone.utc)
    now_wib = now_utc + timedelta(hours=7)
    today_wib = now_wib.date()
    tomorrow_wib = today_wib + timedelta(days=1)
    end_tomorrow_wib = datetime.combine(tomorrow_wib + timedelta(days=1),
                                         datetime.min.time())  # start of day-after-tomorrow
    end_tomorrow_utc = end_tomorrow_wib - timedelta(hours=7)
    end_tomorrow_utc = end_tomorrow_utc.replace(tzinfo=timezone.utc)

    print(f"[*] Now (WIB):       {now_wib.strftime('%a %d/%m/%Y %H:%M')}")
    print(f"[*] Window end:      end of {tomorrow_wib} WIB = {end_tomorrow_utc.isoformat()}")
    print(f"[*] Window: {now_utc} → {end_tomorrow_utc}")

    # --- Fetch champs ---
    print("\n[1/4] Fetching champ list (sport=1)...")
    champs = fetch_champs()
    print(f"    Got {len(champs)} champs")

    # --- Iterate champs, dedupe events, filter window ---
    print("\n[2/4] Fetching events per champ...")
    seen = {}  # event_id -> event
    failed_champs = 0
    for i, c in enumerate(champs, 1):
        cid = c.get("LI")
        cname = c.get("L", "")
        gc = c.get("GC", 0) or 0
        if not cid or gc == 0:
            continue
        try:
            evs = fetch_champ_events(cid)
        except Exception as e:
            failed_champs += 1
            if failed_champs <= 5:
                print(f"    ERR champ {cid} ({cname}): {str(e)[:60]}")
            time.sleep(0.4)
            continue
        n_in_window = 0
        for ev in evs:
            ts = ev.get("S")
            if not ts:
                continue
            ev_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
            if ev_utc < now_utc or ev_utc > end_tomorrow_utc:
                continue
            eid = ev.get("I")
            if eid in seen:
                continue
            seen[eid] = ev
            n_in_window += 1
        if i % 30 == 0 or n_in_window > 0:
            print(f"    [{i:>3}/{len(champs)}] {cname[:50]:<50} +{n_in_window:>3} events  (total so far: {len(seen)})")
        time.sleep(0.18)  # politeness

    print(f"\n    Total unique events in window: {len(seen)}")
    print(f"    Failed champ fetches: {failed_champs}")

    # --- Build rows ---
    print("\n[3/4] Parsing odds per event...")
    rows = []
    for ev in seen.values():
        odds = parse_event_odds(ev)
        row = build_match_row(ev, odds)
        rows.append(row)
    rows.sort(key=lambda r: r.get("UTC_TS") or 0)

    # Save raw JSON for safety
    out_dir = "/projects/sandbox/newk/upcoming"
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "all_matches_today_tomorrow.json"), "w") as f:
        json.dump([{**ev, "_parsed_odds": parse_event_odds(ev)} for ev in seen.values()],
                  f, ensure_ascii=False, indent=1, default=str)

    # --- Write Excel ---
    print("\n[4/4] Writing Excel...")
    wb = openpyxl.Workbook()
    # Sheet 1: Match Summary (one row per match, key markets)
    ws = wb.active
    ws.title = "Matches"

    # Define column headers
    ODDS_COLS = [
        "1X2_H", "1X2_D", "1X2_A",
        "DC_1X", "DC_12", "DC_X2",
        "BTTS_Yes", "BTTS_No",
        "O0.5", "U0.5", "O1.5", "U1.5", "O2.5", "U2.5",
        "O3.5", "U3.5", "O4.5", "U4.5",
        "O1.25_A", "U1.25_A", "O1.75_A", "U1.75_A",
        "O2.25_A", "U2.25_A", "O2.75_A", "U2.75_A",
        "O3.25_A", "U3.25_A", "O3.75_A", "U3.75_A",
        "AH_H_-2", "AH_H_-1.5", "AH_H_-1", "AH_H_-0.5", "AH_H_+0",
        "AH_H_+0.5", "AH_H_+1", "AH_H_+1.5", "AH_H_+2",
        "AH_A_-2", "AH_A_-1.5", "AH_A_-1", "AH_A_-0.5", "AH_A_+0",
        "AH_A_+0.5", "AH_A_+1", "AH_A_+1.5", "AH_A_+2",
        "AHa_H_-1.75", "AHa_H_-1.25", "AHa_H_-0.75", "AHa_H_-0.25",
        "AHa_H_+0.25", "AHa_H_+0.75", "AHa_H_+1.25", "AHa_H_+1.75",
        "AHa_A_-1.75", "AHa_A_-1.25", "AHa_A_-0.75", "AHa_A_-0.25",
        "AHa_A_+0.25", "AHa_A_+0.75", "AHa_A_+1.25", "AHa_A_+1.75",
        "ITT_H_O0.5", "ITT_H_U0.5", "ITT_H_O1.5", "ITT_H_U1.5", "ITT_H_O2.5", "ITT_H_U2.5",
        "ITT_A_O0.5", "ITT_A_U0.5", "ITT_A_O1.5", "ITT_A_U1.5", "ITT_A_O2.5", "ITT_A_U2.5",
    ]
    HEAD = ["ID", "Kickoff_WIB", "Country", "League", "Home", "Away",
            "WP_H", "WP_X", "WP_A"] + ODDS_COLS

    # Write header
    head_font = Font(bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor="2F5496")
    for col_i, h in enumerate(HEAD, 1):
        c = ws.cell(row=1, column=col_i, value=h)
        c.font = head_font
        c.fill = head_fill
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Write data rows
    for row_i, r in enumerate(rows, 2):
        for col_i, h in enumerate(HEAD, 1):
            v = r.get(h)
            if v is not None:
                ws.cell(row=row_i, column=col_i, value=v)

    # Column widths (basic auto-size)
    widths = {"A": 11, "B": 17, "C": 14, "D": 36, "E": 26, "F": 26}
    for col_letter, w in widths.items():
        ws.column_dimensions[col_letter].width = w
    for col_letter in [chr(ord('G') + i) for i in range(len(HEAD) - 6)]:
        if col_letter <= "Z":
            ws.column_dimensions[col_letter].width = 8.5

    # Freeze header + first 6 columns (info)
    ws.freeze_panes = "G2"

    # Sheet 2: Long-format (one row per market outcome)
    ws2 = wb.create_sheet("Markets_Long")
    ws2.append(["Match_ID", "Kickoff_WIB", "Match", "League", "Country",
                "Group_ID", "Group_Label", "Type_ID", "Type_Label",
                "Param", "Odds"])
    for c in ws2[1]:
        c.font = head_font
        c.fill = head_fill
    long_count = 0
    for ev in seen.values():
        s = ev.get("S")
        wib_str = (datetime.fromtimestamp(s, tz=timezone.utc) + timedelta(hours=7)).strftime("%a %d/%m %H:%M") if s else ""
        match_str = f"{ev.get('O1','')} vs {ev.get('O2','')}"
        league = ev.get("L", "")
        country = ev.get("CN", "")
        eid = ev.get("I")
        entries = list(ev.get("E", []))
        for ae in ev.get("AE", []):
            if isinstance(ae, dict):
                entries.extend(ae.get("ME", []) or [])
        for e in entries:
            if not isinstance(e, dict):
                continue
            G, T, P, C = e.get("G"), e.get("T"), e.get("P"), e.get("C")
            if C is None or T is None or G is None:
                continue
            ws2.append([eid, wib_str, match_str, league, country,
                       G, G_LABELS.get(G, f"G{G}"),
                       T, T_LABELS.get(T, f"T{T}"),
                       P, float(C)])
            long_count += 1
    ws2.freeze_panes = "A2"
    for col_letter, w in {"A": 11, "B": 17, "C": 36, "D": 36, "E": 14,
                           "F": 9, "G": 14, "H": 9, "I": 14, "J": 8, "K": 8}.items():
        ws2.column_dimensions[col_letter].width = w

    # Sheet 3: Champ summary
    ws3 = wb.create_sheet("Champs")
    ws3.append(["LI", "League", "Country", "GC_total", "Events_in_window"])
    for c in ws3[1]:
        c.font = head_font
        c.fill = head_fill
    champ_in_window = defaultdict(int)
    for ev in seen.values():
        champ_in_window[ev.get("LE") or 0] += 1
    for c in champs:
        cid = c.get("LI")
        cnt = champ_in_window.get(cid, 0)
        if cnt > 0:
            ws3.append([cid, c.get("L", ""), "", c.get("GC", 0), cnt])
    ws3.column_dimensions["A"].width = 11
    ws3.column_dimensions["B"].width = 50
    ws3.column_dimensions["C"].width = 16

    out_path = f"/projects/sandbox/newk/matches_{today_wib.strftime('%d%b%Y').lower()}.xlsx"
    wb.save(out_path)
    file_size = os.path.getsize(out_path) / 1024
    print(f"\n[*] Saved: {out_path}  ({file_size:.0f} KB)")
    print(f"    Sheet 1 'Matches':      {len(rows)} matches × {len(HEAD)} columns")
    print(f"    Sheet 2 'Markets_Long': {long_count} odds rows")
    print(f"    Sheet 3 'Champs':       {sum(1 for c in champs if champ_in_window.get(c.get('LI')))} active leagues")

    # Country breakdown
    by_country = defaultdict(int)
    for r in rows:
        by_country[r["Country"]] += 1
    print(f"\n[*] Top 12 countries by match count:")
    for cn, n in sorted(by_country.items(), key=lambda x: -x[1])[:12]:
        print(f"      {n:>4}  {cn}")


if __name__ == "__main__":
    main()
