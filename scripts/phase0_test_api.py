#!/usr/bin/env python3
"""Phase 0 - Test API GetGames untuk daftar match"""
import urllib.request, ssl, json, time

IP = open('/projects/sandbox/newk/testing/_ip.txt').read().strip()
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Try multiple host variants — line API often works on www.1xbet.com or 1xstavka
HOSTS_TO_TRY = [
    ('1xbet.mobi', IP),
]

UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'

def try_endpoint(host, ip, path):
    url = f'https://{ip}{path}'
    headers = {
        'Host': host,
        'User-Agent': UA,
        'Accept': '*/*',
        'Accept-Language': 'id-ID,id;q=0.9',
        'Referer': f'https://{host}/id/line',
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        r = urllib.request.urlopen(req, context=ctx, timeout=20)
        body = r.read().decode('utf-8', 'ignore')
        return r.status, len(body), body[:300]
    except Exception as e:
        return None, 0, str(e)

# Football=1, Sports=1
endpoints = [
    '/service-api/LineFeed/Get1x2_Zip?sports=1&count=50&lng=id&tf=2200000&tz=7&mode=4',
    '/LiveFeed/Get1x2_VZip?sports=1&count=50&lng=id&mode=4&country=15&partner=8',
    '/LineFeed/Get1x2_VZip?sports=1&count=50&lng=id&tf=2200000&tz=7',
    '/service-api/LineFeed/GetChampsZip?lng=id&country=15&partner=8&virtualSports=true&groupChamps=true',
]

for host, ip in HOSTS_TO_TRY:
    print(f'\n=== Host {host} via {ip} ===')
    for ep in endpoints:
        status, size, snippet = try_endpoint(host, ip, ep)
        print(f'  [{status}] {size:>8} bytes  {ep}')
        print(f'           {snippet[:200]}')
        time.sleep(0.3)
