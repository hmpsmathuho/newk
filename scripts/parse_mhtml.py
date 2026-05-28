#!/usr/bin/env python3
"""Phase 0.4 fallback - Parse MHTML 1xbet match page → structured odds."""
import re, json, sys

def parse_mhtml(path):
    raw = open(path,'rb').read().decode('utf-8','ignore')
    out = {}

    # Match info from <meta og:url> + page title
    m = re.search(r'og:url"\s+content="([^"]+)"', raw)
    if m: out['url'] = m.group(1)
    m = re.search(r'/(\d+)-([a-z0-9\-]+)$', out.get('url',''))
    if m:
        out['match_id'] = int(m.group(1))
        out['slug'] = m.group(2)
    m = re.search(r'/(\d+)-ireland|/(\d+)-([a-z\-]+league)', out.get('url',''))
    # League
    m = re.search(r'/football/(\d+)-([a-z0-9\-]+)/', out.get('url',''))
    if m:
        out['league_id'] = int(m.group(1))
        out['league_slug'] = m.group(2)
    # Title from header
    m = re.search(r'Subject:\s*=\?utf-8\?Q\?(.*?)\?=', raw, re.DOTALL)
    if m:
        try:
            from quopri import decodestring
            t = decodestring(m.group(1).replace('=20',' ').replace('=\n','').encode()).decode('utf-8','ignore')
            out['title_raw'] = t[:200]
        except: pass
    # Date from header
    m = re.search(r'^Date:\s*(.+)$', raw[:2000], re.MULTILINE)
    if m: out['saved_at'] = m.group(1).strip()

    # Find date/time of match in HTML body
    m = re.search(r'(\d{1,2}\.\d{1,2}\.20\d{2}[, ]+\d{1,2}[:.]\d{2})', raw)
    if m: out['kickoff_str'] = m.group(1)

    # Now: extract market groups and their odds
    # Each market group has structure:
    #   <span ...header...>GROUP_NAME</span> ... ui-accordion__body ... <ul>
    #     <li><button ...><span class="ui-market__name">NAME</span><span class="ui-market__value">ODDS</span>...
    # We need to find each section and pair up names+values.

    # Regex to find name/value pairs
    pair_re = re.compile(
        r'<span[^>]*class="ui-market__name"[^>]*>(?:<!---->)?([^<]+)</span>\s*'
        r'<span[^>]*class="ui-market__value"[^>]*>([0-9]+(?:\.[0-9]+)?)</span>'
    )

    # Header detection: <span ... game-markets-group-header[__title]>NAME</span>
    # OR group title texts. Use text positions.
    # Strategy: find all group headers and all market pairs, then assign each pair to nearest preceding header.

    headers = []
    # Group header text often appears like:
    #   ...title">1x2</span>  or  >Total</span>  or  >Handicap (1.5)</span>
    # We use a simpler heuristic: look for known group keywords as text-only spans before lists.
    header_re = re.compile(r'<span[^>]*game-markets-group-header[^>]*>([^<]+)</span>', re.IGNORECASE)
    for m in header_re.finditer(raw):
        name = re.sub(r'\s+',' ',m.group(1)).strip()
        if name and len(name) < 200:
            headers.append((m.start(), name))

    # Fallback: also match button class with header
    if len(headers) < 5:
        # Try alternative with title element
        for m in re.finditer(r'<button[^>]*game-markets-group-header[^>]*>(.*?)</button>', raw, re.DOTALL):
            seg = m.group(1)
            txt_m = re.search(r'>([^<]{2,80})<', seg)
            if txt_m:
                headers.append((m.start(), re.sub(r'\s+',' ',txt_m.group(1)).strip()))

    # Extract pairs and assign to header
    pairs = []
    for m in pair_re.finditer(raw):
        try:
            v = float(m.group(2))
        except:
            continue
        pairs.append((m.start(), m.group(1).strip(), v))

    # Group pairs by nearest preceding header
    groups = {}
    for pos, name, odds in pairs:
        # Find nearest header before this pos
        header_name = '?'
        for hpos, hname in headers:
            if hpos < pos:
                header_name = hname
            else:
                break
        groups.setdefault(header_name, []).append((name, odds))

    out['headers_found'] = len(headers)
    out['pairs_found'] = len(pairs)
    out['groups'] = groups
    return out

