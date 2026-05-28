#!/usr/bin/env python3
"""Phase 0 - Fetch all football matches via service-api, save list."""
import urllib.request, ssl, json, time, datetime as dt

IP = open('/projects/sandbox/newk/testing/_ip.txt').read().strip()
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
HOST = '1xbet.mobi'

def fetch_json(path):
    url = f'https://{IP}{path}'
    headers = {
        'Host': HOST, 'User-Agent': UA,
        'Accept': '*/*',
        'Referer': f'https://{HOST}/id/line',
    }
    req = urllib.request.Request(url, headers=headers)
    body = urllib.request.urlopen(req, context=ctx, timeout=30).read().decode('utf-8', 'ignore')
    return json.loads(body)

# sports=1 = Football. count=300 untuk dapat banyak. tz=7 = WIB. tf=2200000 = standard.
all_matches = []
for take in [300, 600]:
    path = f'/service-api/LineFeed/Get1x2_Zip?sports=1&count={take}&lng=id&tf=2200000&tz=7&mode=4&country=15&partner=8&getEmpty=true'
    data = fetch_json(path)
    if data.get('Success') and data.get('Value'):
        all_matches = data['Value']
        print(f'count={take}: got {len(all_matches)} matches')
        break

# Save raw lobby
with open('/projects/sandbox/newk/testing/_lobby_api.json', 'w') as f:
    json.dump({'count': len(all_matches), 'matches': all_matches}, f)

# Inspect schema first item
if all_matches:
    sample = all_matches[0]
    print('\nSample match keys:', list(sample.keys()))
    print('Sample (truncated):')
    print(json.dumps({k: v for k, v in sample.items() if k not in ('E','AE','SC')}, indent=2)[:1500])

# Filter only Football. Field SI=Sport Id (1 = football usually)
# But field could differ - check.
sports_seen = {}
for m in all_matches:
    si = m.get('SI', m.get('SportId', '?'))
    sports_seen[si] = sports_seen.get(si, 0) + 1
print('\nSport distribution:', sports_seen)

# Filter to football only (SI=1)
football = [m for m in all_matches if m.get('SI') == 1]
print(f'Football matches: {len(football)}')

# Window subuh WIB: 00:00-07:00 WIB (UTC+7) → UTC = 17:00 prev day - 00:00 today UTC
# But user might want today's matches; let's also categorize by time.
now_utc = dt.datetime.utcnow()
print(f'\nNow UTC: {now_utc.isoformat()}  (WIB: {now_utc + dt.timedelta(hours=7)})')

# Field 'S' = start timestamp (Unix UTC)
buckets = {'past': 0, 'subuh_today': 0, 'pagi_today': 0, 'siang_today': 0, 'malam_today': 0, 'subuh_besok': 0, 'later': 0}
window_subuh = []  # 00:00-07:00 WIB tomorrow (subuh besok)
window_malam = []  # 19:00-23:59 WIB today (malam ini)
window_today_all = []

for m in football:
    ts = m.get('S')
    if not ts:
        continue
    start_utc = dt.datetime.utcfromtimestamp(ts)
    start_wib = start_utc + dt.timedelta(hours=7)
    today_wib = (now_utc + dt.timedelta(hours=7)).date()

    if start_utc < now_utc:
        buckets['past'] += 1
        continue

    if start_wib.date() == today_wib:
        if start_wib.hour < 7:
            buckets['subuh_today'] += 1
        elif start_wib.hour < 12:
            buckets['pagi_today'] += 1
        elif start_wib.hour < 18:
            buckets['siang_today'] += 1
        else:
            buckets['malam_today'] += 1
            window_malam.append(m)
        window_today_all.append(m)
    elif start_wib.date() == today_wib + dt.timedelta(days=1):
        if start_wib.hour < 7:
            buckets['subuh_besok'] += 1
            window_subuh.append(m)
    else:
        buckets['later'] += 1

print('Time buckets (future only):', buckets)
print(f'\nWindow "subuh besok" (00:00-07:00 WIB tomorrow): {len(window_subuh)} matches')
print(f'Window "malam ini" (>=19:00 WIB today): {len(window_malam)} matches')
print(f'Window "today all": {len(window_today_all)} matches')

# Save windows
def slim(m):
    return {
        'I': m.get('I'),         # match id
        'CI': m.get('CI'),       # champ id
        'L': m.get('L'),         # league name
        'O1': m.get('O1') or m.get('Opp1'),  # team home
        'O2': m.get('O2') or m.get('Opp2'),  # team away
        'O1I': m.get('O1I'), 'O2I': m.get('O2I'),
        'S': m.get('S'),         # start ts utc
        'start_wib': (dt.datetime.utcfromtimestamp(m['S']) + dt.timedelta(hours=7)).strftime('%Y-%m-%d %H:%M') if m.get('S') else None,
        'SI': m.get('SI'),
    }

with open('/projects/sandbox/newk/testing/_window_subuh.json', 'w') as f:
    json.dump([slim(m) for m in window_subuh], f, indent=2)
with open('/projects/sandbox/newk/testing/_window_malam.json', 'w') as f:
    json.dump([slim(m) for m in window_malam], f, indent=2)
with open('/projects/sandbox/newk/testing/_window_today.json', 'w') as f:
    json.dump([slim(m) for m in window_today_all], f, indent=2)

print('\n=== Window MALAM INI (preview) ===')
for m in sorted(window_malam, key=lambda x: x.get('S', 0))[:25]:
    s = slim(m)
    print(f"  [{s['start_wib']}] {s['O1']} vs {s['O2']}  | {s['L']}  (id={s['I']})")

print('\n=== Window SUBUH BESOK (preview) ===')
for m in sorted(window_subuh, key=lambda x: x.get('S', 0))[:25]:
    s = slim(m)
    print(f"  [{s['start_wib']}] {s['O1']} vs {s['O2']}  | {s['L']}  (id={s['I']})")
