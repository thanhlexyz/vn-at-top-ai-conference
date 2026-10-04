#!/usr/bin/env python3
"""Download the public accepted-paper lists of the eleven venues and normalize them.

No login needed. Sources:
    iclr.cc / neurips.cc / icml.cc / cvpr.thecvf.com / iccv.thecvf.com   virtual-site JSON (authors with affiliations)
    eccv.ecva.net                                     ECCV virtual-site JSON (2024 on, authors with affiliations)
    openaccess.thecvf.com                             CVPR and ICCV paper lists (author names only)
    ecva.net/papers.php                               ECCV paper lists (author names only)
    aclanthology.org                                  ACL, EMNLP and NAACL main-conference volumes (author names only);
                                                      industry and demo volumes are left out; Findings
                                                      papers count as rejected when a professor's OpenReview record shows them
    ojs.aaai.org                                      AAAI proceedings issues (author names only); the "AAAI Technical
                                                      Track on ..." sections are the main track
    ijcai.org/proceedings                             IJCAI proceedings (author names only); the "Main Track" section
                                                      is the main track. IJCAI-PRICAI 2020 met in January 2021 and is 2020

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

from common import (ACCEPTED, LAST_YEAR, RAW, WORK, YEARS, held, norm_title, presentation, virtual_track, write_json,
                    write_jsonl_gz)

USER_AGENT = "vn-conference-stats/1.0 (personal research script)"
VIRTUAL_SITE = {"iclr": "https://iclr.cc", "neurips": "https://neurips.cc", "icml": "https://icml.cc",
                "cvpr": "https://cvpr.thecvf.com", "iccv": "https://iccv.thecvf.com", "eccv": "https://eccv.ecva.net"}
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
            if data[:2] == b"\x1f\x8b":   # ojs.aaai.org sends gzip even when it is not asked for
                data = gzip.decompress(data)
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
    September 2026 the NeurIPS 2026 list lacked papers that their authors had already announced. The
    schedule is added a few sessions at a time (on 2026-10-02, 22 of 9,236 entries had a time while
    announced papers were still missing), so the list counts as final only once most entries have one.
    """
    try:
        rows = json.loads(data).get("results", [])
    except (ValueError, AttributeError):
        return False
    return bool(rows) and 2 * sum(1 for r in rows if r.get("starttime")) < len(rows)


# ---------------------------------------------------------------- CVF open access

def parse_cvf(year, page, venue="cvpr"):
    out = []
    for block in page.split('<dt class="ptitle">')[1:]:
        m = re.search(r'<a href="([^"]+)">(.*?)</a>', block, re.S)
        if not m:
            continue
        names = re.findall(r'name="query_author" value="([^"]*)"', block.split("<dt", 1)[0])
        out.append({"venue": venue, "year": year, "track": "main",
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


def parse_ecva(year, page):
    """ECCV papers of one year from ecva.net/papers.php, which lists every year on one page under
    'ECCV <year> Papers' headings; titles in <dt class="ptitle">, authors (with * for corresponding) in the next <dd>."""
    start = page.find(f"ECCV {year} Papers")
    if start < 0:
        return []
    nxt = re.search(r"ECCV \d{4} Papers", page[start + 20:])
    section = page[start: start + 20 + nxt.start()] if nxt else page[start:]
    out = []
    for block in section.split('<dt class="ptitle">')[1:]:
        m = re.search(r"<a href=([^>]+)>\s*(.*?)</a>", block, re.S)
        names = re.search(r"</dt>\s*<dd>\s*(.*?)</dd>", block, re.S)
        if not m or not names:
            continue
        authors = [n.strip().rstrip("*").strip() for n in html.unescape(re.sub(r"<[^>]+>", "", names.group(1))).split(",")]
        out.append({"venue": "eccv", "year": year, "track": "main",
                    "title": html.unescape(re.sub(r"\s+", " ", m.group(2))).strip(),
                    "authors": [{"name": a, "aff": ""} for a in authors if a],
                    "url": "https://www.ecva.net/" + m.group(1).strip("'\""), "forum": "", "pres": "",
                    "topic": "", "source": "ecva.net"})
    return out


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


def parse_acl_bib(year, text, venue="acl"):
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
        out.append({"venue": venue, "year": year, "track": "main", "title": debib(fields["title"]),
                    "authors": authors, "url": fields.get("url", ""), "forum": "", "pres": "",
                    "topic": "", "source": "aclanthology.org"})
    return out


def acl_volumes(year, venue="acl"):
    if venue == "naacl":
        return [] if not held("naacl", year) else [f"{year}.naacl-main"] if year < 2024 else [f"{year}.naacl-long", f"{year}.naacl-short"]
    return [f"{year}.acl-main"] if year == 2020 else [f"{year}.acl-long", f"{year}.acl-short"]


# ---------------------------------------------------------------- AAAI and IJCAI proceedings

AAAI = "https://ojs.aaai.org/index.php/AAAI"


def text_of(fragment):
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment)))).strip()


