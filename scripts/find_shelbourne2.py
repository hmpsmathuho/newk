#!/usr/bin/env python3
"""Fetch Irish Premier League matches dari 1xbet, cari Shelbourne vs Waterford."""
import urllib.request, ssl, json, datetime as dt

IP = open('/projects/sandbox/newk/testing/_ip.txt').read().strip()
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
UA='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'

def fetch(p):
    h={'Host':'1xbet.mobi','User-Agent':UA,'Accept':'*/*',
       'Accept-Language':'id-ID,id;q=0.9,en;q=0.8','Referer':'https://1xbet.mobi/id/line'}
    return urllib.request.urlopen(urllib.request.Request(f'https://{IP}{p}', headers=h),
                                  context=ctx, timeout=30).read().decode('utf-8','ignore')

# Irish Premier = LI 119445. Get future matches.
for path in [
    '/service-api/LineFeed/Get1x2_Zip?champs=119445&count=100&lng=id&tz=7&mode=4&country=15&partner=8',
]:
    body = fetch(path)
    d = json.loads(body)
    print(f'Future Irish matches: {len(d.get("Value") or [])}')
    for m in (d.get('Value') or []):
        s = m.get('S')
        sw = (dt.datetime.utcfromtimestamp(s)+dt.timedelta(hours=7)).strftime('%Y-%m-%d %H:%M')
        print(f'  [{sw}] {m.get("O1")} vs {m.get("O2")}  id={m.get("I")}')

# Try archive (results) endpoint
print('\n=== Try Results / Archive ===')
for path in [
    '/service-api/LineFeed/GetResults?lng=id&champs=119445&country=15&partner=8',
    '/service-api/LineFeed/GetResultsZip?lng=id&champs=119445&country=15&partner=8',
    '/service-api/Results/GetResultsZip?lng=id&sports=1&champs=119445&date=2026-05-22',
]:
    try:
        body = fetch(path)
        d = json.loads(body)
        v = d.get('Value') or []
        print(f'  [{path[:80]}] success={d.get("Success")} count={len(v)}')
        if v:
            for m in v[:5]:
                print(f'      {json.dumps(m, ensure_ascii=False)[:200]}')
    except Exception as e:
        print(f'  [{path[:80]}] err {e}')

# Try direct match id guess - search by name in events
print('\n=== Direct GetGameZip on guessed IDs ===')
# 22 May 2026 Irish Premier matches were:
# Reading match IDs would need archive. Try latest-result API:
try:
    body = fetch('/service-api/Results/GetSportsZip?lng=id&country=15&partner=8&dateFrom=2026-05-22&dateTo=2026-05-22')
    d = json.loads(body)
    print(f'GetSportsZip: {d.get("Success")} val={len(d.get("Value") or [])}')
except Exception as e:
    print(f'err {e}')
