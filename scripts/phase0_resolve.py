#!/usr/bin/env python3
"""Phase 0.1 - Resolve IP for 1xbet.mobi via DNS-over-HTTPS"""
import urllib.request, ssl, json, sys

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def resolve(host):
    req = urllib.request.Request(
        f'https://1.1.1.1/dns-query?name={host}&type=A',
        headers={'accept': 'application/dns-json'}
    )
    r = urllib.request.urlopen(req, context=ctx, timeout=15)
    data = json.load(r)
    ips = [a['data'] for a in data.get('Answer', []) if a['type'] == 1]
    return ips

if __name__ == '__main__':
    host = sys.argv[1] if len(sys.argv) > 1 else '1xbet.mobi'
    ips = resolve(host)
    print(f'Host: {host}')
    print(f'IPs: {ips}')
    if ips:
        with open('/projects/sandbox/newk/testing/_ip.txt', 'w') as f:
            f.write(ips[0])
        print(f'Saved primary IP: {ips[0]}')
