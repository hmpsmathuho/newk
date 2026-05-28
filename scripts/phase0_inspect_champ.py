#!/usr/bin/env python3
import urllib.request, ssl, json, sys

IP = open('/projects/sandbox/newk/testing/_ip.txt').read().strip()
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
HOST = '1xbet.mobi'

def fetch(p):
    h = {'Host':HOST,'User-Agent':UA,'Accept':'*/*','Accept-Language':'id-ID,id;q=0.9,en;q=0.8','Referer':f'https://{HOST}/id/line'}
    return urllib.request.urlopen(urllib.request.Request(f'https://{IP}{p}', headers=h), context=ctx, timeout=30).read().decode('utf-8','ignore')

# Test with World Cup 2026 (LI=2708736, GC=72)
LI = 2708736
print(f'=== Test champ LI={LI} (Piala Dunia 2026) ===')

# Try multiple endpoint variations
for path in [
    f'/service-api/LineFeed/GetGamesZip?lng=id&country=15&partner=8&champs={LI}&count=100&tz=7&mode=4',
    f'/service-api/LineFeed/Get1x2_Zip?champs={LI}&count=100&lng=id&tz=7&mode=4&country=15&partner=8',
    f'/service-api/LineFeed/GetGamesByChampZip?champId={LI}&lng=id&tz=7&country=15&partner=8',
    f'/service-api/LineFeed/GetGames?champ={LI}&lng=id&tz=7&country=15&partner=8',
]:
    try:
        body = fetch(path)
        d = json.loads(body)
        v = d.get('Value')
        size_v = len(v) if isinstance(v,list) else (1 if v else 0)
        print(f'  OK [{path[:90]}]')
        print(f'     Success={d.get("Success")} ValueLen={size_v} body={len(body)}b')
        if size_v > 0:
            print(f'     First item type: {type(v[0]).__name__}')
            if isinstance(v[0], dict):
                print(f'     Keys: {list(v[0].keys())[:25]}')
                if 'O1' in v[0]:
                    print(f'     SAMPLE: I={v[0].get("I")} {v[0].get("O1")} vs {v[0].get("O2")} S={v[0].get("S")}')
    except Exception as e:
        print(f'  ERR [{path[:80]}] {e}')

# Save first working response for inspection
print('\n=== Full sample dump ===')
body = fetch(f'/service-api/LineFeed/Get1x2_Zip?champs={LI}&count=100&lng=id&tz=7&mode=4&country=15&partner=8')
d = json.loads(body)
print(f'Value count: {len(d.get("Value") or [])}')
if d.get('Value'):
    print(json.dumps(d['Value'][0], indent=2, ensure_ascii=False)[:1500])
