#!/usr/bin/env python3
"""Phase 1 - Parse odds, hitung implied probability per market."""
import json, os, glob, math

odir = '/projects/sandbox/newk/testing'
index = json.load(open(f'{odir}/_match_index.json'))

def parse_markets(events):
    out = {'1x2':{}, 'dc':{}, 'btts':{}, 'totals':{}, 'ah':{}}
    for e in events:
        T,G,C,P = e.get('T'),e.get('G'),e.get('C'),e.get('P')
        if C is None: continue
        if G==1:
            if T==1: out['1x2']['home']=C
            elif T==2: out['1x2']['draw']=C
            elif T==3: out['1x2']['away']=C
        elif G==8:
            if T==4: out['dc']['1X']=C
            elif T==5: out['dc']['12']=C
            elif T==6: out['dc']['X2']=C
        elif G==17 and P is not None:
            if T==9: out['totals'].setdefault(P,{})['over']=C
            elif T==10: out['totals'].setdefault(P,{})['under']=C
        elif G in (15,19):
            if T==180: out['btts']['yes']=C
            elif T==181: out['btts']['no']=C
        elif G==2 and P is not None:
            if T==7: out['ah'].setdefault(P,{})['home']=C
            elif T==8: out['ah'].setdefault(P,{})['away']=C
    return out

def collect(raw):
    ev = list(raw.get('E',[]) or [])
    for ae in raw.get('AE',[]) or []:
        ev += ae.get('ME',[]) or []
    return ev

def fair_pair(a,b):
    """Remove bookmaker margin from 2-way market. Returns (pa, pb)."""
    if not a or not b: return (None, None)
    ipa, ipb = 1/a, 1/b
    s = ipa + ipb
    return (ipa/s, ipb/s)

def fair_three(a,b,c):
    if not all([a,b,c]): return (None,None,None)
    ips = [1/a,1/b,1/c]
    s = sum(ips)
    return tuple(p/s for p in ips)

# Tier classification per CLAUDE.md
TIER1_KW = ('Premier League','EPL','La Liga','Bundesliga','Ligue 1','Serie A. ','Champions','UEFA Liga Eropa','Champions League')
TIER2_KW = ('Eredivisie','Primeira','Championship','MLS','Liga Pro','Liga Profesional','Mesir. Liga Primer','Egyptian Premier','Brasil','Brazil')
TIER3_KW = ('Liga 3','U21','U-21','Reserve','Kazakhstan','Tajikistan','Piala Tajikistan','Etiopia','Kenya','Madagascar','Albania','Kosovo','Tier','Liga Pro Serie B')

def tier_of(league):
    L = (league or '').lower()
    if any(k.lower() in L for k in TIER1_KW): return 1
    if any(k.lower() in L for k in TIER2_KW): return 2
    return 3

# Parse all
parsed = []
for x in index:
    raw_path = f'{odir}/{x["slug"]}_RAW.json'
    if not os.path.exists(raw_path): continue
    raw = json.load(open(raw_path))
    events = collect(raw)
    m = parse_markets(events)

    # Compute implied/fair probabilities
    p_h, p_d, p_a = fair_three(m['1x2'].get('home'), m['1x2'].get('draw'), m['1x2'].get('away'))
    btts_y_fair, btts_n_fair = fair_pair(m['btts'].get('yes'), m['btts'].get('no'))

    totals_fair = {}
    for line, v in m['totals'].items():
        ov, un = v.get('over'), v.get('under')
        if ov and un:
            o_fair, u_fair = fair_pair(ov, un)
            totals_fair[line] = {'over_odds':ov,'under_odds':un,'over_fair':o_fair,'under_fair':u_fair}

    ah_fair = {}
    for line, v in m['ah'].items():
        h, a = v.get('home'), v.get('away')
        if h and a:
            hf, af = fair_pair(h, a)
            ah_fair[line] = {'home_odds':h,'away_odds':a,'home_fair':hf,'away_fair':af}

    parsed.append({
        'slug': x['slug'], 'id': x['id'],
        'home': x['home'], 'away': x['away'],
        'league': x['league'], 'start_wib': x['start_wib'],
        'tier': tier_of(x['league']),
        'wp_1xbet': raw.get('WP'),
        '1x2': m['1x2'],
        '1x2_fair': {'home':p_h,'draw':p_d,'away':p_a},
        'dc': m['dc'],
        'btts': m['btts'],
        'btts_fair': {'yes':btts_y_fair,'no':btts_n_fair},
        'totals': totals_fair,
        'ah': ah_fair,
    })

with open(f'{odir}/_parsed.json','w') as f:
    json.dump(parsed,f,indent=2,ensure_ascii=False)

