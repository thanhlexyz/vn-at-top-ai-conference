"""Checks the affiliation of every counted official paper against the paper itself.

The accepted-paper lists of the virtual sites (ICLR, NeurIPS, ICML, CVPR, ICCV, ECCV) take each author's affiliation
from their profile, which can name every position they hold: a professor who also works at a company or a research
institute can appear at the university on a paper that only prints the company. This downloads the PDF of each
counted official paper whose affiliation came from such a list (cached in raw/pdf/), reads its first page, footnotes
included, and checks that the professor's institution is printed there by name, short name or e-mail domain.
Papers where it is not are written to work/affiliation_check.csv; each is read by hand, and a correction goes into
affiliation_fixes.csv.

    OPENREVIEW_USERNAME=... OPENREVIEW_PASSWORD=... python3 verify_affiliations.py
"""
import csv
import gzip
import json
import os
import re
import subprocess
import time
import urllib.request

from common import BACKEND, FRONTEND, norm_title, read_csv, strip_accents, vn_institutions

PDF_DIR = BACKEND / "raw" / "pdf"
OUT = BACKEND / "work" / "affiliation_check.csv"
# e-mail domains, which a title page often prints when the affiliation itself is abbreviated
DOMAINS = {"HUST": ["hust.edu.vn"], "VinUni": ["vinuni.edu.vn"], "PTIT": ["ptit.edu.vn"], "HCMUS": ["hcmus.edu.vn"],
           "VNU-UET": ["vnu.edu.vn"], "RMIT": ["rmit.edu.vn"], "UEH": ["ueh.edu.vn"], "VAST": ["math.ac.vn", "vast.vn"],
           "HCMIU": ["hcmiu.edu.vn"], "NEU": ["neu.edu.vn"], "Phenikaa": ["phenikaa-uni.edu.vn"], "CTU": ["ctu.edu.vn"],
           "UIT": ["uit.edu.vn"], "FPTU": ["fpt.edu.vn"], "UDN": ["udn.vn"], "HCMUT": ["hcmut.edu.vn"],
           "HaUI": ["haui.edu.vn"]}


def first_page(path):
    return subprocess.run(["pdftotext", "-l", "1", str(path), "-"], capture_output=True, text=True).stdout


def cvf_pdf(venue, year, title):
    """The CVF open-access PDF of a CVPR or ICCV paper, found in the cached list of that year."""
    for f in sorted((BACKEND / "raw" / "cvf").glob(f"{venue}-{year}*")):
        page = gzip.open(f, "rt").read()
        key = norm_title(title)[:30]
        for href in re.findall(r'href="(/content/[^"]+?_paper\.pdf)"', page):
            if norm_title(href.split("/")[-1].replace("_", " "))[:30].startswith(key[:20]) or key[:20] in norm_title(href):
                return "https://openaccess.thecvf.com" + href
    return None


def ecva_pdf(title):
    page = gzip.open(BACKEND / "raw" / "ecva" / "papers.html.gz", "rt").read()
    i = page.find(title[:40])
    if i < 0:
        return None
    m = re.search(r"href=['\"](papers/eccv_\d+/papers_ECCV/papers/\d+\.pdf)['\"]", page[i:i + 3000])
    return "https://www.ecva.net/" + m.group(1) if m else None


PMLR_VOLUME = {2020: "v119", 2021: "v139", 2022: "v162", 2023: "v202", 2024: "v235", 2025: "v267"}


def pmlr_pdf(year, title, url=""):
    """The PMLR PDF of an ICML paper: from its PMLR page, or found by title in the volume's index."""
    m = re.search(r"proceedings\.mlr\.press/(v\d+)/([\w-]+)\.html", url or "")
    if m:
        return f"https://proceedings.mlr.press/{m.group(1)}/{m.group(2)}/{m.group(2)}.pdf"
    vol = PMLR_VOLUME.get(year)
    if not vol:
        return None
    index = urllib.request.urlopen(urllib.request.Request(f"https://proceedings.mlr.press/{vol}/",
                                                          headers={"User-Agent": "Mozilla/5.0"}), timeout=120).read().decode()
    key = norm_title(title)
    for block in index.split('<div class="paper">')[1:]:
        t = re.search(r'<p class="title">(.*?)</p>', block, re.S)
        if t and norm_title(re.sub("<[^>]+>", "", t.group(1))) == key:
            pdf = re.search(r'href="([^"]+\.pdf)"', block)
            return pdf.group(1) if pdf else None
    return None


