#!/usr/bin/env python3
"""Collect candidate pictures for the site: conference logos, university logos and professor photos.

    python3 fetch_images.py            # download candidates into raw/images/ and write raw/images/candidates.csv
    python3 fetch_images.py --apply    # copy the approved rows of images.csv into frontend/static/img/

Candidates are only proposals. Every picture is looked at by hand before its row in images.csv gets
`approved = yes`; only approved pictures are copied to the site. A professor photo is proposed only from the
professor's own page or their staff page on the roster (or the homepage on their OpenReview profile), and only
when the page marks it as a portrait: the page's preview image, or an image whose file name or alt text
carries the person's name or words such as "profile", "avatar" or "photo". Professors without such a picture
simply get none.

Logos come from Wikipedia's page image for the institution (the infobox logo or seal) and from the
conferences' own sites. Everything is resized to at most 400 px and stored with its source in images.csv.
"""
import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

from common import BACKEND, FRONTEND, OPENREVIEW_RAW, RAW, load_roster, norm_name, read_csv

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
CANDIDATES = RAW / "images"
TABLE = BACKEND / "images.csv"   # hand-checked: kind, key, approved, image_url, source_page, note
STATIC = FRONTEND / "static" / "img"
FIELDS = ["kind", "key", "approved", "image_url", "source_page", "note"]

VENUE_SITES = {"iclr": "https://iclr.cc/", "neurips": "https://neurips.cc/", "icml": "https://icml.cc/",
               "cvpr": "https://cvpr.thecvf.com/", "acl": "https://www.aclweb.org/portal/"}
# English Wikipedia titles of the institutions on the site
WIKIPEDIA = {
    "hust": "Hanoi University of Science and Technology", "vinuni": "VinUniversity",
    "ptit": "Posts and Telecommunications Institute of Technology", "hcmus": "Ho Chi Minh City University of Science",
    "phenikaa": "Phenikaa University", "rmit-vietnam": "RMIT University Vietnam",
    "vnu-uet": "VNU University of Engineering and Technology", "ueh": "University of Economics Ho Chi Minh City",
    "vast": "Vietnam Academy of Science and Technology",
    "hcmiu": "International University – Vietnam National University, Ho Chi Minh City",
    "british-university-vietnam": "British University Vietnam", "ctu": "Can Tho University",
    "fpt-university": "FPT University", "ftu": "Foreign Trade University", "hmu": "Hanoi Medical University",
    "hcmut": "Ho Chi Minh City University of Technology", "quy-nhon-university": "Quy Nhon University",
    "udn": "University of Danang", "uit": "University of Information Technology (Vietnam)",
}
PORTRAIT_WORDS = re.compile(r"profile|avatar|portrait|photo|headshot|me\.(jpe?g|png|webp)|bio|author", re.I)


def get(url, binary=False):
    r = subprocess.run(["curl", "-sL", "--max-time", "40", "-A", UA, url], capture_output=True)
    return r.stdout if binary else r.stdout.decode("utf-8", "ignore")


def save(kind, key, url, page, note, rows):
    data = get(url, binary=True)
    if len(data) < 500:
        return
    ext = re.search(r"\.(png|jpe?g|webp|gif|svg)(\?|$)", url.lower())
    name = f"{kind}-{key}-{hashlib.md5(url.encode()).hexdigest()[:6]}.{ext.group(1) if ext else 'img'}"
    (CANDIDATES / name).write_bytes(data)
    rows.append({"kind": kind, "key": key, "file": name, "image_url": url, "source_page": page, "note": note})


def images_on(page_url, html):
    """(absolute url, alt, how it was found) for the preview image and every <img> of a page."""
    out = []
    for m in re.finditer(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]*>', html, re.I):
        c = re.search(r'content=["\']([^"\']+)', m.group(0))
        if c:
            out.append((urllib.parse.urljoin(page_url, c.group(1)), "", "preview image"))
    for m in re.finditer(r"<img\b[^>]*>", html, re.I):
        tag = m.group(0)
        src = re.search(r'\s(?:data-src|src)=["\']([^"\']+)', tag)
        alt = re.search(r'\salt=["\']([^"\']*)', tag)
        if src and not src.group(1).startswith("data:"):
            out.append((urllib.parse.urljoin(page_url, src.group(1)), alt.group(1) if alt else "", "img"))
    return out


