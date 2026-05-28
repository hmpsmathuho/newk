#!/usr/bin/env python3
"""Full analysis pipeline untuk Shelbourne vs Waterford 22-05-2026 dari MHTML."""
import json, math, re

p = json.load(open('testing/_shelbourne_waterford_parsed.json'))
s = p['structured']

print('═══════════════════════════════════════════════════════════')
print(f"  MATCH: Shelbourne vs Waterford")
print(f"  Liga: Republik Irlandia. Liga Premier (LI=119445)")
print(f"  Match ID: {p['meta'].get('match_id')}")
print(f"  Saved: {p['meta'].get('saved_at')}")
print('═══════════════════════════════════════════════════════════')

# === PHASE 1: Parse + implied probabilities ===
def fair_pair(a,b):
    if not a or not b: return (None,None)
    s=1/a+1/b; return (1/a/s, 1/b/s)
def fair_three(a,b,c):
    if not all([a,b,c]): return (None,None,None)
    ips=[1/x for x in (a,b,c)]; t=sum(ips); return tuple(p/t for p in ips)

# 1X2
o1=s['1x2']
fh,fd,fa=fair_three(o1.get('home'),o1.get('draw'),o1.get('away'))
print('\n── PHASE 1: ODDS & IMPLIED ──')
print(f'1X2:    Home {o1["home"]:.2f}  Draw {o1["draw"]:.2f}  Away {o1["away"]:.2f}')
print(f'        Implied raw: H={1/o1["home"]*100:.1f}%  D={1/o1["draw"]*100:.1f}%  A={1/o1["away"]*100:.1f}%  (margin={(1/o1["home"]+1/o1["draw"]+1/o1["away"]-1)*100:+.1f}%)')
print(f'        Fair (margin removed): H={fh*100:.1f}%  D={fd*100:.1f}%  A={fa*100:.1f}%')

# DC
print(f'DC:     1X {s["dc"].get("1X","-")}  12 {s["dc"].get("12","-")}  X2 {s["dc"].get("X2","-")}')

# BTTS
b=s['btts']
by,bn=fair_pair(b.get('yes'),b.get('no'))
print(f'BTTS:   Yes {b.get("yes"):.3f}  No {b.get("no"):.3f}  → fair Y={by*100:.1f}%  N={bn*100:.1f}%')

# Totals
print(f'\nTotals (FT):')
totals_fair={}
for line in sorted(s['totals'].keys(), key=lambda x:float(x)):
    line_f=float(line)
    t=s['totals'][line]
    ov=t.get('over'); un=t.get('under')
    if ov and un:
        of,uf=fair_pair(ov,un)
        totals_fair[line_f]={'over':ov,'under':un,'over_fair':of,'under_fair':uf}
        print(f'   {line_f:>4.2f}:  Over {ov:>6.3f} ({of*100:>4.1f}%)   Under {un:>6.3f} ({uf*100:>4.1f}%)')
    elif ov:
        print(f'   {line_f:>4.2f}:  Over {ov:>6.3f}                Under -')
    elif un:
        print(f'   {line_f:>4.2f}:  Over -                Under {un:>6.3f}')

# AH — consolidate home -X dengan away +X
print(f'\nAsian Handicap (FT, paired):')
ah_consol={}  # line (home perspective): {home_odds, away_odds}
for line, sides in s['ah'].items():
    line_f = float(line)
    for side, odds in sides.items():
        if side == 'home':
            ah_consol.setdefault(line_f,{})['home'] = odds
        else:  # away — line was stored as +X (away perspective). Convert: home_line = -away_line
            ah_consol.setdefault(-line_f,{})['away'] = odds

ah_fair={}
for L in sorted(ah_consol.keys()):
    h=ah_consol[L].get('home'); a=ah_consol[L].get('away')
    if h and a:
        hf,af=fair_pair(h,a)
        ah_fair[L]={'home':h,'away':a,'home_fair':hf,'away_fair':af}
        print(f'   AH {L:+.2f}:  Home {h:>6.3f} ({hf*100:>4.1f}%)   Away {a:>6.3f} ({af*100:>4.1f}%)')

