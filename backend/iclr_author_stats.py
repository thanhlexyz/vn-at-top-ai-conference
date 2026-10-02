#!/usr/bin/env python3
"""Count ICLR accepted / rejected / withdrawn / desk-rejected submissions per author on OpenReview.

Setup:
    pip install openreview-py
    export OPENREVIEW_USERNAME=you@example.com
    export OPENREVIEW_PASSWORD=...          # or omit and you'll be prompted (needs a real terminal)

Usage:
    python iclr_author_stats.py "Phi Le Nguyen" "Tuan Dam"      # search by name, prints candidate profile IDs
    python iclr_author_stats.py ~Phi_Le_Nguyen2 ~Tuan_Dam1 --list   # count by profile ID, list rejected titles

Name search can return several people with the same name, so the script only prints candidates
for names; rerun with the ~ProfileID you want. A person's merged profile IDs are all queried.

Cache: results are saved next to this script in iclr_cache/people.csv (resolved profile IDs) and
iclr_cache/papers.csv (one row per paper). Later runs reuse them and only log in / query OpenReview for
people not yet cached. Use --refresh to re-query everyone (e.g. after a new ICLR decision round).

Only main-conference submissions are counted (workshops, Tiny Papers and blog tracks are excluded).

Caveats: only what OpenReview makes public is visible. Withdrawn papers may be hidden or anonymized,
so the rejected/withdrawn counts can be low. Venue classification is based on the venue / venueid strings.
"""
import argparse
import collections
import csv
import datetime
import getpass
import os
import re
import sys
from pathlib import Path

import openreview


def login():
    user, pw = os.environ.get("OPENREVIEW_USERNAME"), os.environ.get("OPENREVIEW_PASSWORD")
    for name, v in (("OPENREVIEW_USERNAME", user), ("OPENREVIEW_PASSWORD", pw)):
        if not v:
            print(f"note: {name} is not set in this process's environment (did you `export` it in this shell?)", file=sys.stderr)
    user = user or input("OpenReview username: ")
    pw = pw or getpass.getpass("OpenReview password: ")
    v2 = openreview.api.OpenReviewClient(baseurl="https://api2.openreview.net", username=user, password=pw)
    try:
        v1 = openreview.Client(baseurl="https://api.openreview.net", username=user, password=pw)
    except Exception as e:  # v1 is only needed for older ICLR years
        print(f"warning: API v1 login failed ({e}); older ICLR years may be missing", file=sys.stderr)
        v1 = None
    return v2, v1


def val(x):
    """API v2 wraps fields as {'value': ...}; API v1 uses plain values."""
    return x.get("value") if isinstance(x, dict) else x


def show_candidates(v2, name):
    print(f"\n== candidates for '{name}'")
    for p in v2.search_profiles(fullname=name):
        hist = p.content.get("history") or []
        inst = "; ".join(
            f"{(h.get('institution') or {}).get('name')} ({h.get('start')}-{h.get('end') or 'now'})" for h in hist[:2]
        )
        print(f"  {p.id:32s} {inst}")


# Default run (no arguments): label -> (name variants to search, regex a profile's institution /
# domain / email must match to be accepted as the right person).
HUST = re.compile(r"hanoi university of science|\bhust\b|bach khoa|hust\.edu\.vn", re.I)
VINUNI = re.compile(r"vinuni|vinuniversity|vingroup|vinbigdata", re.I)
HUST_OR_LYON = re.compile(HUST.pattern + r"|ens de lyon|ens-lyon|normale sup.rieure de lyon", re.I)  # HUST now; NUS 2022-25, ENS Lyon PhD
VIETNAM = re.compile(r"hanoi university of science|\bhust\b|bach khoa|vinuni|vinuniversity|vinai|vietnam|hanoi|ho chi minh|\.vn\b", re.I)
DEFAULT_PEOPLE = {
    "Phi Le Nguyen": (["Phi Le Nguyen", "Nguyen Phi Le"], HUST),
    "Tuan Dam": (["Tuan Dam", "Dam Quang Tuan", "Quang Tuan Dam"], HUST),
    "Ngo Van Linh": (["Linh Ngo Van", "Ngo Van Linh", "Van Linh Ngo"], HUST),
    "Than Quang Khoat": (["Khoat Than", "Than Quang Khoat", "Quang Khoat Than"], HUST),
    "Huynh Thi Thanh Binh": (["Huynh Thi Thanh Binh", "Thanh Binh Huynh Thi", "Binh Huynh Thi Thanh"], HUST),
    "Hieu Pham (VinUni)": (["Hieu Pham", "Pham Huy Hieu", "Hieu H. Pham", "Huy Hieu Pham"], VINUNI),
    "Dung D. Le": (["Dung D. Le", "Dung Le", "Le Dung", "Dung Duc Le"], VINUNI),  # assumed VinUni (not verified)
    "Hoang Ta (Ta Duy Hoang)": (["Ta Duy Hoang", "Duy Hoang Ta", "Hoang Ta", "Ta Hoang"], HUST_OR_LYON),
}


