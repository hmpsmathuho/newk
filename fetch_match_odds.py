#!/usr/bin/env python3
"""Phase 0.3 — fetch odds per candidate match via GetGameZip (slate 30/05/2026)."""
import urllib.request, ssl, json, os, time
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
      "Mobile/15E148 Safari/604.1")
HOST="1xbet.mobi"; IP="83.147.204.86"

# Kandidat "mudah diprediksi" untuk slate Sabtu 30/05/2026 dini hari + UCL Final malam
CANDIDATES = [
    # Tier-1 European leagues mid-season, clear talent gaps
    {"id":724491840,"slug":"nice-saintetienne","home":"OGC Nice","away":"AS Saint-Etienne",
     "league":"France Ligue 1/2 Barrage","tier":1,"start":"Sat 30/05 01:45 WIB",
     "logic":"Nice (L1 mid) host vs SE (L2 upper). Barrage relegation/promotion. L1 side biasanya menang."},
    {"id":724062261,"slug":"orgryte-elfsborg","home":"Orgryte","away":"Elfsborg",
     "league":"Sweden Allsvenskan","tier":1,"start":"Sat 30/05 00:00 WIB",
     "logic":"Elfsborg established upper-mid Allsvenskan. Orgryte newly promoted."},
    {"id":724088813,"slug":"brann-sarpsborg","home":"Brann","away":"Sarpsborg 08",
     "league":"Norway Eliteserien","tier":1,"start":"Sat 30/05 00:00 WIB",
     "logic":"Brann elite Norwegian club, strong home. Sarpsborg mid-bottom."},
    {"id":723319875,"slug":"fredrikstad-ikstart","home":"Fredrikstad","away":"IK Start",
     "league":"Norway Eliteserien","tier":1,"start":"Sat 30/05 00:00 WIB",
     "logic":"Fredrikstad strong newly-promoted, IK Start struggling lower-table."},
    {"id":723316826,"slug":"rosenborg-bodoglimt","home":"Rosenborg","away":"Bodo-Glimt",
     "league":"Norway Eliteserien","tier":1,"start":"Sat 30/05 00:00 WIB",
     "logic":"Bodo-Glimt CL group stage team, dominant Norwegian. Rosenborg traditional but down."},
    # Italy / France / Ireland / Iceland
    {"id":724033712,"slug":"monza-catanzaro","home":"Monza 1912","away":"Catanzaro 1929",
     "league":"Italy Serie B Playoff","tier":1,"start":"Sat 30/05 01:00 WIB",
     "logic":"Serie B promotion semifinal. Monza ex-Serie A, Catanzaro mid-table B. Playoff variance."},
    {"id":722374797,"slug":"shelbourne-galway","home":"Shelbourne","away":"Galway",
     "league":"Ireland Premier League","tier":2,"start":"Sat 30/05 01:45 WIB",
     "logic":"Shelbourne defending champion, Galway promoted/mid."},
    {"id":722374794,"slug":"dundalk-derry","home":"Dundalk","away":"Derry City",
     "league":"Ireland Premier League","tier":2,"start":"Sat 30/05 01:45 WIB",
     "logic":"Derry top-3, Dundalk relegation zone. Talent gap clear."},
    {"id":722375391,"slug":"shamrock-stpats","home":"Shamrock Rovers","away":"St Patrick's Athletic",
     "league":"Ireland Premier League","tier":2,"start":"Sat 30/05 02:00 WIB",
     "logic":"Both top-half but Shamrock perennial winners."},
    {"id":723346466,"slug":"fram-breidablik","home":"Fram","away":"Breidablik",
     "league":"Iceland Urvalsdeild","tier":2,"start":"Sat 30/05 02:15 WIB",
     "logic":"Breidablik traditional top-3 Iceland, Fram newly-promoted/struggle."},
    # Egypt PL relegation group final
    {"id":723611729,"slug":"nbe-ittihad","home":"National Bank of Egypt","away":"Al Ittihad Alexandria",
     "league":"Egypt Premier League","tier":2,"start":"Sat 30/05 00:00 WIB",
     "logic":"Egypt PL Reg-Group final round. NBE strong defensively. Both safe likely → low-scoring."},
    # UCL Final - hard but well-researched
    {"id":718933777,"slug":"psg-arsenal","home":"Paris Saint-Germain","away":"Arsenal",
     "league":"UEFA Champions League FINAL","tier":1,"start":"Sat 30/05 23:00 WIB",
     "logic":"UCL Final, 2 elite squads. High variance but TONS of data. Market sangat efficient."},
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
            summary[c["slug"]] = {**c, "groups": n_groups, "size": len(json.dumps(data))}
            print(f"  [OK]   {c['slug']:<28} -> groups={n_groups}  ({c['league']})")
        except Exception as e:
            print(f"  [ERR]  {c['slug']:<28} -> {e}")
        time.sleep(0.3)

    with open(os.path.join(out_dir, "candidates_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