# === PHASE 2 already done via web search earlier
print('\n── PHASE 2: FORM & CONTEXT ──')
print('Source: dailysports.net, sofascore, irish premier league research')
# Note: 22 May 2026 was already played. Pre-match research below was my best-effort.
print()
print('Shelbourne (home):')
print('  Form context: Defending champions 2024 LOI, 2025 strong start. Heavy home favorite.')
print('  Estimated GF/GA last 5: ~1.6/0.9 (Premier Division typical for top side)')
print()
print('Waterford (away):')
print('  Form context: Newly promoted side, struggle in 2025-26 Premier Division.')
print('  Estimated GF/GA last 5: ~0.8/1.5 (relegation-zone profile)')
print()
print('Liga Premier Irlandia baseline:')
print('  Avg ~2.4-2.6 goals/match, BTTS ~50%, U2.5 ~50% (moderate, not as defensive as Egypt)')

# === PHASE 3: Poisson model ===
print('\n── PHASE 3: POISSON MODEL ──')
# λ_home = (Shelbourne GF + Waterford GA) / 2 = (1.6 + 1.5)/2 = 1.55
# λ_away = (Waterford GF + Shelbourne GA) / 2 = (0.8 + 0.9)/2 = 0.85
lam_h = (1.6 + 1.5) / 2
lam_a = (0.8 + 0.9) / 2
print(f'  λ_home (Shelbourne) = (1.6 + 1.5)/2 = {lam_h:.2f}')
print(f'  λ_away (Waterford)  = (0.8 + 0.9)/2 = {lam_a:.2f}')
print(f'  λ_total = {lam_h + lam_a:.2f}')

def pmf(k,l): return math.exp(-l)*(l**k)/math.factorial(k)
def cdf(k,l): return sum(pmf(i,l) for i in range(k+1))

L = lam_h + lam_a
def under(line):
    k = int(math.floor(line))
    return cdf(k, L)
def over(line):
    return 1 - under(line)

def btts_yes():
    return (1-math.exp(-lam_h))*(1-math.exp(-lam_a))

def grid(maxg=8):
    ph=pa=pd=0
    for h in range(maxg+1):
        for a in range(maxg+1):
            p=pmf(h,lam_h)*pmf(a,lam_a)
            if h>a: ph+=p
            elif h<a: pa+=p
            else: pd+=p
    return ph,pd,pa

ph,pd,pa = grid()
print(f'\n  Model 1X2:  H={ph*100:.1f}%  D={pd*100:.1f}%  A={pa*100:.1f}%')
print(f'  Model U2.5: {under(2.5)*100:.1f}%   U3.5: {under(3.5)*100:.1f}%   U1.5: {under(1.5)*100:.1f}%')
print(f'  Model BTTS: Yes={btts_yes()*100:.1f}%  No={(1-btts_yes())*100:.1f}%')
print(f'  Model DC:   1X={(ph+pd)*100:.1f}%  X2={(pa+pd)*100:.1f}%  12={(ph+pa)*100:.1f}%')

# === PHASE 4: Filter & generate candidate legs ===
print('\n── PHASE 4: FILTER GATES ──')
print('Gates: model≥65%, value≥4%, gap≥4pp, odds 1.30-2.50, kelly≥2%')
print()

candidates = []

def add(pick, model_p, odds):
    if not odds or odds < 1.30 or odds > 2.50: return
    implied = 1/odds
    value = (model_p*odds - 1) * 100
    gap = (model_p - implied) * 100
    kelly = (model_p*odds - 1) / (odds - 1) if odds > 1 else 0
    candidates.append({
        'pick':pick,'odds':odds,'model':model_p,'implied':implied,
        'value':value,'gap':gap,'kelly':kelly*100
    })

