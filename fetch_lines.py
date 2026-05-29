#!/usr/bin/env python3
"""Phase 0 (real) — fetch upcoming matches via 1xbet service-api.

Endpoint: /service-api/LineFeed/Get1x2_VZip?sports=1&count=N&lng=en&tf=...&tz=7&mode=4
- sports=1   -> football
- tz=7       -> WIB (UTC+7)
- count=N    -> max events
- lng=en     -> English names (we'll also try lng=id)
- tf=...     -> "time-from" filter, ms-resolution? Actually it's a date-encoded number.

Plan: just pull a big batch (count=300), no time filter; filter client-side by event start time.
"""
import urllib.request
import ssl
import json
import os
import time
from datetime import datetime, timezone, timedelta

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
      "Mobile/15E148 Safari/604.1")
HOST = "1xbet.mobi"
IP = "83.147.204.86"  # resolved earlier; will retry if stale


def resolve():
    req = urllib.request.Request(
        "https://1.1.1.1/dns-query?name=1xbet.mobi&type=A",
        headers={"accept": "application/dns-json"},
    )
    r = urllib.request.urlopen(req, context=ctx, timeout=8)
    data = json.load(r)
    return [a["data"] for a in data.get("Answer", []) if a.get("type") == 1][0]


def fetch_json(path):
    url = f"https://{IP}{path}"
    req = urllib.request.Request(url, headers={
        "Host": HOST, "User-Agent": UA, "Accept": "application/json,*/*",
        "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
    })
    r = urllib.request.urlopen(req, context=ctx, timeout=25)
    return json.loads(r.read().decode("utf-8", "ignore"))


def main():
    global IP
    IP = resolve()
    print(f"[*] IP={IP}")

    # Pull a large batch of football events
    path = "/service-api/LineFeed/Get1x2_VZip?sports=1&count=400&lng=en&tz=7&mode=4"
    print(f"[*] GET {path}")
    data = fetch_json(path)
    events = data.get("Value") or []
    print(f"[*] Got {len(events)} events")

    # Sample one
    if events:
        ev = events[0]
        keys = sorted(ev.keys())
        print(f"[*] Sample event keys: {keys}")

    out_dir = "/projects/sandbox/newk/upcoming"
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "lines_raw.json"), "w") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"[*] Saved raw -> {out_dir}/lines_raw.json")

    # Parse + filter upcoming next 48h
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(hours=48)
    print(f"[*] Now (UTC): {now.isoformat(timespec='seconds')}")
    print(f"[*] Horizon: +48h = {horizon.isoformat(timespec='seconds')}")

    upcoming = []
    for ev in events:
        # Common 1xbet fields:
        # I = event id, S = start time (unix), O1 = home name, O2 = away name,
        # L = league name, LE = league id, LI = league id alt, LR = league region,
        # SE = season info, COR = country
        eid = ev.get("I")
        ts = ev.get("S")
        home = ev.get("O1") or ev.get("O1E") or ""
        away = ev.get("O2") or ev.get("O2E") or ""
        league = ev.get("L") or ev.get("LE") or ""
        country = ev.get("COR") or ev.get("CN") or ""
        if not (eid and ts and home and away):
            continue
        start = datetime.fromtimestamp(ts, tz=timezone.utc)
        if start < now or start > horizon:
            continue
        upcoming.append({
            "id": eid, "start_utc": start.isoformat(timespec="minutes"),
            "start_wib": (start + timedelta(hours=7)).isoformat(timespec="minutes"),
            "home": home, "away": away, "league": league, "country": country,
            "ts": ts,
        })

    upcoming.sort(key=lambda x: x["ts"])
    print(f"[*] Upcoming next 48h: {len(upcoming)} matches")

    with open(os.path.join(out_dir, "upcoming_48h.json"), "w") as f:
        json.dump(upcoming, f, indent=2, ensure_ascii=False)

    # Print first 40
    for u in upcoming[:60]:
        print(f"  {u['start_wib']} WIB | id={u['id']:>10} | {u['country'][:18]:<18} | {u['league'][:30]:<30} | {u['home']} vs {u['away']}")


if __name__ == "__main__":
    main()
