#!/usr/bin/env python3
"""Phase 0.2 - Fetch daftar match dari 1xbet.mobi /id/line"""
import urllib.request, ssl, re, sys, os, json

IP = open('/projects/sandbox/newk/testing/_ip.txt').read().strip()

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    'Host': '1xbet.mobi',
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'id-ID,id;q=0.9,en;q=0.8',
}

def fetch(path):
    url = f'https://{IP}{path}'
    req = urllib.request.Request(url, headers=HEADERS)
    return urllib.request.urlopen(req, context=ctx, timeout=30).read().decode('utf-8', 'ignore')

if __name__ == '__main__':
    print(f'Fetching https://1xbet.mobi/id/line (via IP {IP})...')
    page = fetch('/id/line')
    print(f'Got {len(page)} bytes')
    out = '/projects/sandbox/newk/testing/_lobby.html'
    with open(out, 'w') as f:
        f.write(page)
    print(f'Saved to {out}')

    # Extract match URL pattern: /id/line/football/{LEAGUE_ID}/{MATCH_ID}-{slug}
    pattern = re.compile(r'/id/line/(?:football|soccer)/(\d+)[^"\s<>]*?/(\d+)-([a-z0-9\-]+)', re.IGNORECASE)
    matches = pattern.findall(page)
    print(f'Found {len(matches)} football match link occurrences')
    uniq = {}
    for league_id, match_id, slug in matches:
        uniq[match_id] = (league_id, slug)
    print(f'Unique matches: {len(uniq)}')
    for mid, (lid, slug) in list(uniq.items())[:20]:
        print(f'  {mid}  league={lid}  {slug}')
