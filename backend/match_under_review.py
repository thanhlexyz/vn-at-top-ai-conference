#!/usr/bin/env python3
"""ICLR submissions still under review that are probably by tracked professors: LOCAL USE ONLY.

Submissions under review are anonymous. A submission whose title matches a public preprint (OpenAlex, an author in
Vietnam) that lists a tracked professor is probably theirs; this is how clareLab's ICLR 2027 posters tie scores to
institutions. Naming people during double-blind review is not for the public site, so everything here stays local:
the output is work/under_review.json and frontend/data/under_review.json, both git-ignored, and the Papers page
shows them; the published site redacts the professors' names and the preprint (a title can still be searched, which
the maintainer accepted on 2026-11-25). Decided by the maintainer on
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

from common import FRONTEND, OPENREVIEW_RAW, WORK, LAST_YEAR, load_roster, norm_title, post_class, token_key, vn_institutions

OUT = WORK / "under_review.json"
PAGE = FRONTEND / "data" / "under_review.json"
SINCE = f"{LAST_YEAR - 1}-05-01"   # preprints posted in the months before the ICLR deadline and after
ACCEPT_SCORE = 2.6   # a mean review score above this is a potential accept (the maintainer's threshold)


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
                        "authors": [a["author"]["display_name"] for a in w["authorships"]],
                        # authors listed at an institution in Vietnam, with that institution
                        "in_vn": {a["author"]["display_name"]: "; ".join(i["display_name"] for i in a.get("institutions") or []
                                                                        if i.get("country_code") == "VN")
                                  for a in w["authorships"] if "VN" in (a.get("countries") or [])}})
        if len(d["results"]) < 200:
            return out
        page += 1
        time.sleep(0.3)


def judge(v2, name, institution):
    """The OpenReview profile of an author in Vietnam who is not on the roster, and what it says about them:
    'candidate' (lecturer or higher at a university in Vietnam today), 'researcher', 'student', 'abroad' (no current
    post in Vietnam) or 'no profile'. Profiles are found by name, so a namesake is possible: the one whose post in
    Vietnam names the institution on the preprint is preferred."""
    from fetch_openreview import profile_summary, vietnam_post
    try:
        found = v2.search_profiles(fullname=name)
    except Exception:
        found = []
    best = None
    for p in found:
        s = profile_summary(p)
        if token_key(name) not in {token_key(x) for x in s["names"]}:
            continue
        post = vietnam_post(s)
        current = post if post and post["end"] is None else None
        kind = post_class(current["position"]) if current else ""
        uni = bool(current) and any(u for _, _, u in vn_institutions(current["institution"]))
        verdict = ("candidate" if kind == "staff" and uni else "researcher" if kind in ("researcher", "staff")
                   else "student" if kind == "student" else "abroad" if not current else "other")
        same = bool(current) and bool({x for _, x, _ in vn_institutions(current["institution"])} & {x for _, x, _ in vn_institutions(institution)})
        rank = (same, verdict == "candidate", bool(current))
        if best is None or rank > best[0]:
            best = (rank, {"id": s["id"], "post": f"{current['position']} at {current['institution']}" if current else
                           "; ".join(f"{h['position']} at {h['institution']}" for h in s["history"][:2]),
                           "verdict": verdict, "same_institution": same})
    time.sleep(0.5)
    return best[1] if best else {"id": "", "post": "", "verdict": "no profile", "same_institution": False}


def main():
    year = LAST_YEAR
    subs = json.load(gzip.open(OPENREVIEW_RAW / f"iclr-{year}.json.gz"))
    under = {norm_title(s["title"]): s for s in subs if s["status"] == "unknown" and s.get("title")}
    roster = [p for p in load_roster() if p["approved"] == "yes"]
    # anyone on the roster, approved or not, has been decided: not suggested again
    decided = {token_key(n) for p in load_roster() for n in [p["name"], *p["variants"], p.get("name_vi") or ""] if n}
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
        # authors in Vietnam who are not on the roster at all: people the maintainer may want to track
        others = {a: inst for a, inst in w["in_vn"].items() if token_key(a) not in names and token_key(a) not in decided}
        if not people and not others:
            continue
        m = matches.setdefault(s["forum"], {"forum": s["forum"], "title": s["title"], "preprint": w["url"] or f"https://openalex.org/{w['id']}",
                                            "posted": w["date"], "authors": w["authors"], "professors": {}, "others": {}})
        m["professors"].update(people)
        m["others"].update(others)
    print(f"{len(matches)} submissions under review match a preprint with an author in Vietnam "
          f"({sum(1 for m in matches.values() if m['professors'])} with a tracked professor)")

    from fetch_openreview import login   # needs the OpenReview variables
    from fetch_reviews import reviews_of, submission_number
    from fetch_opentextdetector import lookup, COLLECTIONS, MODE, MIN_SENTENCES
    v2, _ = login()
    for forum, m in matches.items():
        m["number"] = submission_number(v2, forum)
        m["reviews"] = reviews_of(v2, forum)
        scores = [r[0] for r in m["reviews"]]
        m["mean"] = round(sum(scores) / len(scores), 2) if scores else None
        m["likely"] = None if m["mean"] is None else ("accept" if m["mean"] > ACCEPT_SCORE else "reject")
        item = lookup(COLLECTIONS[("iclr", year)], forum)
        counts = ((item or {}).get("flags") or {}).get(MODE)
        m["ai"] = round(100 * counts[0] / counts[1]) if counts and counts[1] >= MIN_SENTENCES else None
        m["professors"] = [{"slug": s, "name": n} for s, n in sorted(m["professors"].items())]
        m["others"] = [{"name": n, "institution": i} for n, i in sorted(m["others"].items())]
        print(f"  #{m['number']} {m['title'][:50]} | {[p['name'] for p in m['professors']]} + {len(m['others'])} others | "
              f"mean {m['mean']} {m['likely']} | AI {m['ai']}")
        time.sleep(0.5)
    judged = {}
    for m in matches.values():
        for o in m["others"]:
            if o["name"] not in judged:
                judged[o["name"]] = judge(v2, o["name"], o["institution"])
                print(f"    {o['name']} ({o['institution'][:40]}): {judged[o['name']]['verdict']} {judged[o['name']]['id']} {judged[o['name']]['post'][:60]}")
            o["openreview"] = judged[o["name"]]
    rows = sorted((m for m in matches.values() if m["professors"]), key=lambda m: (-(m["mean"] or 0), m["title"]))
    outside = sorted((m for m in matches.values() if not m["professors"]), key=lambda m: m["title"])
    data = {"year": year, "fetched": time.strftime("%Y-%m-%d"), "threshold": ACCEPT_SCORE, "papers": rows, "outside": outside}
    for path in (OUT, PAGE):
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"-> {OUT} and {PAGE} (both git-ignored)")


if __name__ == "__main__":
    main()
