#!/usr/bin/env python3
"""Fetch the reviewers' scores of the papers on the site from OpenReview, as score(confidence) pairs.

Reads frontend/data/papers.json (run build_site_data.py first), asks OpenReview for the official reviews of every
ICLR, NeurIPS and ICML paper whose address is an OpenReview forum, and writes reviews.json:
{forum id: [[score, confidence], ...]}, one pair per review, scores exactly as the reviewers gave them (the scales
differ by venue and year, so only the number before the colon is kept). Papers with no public review are left out.
Also writes submission_numbers.json: the submission number of every OpenReview paper on the site, any venue.

Needs OPENREVIEW_USERNAME and OPENREVIEW_PASSWORD (and a TOTP code when asked). Resumable: forums already in
reviews.json are skipped; --refresh reads all again (reviews appear and change during review periods).
"""
import argparse
import json
import re
import sys

from common import JSON_DIR  # backend/data/
from common import BACKEND, FRONTEND, write_json
from fetch_openreview import login, val, with_retry

OUT = JSON_DIR / "reviews.json"
NUMBERS = JSON_DIR / "submission_numbers.json"   # {forum id: the submission's number at its venue}
VENUES = ("iclr", "neurips", "icml")
SCORE_KEYS = ("rating", "overall_recommendation", "recommendation")


def number(value):
    m = re.match(r"\s*(\d+)", str(val(value) or ""))
    return int(m.group(1)) if m else None


def reviews_of(client, forum):
    out = []
    for n in with_retry(client.get_notes, forum=forum):
        invs = getattr(n, "invitations", None) or [getattr(n, "invitation", "") or ""]
        if n.id == n.forum or not any(i.endswith("Official_Review") for i in invs):
            continue
        score = next((number(n.content[k]) for k in SCORE_KEYS if k in n.content), None)
        if score is not None:
            out.append([score, number(n.content.get("confidence"))])
    return out


def submission_number(client, forum):
    try:
        return getattr(with_retry(client.get_note, forum), "number", None)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--refresh", action="store_true", help="read every paper again")
    args = ap.parse_args()
    papers = json.loads((FRONTEND / "data" / "papers.json").read_text(encoding="utf-8"))
    known = {} if args.refresh or not OUT.exists() else json.loads(OUT.read_text(encoding="utf-8"))
    v2, v1 = login()
    todo = {}
    for p in papers:
        m = re.search(r"openreview\.net/forum\?id=([\w-]+)", p["url"] or "")
        if m and p["venue"] in VENUES:
            todo[m.group(1)] = p["year"]
    for i, (forum, year) in enumerate(sorted(todo.items()), 1):
        if forum in known:
            continue
        found = reviews_of(v2, forum) or (reviews_of(v1, forum) if v1 is not None and year <= 2023 else [])
        known[forum] = found
        print(f"{i}/{len(todo)} {forum}: {found}", file=sys.stderr)
    known = {f: r for f, r in known.items() if f in todo and r}
    write_json(OUT, dict(sorted(known.items())))
    print(f"{len(known)} of {len(todo)} papers have public review scores -> {OUT}")

    # the submission number of every OpenReview paper on the site, any venue (shown as its Submission ID)
    numbers = {} if args.refresh or not NUMBERS.exists() else json.loads(NUMBERS.read_text(encoding="utf-8"))
    forums = {m.group(1): p["year"] for p in papers
              if (m := re.search(r"openreview\.net/forum\?id=([\w-]+)", p["url"] or ""))}
    for forum, year in sorted(forums.items()):
        if forum not in numbers:
            n = submission_number(v2, forum) or (submission_number(v1, forum) if v1 is not None else None)
            if n:
                numbers[forum] = n
    numbers = {f: n for f, n in numbers.items() if f in forums}
    write_json(NUMBERS, dict(sorted(numbers.items())))
    print(f"{len(numbers)} of {len(forums)} OpenReview papers have a submission number -> {NUMBERS}")


if __name__ == "__main__":
    main()
