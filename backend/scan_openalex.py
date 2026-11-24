#!/usr/bin/env python3
"""Leads for AAAI and IJCAI papers with an author at an institution in Vietnam, from OpenAlex.

ojs.aaai.org answers scripts with a bot check, so the AAAI PDFs that fetch_affiliations.py --scan reads cannot be
downloaded. OpenAlex keeps the affiliation of each author as printed on the paper (raw_affiliation_strings) and the
country of the matched institution. This script asks it for every AAAI and IJCAI paper (2020 to now) with an author
in Vietnam and writes work/openalex_vn.csv: one row per such author, with the track the paper is in (from the lists
the site uses), the printed affiliation and whether the name is on the roster. These are leads, not facts: a row
is checked against the person's OpenReview profile (current post, a student is not a candidate) and, where the PDF
can be had, against its title page. Against the 23 AAAI papers already counted for listed professors it found all 23.

    python3 scan_openalex.py

An API key is optional (OPENALEX_API_KEY in the environment; never printed): without one the daily budget is shared
and paging past the first page uses page= up to 10,000 results, which is enough for a year at a time.
"""
import csv
import gzip
import json
import os
import time
import urllib.parse
import urllib.request

from common import BACKEND, WORK, YEARS, load_roster, name_key, norm_title

SOURCES = {"aaai": "S4210191458", "ijcai": "S4306419999"}   # OpenAlex sources: AAAI and IJCAI proceedings
OUT = WORK / "openalex_vn.csv"
FIELDS = ["venue", "year", "title", "track", "author", "openalex_author", "printed_affiliation", "institutions",
          "on_roster", "roster_approved"]


def get(params):
    key = os.environ.get("OPENALEX_API_KEY")
    if key:
        params = {**params, "api_key": key}
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    for _ in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "vn-ai-ranking"}), timeout=90) as r:
                return json.load(r)
        except Exception as e:
            print("retry:", str(e).replace(key or "\0", "***")[:100])
            time.sleep(8)
    raise SystemExit("OpenAlex did not answer")


def main():
    tracks = {}
    for line in gzip.open(WORK / "accepted.jsonl.gz", "rt"):
        p = json.loads(line)
        tracks[(p["venue"], norm_title(p["title"]))] = p["track"]
    roster = {}
    for p in load_roster():
        for n in [p["name"], *p["variants"], p.get("name_vi", "")]:
            if n:
                roster[name_key(n)] = p
    rows = []
    for venue, source in SOURCES.items():
        for year in range(min(YEARS), max(YEARS) + 1):
            page = 1
            while True:
                d = get({"filter": f"primary_location.source.id:{source},publication_year:{year},authorships.countries:VN",
                         "per-page": 100, "page": page, "select": "title,publication_year,authorships"})
                for w in d["results"]:
                    for a in w["authorships"]:
                        if "VN" not in (a.get("countries") or []):
                            continue
                        who = roster.get(name_key(a["author"]["display_name"]))
                        rows.append({"venue": venue, "year": year, "title": w["title"],
                                     "track": tracks.get((venue, norm_title(w["title"] or "")), "not in the site's list"),
                                     "author": a["author"]["display_name"],
                                     "openalex_author": (a["author"].get("id") or "").split("/")[-1],
                                     "printed_affiliation": " | ".join(a.get("raw_affiliation_strings") or [])[:200],
                                     "institutions": "; ".join(i["display_name"] for i in a.get("institutions", [])
                                                               if i.get("country_code") == "VN"),
                                     "on_roster": who["slug"] if who else "", "roster_approved": who["approved"] if who else ""})
                if len(d["results"]) < 100:
                    break
                page += 1
                time.sleep(0.3)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    main_rows = [r for r in rows if r["track"] == "main"]
    new = {r["author"] for r in main_rows if r["roster_approved"] != "yes"}
    print(f"{len(rows)} authors in Vietnam on {len({(r['venue'], r['title']) for r in rows})} papers -> {OUT}")
    print(f"main track: {len(main_rows)} rows, {len(new)} names not (approved) on the roster")


if __name__ == "__main__":
    main()