def normalize_groups(groups):
    """Convert raw groups to structured markets per CLAUDE.md.
    Only take FT (full match, no half/corner/team-specific)."""
    structured = {'1x2':{}, 'dc':{}, 'btts':{}, 'totals':{}, 'ah':{}, 'team_totals':{}, 'other':{}}

    EXCLUDE_KW = ('babak','sudut','statistik pemain','tim 1','tim 2','team 1','team 2',
                  'mencetak gol','gol berikutnya','tendangan','pemain','goal scorer',
                  'kartu','margin','tebak skor','correct score')

    def excluded(h):
        return any(kw in h for kw in EXCLUDE_KW)

    for header, items in groups.items():
        h = header.lower()
        if excluded(h):
            continue
        # 1x2 (exact full-match)
        if h == '1x2':
            for name, odds in items:
                if name in ('M1','1'): structured['1x2']['home'] = odds
                elif name == 'X': structured['1x2']['draw'] = odds
                elif name in ('M2','2'): structured['1x2']['away'] = odds
        elif h == 'double chance' or h == 'kesempatan ganda':
            for name, odds in items:
                n = name.replace(' ','').upper()
                if n in ('M1X','1X','X1'): structured['dc']['1X'] = odds
                elif n in ('M12','12'): structured['dc']['12'] = odds
                elif n in ('XM2','X2','2X'): structured['dc']['X2'] = odds
        elif h == 'kedua tim mencetak skor':
            for name, odds in items:
                ln = name.lower()
                if ln in ('ya','yes'): structured['btts']['yes'] = odds
                elif ln in ('tidak','no'): structured['btts']['no'] = odds
        elif h == 'total':
            for name, odds in items:
                # "0.5 Over" / "1.5 Under"
                lm = re.match(r'^([0-9]+(?:\.[0-9]+)?)\s+(Over|Under|Lebih|Kurang)', name)
                if lm:
                    line = float(lm.group(1))
                    side = lm.group(2).lower()
                    if side in ('over','lebih'):
                        structured['totals'].setdefault(line,{})['over'] = odds
                    else:
                        structured['totals'].setdefault(line,{})['under'] = odds
        elif h == 'total asia':
            # asian totals (.25 / .75 lines)
            for name, odds in items:
                lm = re.match(r'^([0-9]+(?:\.[0-9]+)?)\s+(Over|Under|Lebih|Kurang)', name)
                if lm:
                    line = float(lm.group(1))
                    side = lm.group(2).lower()
                    bucket = structured['totals'].setdefault(line,{})
                    bucket[('over' if side in ('over','lebih') else 'under')] = odds
        elif h == 'handicap':
            for name, odds in items:
                lm = re.match(r'^(\d)\s+\(([+-]?[0-9]+(?:\.[0-9]+)?)\)$', name)
                if lm:
                    side = lm.group(1)
                    line = float(lm.group(2))
                    if side == '1':
                        structured['ah'].setdefault(line,{})['home'] = odds
                    else:
                        structured['ah'].setdefault(line,{})['away'] = odds
        elif h == 'handicap asia':
            for name, odds in items:
                lm = re.match(r'^(\d)\s+\(([+-]?[0-9]+(?:\.[0-9]+)?)\)$', name)
                if lm:
                    side = lm.group(1); line = float(lm.group(2))
                    if side == '1':
                        structured['ah'].setdefault(line,{})['home'] = odds
                    else:
                        structured['ah'].setdefault(line,{})['away'] = odds
        else:
            structured['other'][header] = items
    return structured

if __name__ == '__main__':
    fpath = sys.argv[1] if len(sys.argv) > 1 else 'Taruhan_Shelbourne_Waterford_22_05_2026_Republik_Irlandia_Liga_Premier.mobi'
    res = parse_mhtml(fpath)
    print('=== File metadata ===')
    print(f"  URL: {res.get('url')}")
    print(f"  Match ID: {res.get('match_id')}")
    print(f"  League: {res.get('league_id')} ({res.get('league_slug')})")
    print(f"  Saved: {res.get('saved_at')}")
    print(f"  Kickoff: {res.get('kickoff_str')}")
    print(f"  Headers found: {res['headers_found']}")
    print(f"  Pairs found: {res['pairs_found']}")
    print(f"  Distinct groups: {len(res['groups'])}")

    print('\n=== Top groups by # of pairs ===')
    for h, items in sorted(res['groups'].items(), key=lambda x: -len(x[1]))[:25]:
        print(f"  [{len(items):3d}] {h}")

    print('\n=== Sample groups ===')
    for h, items in list(res['groups'].items())[:30]:
        print(f"  {h}: {items[:6]}{'...' if len(items)>6 else ''}")

    structured = normalize_groups(res['groups'])
    print('\n=== STRUCTURED ===')
    print(json.dumps({k:(v if isinstance(v,dict) and not k=='other' else (list(v.keys())[:10] if k=='other' else v)) for k,v in structured.items()}, indent=2, default=str))

    # Save
    out = {'meta':{k:v for k,v in res.items() if k!='groups'},
           'structured': structured,
           'raw_groups': res['groups']}
    with open('testing/_shelbourne_waterford_parsed.json','w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print('\nSaved to testing/_shelbourne_waterford_parsed.json')
