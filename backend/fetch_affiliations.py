"""Affiliations read from the PDF of a paper, for accepted papers whose official list prints none (ACL, EMNLP, most
CVPR years).

For every accepted paper of a tracked person that has no affiliation in its list, this downloads the PDF (cached in
raw/pdf/), writes the title page to work/pdf_headers/, and adds one row per author to affiliations.csv with a guess
read from numbered markers ("Name1,2 ... 1University"). Title pages differ too much for the guess to be trusted, so
each row is checked against the title page by hand and marked checked=yes; build_site_data.py uses checked rows only.

    python3 fetch_affiliations.py    # then fill and check the new rows of affiliations.csv
"""
import csv
import gzip
import json
import re
import subprocess
import time
import urllib.request

from common import BACKEND, FRONTEND, norm_title, read_csv

PDF_DIR = BACKEND / "raw" / "pdf"
HEADERS = BACKEND / "work" / "pdf_headers"
CSV = BACKEND / "affiliations.csv"
FIELDS = ["venue", "year", "title", "position", "author", "affiliation", "checked"]


def pdf_url(url):
    if "thecvf.com" in url:      # .../html/X_paper.html -> .../papers/X_paper.pdf
        return url.replace("/html/", "/papers/").replace(".html", ".pdf")
    if "aclanthology.org" in url:
        return url.rstrip("/") + ".pdf"
    return None


def title_page(path):
    text = subprocess.run(["pdftotext", "-l", "1", str(path), "-"], capture_output=True, text=True).stdout
    head = re.split(r"\n\s*Abstract\b", text, maxsplit=1)[0]
    return "\n".join(l for l in head.splitlines() if "Open Access version" not in l and "watermark" not in l
                     and "IEEE Xplore" not in l)


def guess(text, names):
    """Affiliation per author from numbered markers; '' where the markers cannot be read."""
    flat = re.sub(r"\s+", " ", text)
    marks = []
    for name in names:
        m = re.search(re.escape(name) + r"\s*((?:\d+\s*,?\s*)+)", flat)
        marks.append(re.findall(r"\d+", m.group(1)) if m else [])
    last = max((flat.find(n) + len(n) for n in names if n in flat), default=-1)
    tail = flat[last:] if last >= 0 else ""
    places = {}
    for num, place in re.findall(r"(?:^|[\s;,])(\d{1,2})\s+([A-Z][^;@{}]*?)(?=\s*[;,]?\s+\d{1,2}\s+[A-Z]|\s*\{|\s+\S+@|$)", tail):
        places.setdefault(num, place.strip(" ,;"))
    return ["; ".join(places[n] for n in m if n in places) for m in marks]


def main():
    papers = {}
    for line in gzip.open(BACKEND / "work" / "accepted.jsonl.gz", "rt"):
        p = json.loads(line)
        papers[(p["venue"], p["year"], norm_title(p["title"]))] = p
    wanted = {}
    for person in json.load(open(FRONTEND / "data" / "professors.json")):
        for e in person["accepted_papers"]:
            p = papers.get((e["venue"], e["year"], norm_title(e["title"])))
            if p and not e.get("unofficial") and not any(a["aff"] for a in p["authors"]) and pdf_url(p["url"]):
                wanted[(p["venue"], p["year"], norm_title(p["title"]))] = p
    rows = read_csv(CSV) if CSV.exists() else []
    done = {(r["venue"], int(r["year"]), norm_title(r["title"])) for r in rows}
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    HEADERS.mkdir(parents=True, exist_ok=True)
    added = 0
    for key, p in sorted(wanted.items()):
        url = pdf_url(p["url"])
        path = PDF_DIR / re.sub(r"\W+", "_", url.split("/")[-1])
        if not path.exists():
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            path.write_bytes(urllib.request.urlopen(req, timeout=120).read())
            time.sleep(1)
        text = title_page(path)
        (HEADERS / (path.stem + ".txt")).write_text(f"{url}\n\n{text}\n")
        if key in done:
            continue
        names = [a["name"] for a in p["authors"]]
        for k, (name, aff) in enumerate(zip(names, guess(text, names))):
            rows.append({"venue": p["venue"], "year": p["year"], "title": p["title"], "position": k + 1,
                         "author": name, "affiliation": aff, "checked": ""})
        added += 1
        print(f"new: {p['venue']} {p['year']} {p['title'][:70]}  ({HEADERS / (path.stem + '.txt')})")
    with open(CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    unchecked = len({(r["venue"], r["year"], r["title"]) for r in rows if r["checked"] != "yes"})
    print(f"{len(wanted)} papers without affiliations in their list, {added} new; {unchecked} papers in "
          f"{CSV.name} still to check by hand")


if __name__ == "__main__":
    main()