# Print summary table
print(f'{"Match":50s} {"Tier":4s} {"1X2 fair":18s} {"BTTS_Y":7s} {"U2.5":7s} {"U3.5":7s}')
print('-'*120)
for p in parsed:
    f = p['1x2_fair']
    fh = f.get('home') or 0; fd = f.get('draw') or 0; fa = f.get('away') or 0
    bttsy = (p['btts_fair'].get('yes') or 0)
    u25 = (p['totals'].get(2.5) or {}).get('under_fair') or 0
    u35 = (p['totals'].get(3.5) or {}).get('under_fair') or 0
    name = f"{p['home'][:23]} v {p['away'][:23]}"
    print(f'{name:50s}  T{p["tier"]}  {fh:.2f}/{fd:.2f}/{fa:.2f}     {bttsy:.2f}    {u25:.2f}    {u35:.2f}')

# Identify potential candidates per CLAUDE.md hierarchy:
# 1. U3.5 (most safe), 2. U2.5 ≥65%, 3. BTTS No ≥65%, 4. AH ±0.5/±1.0 ≥65%, 5. DC ≥70%
print('\n=== CANDIDATE LEGS (raw fair probability ≥ 0.60, before form adjustment) ===')
candidates = []
for p in parsed:
    name = f"{p['home']} vs {p['away']}"
    # U3.5
    if 3.5 in p['totals']:
        t = p['totals'][3.5]
        if t['under_fair'] and t['under_fair'] >= 0.60:
            candidates.append({'match':name,'pick':'U3.5','odds':t['under_odds'],'fair':t['under_fair'],'p':p,'market':'U3.5'})
    # U2.5
    if 2.5 in p['totals']:
        t = p['totals'][2.5]
        if t['under_fair'] and t['under_fair'] >= 0.55:
            candidates.append({'match':name,'pick':'U2.5','odds':t['under_odds'],'fair':t['under_fair'],'p':p,'market':'U2.5'})
    # BTTS No
    bn = p['btts_fair'].get('no')
    if bn and bn >= 0.55:
        candidates.append({'match':name,'pick':'BTTS No','odds':p['btts'].get('no'),'fair':bn,'p':p,'market':'BTTS_No'})
    # AH ±0.5 / ±1.0 (favourite side)
    for ah_line in (-1.0, -0.5, 0.5, 1.0):
        if ah_line in p['ah']:
            a = p['ah'][ah_line]
            if a['home_fair'] and a['home_fair'] >= 0.60:
                candidates.append({'match':name,'pick':f'AH Home {ah_line:+}','odds':a['home_odds'],'fair':a['home_fair'],'p':p,'market':f'AH_H_{ah_line}'})
            if a['away_fair'] and a['away_fair'] >= 0.60:
                candidates.append({'match':name,'pick':f'AH Away {ah_line:+}','odds':a['away_odds'],'fair':a['away_fair'],'p':p,'market':f'AH_A_{ah_line}'})
    # DC
    fh = p['1x2_fair'].get('home') or 0
    fd = p['1x2_fair'].get('draw') or 0
    fa = p['1x2_fair'].get('away') or 0
    dc1x_fair = fh + fd
    dcx2_fair = fa + fd
    if dc1x_fair >= 0.70 and p['dc'].get('1X'):
        candidates.append({'match':name,'pick':'DC 1X','odds':p['dc']['1X'],'fair':dc1x_fair,'p':p,'market':'DC_1X'})
    if dcx2_fair >= 0.70 and p['dc'].get('X2'):
        candidates.append({'match':name,'pick':'DC X2','odds':p['dc']['X2'],'fair':dcx2_fair,'p':p,'market':'DC_X2'})

# Filter odds range [1.30, 2.50] per Phase 4
candidates = [c for c in candidates if c['odds'] and 1.30 <= c['odds'] <= 2.50]

# Sort by fair prob desc
candidates.sort(key=lambda c: -c['fair'])
print(f'\nFound {len(candidates)} raw candidates (odds 1.30-2.50, fair≥0.55-0.60)')
for c in candidates[:50]:
    p = c['p']
    print(f"  T{p['tier']} {c['pick']:18s} odds={c['odds']:.2f} fair={c['fair']:.3f}  {c['match'][:55]:55s} | {p['league'][:30]}")

# Save candidates
with open(f'{odir}/_candidates.json','w') as f:
    json.dump([{**{k:v for k,v in c.items() if k!='p'},
                'tier':c['p']['tier'],
                'league':c['p']['league'],
                'start_wib':c['p']['start_wib'],
                'slug':c['p']['slug']} for c in candidates], f, indent=2, ensure_ascii=False)
print(f'\nSaved candidates to _candidates.json')