def resolve_one(v2, variants, want):
    """~ProfileIDs (over all name variants) whose institution / domain / email matches `want`."""
    ids = []
    for v in variants:
        for p in v2.search_profiles(fullname=v):
            c = p.content
            text = " ".join(
                [str((h.get("institution") or {}).get(k) or "") for h in (c.get("history") or []) for k in ("name", "domain")]
                + [str(e) for e in (c.get("emails") or [])]
                + [str(c.get("preferredEmail") or "")]
            )
            if want.search(text) and p.id not in ids:
                ids.append(p.id)
    return ids


def profile_ids(v2, pid):
    """All usernames attached to a profile (merged profiles have more than one)."""
    p = v2.get_profile(pid)
    return sorted({n["username"] for n in p.content.get("names", []) if n.get("username")} | {p.id})


def classify(venue, venueid):
    s = f"{venue} {venueid}"
    if "Desk" in s and "Reject" in s:
        return "desk_rejected"
    if "Withdrawn" in s:
        return "withdrawn"
    if venueid.endswith("Rejected_Submission") or venue.startswith("Submitted to"):
        return "rejected"
    if re.search(r"ICLR \d{4}", venue) or re.fullmatch(r"ICLR\.cc/\d{4}/Conference", venueid):
        return "accepted"
    return "other/under review"


def iclr_year(note, venue, venueid):
    m = re.search(r"ICLR\.cc/(\d{4})|ICLR (\d{4})", f"{venueid} {venue} {' '.join(note.invitations or [])}")
    return int(next(g for g in m.groups() if g)) if m else None


# Main-conference submissions only: ICLR.cc/<year>/Conference/... (excludes Workshop, TinyPapers, Blogposts tracks)
MAIN_INV = re.compile(r"ICLR\.cc/\d{4}/Conference/")
NON_MAIN = re.compile(r"workshop|tiny ?papers|blogpost", re.I)


def fetch(v2, v1, ids):
    seen, out = set(), []
    for pid in ids:
        batches = [v2.get_all_notes(content={"authorids": pid})]
        if v1 is not None:
            batches.append(v1.get_all_notes(content={"authorids": pid}))
        for notes in batches:
            for n in notes:
                invs = " ".join(getattr(n, "invitations", None) or [getattr(n, "invitation", "") or ""])
                if n.id != n.forum or not MAIN_INV.search(invs) or n.id in seen:
                    continue
                n.invitations = getattr(n, "invitations", None) or [invs]
                seen.add(n.id)
                out.append(n)
    return out


CACHE = Path(__file__).resolve().parent / "iclr_cache"
PEOPLE_CSV, PAPERS_CSV = CACHE / "people.csv", CACHE / "papers.csv"
PAPER_FIELDS = ["label", "year", "status", "title", "venue", "venueid", "authors", "forum", "url"]


