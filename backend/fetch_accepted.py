#!/usr/bin/env python3
"""Download the public accepted-paper lists of ICLR, NeurIPS, ICML, CVPR and ACL and normalize them.

No login needed. Sources:
    iclr.cc / neurips.cc / icml.cc / cvpr.thecvf.com  virtual-site JSON (authors with affiliations)
    openaccess.thecvf.com                             CVPR paper lists (author names only)
    aclanthology.org                                  ACL main-conference volumes (author names only)

Downloads are kept in raw/ and reused; pass --refresh to download again (for example after a
conference publishes its list). The result is work/accepted.jsonl.gz, one paper per line:

    {"venue", "year", "track", "title", "authors": [{"name", "aff"}], "url", "forum", "pres", "topic", "source"}

`track` is "main" for the main conference; other tracks are kept so the site can say why a paper
is not counted.
"""
import argparse
import collections
import gzip
import html
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request

from common import (ACCEPTED, LAST_YEAR, RAW, WORK, YEARS, norm_title, presentation, virtual_track, write_json,
                    write_jsonl_gz)

USER_AGENT = "vn-conference-stats/1.0 (personal research script)"
VIRTUAL_SITE = {"iclr": "https://iclr.cc", "neurips": "https://neurips.cc", "icml": "https://icml.cc",
                "cvpr": "https://cvpr.thecvf.com"}
CVPR2020_DAYS = ["2020-06-16", "2020-06-17", "2020-06-18"]  # the 2020 list has no "all days" page
PRES_ORDER = {"": 0, "highlight": 1, "spotlight": 1, "oral": 2}


# ---------------------------------------------------------------- download

def fetch(url, name, refresh=False):
    """Return the bytes of `url`, cached gzip-compressed as raw/<name>.gz. None if the server has no such file."""
    path = RAW / (name + ".gz")
    missing = RAW / (name + ".missing")
    if not refresh:
        if path.exists():
            return gzip.decompress(path.read_bytes())
        if missing.exists() and time.time() - missing.stat().st_mtime < 86400:
            return None
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"  downloading {url}", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = r.read()
            break
        except urllib.error.HTTPError as e:
            if e.code in (403, 404, 410):
                missing.write_text(f"{e.code} {url}\n")
                return None
            err = e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            err = e
        time.sleep(3 * (attempt + 1))
    else:
        print(f"  warning: could not download {url}: {err}", file=sys.stderr)
        return None
    path.write_bytes(gzip.compress(data))
    missing.unlink(missing_ok=True)
    time.sleep(1)  # stay polite between downloads
    return data


# ---------------------------------------------------------------- virtual-site JSON

def parse_virtual(venue, year, data):
    try:
        rows = json.loads(data).get("results", [])
    except (ValueError, AttributeError):
        return []
    has_source = sum(1 for r in rows if r.get("sourceurl")) > len(rows) / 2
    site = VIRTUAL_SITE[venue]
    papers = {}
    for r in rows:
        title = html.unescape(r.get("name") or "").strip()
        authors = [{"name": html.unescape(a.get("fullname") or "").strip(),
                    "aff": html.unescape(a.get("institution") or "").strip()}
                   for a in r.get("authors") or [] if (a.get("fullname") or "").strip()]
        if not title or not authors:
            continue
        track = virtual_track(title, r.get("sourceurl"), r.get("event_type"), has_source)
        paper_url = r.get("paper_url") or ""
        forum = re.search(r"openreview\.net/forum\?id=([\w-]+)", paper_url)
        url = paper_url if paper_url.startswith("http") else (
            site + r["virtualsite_url"] if r.get("virtualsite_url") else "")
        pres = presentation(f"{r.get('decision') or ''} {r.get('event_type') or ''} {r.get('eventtype') or ''}")
        topic = html.unescape(r.get("topic") or "").strip()
        key = (track, norm_title(title))
        p = papers.get(key)
        if p is None:
            papers[key] = {"venue": venue, "year": year, "track": track, "title": title, "authors": authors,
                           "url": url, "forum": forum.group(1) if forum else "", "pres": pres,
                           "topic": topic, "source": site.split("//")[1]}
            continue
        # the same paper listed again as an oral/spotlight session: keep the richer record
        if PRES_ORDER[pres] > PRES_ORDER[p["pres"]]:
            p["pres"] = pres
        if forum and not p["forum"]:
            p["forum"], p["url"] = forum.group(1), url
        p["topic"] = p["topic"] or topic
        if sum(bool(a["aff"]) for a in authors) > sum(bool(a["aff"]) for a in p["authors"]):
            p["authors"] = authors
    # an oral listed a second time without a sourceurl is the same paper as its main-track poster
    for track, title in [k for k in papers if k[0] == "other"]:
        main = papers.get(("main", title))
        if main:
            dup = papers.pop((track, title))
            if PRES_ORDER[dup["pres"]] > PRES_ORDER[main["pres"]]:
                main["pres"] = dup["pres"]
    return list(papers.values())


