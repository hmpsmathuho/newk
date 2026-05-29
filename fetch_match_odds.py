#!/usr/bin/env python3
"""Phase 0.3 — fetch odds per kandidat match via GetGameZip."""
import urllib.request, ssl, json, os, time
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
HOST="1xbet.mobi"; IP="83.147.204.86"

# Kandidat match (29/05/2026 upcoming)
CANDIDATES = [
    {"id":723811795,"slug":"liaoning-shanghaiport","home":"Liaoning Tieren","away":"Shanghai Port",
     "league":"China Super League","tier":2,"start":"Fri 29/05 18:35 WIB"},
    {"id":724487733,"slug":"shaanxi-nanjing","home":"Shaanxi Union","away":"Nanjing City",
     "league":"China League One","tier":3,"start":"Fri 29/05 14:00 WIB"},
    {"id":724742130,"slug":"ningbo-nantong","home":"Ningbo","away":"Nantong Zhiyun",
     "league":"China League One","tier":3,"start":"Fri 29/05 18:00 WIB"},
    {"id":724742133,"slug":"guangdong-shenzhen","home":"Guangdong GZ-Power","away":"Shenzhen Juniors",
     "league":"China League One","tier":3,"start":"Fri 29/05 18:30 WIB"},
    {"id":723611726,"slug":"mokawloon-modernsport","home":"El Mokawloon","away":"Modern Sport",
     "league":"Egypt Premier League","tier":2,"start":"Fri 29/05 21:00 WIB"},
    {"id":723611720,"slug":"zed-kahrbaa","home":"ZED","away":"Kahrbaa Alasmalia",
     "league":"Egypt Premier League","tier":2,"start":"Fri 29/05 21:00 WIB"},
    {"id":724258698,"slug":"naftan-torpedobelaz","home":"Naftan","away":"Torpedo-BelAZ",
     "league":"Belarus Premier League","tier":2,"start":"Fri 29/05 22:00 WIB"},
    {"id":724346628,"slug":"iran-gambia","home":"Iran","away":"Republic of the Gambia",
     "league":"Friendlies. National Teams","tier":3,"start":"Fri 29/05 22:30 WIB"},
    {"id":724347853,"slug":"andorra-iraq","home":"Andorra","away":"Iraq",
     "league":"Friendlies. National Teams","tier":3,"start":"Fri 29/05 23:00 WIB"},
    {"id":724346634,"slug":"sa-nicaragua","home":"South Africa","away":"Nicaragua",
     "league":"Friendlies. National Teams","tier":3,"start":"Fri 29/05 23:00 WIB"},
    {"id":724840872,"slug":"fergana-olimpik","home":"Fergana State University","away":"Olimpik MobiUZ",
     "league":"Uzbekistan Pro League","tier":3,"start":"Fri 29/05 19:00 WIB"},
    {"id":724840875,"slug":"terdu-aral","home":"Terdu","away":"Aral",
     "league":"Uzbekistan Pro League","tier":3,"start":"Fri 29/05 19:00 WIB"},
]


def get_json(path):
    url=f"https://{IP}{path}"
    req=urllib.request.Request(url, headers={"Host":HOST,"User-Agent":UA,"Accept":"application/json,*/*"})
    r=urllib.request.urlopen(req, context=ctx, timeout=25)
    return json.loads(r.read().decode("utf-8","ignore"))


def fetch_match(eid):
    return get_json(f"/service-api/LineFeed/GetGameZip?id={eid}&lng=en&tz=7&isSubGames=true&GroupEvents=true&allEventsGroupSubGames=true&countevents=250&grMode=4&country=44&marketType=1")


def main():
    out_dir = "/projects/sandbox/newk/upcoming"
    os.makedirs(out_dir, exist_ok=True)
    summary = {}
    for c in CANDIDATES:
        try:
            data = fetch_match(c["id"])
            v = data.get("Value")
            if not v:
                print(f"  [SKIP] {c['slug']} -> empty Value")
                continue
            with open(os.path.join(out_dir, f"{c['slug']}_RAW.json"), "w") as f:
                json.dump(data, f, ensure_ascii=False)
            n_groups = len(v.get("GE") or [])
            n_events_total = sum(len(g.get("E", [])) for g in (v.get("GE") or []) if isinstance(g, dict))
            summary[c["slug"]] = {**c, "groups": n_groups, "events": n_events_total, "size": len(json.dumps(data))}
            print(f"  [OK]   {c['slug']} -> groups={n_groups} events={n_events_total}")
        except Exception as e:
            print(f"  [ERR]  {c['slug']} -> {e}")
        time.sleep(0.4)

    with open(os.path.join(out_dir, "candidates_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
