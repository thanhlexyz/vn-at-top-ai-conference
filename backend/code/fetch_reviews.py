import argparse
import json
import re
import sys

from common import JSON_DIR, FRONTEND, write_json
from fetch_openreview import login, val, with_retry

OUT = JSON_DIR / "reviews.json"
NUMBERS = JSON_DIR / "submission_numbers.json"
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
    ap = argparse.ArgumentParser(description="Fetch the reviewers' scores of the papers on the site from OpenReview, as score(confidence) pairs.")
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
