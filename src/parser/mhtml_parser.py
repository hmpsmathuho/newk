"""Decode MHTML / .mobi (Saved-by-Blink format) into raw text.

MHTML is a multipart/related MIME container. We extract the first text/html part,
decode quoted-printable, strip HTML tags, and collapse whitespace into a single
search-friendly text blob that the odds extractor can regex over.
"""
from __future__ import annotations

import quopri
import re
from email import message_from_bytes
from email.policy import default as default_policy


def decode_mhtml(path: str) -> dict:
    """Read an MHTML file and return a structured dict.

    Returns:
      {
        "url": Snapshot-Content-Location URL (best-effort match URL),
        "subject": Subject header,
        "html": first text/html part (decoded),
        "plain_text": HTML stripped of tags + whitespace collapsed,
      }
    """
    with open(path, "rb") as f:
        raw = f.read()

    # Snapshot URL is usually in the top-level header before MIME parsing
    head = raw[:8192].decode("utf-8", errors="ignore")
    url_m = re.search(r"Snapshot-Content-Location:\s*(\S+)", head)
    subject_m = re.search(r"Subject:\s*([^\r\n]+)", head)
    url = url_m.group(1).strip() if url_m else ""
    subject = subject_m.group(1).strip() if subject_m else ""

    # Try MIME multipart parsing first
    html_part = None
    try:
        msg = message_from_bytes(raw, policy=default_policy)
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/html" and html_part is None:
                    payload = part.get_payload(decode=True)
                    if payload:
                        # email lib already decoded transfer encoding
                        try:
                            html_part = payload.decode("utf-8", errors="ignore")
                        except Exception:
                            html_part = str(payload)
                        break
        elif msg.get_content_type() == "text/html":
            payload = msg.get_payload(decode=True)
            if payload:
                html_part = payload.decode("utf-8", errors="ignore")
    except Exception:
        pass

    # Fallback: brute-force quoted-printable decode of entire file.
    # Many .mhtml saves from Blink use quoted-printable globally; this catches them.
    if not html_part:
        try:
            html_part = quopri.decodestring(raw).decode("utf-8", errors="ignore")
        except Exception:
            html_part = raw.decode("utf-8", errors="ignore")

    # Strip HTML tags, collapse whitespace
    no_tags = re.sub(r"<[^>]+>", " ", html_part)
    plain_text = re.sub(r"\s+", " ", no_tags).strip()

    return {
        "url": url,
        "subject": subject,
        "html": html_part,
        "plain_text": plain_text,
    }


def parse_match_meta_from_url(url: str) -> dict:
    """Parse 1xbet match URL to extract league_id, match_id, slug, and team names.

    Examples:
      https://1xbet.mobi/id/top-events/epl/line/football/88637-england-premier-league/333748322-burnley-wolverhampton-wanderers
      https://1xbet.mobi/id/line/football/119445-ireland-premier-league/333772928-shelbourne-waterford
    """
    out = {"league_id": None, "league_slug": None, "match_id": None, "match_slug": None,
           "home_slug": None, "away_slug": None}
    if not url:
        return out
    m = re.search(r"football/(\d+)-([^/]+)/(\d+)-([a-z0-9\-]+)", url)
    if m:
        out["league_id"] = m.group(1)
        out["league_slug"] = m.group(2)
        out["match_id"] = m.group(3)
        out["match_slug"] = m.group(4)
        # Try to split team slugs by common separators (-vs- or last word boundary)
        slug = m.group(4)
        # Heuristic: 1xbet uses 'team1-team2' joined by hyphen — disambiguate is hard
        # without external mapping, so we leave home_slug/away_slug for caller
        out["home_slug"] = slug  # the caller can rely on subject/Snapshot or rendered text
        out["away_slug"] = slug
    return out


def humanize_slug(slug: str) -> str:
    """Convert kebab-case slug to title-cased name."""
    if not slug:
        return ""
    return " ".join(w.capitalize() for w in slug.split("-"))