def neurips_pdf(url):
    """proceedings.neurips.cc: the paper's PDF next to its abstract page."""
    if "proceedings.neurips.cc" not in (url or ""):
        return None
    return url.replace("/hash/", "/file/").replace("-Abstract-Conference.html", "-Paper-Conference.pdf") \
              .replace("-Abstract.html", "-Paper.pdf")


def fetch(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    path.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    time.sleep(1)


def printed(text, person):
    """True if the page names the person's institution, by name, short name or e-mail domain."""
    flat = " ".join(strip_accents(text).split())
    short = person["institution_short"]
    found = {s for _, s, _ in vn_institutions(flat)}
    if short in found or person["institution"].lower() in flat.lower():
        return True
    if re.search(rf"(?<![\w-]){re.escape(short)}(?![\w-])", flat):
        return True
    if short in ("HCMUS", "VNU-HUS") and re.search(r"\buniversity of science\b", flat, re.I):
        return True
    return any(d in flat.lower() for d in DOMAINS.get(short, []))


def main():
    import openreview
    client = openreview.api.OpenReviewClient(baseurl="https://api2.openreview.net",
                                             username=os.environ["OPENREVIEW_USERNAME"],
                                             password=os.environ["OPENREVIEW_PASSWORD"])
    client_v1 = openreview.Client(baseurl="https://api.openreview.net", username=os.environ["OPENREVIEW_USERNAME"],
                                  password=os.environ["OPENREVIEW_PASSWORD"])
    papers = {}
    for line in gzip.open(BACKEND / "work" / "accepted.jsonl.gz", "rt"):
        p = json.loads(line)
        papers[(p["venue"], p["year"], norm_title(p["title"]))] = p
    checked = {(r["venue"], int(r["year"]), norm_title(r["title"]))
               for f in ("affiliations.csv", "affiliation_fixes.csv") for r in read_csv(BACKEND / f)}
    people = {p["slug"]: p for p in json.load(open(FRONTEND / "data" / "professors.json"))}
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    todo = {}
    for p in people.values():
        for e in p["accepted_papers"]:
            k = (e["venue"], e["year"], norm_title(e["title"]))
            if not e.get("unofficial") and k in papers and k not in checked:
                todo.setdefault(k, []).append(p["slug"])
    for k, who in sorted(todo.items()):
        p = papers[k]
        path = PDF_DIR / f"check-{p['venue']}-{p['year']}-{norm_title(p['title'])[:40]}.pdf"
        status = ""
        if not path.exists():
            try:
                if p["venue"] in ("iclr", "neurips", "icml"):
                    data = None
                    for cl in (client, client_v1):   # notes before 2023 are on the older API
                        try:
                            data = cl.get_attachment(id=p["forum"], field_name="pdf") if p.get("forum") else None
                        except Exception:
                            data = None
                        if data:
                            break
                    if data:
                        path.write_bytes(data)
                        time.sleep(1)
                    else:
                        url = neurips_pdf(p["url"]) or (pmlr_pdf(p["year"], p["title"], p["url"]) if p["venue"] == "icml" else None)
                        if not url and p["venue"] == "iclr":   # an ICLR paper listed without its forum: find it by title
                            notes = client_v1.get_notes(content={"title": p["title"]}, limit=5)
                            url = next((f"https://openreview.net/pdf?id={n.forum}" for n in notes), None)
                            if url:
                                path.write_bytes(client_v1.get_attachment(id=url.split("=")[-1], field_name="pdf"))
                                url = None
                        fetch(url, path) if url else None
                elif p["venue"] in ("cvpr", "iccv"):
                    url = cvf_pdf(p["venue"], p["year"], p["title"])
                    fetch(url, path) if url else None
                elif p["venue"] == "eccv":
                    url = ecva_pdf(p["title"])
                    fetch(url, path) if url else None
                elif p.get("pdf"):   # AAAI and IJCAI lists carry the PDF link
                    fetch(p["pdf"], path)
            except Exception as exc:
                status = f"no PDF ({str(exc)[:60]})"
        if not path.exists():
            status = status or "no PDF"
        text = first_page(path) if path.exists() else ""
        for slug in who:
            person = people[slug]
            ok = printed(text, person) if text else None
            rows.append({"venue": p["venue"], "year": p["year"], "title": p["title"], "professor": slug,
                         "institution": person["institution_short"],
                         "printed": {True: "yes", False: "NO", None: ""}[ok], "status": status, "pdf": path.name})
            print(f"{p['venue']} {p['year']} {slug:22} {rows[-1]['printed'] or status:4} {p['title'][:60]}")
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{sum(r['printed'] == 'NO' for r in rows)} not printed, {sum(not r['printed'] for r in rows)} without a PDF; "
          f"see {OUT}")


if __name__ == "__main__":
    main()
