#!/usr/bin/env python3
"""Coba endpoint lain untuk dapat lebih banyak match."""
import urllib.request, ssl, json, datetime as dt

IP = open('/projects/sandbox/newk/testing/_ip.txt').read().strip()
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
HOST = '1xbet.mobi'

def fetch(path):
    url = f'https://{IP}{path}'
    h = {'Host': HOST, 'User-Agent': UA, 'Accept': '*/*',
         'Accept-Language': 'id-ID,id;q=0.9,en;q=0.8',
         'Referer': f'https://{HOST}/id/line'}
    req = urllib.request.Request(url, headers=h)
    return urllib.request.urlopen(req, context=ctx, timeout=30).read().decode('utf-8', 'ignore')

# Try GetChampsZip then specific champ
print('=== GetChampsZip filter only Football ===')
data = json.loads(fetch('/service-api/LineFeed/GetChampsZip?lng=id&country=15&partner=8&virtualSports=true&groupChamps=true'))
champs_football = [c for c in data.get('Value', []) if c.get('SI') == 1]
print(f'Total football champs: {len(champs_football)}')
for c in champs_football[:30]:
    print(f"  L={c.get('LI')}  {c.get('L')}  GC={c.get('GC')}  CN={c.get('CN','')}")

# Save for later
with open('/projects/sandbox/newk/testing/_champs_football.json', 'w') as f:
    json.dump(champs_football, f, indent=2)

print(f'\nTotal football matches across all champs (sum GC): {sum(c.get("GC",0) for c in champs_football)}')

# Try paginated list with sport=1, all leagues
print('\n=== GetGamesZip via different params (paginate skip) ===')
all_matches = {}
for skip in range(0, 600, 50):
    path = f'/service-api/LineFeed/Get1x2_Zip?sports=1&count=50&skip={skip}&lng=id&tf=2200000&tz=7&mode=4&country=15&partner=8&getEmpty=true'
    try:
        d = json.loads(fetch(path))
        if d.get('Success') and d.get('Value'):
            new = 0
            for m in d['Value']:
                if m['I'] not in all_matches:
                    all_matches[m['I']] = m
                    new += 1
            print(f'  skip={skip}: returned {len(d["Value"])}, new {new}, total {len(all_matches)}')
            if new == 0:
                break
    except Exception as e:
        print(f'  skip={skip}: error {e}')
        break

print(f'\nGrand total unique football matches: {len(all_matches)}')

# Save all
with open('/projects/sandbox/newk/testing/_lobby_api.json', 'w') as f:
    json.dump({'count': len(all_matches), 'matches': list(all_matches.values())}, f)

# Bucket by time
now_utc = dt.datetime.utcnow()
today_wib = (now_utc + dt.timedelta(hours=7)).date()
buckets = {'past':0,'siang_today':0,'malam_today':0,'subuh_besok':0,'pagi_besok':0,'later':0}
window_malam=[]
window_subuh_besok=[]
for m in all_matches.values():
    ts=m.get('S')
    if not ts: continue
    su=dt.datetime.utcfromtimestamp(ts)
    sw=su+dt.timedelta(hours=7)
    if su < now_utc:
        buckets['past']+=1; continue
    if sw.date()==today_wib:
        if sw.hour<12: buckets['siang_today']+=1
        elif sw.hour<19: buckets['siang_today']+=1
        else: buckets['malam_today']+=1; window_malam.append(m)
    elif sw.date()==today_wib+dt.timedelta(days=1):
        if sw.hour<7: buckets['subuh_besok']+=1; window_subuh_besok.append(m)
        elif sw.hour<12: buckets['pagi_besok']+=1
        else: buckets['later']+=1
    else:
        buckets['later']+=1

print('Buckets:', buckets)
print(f'Window MALAM ini: {len(window_malam)}')
print(f'Window SUBUH besok: {len(window_subuh_besok)}')

# Save windows
def slim(m):
    return {
        'I': m.get('I'), 'CI': m.get('CI'), 'L': m.get('L'),
        'O1': m.get('O1'), 'O2': m.get('O2'),
        'O1I': m.get('O1I'), 'O2I': m.get('O2I'),
        'S': m.get('S'),
        'start_wib': (dt.datetime.utcfromtimestamp(m['S']) + dt.timedelta(hours=7)).strftime('%Y-%m-%d %H:%M') if m.get('S') else None,
        'WP': m.get('WP'),  # win prob hint
        'LI': m.get('LI'),
        'CN': m.get('CN'),  # country
    }

with open('/projects/sandbox/newk/testing/_window_malam.json', 'w') as f:
    json.dump([slim(m) for m in window_malam], f, indent=2)
with open('/projects/sandbox/newk/testing/_window_subuh_besok.json', 'w') as f:
    json.dump([slim(m) for m in window_subuh_besok], f, indent=2)

print('\n=== MALAM (sorted) ===')
for m in sorted(window_malam, key=lambda x:x['S']):
    s = slim(m)
    wp = s['WP'] or {}
    print(f"  [{s['start_wib']}] {s['O1']:32s} vs {s['O2']:32s} | {s['L'][:40]:40s} | wp={wp.get('P1','?'):.2f}/{wp.get('PX','?'):.2f}/{wp.get('P2','?'):.2f}" if isinstance(wp.get('P1'), float) else f"  [{s['start_wib']}] {s['O1']} vs {s['O2']} | {s['L']}")

print('\n=== SUBUH BESOK ===')
for m in sorted(window_subuh_besok, key=lambda x:x['S']):
    s = slim(m)
    wp = s['WP'] or {}
    print(f"  [{s['start_wib']}] {s['O1']} vs {s['O2']} | {s['L']}")
