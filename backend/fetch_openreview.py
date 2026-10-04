#!/usr/bin/env python3
"""Fetch every public OpenReview submission of the approved people in roster.csv.

This is the only step that needs a login, and the only source of rejected and withdrawn papers.

Setup (once):
    pip install openreview-py
    export OPENREVIEW_USERNAME=you@example.com
    export OPENREVIEW_PASSWORD=...        # or leave it out and type it when asked

Usage:
    python fetch_openreview.py                     # everyone with approved = yes and an OpenReview ID
    python fetch_openreview.py --only tuan-dam     # just these slugs
    python fetch_openreview.py --search "Khoa D Doan" "Doan Khoa"   # find the ~ID of a person
    python fetch_openreview.py --candidates 60     # look up the first 60 people of candidates.csv

People are queried by the profile IDs in roster.csv only, never by name, because a name search mixes
different people. Results go to raw/openreview/<slug>.json with the labels exactly as OpenReview gives
them; build_site_data.py turns those into accepted / rejected / withdrawn, so a change in the rules
never needs a new download.

What OpenReview does not show cannot be fetched: NeurIPS rejections unless the authors opted in, all
ICML, CVPR, ICCV, ECCV, ACL and EMNLP rejections, and withdrawn papers that were removed or left anonymous.
"""
import argparse
import datetime
import getpass
import json
import os
import re
import sys
import time

from common import (CANDIDATES, OPENREVIEW_RAW, classify_status, load_roster, name_key, openreview_venue, read_csv,
                    vn_institution, write_json)


def login():
    import openreview  # imported here so that the rest of the pipeline works without the package

    user, pw = os.environ.get("OPENREVIEW_USERNAME"), os.environ.get("OPENREVIEW_PASSWORD")
    for name, v in (("OPENREVIEW_USERNAME", user), ("OPENREVIEW_PASSWORD", pw)):
        if not v:
            print(f"note: {name} is not set in this process's environment (did you `export` it in this shell?)",
                  file=sys.stderr)
    user = user or input("OpenReview username: ")
    pw = pw or getpass.getpass("OpenReview password: ")
    v2 = with_retry(openreview.api.OpenReviewClient, baseurl="https://api2.openreview.net", username=user, password=pw)
    try:
        v1 = with_retry(openreview.Client, baseurl="https://api.openreview.net", username=user, password=pw)
    except Exception as e:  # API v1 holds the conferences up to 2023
        print(f"warning: API v1 login failed ({e}); submissions before 2024 will be missing", file=sys.stderr)
        v1 = None
    return v2, v1


def with_retry(call, *args, **kwargs):
    """OpenReview allows three logins a minute and answers 429 above that; wait as long as it asks."""
    for _ in range(6):
        try:
            return call(*args, **kwargs)
        except Exception as e:
            m = re.search(r"try again in (\d+) seconds", str(e))
            if "RateLimit" not in str(e):
                raise
            wait = int(m.group(1)) + 2 if m else 30
            print(f"  OpenReview rate limit, waiting {wait} s", file=sys.stderr)
            time.sleep(wait)
    return call(*args, **kwargs)


def val(x):
    """API v2 wraps fields as {'value': ...}; API v1 uses plain values."""
    return x.get("value") if isinstance(x, dict) else x


def profile_summary(p):
    """The parts of a profile the pipeline uses: its usernames and the employment history."""
    c = p.content
    history = [{"position": h.get("position") or "", "institution": (h.get("institution") or {}).get("name") or "",
                "domain": (h.get("institution") or {}).get("domain") or "", "start": h.get("start"),
                "end": h.get("end")} for h in c.get("history") or []]
    names = [n.get("fullname") or " ".join(x for x in (n.get("first"), n.get("middle"), n.get("last")) if x)
             for n in c.get("names", [])]
    usernames = sorted({n["username"] for n in c.get("names", []) if n.get("username")} | {p.id})
    return {"id": p.id, "names": names, "usernames": usernames, "history": history,
            "homepage": c.get("homepage") or "", "dblp": c.get("dblp") or ""}


def vietnam_post(summary):
    """The most recent entry of a profile's history at a Vietnamese institution, or None."""
    posts = [h for h in summary["history"] if vn_institution(h["institution"]) or h["domain"].endswith(".vn")]
    return max(posts, key=lambda h: (h["end"] is None, h["end"] or 0, h["start"] or 0)) if posts else None


def split_authors(content):
    """Author names and profile IDs of a note. Older notes keep them in two parallel lists; since 2026 some
    notes give one object per author ({"username", "fullname", "institutions"}) and leave authorids empty."""
    authors = val(content.get("authors")) or []
    if not isinstance(authors, list):
        authors = [str(authors)]
    ids = val(content.get("authorids")) or []
    if any(isinstance(a, dict) for a in authors):
        ids = [a.get("username") or "" for a in authors if isinstance(a, dict)] if not ids else ids
        authors = [a.get("fullname") or a.get("username") or "" if isinstance(a, dict) else str(a) for a in authors]
    return authors, ids


