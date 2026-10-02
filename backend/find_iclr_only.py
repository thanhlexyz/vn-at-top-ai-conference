#!/usr/bin/env python3
"""People in Vietnam with ICLR submissions that were not accepted and no accepted paper at all.

candidates.csv is built from accepted papers, so it cannot show someone whose papers were all
rejected. This script reads the full ICLR submission lists on OpenReview instead:

1. every ICLR main-track submission 2020-now with its outcome and author profile IDs;
2. authors with at least one ICLR paper not accepted and none accepted;
3. minus everyone with an accepted NeurIPS (2021-now) or ICML (2023-now) paper on OpenReview,
   matched by profile ID;
4. their OpenReview profiles, kept if the profile's *current* post (no end year) is in Vietnam;
5. minus the roster, then checked by name against the accepted lists the site uses
   (work/accepted.jsonl.gz, which covers CVPR, ACL, NeurIPS 2020 and ICML before 2023):
   a name match at the same institution removes the person, any other name match is only flagged.

"In Vietnam" means the profile's current post, not the affiliation at submission time: OpenReview
does not keep an affiliation per paper. This differs from candidates.csv, which uses the
affiliation printed on each accepted paper.

Downloads are cached under raw/openreview/ (iclr-YYYY.json.gz, accepted-<venue>-YYYY.json.gz,
profiles.json.gz); --refresh downloads again. Writes iclr_only.csv. Needs OPENREVIEW_USERNAME and
OPENREVIEW_PASSWORD.
"""
import argparse
import collections
import gzip
import json
import os
import re
import sys
import time

from common import (ACCEPTED, BACKEND, LAST_YEAR, OPENREVIEW_RAW, YEARS, classify_status, load_roster, name_key,
                    read_jsonl_gz, same_institution, vn_institution, vn_institutions, write_csv)
from fetch_openreview import profile_summary, split_authors, val, vietnam_post

OUT = BACKEND / "iclr_only.csv"
FIELDS = ["name", "openreview_id", "profile", "position", "institution", "since", "faculty", "not_accepted",
          "rejected", "withdrawn", "desk_rejected", "years", "same_name_accepted", "sample_paper", "sample_url"]
FACULTY = re.compile(r"lecturer|professor|instructor|teacher|faculty|dean|head of|director", re.I)


