#!/usr/bin/env python3
"""Save the professors' own pages and pull out the lines that mention one of the five venues.

The pages are the ones in the `pages` column of roster.csv (several addresses separated by `;`).
Each is kept in raw/homepages/ and its venue lines go to work/homepage_hits.txt, grouped by professor.

Nothing is turned into data here. Personal pages are too different from each other to parse safely,
so read homepage_hits.txt and copy the papers into self_reported.csv by hand, one row per paper:

    professor, venue, year, title, track, coauthors, announced, source_url, fetched, note

`track` is main unless the page says otherwise (datasets_benchmarks, findings, workshop, position).
A page that only announces a number ("five papers accepted") gets one row with an empty title and the
number in `announced`. build_site_data.py decides what is counted; see the About page for the rule.
"""
import argparse
import datetime
import gzip
import html
import re
import sys
import time
import urllib.error
import urllib.request

from common import RAW, WORK, load_roster, slugify

USER_AGENT = "vn-conference-stats/1.0 (personal research script)"
VENUE = re.compile(r"NeurIPS|NIPS\b|Neural Information Processing|ICLR|Learning Representations|ICML|"
                   r"International Conference on Machine Learning|CVPR|Computer Vision and Pattern Recognition|"
                   r"\bACL\b|Association for Computational Linguistics")
YEAR = re.compile(r"20(2[0-9])|[’'](2[0-9])\b")


def download(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def text_lines(data):
    """Visible text of a page, one block per line. Some old university pages are UTF-16."""
    text = data.decode("utf-16", "replace") if data[:2] in (b"\xff\xfe", b"\xfe\xff") else data.decode("utf-8", "replace")
    text = re.sub(r"<(script|style)\b.*?</\1>", " ", text, flags=re.S | re.I).replace("\r", " ").replace("\n", " ")
    text = re.sub(r"<(/p|/li|/tr|/h\d|/div|br|/dd|/dt)\b[^>]*>", "\n", text, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return [re.sub(r"\s+", " ", line).strip() for line in text.split("\n") if line.strip()]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", nargs="+", metavar="SLUG", help="fetch only these people")
    args = ap.parse_args()

    today = datetime.date.today().isoformat()
    out = [f"Lines that mention a venue and a year, read {today}. Copy papers into self_reported.csv by hand.\n"]
    folder = RAW / "homepages"
    folder.mkdir(parents=True, exist_ok=True)
    for person in load_roster():
        if person["approved"] != "yes" or (args.only and person["slug"] not in args.only):
            continue
        out.append(f"\n{'=' * 100}\n{person['name']} ({person['slug']})")
        if not person["pages"]:
            out.append("  no page in roster.csv")
        for url in person["pages"]:
            try:
                data = download(url)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                out.append(f"\n  {url}\n    could not be read: {e}")
                print(f"{person['name']}: {url} could not be read ({e})", file=sys.stderr)
                continue
            (folder / f"{person['slug']}-{slugify(url)[:80]}-{today}.html.gz").write_bytes(gzip.compress(data))
            lines = text_lines(data)
            hits = [line for line in lines if VENUE.search(line) and YEAR.search(line)]
            out.append(f"\n  {url}\n    {len(data)} bytes, {len(hits)} of {len(lines)} lines mention a venue and a year")
            out += [f"    - {line[:700]}" for line in hits]
            time.sleep(1)
        print(f"{person['name']}: {len(person['pages'])} page(s)")
    WORK.mkdir(exist_ok=True)
    (WORK / "homepage_hits.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"\n-> {WORK / 'homepage_hits.txt'}")


if __name__ == "__main__":
    main()
