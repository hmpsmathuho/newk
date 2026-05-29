#!/usr/bin/env python3
"""Phase 0 — fetch match list dari 1xbet.mobi untuk parlay upcoming.

Strategi:
1. Resolve IP 1xbet.mobi via DNS-over-HTTPS (1.1.1.1).
2. Fetch /id/line untuk lihat daftar match aktif.
3. Filter ke match yang start dalam 24-48 jam ke depan dari sekarang.
4. Save raw HTML + extract daftar match.
"""
import urllib.request
import ssl
import json
import re
import os
from datetime import datetime, timezone, timedelta

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    "Host": "1xbet.mobi",
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                  "Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
}


def resolve_ip(domain="1xbet.mobi"):
    req = urllib.request.Request(
        f"https://1.1.1.1/dns-query?name={domain}&type=A",
        headers={"accept": "application/dns-json"},
    )
    r = urllib.request.urlopen(req, context=ctx, timeout=10)
    data = json.load(r)
    ips = [a["data"] for a in data.get("Answer", []) if a.get("type") == 1]
    if not ips:
        raise RuntimeError(f"No A record for {domain}")
    return ips


def fetch_line_page(ip):
    url = f"https://{ip}/id/line"
    req = urllib.request.Request(url, headers=HEADERS)
    r = urllib.request.urlopen(req, context=ctx, timeout=25)
    return r.read().decode("utf-8", "ignore")


def fetch_line_section(ip, sport_id=1):
    """sport_id 1 = football."""
    url = f"https://{ip}/id/line/{sport_id}"
    req = urllib.request.Request(url, headers=HEADERS)
    r = urllib.request.urlopen(req, context=ctx, timeout=25)
    return r.read().decode("utf-8", "ignore")


def main():
    out_dir = "/projects/sandbox/newk/upcoming"
    os.makedirs(out_dir, exist_ok=True)

    print("[*] Resolving 1xbet.mobi IP...")
    ips = resolve_ip()
    print(f"    IPs: {ips}")

    last_err = None
    page_html = None
    used_ip = None
    for ip in ips:
        try:
            print(f"[*] Fetch /id/line via {ip} ...")
            page_html = fetch_line_page(ip)
            used_ip = ip
            break
        except Exception as e:
            print(f"    ERR via {ip}: {e}")
            last_err = e
    if not page_html:
        raise SystemExit(f"All IPs failed: {last_err}")

    with open(os.path.join(out_dir, "id_line_root.html"), "w") as f:
        f.write(page_html)
    print(f"[*] Saved root /id/line ({len(page_html)} bytes)")

    # Try football section
    try:
        print(f"[*] Fetch /id/line/1 (football) via {used_ip} ...")
        football = fetch_line_section(used_ip, 1)
        with open(os.path.join(out_dir, "id_line_football.html"), "w") as f:
            f.write(football)
        print(f"    Saved football page ({len(football)} bytes)")
    except Exception as e:
        print(f"    Football section ERR: {e}")

    # Save IP for downstream use
    with open(os.path.join(out_dir, "ip.txt"), "w") as f:
        f.write(used_ip)
    print(f"[*] Done. Used IP: {used_ip}")


if __name__ == "__main__":
    main()