def is_provisional(data):
    """True for a virtual-site list that has no schedule yet (only meaningful for the current year).

    Such a list was put up between the decisions and the conference and is still being filled: in
    September 2026 the NeurIPS 2026 list lacked papers that their authors had already announced.
    """
    try:
        rows = json.loads(data).get("results", [])
    except (ValueError, AttributeError):
        return False
    return bool(rows) and not any(r.get("starttime") for r in rows)


# ---------------------------------------------------------------- CVF open access

def parse_cvf(year, page):
    out = []
    for block in page.split('<dt class="ptitle">')[1:]:
        m = re.search(r'<a href="([^"]+)">(.*?)</a>', block, re.S)
        if not m:
            continue
        names = re.findall(r'name="query_author" value="([^"]*)"', block.split("<dt", 1)[0])
        out.append({"venue": "cvpr", "year": year, "track": "main",
                    "title": html.unescape(re.sub(r"\s+", " ", m.group(2))).strip(),
                    "authors": [{"name": html.unescape(n).strip(), "aff": ""} for n in names if n.strip()],
                    "url": "https://openaccess.thecvf.com" + m.group(1), "forum": "", "pres": "",
                    "topic": "", "source": "openaccess.thecvf.com"})
    return out


def merge_cvpr(virtual, cvf):
    """Use the CVF list as the base (it is the proceedings) and copy affiliations from the virtual site.

    When the virtual-site list is as complete as the CVF one, it is used directly: every author then
    has an affiliation, which the name matching needs.
    """
    vmain = [p for p in virtual if p["track"] == "main"]
    other = [p for p in virtual if p["track"] != "main"]
    if not cvf:
        return virtual
    if len(vmain) >= 0.95 * len(cvf):
        return vmain + other
    by_title = {norm_title(p["title"]): p for p in vmain}
    for p in cvf:
        v = by_title.get(norm_title(p["title"]))
        if v and len(v["authors"]) == len(p["authors"]):
            p["authors"], p["pres"] = v["authors"], v["pres"]
    return cvf + other


# ---------------------------------------------------------------- ACL Anthology BibTeX

_ACCENT = {"`": "\u0300", "'": "\u0301", "^": "\u0302", "~": "\u0303", "=": "\u0304", "u": "\u0306",
           ".": "\u0307", '"': "\u0308", "h": "\u0309", "r": "\u030a", "H": "\u030b", "v": "\u030c",
           "d": "\u0323", "c": "\u0327", "k": "\u0328", "b": "\u0331"}
_LETTER = {"DJ": "Đ", "dj": "đ", "o": "ø", "O": "Ø", "l": "ł", "L": "Ł", "ss": "ß", "ae": "æ", "AE": "Æ",
           "aa": "å", "AA": "Å", "oe": "œ", "OE": "Œ", "i": "i", "j": "j"}
_BASE = r"([A-Za-z\u00c0-\u024f\u1e00-\u1eff][\u0300-\u036f]*)"
_ACCENT_RX = [re.compile(r"\\([`'^~=.\"])\s*\{?" + _BASE + r"\}?"),
              re.compile(r"\\([uhrHvdckb])\s*\{" + _BASE + r"\}"),
              re.compile(r"\\([uhrHvdckb])\s+" + _BASE)]


def debib(s):
    """BibTeX/LaTeX text to plain Unicode: '{\\DJ}o{\\`a}n' -> 'Đoàn', '{E}com{S}cript' -> 'EcomScript'."""
    s = re.sub(r"\\(DJ|dj|ss|ae|AE|aa|AA|oe|OE|[oOlLij])(?![A-Za-z]) ?", lambda m: _LETTER[m.group(1)], s)
    for _ in range(4):  # accents can be nested, e.g. \~{\^e}
        before = s
        for rx in _ACCENT_RX:
            s = rx.sub(lambda m: m.group(2) + _ACCENT[m.group(1)], s)
        if s == before:
            break
    s = s.replace("\\&", "&").replace("\\%", "%").replace("\\$", "$").replace("\\_", "_").replace("\\#", "#")
    s = re.sub(r"\\[a-zA-Z]+\s*", "", s).replace("{", "").replace("}", "").replace("\\", "")
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", s)).strip()