def retry(call, *args, **kwargs):
    """OpenReview answers 429 when requests come too fast; wait as long as it asks and try again."""
    for attempt in range(8):
        try:
            return call(*args, **kwargs)
        except Exception as e:
            text = str(e)
            if "RateLimit" not in text and "429" not in text:
                raise
            wait = int(m.group(1)) + 2 if (m := re.search(r"try again in (\d+) seconds", text)) else 30
            print(f"  rate limited, waiting {wait} s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError("still rate limited after 8 attempts")


def login():
    import openreview

    user, pw = os.environ["OPENREVIEW_USERNAME"], os.environ["OPENREVIEW_PASSWORD"]
    v2 = retry(openreview.api.OpenReviewClient, baseurl="https://api2.openreview.net", username=user, password=pw)
    v1 = retry(openreview.Client, baseurl="https://api.openreview.net", username=user, password=pw)
    return v2, v1


def cached(path, refresh, download):
    if path.exists() and not refresh:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    data = download()
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return data


def record(n, status):
    c = n.content
    authors, ids = split_authors(c)
    return {"forum": n.forum, "title": str(val(c.get("title")) or ""), "status": status,
            "authorids": [a for a in ids if isinstance(a, str)], "authors": authors}


def decision(n):
    for r in (n.details or {}).get("directReplies") or []:
        if r.get("invitation", "").endswith("Decision"):
            return str(r["content"].get("decision") or r["content"].get("recommendation") or "")
    return ""


def iclr_year(v2, v1, year):
    """Every ICLR main-track submission of one year as {forum, title, status, authorids}."""
    if year >= 2024:
        notes = retry(v2.get_all_notes, invitation=f"ICLR.cc/{year}/Conference/-/Submission")
        return [record(n, classify_status(str(val(n.content.get("venue")) or ""),
                                          str(val(n.content.get("venueid")) or ""))) for n in notes]
    rows = []
    for n in retry(v1.get_all_notes, invitation=f"ICLR.cc/{year}/Conference/-/Blind_Submission",
                   details="directReplies"):
        venue = n.content.get("venue") or ""
        rows.append(record(n, classify_status(venue, decision="" if venue else decision(n))))
    for kind, status in (("Withdrawn_Submission", "withdrawn"), ("Desk_Rejected_Submission", "desk_rejected")):
        rows += [record(n, status) for n in retry(v1.get_all_notes, invitation=f"ICLR.cc/{year}/Conference/-/{kind}")]
    return rows


def accepted_ids(v2, v1, venue, year):
    """Profile IDs on accepted main-conference papers of NeurIPS or ICML, read from OpenReview."""
    group = f"{'NeurIPS' if venue == 'neurips' else 'ICML'}.cc/{year}/Conference"
    client = v2 if year >= 2023 else v1
    notes = retry(client.get_all_notes, content={"venueid": group})
    return sorted({a for n in notes for a in (val(n.content.get("authorids")) or []) if str(a).startswith("~")})


def profiles(v2, ids, refresh):
    """Profile summaries by ID, cached; the IDs of merged profiles all point to the same summary."""
    path = OPENREVIEW_RAW / "profiles.json.gz"
    known = {}
    if path.exists() and not refresh:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            known = json.load(f)
    wanted = sorted(set(ids) - set(known))
    for k in range(0, len(wanted), 500):
        batch = wanted[k:k + 500]
        for p in retry(v2.search_profiles, ids=batch):
            s = profile_summary(p)
            for u in s["usernames"]:
                known[u] = s
        for u in batch:
            known.setdefault(u, None)  # deleted or hidden profile
        print(f"  profiles {min(k + 500, len(wanted))}/{len(wanted)}", file=sys.stderr)
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump(known, f, ensure_ascii=False)
    return known


def roster_ids(roster):
    ids = {i for p in roster for i in p["openreview_ids"]}
    for p in roster:
        path = OPENREVIEW_RAW / f"{p['slug']}.json"
        if path.exists():
            ids.update(json.loads(path.read_text(encoding="utf-8")).get("profile_ids", []))
    return ids


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--refresh", action="store_true", help="download the OpenReview lists and profiles again")
    ap.add_argument("--keep-roster", action="store_true", help="do not remove roster people (to test the matching)")
    args = ap.parse_args()
    v2, v1 = login()

    # 1-2: ICLR outcomes per author
    tally = collections.defaultdict(lambda: collections.defaultdict(list))
    missing_ids = collections.Counter()
    by_email = collections.defaultdict(lambda: collections.defaultdict(list))
    for year in YEARS:
        rows = cached(OPENREVIEW_RAW / f"iclr-{year}.json.gz", args.refresh, lambda: iclr_year(v2, v1, year))
        for r in rows:
            ids = [a for a in r["authorids"] if a.startswith("~")]
            # ICLR 2020 lists authors by e-mail, which ordinary accounts cannot turn into a profile; an
            # address at a .vn domain is kept under the author's name and handled after the profiles
            for a, name in zip(r["authorids"], r.get("authors") or []):
                if "@" in a and a.lower().rstrip(">").endswith(".vn"):
                    by_email[a.lower()]["name"] = name
                    by_email[a.lower()][r["status"]].append({**r, "year": year})
            if not ids:
                missing_ids[(year, r["status"])] += 1
            for a in ids:
                tally[a][r["status"]].append({**r, "year": year})
        print(f"ICLR {year}: {len(rows)} submissions", file=sys.stderr)
    only_rejected = {a for a, t in tally.items() if not t["accepted"] and any(t[s] for s in
                                                                            ("rejected", "withdrawn", "desk_rejected"))}
    print(f"{len(only_rejected)} ICLR authors with papers not accepted and none accepted", file=sys.stderr)

    # 3: accepted NeurIPS / ICML by profile ID
    elsewhere = set()
    for venue, first in (("neurips", 2021), ("icml", 2023)):
        for year in range(first, LAST_YEAR + 1):
            elsewhere.update(cached(OPENREVIEW_RAW / f"accepted-{venue}-{year}.json.gz", args.refresh,
                                    lambda: accepted_ids(v2, v1, venue, year)))
    pool = only_rejected - elsewhere
    print(f"{len(pool)} left after removing accepted NeurIPS/ICML authors", file=sys.stderr)

    # 4: current post in Vietnam
    known = profiles(v2, pool, args.refresh)
    people = {}
    for a in sorted(pool):
        s = known.get(a)
        post = vietnam_post(s) if s else None
        if post and post["end"] is None:
            people.setdefault(s["id"], (s, post, set()))[2].add(a)

    # 5: roster, then names against the accepted lists the site uses
    roster = load_roster()
    on_roster = roster_ids(roster) if not args.keep_roster else set()
    # a roster name only removes someone at the same institution: common names are shared by many people
    roster_names = collections.defaultdict(list)
    for p in roster if not args.keep_roster else []:
        for n in [p["name"], *p["variants"]]:
            roster_names[name_key(n)].append(p)
    accepted_names = collections.defaultdict(list)
    for p in read_jsonl_gz(ACCEPTED):
        for au in p["authors"]:
            accepted_names[name_key(au["name"])].append((au.get("affiliation") or "", p))

    out, removed_by_name = [], 0
    for pid, (s, post, ids) in people.items():
        names = {name_key(n) for n in s["names"] if n}
        home = vn_institution(post["institution"]) or (post["institution"], post["institution"], True)
        person = {"institution": home[0], "institution_short": home[1]}
        if set(s["usernames"]) & on_roster or any(same_institution(post["institution"], p)
                                                  for n in names for p in roster_names.get(n, [])):
            continue
        hits = [(aff, p) for n in names for aff, p in accepted_names.get(n, [])]
        if any(aff and same_institution(aff, person) for aff, p in hits):
            removed_by_name += 1
            continue
        flag = "; ".join(sorted({f"{p['venue'].upper()} {p['year']}" + (f" ({vn_institution(aff)[1]})" if vn_institutions(aff)
                                 else " (no affiliation)" if not aff else " (abroad)") for aff, p in hits}))
        papers = {r["forum"]: r for a in ids for st in ("rejected", "withdrawn", "desk_rejected") for r in tally[a][st]}
        by = collections.Counter(r["status"] for r in papers.values())
        latest = max(papers.values(), key=lambda r: (r["year"], r["title"]))
        out.append({
            "name": s["names"][0] if s["names"] else pid, "openreview_id": pid,
            "profile": f"https://openreview.net/profile?id={pid}", "position": post["position"],
            "institution": post["institution"], "since": post["start"] or "",
            "faculty": "yes" if FACULTY.search(post["position"] or "") else "",
            "not_accepted": len(papers), "rejected": by["rejected"], "withdrawn": by["withdrawn"],
            "desk_rejected": by["desk_rejected"], "years": ", ".join(str(y) for y in sorted({r["year"] for r in papers.values()})),
            "same_name_accepted": flag, "sample_paper": f"{latest['title']} (ICLR {latest['year']})",
            "sample_url": f"https://openreview.net/forum?id={latest['forum']}"})
    # authors known only by a .vn e-mail address (ICLR 2020): matched by name to the people above,
    # otherwise listed with the e-mail domain as the only hint of where they are
    by_name = {name_key(n): row for row in out for n in known[row["openreview_id"]]["names"] if n}
    for email, t in by_email.items():
        if t["accepted"] or not any(t[st] for st in ("rejected", "withdrawn", "desk_rejected")):
            continue
        key, domain = name_key(t["name"]), email.split("@")[1]
        papers = {r["forum"]: r for st in ("rejected", "withdrawn", "desk_rejected") for r in t[st]}
        if key in by_name:
            row = by_name[key]
            row["not_accepted"] += len(papers)
            for r in papers.values():
                row[r["status"]] += 1
            row["years"] = ", ".join(sorted(set(row["years"].split(", ")) | {str(r["year"]) for r in papers.values()}))
            continue
        hits = accepted_names.get(key, [])
        if hits or roster_names.get(key):
            continue  # with no profile to tell namesakes apart, any accepted paper under the name removes them
        by = collections.Counter(r["status"] for r in papers.values())
        latest = max(papers.values(), key=lambda r: (r["year"], r["title"]))
        out.append({
            "name": t["name"], "openreview_id": "", "profile": "", "position": "",
            "institution": f"e-mail at {domain}", "since": "", "faculty": "",
            "not_accepted": len(papers), "rejected": by["rejected"], "withdrawn": by["withdrawn"],
            "desk_rejected": by["desk_rejected"], "years": ", ".join(sorted({str(r["year"]) for r in papers.values()})),
            "same_name_accepted": "; ".join(sorted({f"{p['venue'].upper()} {p['year']}" for _, p in hits})),
            "sample_paper": f"{latest['title']} (ICLR {latest['year']})",
            "sample_url": f"https://openreview.net/forum?id={latest['forum']}"})
    out.sort(key=lambda r: (r["faculty"] != "yes", -r["not_accepted"], r["name"]))
    write_csv(OUT, FIELDS, out)
    print(f"{removed_by_name} removed by a name match at the same institution in the accepted lists", file=sys.stderr)
    if missing_ids:
        print("ICLR submissions without author profile IDs (not counted): "
              + ", ".join(f"{y} {s} {n}" for (y, s), n in sorted(missing_ids.items())), file=sys.stderr)
    print(f"{len(out)} people ({sum(r['faculty'] == 'yes' for r in out)} lecturers or professors) -> {OUT}")


if __name__ == "__main__":
    main()
