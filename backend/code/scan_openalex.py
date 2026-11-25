#!/usr/bin/env python3
"""Leads for AAAI and IJCAI papers with an author at an institution in Vietnam, from OpenAlex.

ojs.aaai.org answers scripts with a bot check, so the AAAI PDFs that fetch_affiliations.py --scan reads cannot be
downloaded. OpenAlex keeps the affiliation of each author as printed on the paper (raw_affiliation_strings) and the
country of the matched institution. This script asks it for every AAAI and IJCAI paper (2020 to now) with an author
in Vietnam and writes work/openalex_vn.csv: one row per such author, with the track the paper is in (from the lists
the site uses), the printed affiliation and whether the name is on the roster. These are leads, not facts: a row
is checked against the person's OpenReview profile (current post, a student is not a candidate) and, where the PDF
can be had, against its title page. Against the 23 AAAI papers already counted for listed professors it found all 23.

    python3 scan_openalex.py            # leads -> work/openalex_vn.csv
    python3 scan_openalex.py --leads    # also look each name up on OpenReview -> staff_leads.csv (needs the
                                        # OpenReview variables), the table at the top of the Candidates page

staff_leads.csv holds the names (not on the roster yet) whose OpenReview profile shows a current post at a university in
Vietnam of lecturer or higher, or such a post that ended in the last two years. Students are left out: they are never
suggested. The maintainer answers each lead: a roster row with approved yes, or no, takes the name off the list.

An API key is optional (OPENALEX_API_KEY in the environment; never printed): without one the daily budget is shared
and paging past the first page uses page= up to 10,000 results, which is enough for a year at a time.
"""
import argparse
import csv
import datetime
import gzip
import json
import os
import sys
import time
import urllib.parse
import urllib.request

from common import CSV_DIR  # backend/data/
from common import (BACKEND, WORK, YEARS, load_roster, name_key, norm_title, post_class,
                    token_key, vn_institutions, PARENT)

SOURCES = {"aaai": "S4210191458", "ijcai": "S4306419999"}   # OpenAlex sources: AAAI and IJCAI proceedings
OUT = WORK / "openalex_vn.csv"
LEADS = CSV_DIR / "staff_leads.csv"
LEAD_FIELDS = ["name", "openreview_id", "post", "institution_on_paper", "papers", "paper_url", "note", "found"]
FIELDS = ["venue", "year", "title", "track", "url", "author", "openalex_author", "printed_affiliation", "institutions",
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


def shorts(text):
    """The Vietnamese institutions named in a text, with their parent university (UIT is part of VNU-HCM)."""
    found = {short for _, short, _ in vn_institutions(text)}
    return found | {PARENT[x] for x in found if x in PARENT}


SEARCHES = WORK / "openreview_name_search.json"   # name -> profile summaries; OpenReview allows ~126 searches per window


def write_leads(rows, roster):
    """Names on main-track papers whose OpenReview profile shows a lecturer or higher at a university in Vietnam today
    (or until last year). A student is dropped, whatever the paper says. A profile already on the roster (approved or
    not) has been decided; a lead that only shares a name with a roster person is kept, with a note."""
    from find_iclr_only import login
    from fetch_openreview import profile_summary, vietnam_post
    v2, _ = login()
    on_roster = {i for p in roster for i in p["openreview_ids"]}
    roster_names = {token_key(n): p["name"] for p in roster for n in [p["name"], *p["variants"], p.get("name_vi", "")] if n}
    by_name = {}
    for r in rows:
        if r["track"] == "main":
            by_name.setdefault(r["author"], []).append(r)
    cache = json.loads(SEARCHES.read_text(encoding="utf-8")) if SEARCHES.exists() else {}
    this_year = datetime.date.today().year
    leads = []
    for name, papers in sorted(by_name.items()):
        if name not in cache:
            # the client waits out a rate limit by itself (up to ~25 minutes); the cache keeps what was found
            cache[name] = [profile_summary(p) for p in v2.search_profiles(fullname=name)]
            SEARCHES.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
            time.sleep(0.5)
        best = None
        for s in cache[name]:
            if s["id"] in on_roster or token_key(name) not in {token_key(x) for x in s["names"]}:
                continue
            post = vietnam_post(s)
            if not post or post_class(post["position"]) != "staff":
                continue
            if not any(uni for _, _, uni in vn_institutions(post["institution"])) and not post["domain"].endswith(".edu.vn"):
                continue   # a director or head at a company is not a candidate
            if post["end"] is not None and post["end"] < this_year - 1:
                continue
            if best is None or (post["end"] is None, post["start"] or 0) > (best[1]["end"] is None, best[1]["start"] or 0):
                best = (s, post)
        if not best:
            continue
        s, post = best
        paper_inst = papers[0]["institutions"] or papers[0]["printed_affiliation"]
        note = []
        if post["end"] is not None:
            note.append(f"the post ended in {post['end']}")
        if shorts(paper_inst).isdisjoint(shorts(post["institution"])):
            note.append("the paper and OpenReview name different institutions: check it is the same person")
        if token_key(name) in roster_names:
            note.append(f"same name as {roster_names[token_key(name)]} on the roster")
        leads.append({"name": name, "openreview_id": s["id"], "post": f"{post['position']} at {post['institution']}",
                      "institution_on_paper": paper_inst[:80],
                      "papers": "; ".join(f"{r['venue'].upper()} {r['year']}: {r['title']}" for r in papers),
                      "paper_url": papers[0].get("url", ""), "note": "; ".join(note),
                      "found": datetime.date.today().isoformat()})
    with open(LEADS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LEAD_FIELDS)
        w.writeheader()
        w.writerows(leads)
    print(f"{len(by_name)} names on main-track papers: {len(leads)} possible staff -> {LEADS}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--leads", action="store_true", help="look the names up on OpenReview and write staff_leads.csv")
    args = ap.parse_args()
    tracks = {}
    for line in gzip.open(WORK / "accepted.jsonl.gz", "rt"):
        p = json.loads(line)
        tracks[(p["venue"], norm_title(p["title"]))] = (p["track"], p["url"])
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
                                     "track": tracks.get((venue, norm_title(w["title"] or "")), ("not in the site's list", ""))[0],
                                     "url": tracks.get((venue, norm_title(w["title"] or "")), ("", ""))[1],
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
    if args.leads:
        write_leads(rows, load_roster())


if __name__ == "__main__":
    main()
