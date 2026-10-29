# /// script
# requires-python = ">=3.11"
# ///
"""Build Atom feeds of Hacker News stories whose titles match exact terms.

Reads feeds.toml, searches the HN Algolia API once per term, and writes one
Atom file per feed, plus feeds.opml for importing them all, into site/.
"""

import json
import re
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "site"
API = "https://hn.algolia.com/api/v1/search_by_date"
ITEM_URL = "https://news.ycombinator.com/item?id="
ATOM = "http://www.w3.org/2005/Atom"
MAX_ENTRIES = 200


def fetch(params, attempts=4):
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                return json.load(resp)
        except (urllib.error.URLError, TimeoutError):
            if attempt == attempts - 1:
                raise
            time.sleep(2 ** (attempt + 1))


def title_pattern(term, case_sensitive):
    # Algolia finds candidates; this keeps only titles that really contain the
    # term as whole words, optionally plural.
    words = r"\s+".join(re.escape(w) for w in term.split())
    flags = 0 if term in case_sensitive else re.IGNORECASE
    return re.compile(rf"\b{words}s?\b", flags)


def search(term, kind, exclude_tags, since, pattern):
    query = f'"{term}"' if " " in term else term
    data = fetch(
        {
            "query": query,
            "tags": kind,
            "numericFilters": f"created_at_i>{since}",
            "restrictSearchableAttributes": "title",
            "typoTolerance": "false",
            "advancedSyntax": "true",
            "hitsPerPage": 1000,
        }
    )
    return [
        h
        for h in data["hits"]
        if h.get("title")
        and pattern.search(h["title"])
        and not set(exclude_tags) & set(h["_tags"])
    ]


def entry_html(hit, terms):
    parts = []
    if hit.get("url"):
        domain = urllib.parse.urlparse(hit["url"]).netloc.removeprefix("www.")
        parts.append(f'<p><a href="{hit["url"]}">{domain}</a></p>')
    if hit.get("story_text"):
        parts.append(hit["story_text"])
    parts.append(f"<p>Matched: {', '.join(terms)}</p>")
    return "\n".join(parts)


def atom_time(ts):
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_feed(feed, hits, matched, base_url):
    ET.register_namespace("", ATOM)
    root = ET.Element(f"{{{ATOM}}}feed")
    self_url = f"{base_url}{feed['slug']}.xml"

    def sub(parent, tag, text=None, **attrs):
        el = ET.SubElement(parent, f"{{{ATOM}}}{tag}", attrs)
        el.text = text
        return el

    sub(root, "id", self_url)
    sub(root, "title", feed["title"])
    sub(root, "updated", atom_time(time.time()))
    sub(root, "link", rel="self", href=self_url)
    sub(root, "link", rel="alternate", href="https://news.ycombinator.com/")
    for hit in hits:
        # Entries keep only fields that never change (no points or comment
        # counts), so a reader doesn't treat old stories as updated.
        entry = sub(root, "entry")
        link = ITEM_URL + hit["objectID"]
        sub(entry, "id", link)
        sub(entry, "title", hit["title"])
        sub(entry, "link", rel="alternate", href=link)
        sub(entry, "published", atom_time(hit["created_at_i"]))
        sub(entry, "updated", atom_time(hit["created_at_i"]))
        sub(sub(entry, "author"), "name", hit["author"])
        content = entry_html(hit, matched[hit["objectID"]])
        sub(entry, "content", content, type="html")
    ET.indent(root)
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def build_opml(feeds, base_url):
    root = ET.Element("opml", version="2.0")
    ET.SubElement(ET.SubElement(root, "head"), "title").text = "Steven's feeds"
    body = ET.SubElement(root, "body")
    for feed in feeds:
        url = f"{base_url}{feed['slug']}.xml"
        ET.SubElement(body, "outline", type="rss", text=feed["title"], xmlUrl=url)
    ET.indent(root)
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def main():
    config = tomllib.loads((ROOT / "feeds.toml").read_text())
    feeds = config["feed"]
    by_slug = {f["slug"]: f for f in feeds}
    case_sensitive = set(config.get("case_sensitive", []))
    since = int(time.time()) - config["days"] * 86400
    OUT.mkdir(exist_ok=True)

    for feed in feeds:
        terms = feed.get("terms") or by_slug[feed["terms_from"]]["terms"]
        exclude_tags = feed.get("exclude_tags", [])
        stories, matched = {}, {}
        for term in terms:
            pattern = title_pattern(term, case_sensitive)
            for hit in search(term, feed["kind"], exclude_tags, since, pattern):
                stories[hit["objectID"]] = hit
                matched.setdefault(hit["objectID"], []).append(term)
            time.sleep(0.2)
        hits = sorted(stories.values(), key=lambda h: h["created_at_i"], reverse=True)
        hits = hits[:MAX_ENTRIES]
        xml = build_feed(feed, hits, matched, config["base_url"])
        (OUT / f"{feed['slug']}.xml").write_text(xml)
        print(f"{feed['slug']}: {len(hits)} stories")

    (OUT / "feeds.opml").write_text(build_opml(feeds, config["base_url"]))


if __name__ == "__main__":
    main()
