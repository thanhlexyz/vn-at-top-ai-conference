#!/usr/bin/env python3
"""ICLR submissions still under review that are probably by tracked professors: LOCAL USE ONLY.

Submissions under review are anonymous. A submission whose title matches a public preprint (OpenAlex, an author in
Vietnam) that lists a tracked professor is probably theirs; this is how clareLab's ICLR 2027 posters tie scores to
institutions. Naming people during double-blind review is not for the public site, so everything here stays local:
the output is work/under_review.json and frontend/data/under_review.json, both git-ignored, and the Papers page
shows the rows only in a local build (site param `local`; publish.toml turns it off). Decided by the maintainer on
2026-11-25.

For each match it keeps the submission's forum id, the preprint, the professors on it, the reviewers' scores
(fetch_reviews.reviews_of) and Open Text Detector's AI-text share (fetch_opentextdetector.lookup).

    python3 match_under_review.py            # needs the OpenReview variables
"""
import json
import time
import urllib.parse
import urllib.request

import gzip

from common import FRONTEND, OPENREVIEW_RAW, WORK, LAST_YEAR, load_roster, norm_title, token_key

OUT = WORK / "under_review.json"
PAGE = FRONTEND / "data" / "under_review.json"
SINCE = f"{LAST_YEAR - 1}-05-01"   # preprints posted in the months before the ICLR deadline and after


def openalex(params):
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    for wait in (5, 20, 60, 0):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "vn-ai-ranking"}), timeout=90) as r:
                return json.load(r)
        except Exception as e:
            print("retry:", str(e)[:80])
            if not wait:
                raise
            time.sleep(wait)


def preprints():
    """Preprints since SINCE with an author at an institution in Vietnam: title and author names."""
    out, page = [], 1
    while True:
        d = openalex({"filter": f"authorships.countries:VN,from_publication_date:{SINCE},type:preprint",
                      "per-page": 200, "page": page, "select": "id,title,publication_date,authorships,primary_location"})
        for w in d["results"]:
            out.append({"id": w["id"].rsplit("/", 1)[-1], "title": w["title"] or "", "date": w["publication_date"],
                        "url": ((w.get("primary_location") or {}).get("landing_page_url") or ""),
                        "authors": [a["author"]["display_name"] for a in w["authorships"]]})
        if len(d["results"]) < 200:
            return out
        page += 1
        time.sleep(0.3)


def main():
    year = LAST_YEAR
    subs = json.load(gzip.open(OPENREVIEW_RAW / f"iclr-{year}.json.gz"))
    under = {norm_title(s["title"]): s for s in subs if s["status"] == "unknown" and s.get("title")}
    roster = [p for p in load_roster() if p["approved"] == "yes"]
    names = {}
    for p in roster:
        for n in [p["name"], *p["variants"], p.get("name_vi") or ""]:
            if n:
                names[token_key(n)] = p
    found = preprints()
    print(f"{len(found)} preprints with an author in Vietnam since {SINCE}; {len(under)} ICLR {year} submissions under review")
    matches = {}
    for w in found:
        s = under.get(norm_title(w["title"]))
        if not s:
            continue
        people = {names[token_key(a)]["slug"]: names[token_key(a)]["name"] for a in w["authors"] if token_key(a) in names}
        if not people:
            continue
        m = matches.setdefault(s["forum"], {"forum": s["forum"], "title": s["title"], "preprint": w["url"] or f"https://openalex.org/{w['id']}",
                                            "posted": w["date"], "authors": w["authors"], "professors": {}})
        m["professors"].update(people)
    print(f"{len(matches)} submissions under review match a preprint with a tracked professor")

    from fetch_openreview import login   # needs the OpenReview variables
    from fetch_reviews import reviews_of
    from fetch_opentextdetector import lookup, COLLECTIONS, MODE, MIN_SENTENCES
    v2, _ = login()
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    for forum, m in matches.items():
        m["reviews"] = reviews_of(v2, forum)
        item = lookup(COLLECTIONS[("iclr", year)], forum)
        counts = ((item or {}).get("flags") or {}).get(MODE)
        m["ai"] = round(100 * counts[0] / counts[1]) if counts and counts[1] >= MIN_SENTENCES else None
        m["professors"] = [{"slug": s, "name": n} for s, n in sorted(m["professors"].items())]
        print(f"  {forum}: {m['title'][:60]} | {[p['name'] for p in m['professors']]} | {m['reviews']} | AI {m['ai']}")
        time.sleep(0.5)
    rows = sorted(matches.values(), key=lambda m: (m["professors"][0]["name"], m["title"]))
    data = {"year": year, "fetched": time.strftime("%Y-%m-%d"), "papers": rows}
    for path in (OUT, PAGE):
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"-> {OUT} and {PAGE} (both git-ignored)")


if __name__ == "__main__":
    main()