def people(rows):
    for p in load_roster():
        if p["approved"] != "yes":
            continue
        pages = [x for x in [p["homepage"], *p["pages"]] if x]
        f = OPENREVIEW_RAW / f"{p['slug']}.json"
        if f.exists():
            pages += [pr["homepage"] for pr in json.loads(f.read_text()).get("profiles", []) if pr.get("homepage")]
        tokens = {t for t in norm_name(" ".join([p["name"], *p["variants"]])).split() if len(t) > 2}
        seen = set()
        for page in dict.fromkeys(pages):
            if "researchgate" in page or "openreview" in page or page.endswith(".htm") and "publication" in page:
                continue
            html = get(page)
            for url, alt, how in images_on(page, html):
                if url in seen or re.search(r"logo|icon|banner|favicon|sprite|badge|flag", url, re.I):
                    continue
                low = norm_name(urllib.parse.unquote(url.rsplit("/", 1)[-1]) + " " + alt)
                named = sum(t in low.split() or t in low.replace(" ", "") for t in tokens) >= 1
                if how == "preview image" or named or PORTRAIT_WORDS.search(url + " " + alt):
                    seen.add(url)
                    save("person", p["slug"], url, page, f"{how}; alt: {alt[:60]}", rows)
        print(f"  {p['slug']}: {sum(r['key'] == p['slug'] for r in rows)} candidates", file=sys.stderr)


def institutions(rows):
    for key, title in WIKIPEDIA.items():
        api = ("https://en.wikipedia.org/w/api.php?action=query&format=json&prop=pageimages&piprop=original"
               "&redirects=1&titles=" + urllib.parse.quote(title))
        try:
            pages = json.loads(get(api))["query"]["pages"]
        except (ValueError, KeyError):
            continue
        for pg in pages.values():
            if pg.get("original"):
                save("institution", key, pg["original"]["source"], f"https://en.wikipedia.org/wiki/{urllib.parse.quote(pg['title'])}",
                     "Wikipedia page image", rows)


def venues(rows):
    for key, site in VENUE_SITES.items():
        html = get(site)
        for url, alt, how in images_on(site, html):
            if re.search(r"logo", url + " " + alt, re.I) or how == "preview image":
                save("venue", key, url, site, f"{how}; alt: {alt[:60]}", rows)


def apply():
    STATIC.mkdir(parents=True, exist_ok=True)
    cands = {(r["kind"], r["key"], r["image_url"]): r for r in read_csv(CANDIDATES / "candidates.csv")}
    done = 0
    for r in read_csv(TABLE):
        if r["approved"] != "yes":
            continue
        c = cands.get((r["kind"], r["key"], r["image_url"]))
        if not c:
            print(f"  not downloaded: {r['kind']} {r['key']}", file=sys.stderr)
            continue
        folder = STATIC / {"person": "people", "institution": "institutions", "venue": "venues"}[r["kind"]]
        folder.mkdir(parents=True, exist_ok=True)
        src = CANDIDATES / c["file"]
        if src.suffix == ".svg":
            dest = folder / f"{r['key']}.svg"
            dest.write_bytes(src.read_bytes())
        else:   # a still image at most 400 px on its longer side; logos keep transparency
            dest = folder / f"{r['key']}.{'png' if r['kind'] != 'person' else 'jpg'}"
            subprocess.run(["magick", f"{src}[0]", "-auto-orient", "-resize", "400x400>", "-strip", str(dest)], check=True)
        done += 1
    print(f"{done} pictures -> {STATIC}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="copy the approved pictures into frontend/static/img")
    ap.add_argument("--only", choices=["person", "institution", "venue"])
    args = ap.parse_args()
    if args.apply:
        return apply()
    CANDIDATES.mkdir(parents=True, exist_ok=True)
    rows = []
    for kind, step in (("venue", venues), ("institution", institutions), ("person", people)):
        if not args.only or args.only == kind:
            step(rows)
    with open(CANDIDATES / "candidates.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["kind", "key", "file", "image_url", "source_page", "note"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} candidates -> {CANDIDATES}")


if __name__ == "__main__":
    main()