def load_cache():
    people, papers = {}, collections.defaultdict(list)
    if PEOPLE_CSV.exists():
        with open(PEOPLE_CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                people[r["label"]] = r
    if PAPERS_CSV.exists():
        with open(PAPERS_CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                papers[r["label"]].append(r)
    return people, papers


def save_cache(people, papers):
    CACHE.mkdir(exist_ok=True)
    with open(PEOPLE_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["label", "profile_ids", "fetched_at"])
        w.writeheader()
        w.writerows(people.values())
    with open(PAPERS_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=PAPER_FIELDS)
        w.writeheader()
        for label in people:
            w.writerows(papers.get(label, []))


def note_row(label, n):
    venue = str(val(n.content.get("venue")) or "")
    venueid = str(val(n.content.get("venueid")) or "")
    authors = val(n.content.get("authors")) or []
    return {
        "label": label,
        "year": iclr_year(n, venue, venueid) or "",
        "status": classify(venue, venueid),
        "title": str(val(n.content.get("title")) or ""),
        "venue": venue,
        "venueid": venueid,
        "authors": "; ".join(authors) if isinstance(authors, list) else str(authors),
        "forum": n.forum,
        "url": f"https://openreview.net/forum?id={n.forum}",
    }


def report(label, rows, list_titles):
    by_year = collections.defaultdict(collections.Counter)
    for r in rows:
        by_year[r["year"]][r["status"]] += 1
    print(f"\n== {label}: {len(rows)} ICLR submissions visible")
    print(f"{'year':6s}{'accepted':>9s}{'rejected':>9s}{'withdrawn':>10s}{'desk_rej':>9s}{'other':>7s}")
    tot = collections.Counter()
    for y in sorted(by_year, key=lambda k: (k == "", k)):
        c = by_year[y]
        tot.update(c)
        print(f"{str(y) or '?':6s}{c['accepted']:9d}{c['rejected']:9d}{c['withdrawn']:10d}"
              f"{c['desk_rejected']:9d}{c['other/under review']:7d}")
    print(f"{'total':6s}{tot['accepted']:9d}{tot['rejected']:9d}{tot['withdrawn']:10d}"
          f"{tot['desk_rejected']:9d}{tot['other/under review']:7d}")
    if list_titles:
        for r in sorted(rows, key=lambda r: (str(r["year"]), r["status"])):
            if r["status"] != "accepted":
                print(f"  [{r['year']} {r['status']}] {r['title']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("who", nargs="*", help="none = the hard-coded people; or names (search only) / ~ProfileIDs (count)")
    ap.add_argument("--list", action="store_true", help="list non-accepted titles")
    ap.add_argument("--refresh", action="store_true", help="ignore the cache and re-query OpenReview")
    args = ap.parse_args()

    people, papers = load_cache()
    clients = []  # logged in lazily, only if something isn't cached

    def get_clients():
        if not clients:
            clients.append(login())
        return clients[0]

    labels = []  # labels to report
    for w in args.who:
        if w.startswith("~"):
            labels.append(w)
        else:
            show_candidates(get_clients()[0], w)
    if not args.who:
        labels = list(DEFAULT_PEOPLE)

    for label in labels:
        if label in people and not args.refresh:
            print(f"{label}: using cache ({people[label]['fetched_at']})")
        else:
            v2, v1 = get_clients()
            if label.startswith("~"):
                pids = [label]
            else:
                variants, want = DEFAULT_PEOPLE[label]
                pids = resolve_one(v2, variants, want)
                print(f"{label}: matched {pids or 'NOTHING (try a name search and pass the ~ID by hand)'}")
            if not pids:
                continue
            all_ids = sorted({i for pid in pids for i in profile_ids(v2, pid)})
            papers[label] = [note_row(label, n) for n in fetch(v2, v1, all_ids)]
            people[label] = {"label": label, "profile_ids": ";".join(all_ids),
                             "fetched_at": datetime.datetime.now().isoformat(timespec="seconds")}
            save_cache(people, papers)
        # also drop workshop-type rows from CSVs cached before this filter existed
        rows = [r for r in papers.get(label, []) if not NON_MAIN.search(f"{r['venue']} {r['venueid']}")]
        report(label, rows, args.list)
    print(f"\ncache: {PEOPLE_CSV} , {PAPERS_CSV}")


if __name__ == "__main__":
    main()
