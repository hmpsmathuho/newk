#!/usr/bin/env python3
"""Cari match Shelbourne vs Waterford di archive/results 1xbet."""
import urllib.request, ssl, json

IP = open('/projects/sandbox/newk/testing/_ip.txt').read().strip()
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
UA='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'

def fetch(p):
    h={'Host':'1xbet.mobi','User-Agent':UA,'Accept':'*/*',
       'Accept-Language':'id-ID,id;q=0.9,en;q=0.8','Referer':'https://1xbet.mobi/id/line'}
    return urllib.request.urlopen(urllib.request.Request(f'https://{IP}{p}', headers=h),
                                  context=ctx, timeout=30).read().decode('utf-8','ignore')

# Try search
for q in ['shelbourne','Shelbourne','waterford','Shelbourne Waterford']:
    try:
        # Search-style endpoint
        for ep in [
            f'/service-api/LineFeed/SearchSquads?text={urllib.parse.quote(q)}&lng=id&country=15',
            f'/service-api/LineFeed/Search?text={urllib.parse.quote(q)}&lng=id&country=15',
            f'/service-api/LineFeed/GetSearchByName?lng=id&country=15&text={urllib.parse.quote(q)}',
        ]:
            try:
                body = fetch(ep)
                d = json.loads(body)
                if d.get('Success') and d.get('Value'):
                    print(f'  [OK] {ep[:90]} : {len(body)}b')
                    print(f'       {json.dumps(d.get("Value"), ensure_ascii=False)[:400]}')
            except Exception as e:
                pass
    except Exception as e:
        pass

# Try Republik Irlandia champ via GetChampsZip
import urllib.parse
champs = json.load(open('/projects/sandbox/newk/testing/_champs_football.json'))
for c in champs:
    n = (c.get('L') or '') + (c.get('CN') or '')
    if 'rlandia' in n.lower() or 'reland' in n.lower():
        print(f'  Irish champ: LI={c.get("LI")} L={c.get("L")} GC={c.get("GC")} CN={c.get("CN")}')

# Also check sports-like search
try:
    body = fetch('/service-api/LineFeed/Get1x2_Zip?sports=1&champs=1417&count=100&lng=id&tz=7&mode=4')
    d = json.loads(body)
    print(f'\n1417: {d.get("Success")} count={len(d.get("Value") or [])}')
except Exception as e:
    print(f'1417 err: {e}')