def bib_fields(entry):
    """Fields of one BibTeX entry. Values are delimited by "..." or {...} (the latter may nest)."""
    fields, i = {}, entry.find("\n")
    while True:
        m = re.compile(r"\s*(\w+)\s*=\s*").match(entry, i)
        if not m:
            return fields
        name, i = m.group(1).lower(), m.end()
        if entry[i] == "{":
            depth, j = 1, i + 1
            while j < len(entry) and depth:
                depth += {"{": 1, "}": -1}.get(entry[j], 0)
                j += 1
            value, i = entry[i + 1:j - 1], j
        elif entry[i] == '"':
            depth, j = 0, i + 1
            while j < len(entry) and not (entry[j] == '"' and depth == 0):
                depth += {"{": 1, "}": -1}.get(entry[j], 0)
                j += 1
            value, i = entry[i + 1:j], j + 1
        else:
            j = i
            while j < len(entry) and entry[j] not in ",\n":
                j += 1
            value, i = entry[i:j], j
        fields[name] = value
        i = entry.find(",", i) + 1 if entry[i:i + 3].lstrip().startswith(",") else i


def parse_acl_bib(year, text):
    out = []
    for entry in re.split(r"\n(?=@)", text):
        if not entry.startswith("@inproceedings"):
            continue
        fields = bib_fields(entry)
        if "title" not in fields or "author" not in fields:
            continue
        authors = []
        for a in re.split(r"\s+and\s+", fields["author"]):
            last, _, first = debib(a).partition(",")
            authors.append({"name": f"{first.strip()} {last.strip()}".strip(), "aff": ""})
        out.append({"venue": "acl", "year": year, "track": "main", "title": debib(fields["title"]),
                    "authors": authors, "url": fields.get("url", ""), "forum": "", "pres": "",
                    "topic": "", "source": "aclanthology.org"})
    return out


def acl_volumes(year):
    return [f"{year}.acl-main"] if year == 2020 else [f"{year}.acl-long", f"{year}.acl-short"]


# ---------------------------------------------------------------- main

def collect(years, refresh=False):
    papers, coverage = [], []

    def add(venue, year, rows, sources, provisional=False):
        main = [p for p in rows if p["track"] == "main"]
        affs = [bool(a["aff"]) for p in main for a in p["authors"]]
        other = collections.Counter(p["track"] for p in rows if p["track"] != "main")
        coverage.append({"venue": venue, "year": year, "papers": len(main), "sources": sources,
                         "with_affiliation": round(100 * sum(affs) / len(affs)) if affs else 0,
                         "other_tracks": dict(other), "provisional": provisional})
        papers.extend(rows)

    for year in years:
        for venue in ("iclr", "neurips", "icml"):
            data = fetch(f"{VIRTUAL_SITE[venue]}/static/virtual/data/{venue}-{year}-orals-posters.json",
                         f"virtual/{venue}-{year}.json", refresh)
            add(venue, year, parse_virtual(venue, year, data) if data else [],
                [VIRTUAL_SITE[venue].split("//")[1]] if data else [],
                bool(data) and year >= LAST_YEAR and is_provisional(data))

        data = fetch(f"{VIRTUAL_SITE['cvpr']}/static/virtual/data/cvpr-{year}-orals-posters.json",
                     f"virtual/cvpr-{year}.json", refresh)
        virtual = parse_virtual("cvpr", year, data) if data else []
        cvf = []
        for day in (CVPR2020_DAYS if year == 2020 else ["all"]):
            page = fetch(f"https://openaccess.thecvf.com/CVPR{year}?day={day}", f"cvf/cvpr-{year}-{day}.html", refresh)
            cvf += parse_cvf(year, page.decode("utf-8", "replace")) if page else []
        rows = merge_cvpr(virtual, cvf)
        add("cvpr", year, rows, sorted({p["source"] for p in rows}))

        rows = []
        for vol in acl_volumes(year):
            bib = fetch(f"https://aclanthology.org/volumes/{vol}.bib", f"acl/{vol}.bib", refresh)
            rows += parse_acl_bib(year, bib.decode("utf-8", "replace")) if bib else []
        add("acl", year, rows, ["aclanthology.org"] if rows else [])
    return papers, coverage


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--refresh", action="store_true", help="download everything again instead of using raw/")
    args = ap.parse_args()

    papers, coverage = collect(YEARS, args.refresh)
    write_jsonl_gz(ACCEPTED, papers)
    write_json(WORK / "coverage.json", coverage)

    print(f"{'venue':8s}{'year':>5s}{'main':>7s}{'affil%':>8s}  other tracks / note")
    for c in coverage:
        note = ", ".join(f"{k} {v}" for k, v in sorted(c["other_tracks"].items())) if c["papers"] else "not published yet"
        note += "  (no schedule yet: the list may be incomplete)" if c["provisional"] else ""
        print(f"{c['venue']:8s}{c['year']:5d}{c['papers']:7d}{c['with_affiliation']:7d}%  {note}")
    print(f"\n{sum(c['papers'] for c in coverage)} main-track papers -> {ACCEPTED}")


if __name__ == "__main__":
    main()
