#!/usr/bin/env python3
"""Phase 0.3 - Fetch full odds per match via GetGameZip, parse key markets."""
import urllib.request, ssl, json, time, datetime as dt, os, re

IP = open('/projects/sandbox/newk/testing/_ip.txt').read().strip()
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
HOST = '1xbet.mobi'

def fetch(p):
    h = {'Host':HOST,'User-Agent':UA,'Accept':'*/*',
         'Accept-Language':'id-ID,id;q=0.9,en;q=0.8',
         'Referer':f'https://{HOST}/id/line'}
    return urllib.request.urlopen(urllib.request.Request(f'https://{IP}{p}', headers=h),
                                  context=ctx, timeout=30).read().decode('utf-8','ignore')

def slugify(s):
    s = re.sub(r'[^a-zA-Z0-9]+','-', s.lower()).strip('-')
    return s[:50]

def fetch_match(mid):
    body = fetch(f'/service-api/LineFeed/GetGameZip?id={mid}&lng=id&country=15&partner=8&isSubGames=true&GroupEvents=true&grMode=4')
    return json.loads(body)

# Group/Type mapping per CLAUDE.md
def parse_markets(events):
    """events = list of {T,P,C,G,...}. Returns dict of markets."""
    out = {
        '1x2': {},          # {home, draw, away}
        'dc': {},           # double chance {1X, 12, X2}
        'btts': {},         # {yes, no}
        'totals': {},       # {line: {over, under}}
        'ah': {},           # {line: {home, away}}
        'team_totals': {},  # not used
    }
    for e in events:
        T = e.get('T'); G = e.get('G'); C = e.get('C'); P = e.get('P')
        if C is None: continue
        # G=1: 1X2
        if G == 1:
            if T == 1: out['1x2']['home'] = C
            elif T == 2: out['1x2']['draw'] = C
            elif T == 3: out['1x2']['away'] = C
        # G=8: Double chance
        elif G == 8:
            if T == 4: out['dc']['1X'] = C
            elif T == 5: out['dc']['12'] = C
            elif T == 6: out['dc']['X2'] = C
        # G=17: Total goals (P=line)
        elif G == 17 and P is not None:
            line = P
            if T == 9: out['totals'].setdefault(line,{})['over'] = C
            elif T == 10: out['totals'].setdefault(line,{})['under'] = C
        # G=15 or G=19: BTTS
        elif G in (15,19):
            if T == 180: out['btts']['yes'] = C
            elif T == 181: out['btts']['no'] = C
        # G=2: Asian Handicap (P=line)
        elif G == 2 and P is not None:
            line = P
            if T == 7: out['ah'].setdefault(line,{})['home'] = C
            elif T == 8: out['ah'].setdefault(line,{})['away'] = C
    return out

def collect_events(raw):
    events = list(raw.get('E', []) or [])
    for ae in raw.get('AE', []) or []:
        events += ae.get('ME', []) or []
    return events

def fmt_market_summary(m, raw):
    o1 = raw.get('O1','?'); o2 = raw.get('O2','?')
    L = raw.get('L','?')
    s_wib = (dt.datetime.utcfromtimestamp(raw['S'])+dt.timedelta(hours=7)).strftime('%Y-%m-%d %H:%M') if raw.get('S') else '?'
    lines=[]
    lines.append(f'Match: {o1} vs {o2}')
    lines.append(f'Liga: {L}')
    lines.append(f'Start (WIB): {s_wib}')
    lines.append(f'ID: {raw.get("I")}')
    wp = raw.get('WP') or {}
    if wp:
        lines.append(f'WP (1xbet hint): P1={wp.get("P1","?")} PX={wp.get("PX","?")} P2={wp.get("P2","?")}')
    lines.append('')
    lines.append('-- 1X2 --')
    x = m['1x2']
    if x:
        lines.append(f'  Home {x.get("home","-")}  Draw {x.get("draw","-")}  Away {x.get("away","-")}')
        if all(k in x for k in ('home','draw','away')):
            ip_h = 1/x['home']; ip_d=1/x['draw']; ip_a=1/x['away']
            margin = (ip_h+ip_d+ip_a-1)*100
            lines.append(f'  Implied: H={ip_h:.3f} D={ip_d:.3f} A={ip_a:.3f}  Margin={margin:.1f}%')
    lines.append('-- Double Chance --')
    if m['dc']:
        d=m['dc']
        lines.append(f'  1X {d.get("1X","-")}  12 {d.get("12","-")}  X2 {d.get("X2","-")}')
    lines.append('-- Total Goals --')
    for line in sorted(m['totals'].keys()):
        t = m['totals'][line]
        lines.append(f'  Line {line}: Over {t.get("over","-")}  Under {t.get("under","-")}')
    lines.append('-- BTTS --')
    if m['btts']:
        b = m['btts']
        lines.append(f'  Yes {b.get("yes","-")}  No {b.get("no","-")}')
    lines.append('-- Asian Handicap --')
    for line in sorted(m['ah'].keys()):
        a = m['ah'][line]
        lines.append(f'  AH {line:+.2f}: Home {a.get("home","-")}  Away {a.get("away","-")}')
    return '\n'.join(lines)

