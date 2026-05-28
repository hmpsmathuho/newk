#!/usr/bin/env python3
"""Fetch matches per champ untuk dapat semua match malam ini + besok."""
import urllib.request, ssl, json, datetime as dt, time

IP = open('/projects/sandbox/newk/testing/_ip.txt').read().strip()
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
HOST = '1xbet.mobi'

def fetch(path):
    url = f'https://{IP}{path}'
    h = {'Host':HOST,'User-Agent':UA,'Accept':'*/*',
         'Accept-Language':'id-ID,id;q=0.9,en;q=0.8',
         'Referer':f'https://{HOST}/id/line'}
    return urllib.request.urlopen(urllib.request.Request(url, headers=h), context=ctx, timeout=30).read().decode('utf-8','ignore')

champs = json.load(open('/projects/sandbox/newk/testing/_champs_football.json'))
print(f'Total football champs: {len(champs)}')

now_utc = dt.datetime.utcnow()
horizon_utc = now_utc + dt.timedelta(hours=48)
print(f'Now UTC: {now_utc}, fetching matches up to: {horizon_utc}')

all_matches = {}

# Strategy: fetch each champ that has GC>=1 within next 48h
# Endpoint: /service-api/LineFeed/GetGamesByChampZip?champId=...
for c in champs:
    li = c.get('LI')
    gc = c.get('GC', 0)
    if gc < 1:
        continue
    name = c.get('L','')
    # Skip outright/winner-only markets
    skip_kw = ('Pemenang','Tim vs Pemain','Statistik','Babak Statistik','Kualifikasi Piala Dunia 2027')
    if any(k in name for k in skip_kw):
        continue
    try:
        d = json.loads(fetch(f'/service-api/LineFeed/GetGamesZip?lng=id&country=15&partner=8&virtualSports=true&groupChamps=true&champs={li}&count=50&tz=7&mode=4&getEmpty=true'))
        if d.get('Success') and d.get('Value'):
            v = d['Value']
            # Value might be array of matches OR array of {Sports:[{Champs:[{Games:[...]}]}]}
            if isinstance(v, list) and v and 'I' in v[0] and 'O1' in v[0]:
                # array of matches directly
                games = v
            elif isinstance(v, list) and v and 'GE' in v[0]:
                games = []
                for sp in v:
                    for ch in sp.get('CC', []) or []:
                        games += ch.get('GE', []) or []
            else:
                games = []
            new = 0
            for m in games:
                ts = m.get('S')
                if ts and now_utc.timestamp() <= ts <= horizon_utc.timestamp():
                    if m['I'] not in all_matches:
                        all_matches[m['I']] = m; new += 1
            print(f"  L={li:>8} GC={gc:>3} +{new} {name[:60]}")
    except Exception as e:
        print(f"  L={li} ERR {e}")
    time.sleep(0.05)

print(f'\n=== TOTAL unique upcoming matches (next 48h): {len(all_matches)} ===')

# Bucket
today_wib = (now_utc + dt.timedelta(hours=7)).date()
buckets = {'siang_today':[],'malam_today':[],'subuh_besok':[],'pagi_besok':[],'siang_besok':[],'malam_besok':[]}
for m in all_matches.values():
    ts=m.get('S')
    sw=dt.datetime.utcfromtimestamp(ts)+dt.timedelta(hours=7)
    if sw.date()==today_wib:
        if sw.hour<19: buckets['siang_today'].append(m)
        else: buckets['malam_today'].append(m)
    elif sw.date()==today_wib+dt.timedelta(days=1):
        if sw.hour<7: buckets['subuh_besok'].append(m)
        elif sw.hour<12: buckets['pagi_besok'].append(m)
        elif sw.hour<19: buckets['siang_besok'].append(m)
        else: buckets['malam_besok'].append(m)

for k,v in buckets.items():
    print(f'  {k}: {len(v)}')

# Save
def slim(m):
    return {
        'I':m.get('I'),'CI':m.get('CI'),'L':m.get('L'),
        'O1':m.get('O1'),'O2':m.get('O2'),'O1I':m.get('O1I'),'O2I':m.get('O2I'),
        'S':m.get('S'),
        'start_wib':(dt.datetime.utcfromtimestamp(m['S'])+dt.timedelta(hours=7)).strftime('%Y-%m-%d %H:%M'),
        'WP':m.get('WP'),'LI':m.get('LI'),'CN':m.get('CN'),
    }

with open('/projects/sandbox/newk/testing/_lobby_full.json','w') as f:
    json.dump([slim(m) for m in all_matches.values()], f, indent=2, ensure_ascii=False)

# Show malam ini list
print('\n=== MALAM INI (today >=19:00 WIB) ===')
for m in sorted(buckets['malam_today'], key=lambda x:x['S']):
    s=slim(m); wp=s['WP'] or {}
    p1=wp.get('P1'); px=wp.get('PX'); p2=wp.get('P2')
    pp=f"wp={p1:.2f}/{px:.2f}/{p2:.2f}" if isinstance(p1,float) else ""
    print(f"  [{s['start_wib']}] {s['O1'][:25]:25s} vs {s['O2'][:25]:25s} | {s['L'][:40]:40s} | {pp}")

print('\n=== SUBUH BESOK (00:00-07:00 WIB tomorrow) ===')
for m in sorted(buckets['subuh_besok'], key=lambda x:x['S']):
    s=slim(m); wp=s['WP'] or {}
    p1=wp.get('P1'); px=wp.get('PX'); p2=wp.get('P2')
    pp=f"wp={p1:.2f}/{px:.2f}/{p2:.2f}" if isinstance(p1,float) else ""
    print(f"  [{s['start_wib']}] {s['O1'][:25]:25s} vs {s['O2'][:25]:25s} | {s['L'][:40]:40s} | {pp}")