def note_record(n):
    c = n.content
    invitations = getattr(n, "invitations", None) or [getattr(n, "invitation", "") or ""]
    authors, authorids = split_authors(c)
    return {"id": n.id, "forum": n.forum, "invitations": invitations,
            "venue": str(val(c.get("venue")) or ""), "venueid": str(val(c.get("venueid")) or ""),
            "title": str(val(c.get("title")) or ""), "authors": authors,
            "authorids": authorids, "primary_area": str(val(c.get("primary_area")) or ""),
            "keywords": val(c.get("keywords")) or [], "cdate": getattr(n, "cdate", None), "decision": ""}


def decision_of(v1, forum):
    """ICLR 2020-2021 keep the outcome in a Decision reply instead of a venue label."""
    for r in v1.get_all_notes(forum=forum):
        if (getattr(r, "invitation", "") or "").endswith("Decision"):
            return str(r.content.get("decision") or r.content.get("recommendation") or "")
    return ""


def fetch_person(v2, v1, person):
    profiles, usernames = [], set()
    for pid in person["openreview_ids"]:
        try:
            s = profile_summary(v2.get_profile(pid))
        except Exception as e:
            print(f"  warning: profile {pid} could not be read ({e})", file=sys.stderr)
            usernames.add(pid)
            continue
        if s["usernames"] not in [p["usernames"] for p in profiles]:
            profiles.append(s)
        usernames.update(s["usernames"])

    notes, seen = [], set()
    for username in sorted(usernames):
        batches = [v2.get_all_notes(content={"authorids": username})]
        if v1 is not None:
            batches.append(v1.get_all_notes(content={"authorids": username}))
        for batch in batches:
            for n in batch:
                if n.id != n.forum or n.id in seen:
                    continue  # replies and duplicates
                rec = note_record(n)
                if openreview_venue(rec["invitations"], rec["venueid"]) is None:
                    continue  # not one of the eleven venues
                seen.add(n.id)
                notes.append(rec)

    for rec in notes:
        _, _, track = openreview_venue(rec["invitations"], rec["venueid"])
        unknown = classify_status(rec["venue"], rec["venueid"], rec["invitations"]) == "unknown"
        if v1 is not None and track == "main" and unknown:
            try:
                rec["decision"] = decision_of(v1, rec["forum"])
            except Exception as e:
                print(f"  warning: no decision read for {rec['forum']} ({e})", file=sys.stderr)
    return {"slug": person["slug"], "name": person["name"],
            "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "queried_ids": person["openreview_ids"], "profile_ids": sorted(usernames),
            "profiles": profiles, "notes": notes}


def search(v2, names):
    for name in names:
        print(f"\n== profiles named '{name}'")
        for p in v2.search_profiles(fullname=name):
            s = profile_summary(p)
            jobs = "; ".join(f"{h['position'] or '?'} at {h['institution'] or '?'} ({h['start'] or '?'}-{h['end'] or 'now'})"
                             for h in s["history"][:3])
            print(f"  {p.id:30s} {jobs}")


def lookup_candidates(v2, limit):
    """Find the OpenReview profiles of the first `limit` people at a university in candidates.csv that show a post in
    Vietnam."""
    path = OPENREVIEW_RAW / "_candidates.json"
    found = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    # company staff are not tracked, so only people at a university are looked up
    for row in [r for r in read_csv(CANDIDATES) if r.get("at_university") == "yes"][:limit]:
        names = [row["display_name"], *[v.strip() for v in row["name_variants"].split(";") if v.strip()]]
        key = name_key(names[0])
        if key in found:
            continue
        hits = {}
        for name in names:
            for p in v2.search_profiles(fullname=name):
                s = profile_summary(p)
                post = vietnam_post(s)
                if post:
                    hits[p.id] = {"id": p.id, "position": post["position"], "institution": post["institution"],
                                  "start": post["start"], "end": post["end"]}
            time.sleep(0.5)
        found[key] = list(hits.values())
        print(f"  {names[0]}: " + ("; ".join(f"{h['id']} {h['position']} at {h['institution']}" for h in hits.values())
                                  or "no profile with a post in Vietnam"))
        write_json(path, found)
    print(f"\nsaved to {path}; run `python find_candidates.py` to see the positions in candidates.csv")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", nargs="+", metavar="SLUG", help="fetch only these people")
    ap.add_argument("--search", nargs="+", metavar="NAME", help="print the profiles with this name and stop")
    ap.add_argument("--candidates", type=int, metavar="N", help="look up the first N people of candidates.csv")
    args = ap.parse_args()

    v2, v1 = login()
    if args.search:
        return search(v2, args.search)
    if args.candidates:
        return lookup_candidates(v2, args.candidates)

    people = [p for p in load_roster() if p["approved"] == "yes"]
    if args.only:
        unknown = set(args.only) - {p["slug"] for p in people}
        if unknown:
            sys.exit(f"not approved in roster.csv: {', '.join(sorted(unknown))}")
        people = [p for p in people if p["slug"] in args.only]
    for person in people:
        if not person["openreview_ids"]:
            print(f"{person['name']}: no openreview_ids in roster.csv, skipped")
            continue
        data = fetch_person(v2, v1, person)
        write_json(OPENREVIEW_RAW / f"{person['slug']}.json", data)
        print(f"{person['name']}: {len(data['notes'])} submissions at the eleven venues "
              f"(profile IDs queried: {', '.join(data['profile_ids'])})")
    print("\nnow run: python build_site_data.py")


if __name__ == "__main__":
    main()