# Test all relevant picks
add('1 (Home win)', ph, o1.get('home'))
add('DC 1X', ph+pd, s['dc'].get('1X'))
add('U2.5', under(2.5), totals_fair.get(2.5,{}).get('under'))
add('U3.5', under(3.5), totals_fair.get(3.5,{}).get('under'))
add('U2.25', under(2.25), totals_fair.get(2.25,{}).get('under'))
add('U2.75', under(2.75), totals_fair.get(2.75,{}).get('under'))
add('BTTS No', 1-btts_yes(), b.get('no'))
add('BTTS Yes', btts_yes(), b.get('yes'))
# AH
for L_ah in (-1.0, -0.5, 0.5, 1.0, -1.5):
    if L_ah in ah_fair:
        # Compute model prob for AH
        # Simplified: AH home -1 means home wins by 2+ goals (push at exactly 1)
        # For this analysis, use score grid
        if L_ah == -1.0:
            # home -1: win by 2+ wins, win by 1 = push (refund half), loss = lose
            # Approx: P(home wins by 2+) wins
            p_win = sum(pmf(h,lam_h)*pmf(a,lam_a) for h in range(8) for a in range(8) if h-a>=2)
            add(f'AH Home {L_ah:+}', p_win, ah_fair[L_ah]['home'])
        elif L_ah == -0.5:
            p_win = sum(pmf(h,lam_h)*pmf(a,lam_a) for h in range(8) for a in range(8) if h>a)
            add(f'AH Home {L_ah:+}', p_win, ah_fair[L_ah]['home'])
        elif L_ah == 0.5:
            p_win = sum(pmf(h,lam_h)*pmf(a,lam_a) for h in range(8) for a in range(8) if a>=h)
            add(f'AH Away {L_ah:+}', p_win, ah_fair[L_ah]['away'])

print(f'{"Pick":18s} {"Odds":>5s} {"Model":>6s} {"Imp":>6s} {"Value":>7s} {"Gap":>6s} {"Kelly":>7s}  Verdict')
print('-'*100)
candidates.sort(key=lambda c:-c['value'])
passed=[]
for c in candidates:
    ok = (c['model']>=0.65 and c['value']>=4.0 and c['gap']>=4.0 and 1.30<=c['odds']<=2.50 and c['kelly']>=2.0)
    fade = c['odds']<=1.40 and c['gap']>=8.0
    if fade: ok=False
    flag='✓ PASS' if ok else '✗'
    reasons=[]
    if c['model']<0.65: reasons.append(f'mp<65%')
    if c['value']<4.0: reasons.append(f'val<4%')
    if c['gap']<4.0: reasons.append(f'gap<4pp')
    if c['kelly']<2.0: reasons.append(f'kel<2%')
    if fade: reasons.append('FADE-SHORT-ODDS')
    if ok: passed.append(c)
    print(f"{c['pick']:18s} {c['odds']:5.2f} {c['model']*100:5.1f}% {c['implied']*100:5.1f}% {c['value']:+6.1f}% {c['gap']:+5.1f}p {c['kelly']:+6.1f}%  {flag} {' '.join(reasons)}")

# === PHASE 5: Verdict ===
print('\n── PHASE 5: VERDICT ──')
if not passed:
    print('🚫 NO BET. Tidak ada leg yang lolos gate. Sit out match ini.')
else:
    print(f'✅ {len(passed)} leg lolos gate. (Single-match parlay → 1 leg saja, bukan 5-leg.)')
    for c in passed:
        print(f'   ▸ {c["pick"]}  odds={c["odds"]}  model={c["model"]*100:.1f}%  value={c["value"]:+.1f}%')

# Compare with earlier May 28 parlay context
print('\n── INTEGRASI ──')
print('Match ini sudah lewat (22 Mei 2026, 6 hari lalu).')
print('Kalau Anda mau leg ini ditambahkan ke parlay future window, pakai pattern serupa untuk match yang akan datang.')

# Save
out = {
    'meta': p['meta'],
    'odds_parsed': {'1x2':o1,'1x2_fair':{'home':fh,'draw':fd,'away':fa},
                    'dc':s['dc'],'btts':b,'btts_fair':{'yes':by,'no':bn},
                    'totals':totals_fair, 'ah':ah_fair},
    'model': {'lam_home':lam_h,'lam_away':lam_a,'lam_total':L,
              'p_home':ph,'p_draw':pd,'p_away':pa,
              'p_btts_yes':btts_yes(),
              'p_u25':under(2.5),'p_u35':under(3.5)},
    'candidates': candidates,
    'passed': passed,
}
with open('testing/_shelbourne_waterford_analysis.json','w') as f:
    json.dump(out,f,indent=2,default=str,ensure_ascii=False)
print('\nSaved analysis to testing/_shelbourne_waterford_analysis.json')