def aaai_issues(refresh=False):
    """{year: [(issue id, title)]} from the AAAI archive, newest first, down to AAAI-20 (Vol. 34)."""
    out, page = collections.defaultdict(list), 1
    while True:
        data = fetch(f"{AAAI}/issue/archive/{page}", f"aaai/archive-{page}.html", refresh)
        found = re.findall(r'<a class="title" href="[^"]*issue/view/(\d+)">(.*?)</a>', data.decode("utf-8", "replace"), re.S) if data else []
        years = []
        for issue, title in found:
            title = text_of(title)
            m = re.search(r"\bAAAI-(\d\d)\b", title)
            if m:
                years.append(2000 + int(m.group(1)))
                if years[-1] >= YEARS[0]:
                    out[years[-1]].append((issue, title))
        if not found or (years and min(years) < YEARS[0]):
            return out
        page += 1


def aaai_track(section):
    """'main' for an "AAAI Technical Track on ..." section; otherwise the section's own name, e.g. a special track.
    AAAI-24 and AAAI-25 print three special tracks under technical-track names; they stay special tracks."""
    if re.search(r"Safe, Robust and Responsible|AI for Social Impact|AI Alignment", section):
        return section
    return "main" if re.match(r"AAAI Technical Track\b", section) else section


def parse_aaai(year, page):
    out = []
    for part in re.split(r'<div class="section">', page)[1:]:
        h = re.search(r"<h2>(.*?)</h2>", part, re.S)
        track = aaai_track(text_of(h.group(1))) if h else "other"
        for art in re.findall(r'<div class="obj_article_summary">(.*?)</ul>\s*</div>', part, re.S):
            t = re.search(r'<h3 class="title">\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', art, re.S)
            a = re.search(r'<div class="authors">(.*?)</div>', art, re.S)
            if not t:
                continue
            pdf = re.search(r'class="obj_galley_link pdf" href="([^"]+)"', art)
            names = [n.strip() for n in text_of(a.group(1)).split(",") if n.strip()] if a else []
            out.append({"venue": "aaai", "year": year, "track": track, "title": text_of(t.group(2)),
                        "authors": [{"name": n, "aff": ""} for n in names], "url": t.group(1),
                        "pdf": pdf.group(1).replace("/article/view/", "/article/download/") if pdf else "",
                        "forum": "", "pres": "", "topic": "", "source": "ojs.aaai.org"})
    return out