# Load match list - use full saved lobby
matches_file = '/projects/sandbox/newk/testing/_lobby_full.json'
if not os.path.exists(matches_file) or os.path.getsize(matches_file) < 100:
    matches_file = '/projects/sandbox/newk/testing/_window_malam.json'
slim_list = json.load(open(matches_file))
print(f'Loaded {len(slim_list)} matches from {matches_file}')

# Filter window: malam ini (>=19:00 WIB hari ini)
now_utc = dt.datetime.utcnow()
today_wib = (now_utc + dt.timedelta(hours=7)).date()
malam_ini = []
for s in slim_list:
    if not s.get('S'): continue
    sw = dt.datetime.utcfromtimestamp(s['S']) + dt.timedelta(hours=7)
    if sw.date() == today_wib and sw.hour >= 19 and sw.replace(tzinfo=None) > (now_utc + dt.timedelta(hours=7)):
        malam_ini.append(s)
malam_ini.sort(key=lambda x: x['S'])
print(f'Window MALAM INI (>=19:00 WIB today, future only): {len(malam_ini)}')

odir = '/projects/sandbox/newk/testing'
os.makedirs(odir, exist_ok=True)

# Save index
index = []
fail = 0
for i,s in enumerate(malam_ini, 1):
    mid = s['I']
    slug = f"{slugify(s.get('O1','x')+'-vs-'+s.get('O2','x'))}_{mid}"
    print(f'  [{i}/{len(malam_ini)}] {s["O1"]} vs {s["O2"]} (id={mid}) ...')
    try:
        raw = fetch_match(mid)
        if not raw.get('Success'):
            print(f'      API error: {raw.get("Error")}')
            fail += 1; continue
        v = raw.get('Value') or {}
        events = collect_events(v)
        m = parse_markets(events)
        # Save
        with open(f'{odir}/{slug}_RAW.json', 'w') as f:
            json.dump(v, f, ensure_ascii=False)
        with open(f'{odir}/{slug}.txt', 'w') as f:
            f.write(fmt_market_summary(m, v))
        n_markets = sum([
            len(m['1x2'])>0, len(m['dc'])>0, len(m['btts'])>0,
            len(m['totals'])>0, len(m['ah'])>0
        ])
        index.append({
            'slug': slug, 'id': mid,
            'home': v.get('O1'), 'away': v.get('O2'),
            'league': v.get('L'),
            'start_wib': (dt.datetime.utcfromtimestamp(v['S'])+dt.timedelta(hours=7)).strftime('%Y-%m-%d %H:%M'),
            'wp': v.get('WP'),
            'has_1x2': bool(m['1x2']),
            'has_btts': bool(m['btts']),
            'totals_lines': sorted(m['totals'].keys()),
            'ah_lines': sorted(m['ah'].keys()),
            'n_events': len(events),
            'n_markets': n_markets,
        })
    except Exception as e:
        print(f'      ERR: {e}')
        fail += 1
    time.sleep(0.1)

with open(f'{odir}/_match_index.json', 'w') as f:
    json.dump(index, f, indent=2, ensure_ascii=False)

print(f'\nDone. Saved {len(index)} matches, fail={fail}')
print('\n=== INDEX ===')
for x in index:
    wp=x['wp'] or {}
    p1,px,p2 = wp.get('P1','?'),wp.get('PX','?'),wp.get('P2','?')
    if isinstance(p1,float):
        wpstr = f'{p1:.2f}/{px:.2f}/{p2:.2f}'
    else:
        wpstr='-'
    print(f"  [{x['start_wib']}] {x['home'][:22]:22s} vs {x['away'][:22]:22s} | {x['league'][:35]:35s} | wp={wpstr} | tot={len(x['totals_lines'])} ah={len(x['ah_lines'])} ev={x['n_events']}")