def parse_ijcai(year, page):
    out = []
    for part in re.split(r'<div class="section_title">', page)[1:]:
        h = re.match(r"\s*<h3>(.*?)</h3>", part, re.S)
        section = text_of(h.group(1)) if h else ""
        track = "main" if section.lower().startswith("main track") else section or "other"
        sub = ""
        for m in re.finditer(r'<div class="subsection_title">(.*?)</div>|<div id="paper\d+" class="paper_wrapper">'
                             r'<div class="title">(.*?)</div><div class="authors">(.*?)</div>'
                             r'<div class="details">.*?href="([^"]+\.pdf)".*?href="(/proceedings/[^"]+)"', part, re.S):
            if m.group(1) is not None:
                sub = text_of(m.group(1))
                continue
            out.append({"venue": "ijcai", "year": year, "track": track, "title": text_of(m.group(2)),
                        "authors": [{"name": n.strip(), "aff": ""} for n in text_of(m.group(3)).split(",") if n.strip()],
                        "url": "https://www.ijcai.org" + m.group(5),
                        "pdf": f"https://www.ijcai.org/proceedings/{year}/{m.group(4)}",
                        "forum": "", "pres": "", "topic": sub, "source": "ijcai.org"})
    return out


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

    issues = aaai_issues(refresh)
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

        # ICCV is held in odd years; only 2025 has a virtual site with affiliations
        if year % 2 == 1:
            data = fetch(f"{VIRTUAL_SITE['iccv']}/static/virtual/data/iccv-{year}-orals-posters.json",
                         f"virtual/iccv-{year}.json", refresh)
            virtual = parse_virtual("iccv", year, data) if data else []
            page = fetch(f"https://openaccess.thecvf.com/ICCV{year}?day=all", f"cvf/iccv-{year}-all.html", refresh)
            cvf = parse_cvf(year, page.decode("utf-8", "replace"), "iccv") if page else []
            rows = merge_cvpr(virtual, cvf)
        else:
            rows = []
        add("iccv", year, rows, sorted({p["source"] for p in rows}))

        # ECCV is held in even years: ecva.net for the proceedings, the virtual site (2024 on) for affiliations
        if year % 2 == 0:
            data = fetch(f"{VIRTUAL_SITE['eccv']}/static/virtual/data/eccv-{year}-orals-posters.json",
                         f"virtual/eccv-{year}.json", refresh)
            virtual = parse_virtual("eccv", year, data) if data else []
            page = fetch("https://www.ecva.net/papers.php", "ecva/papers.html", refresh and year == YEARS[0])
            listed = parse_ecva(year, page.decode("utf-8", "replace")) if page else []
            rows = merge_cvpr(virtual, listed)
        else:
            rows = []
        add("eccv", year, rows, sorted({p["source"] for p in rows}))

        bib = fetch(f"https://aclanthology.org/volumes/{year}.emnlp-main.bib", f"acl/{year}.emnlp-main.bib", refresh)
        rows = parse_acl_bib(year, bib.decode("utf-8", "replace"), "emnlp") if bib else []
        add("emnlp", year, rows, ["aclanthology.org"] if rows else [])

        rows = []
        for vol in acl_volumes(year, "naacl"):
            bib = fetch(f"https://aclanthology.org/volumes/{vol}.bib", f"acl/{vol}.bib", refresh)
            rows += parse_acl_bib(year, bib.decode("utf-8", "replace"), "naacl") if bib else []
        add("naacl", year, rows, ["aclanthology.org"] if rows else [])

        rows = []
        for issue, _ in issues.get(year, []):
            page = fetch(f"{AAAI}/issue/view/{issue}", f"aaai/issue-{issue}.html", refresh and year >= LAST_YEAR)
            rows += parse_aaai(year, page.decode("utf-8", "replace")) if page else []
        add("aaai", year, rows, ["ojs.aaai.org"] if rows else [])

        page = fetch(f"https://www.ijcai.org/proceedings/{year}/", f"ijcai/{year}.html", refresh)
        rows = parse_ijcai(year, page.decode("utf-8", "replace")) if page else []
        add("ijcai", year, rows, ["ijcai.org"] if rows else [])
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
        note = ", ".join(f"{k} {v}" for k, v in sorted(c["other_tracks"].items())) if c["papers"] else ("not held" if not held(c["venue"], c["year"]) else "not published yet")
        note += "  (no schedule yet: the list may be incomplete)" if c["provisional"] else ""
        print(f"{c['venue']:8s}{c['year']:5d}{c['papers']:7d}{c['with_affiliation']:7d}%  {note}")
    print(f"\n{sum(c['papers'] for c in coverage)} main-track papers -> {ACCEPTED}")


if __name__ == "__main__":
    main()
