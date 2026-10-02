#!/usr/bin/env python3
"""List people with a Vietnamese affiliation on accepted papers who are not on the roster yet.

Reads work/accepted.jsonl.gz and writes candidates.csv, people with the most accepted papers first. The first
columns are the roster columns, so approving someone is one command:

    python find_candidates.py --add "Nguyen Van A" "Tran Thi B"

which appends them to roster.csv with `approved` left empty. Then open roster.csv, fill in `rank`,
`vn_since` and `openreview_ids`, and set `approved` to yes.

Only sources that give an affiliation per author can be searched: ICLR, NeurIPS and ICML (all years)
and CVPR from 2023. People who publish only at ACL, or at CVPR before 2023, have to be added by hand.

If `python fetch_openreview.py --candidates` has been run, their OpenReview position is shown too.
"""
import argparse
import collections
import csv
import json
import sys

from common import (ACCEPTED, BACKEND, CANDIDATES, FIRST_YEAR, OPENREVIEW_RAW, ROSTER, ROSTER_FIELDS, VENUE_KEYS,
                    VENUE_NAME, load_roster, name_key, norm_name, read_csv, read_jsonl_gz, slugify, vn_institution,
                    write_csv)

EVIDENCE_FIELDS = ["papers", "senior_author", "first_year", "last_year", "venues", "at_university",
                   "faculty_page", "faculty_rank", "faculty_match",
                   "affiliations", "openreview_position", "sample_paper", "sample_url", "first_paper", "first_url"]
PROFILES = OPENREVIEW_RAW / "_candidates.json"  # written by fetch_openreview.py --candidates
FACULTY = BACKEND / "faculty.csv"  # hand-kept: names and titles copied from the universities' faculty pages
MATCH_ORDER = {"exact": 0, "likely": 1, "possible": 2}


def faculty_match(forms, institutions, faculty):
    """The faculty-page entry that fits a candidate's name forms best, as (row, quality), or None.

    Faculty pages print Vietnamese names family name first ("Doan Dang Khoa"); papers print them given
    name first and often shortened ("Khoa D. Doan"). A form fits when all its words are in the listed
    name, it has both the family and the given name, and its initials stand for the remaining words.
      exact     every word of the listed name is there
      likely    three or more words, or initials that fit
      possible  given and family name only; several people at one university can share those
    """
    best = None
    for row in faculty:
        if not any(i == row["institution_short"] or row["institution_short"].startswith(i + "-") for i in institutions):
            continue  # full names repeat across universities, so the paper must name the same institution
        listed = norm_name(row["name"]).split()
        for form in forms:
            words = norm_name(form).split()
            full, initials = [w for w in words if len(w) > 1], [w for w in words if len(w) == 1]
            if len(full) < 2 or not set(full) <= set(listed) or not {listed[0], listed[-1]} <= set(full):
                continue
            rest = [w for w in listed if w not in full]
            if any(not any(r.startswith(i) for r in rest) for i in initials):
                continue
            quality = "exact" if set(full) == set(listed) else "likely" if initials or len(full) >= 3 else "possible"
            if best is None or MATCH_ORDER[quality] < MATCH_ORDER[best[1]]:
                best = (row, quality)
    return best


def find(accepted, roster):
    known = {v for p in roster for v in p["variants"]} | {name_key(p["name"]) for p in roster}
    people = {}
    for paper in accepted:
        if paper["track"] != "main":
            continue
        n = len(paper["authors"])
        for i, a in enumerate(paper["authors"]):
            inst = vn_institution(a["aff"])
            if not inst:
                continue
            key = name_key(a["name"])
            c = people.setdefault(key, {"names": collections.Counter(), "inst": collections.Counter(),
                                        "raw": collections.Counter(), "papers": {}, "senior": set()})
            c["names"][a["name"].strip()] += 1
            c["inst"][inst] += 1
            c["raw"][a["aff"]] += 1
            pid = (paper["venue"], paper["year"], paper["title"])
            c["papers"][pid] = paper["url"]
            if n > 1 and i == n - 1:
                c["senior"].add(pid)

    profiles = json.loads(PROFILES.read_text(encoding="utf-8")) if PROFILES.exists() else {}
    faculty = read_csv(FACULTY)
    rows = []
    for key, c in people.items():
        names = [n for n, _ in c["names"].most_common()]
        if key in known or any(norm_name(n) in known for n in names):
            continue
        (full, short, _), _ = c["inst"].most_common(1)[0]
        years = [y for _, y, _ in c["papers"]]
        venues = collections.Counter(v for v, _, _ in c["papers"])
        latest = max(c["papers"], key=lambda p: (p[1], p[2]))
        oldest = min(c["papers"], key=lambda p: (p[1], p[2]))
        prof = profiles.get(key, [])
        listed = faculty_match(names, {short for (_, short, _) in c["inst"]}, faculty)
        rows.append({
            "faculty_page": f"{listed[0]['name']} ({listed[0]['institution_short']})" if listed else "",
            "faculty_rank": listed[0]["rank"] if listed else "", "faculty_match": listed[1] if listed else "",
            "approved": "", "display_name": names[0], "name_variants": "; ".join(names[1:]),
            "institution": full, "institution_short": short,
            "rank": "; ".join(sorted({p["position"] for p in prof if p.get("position")})),
            "vn_since": "", "openreview_ids": ";".join(p["id"] for p in prof), "homepage": "",
            "to_confirm": "rank, vn_since and OpenReview ID", "notes": "", "slug": slugify(names[0]),
            "papers": len(c["papers"]), "senior_author": len(c["senior"]),
            "first_year": min(years), "last_year": max(years),
            "venues": ", ".join(f"{VENUE_NAME[v]} {venues[v]}" for v in VENUE_KEYS if venues[v]),
            "at_university": "yes" if any(uni for (_, _, uni) in c["inst"]) else "no",
            "affiliations": " | ".join(a for a, _ in c["raw"].most_common(3)),
            "openreview_position": "; ".join(
                f"{p['id']}: {p.get('position') or '?'} at {p.get('institution') or '?'}" for p in prof),
            "sample_paper": f"{latest[2]} ({VENUE_NAME[latest[0]]} {latest[1]})", "sample_url": c["papers"][latest],
            "first_paper": f"{oldest[2]} ({VENUE_NAME[oldest[0]]} {oldest[1]})", "first_url": c["papers"][oldest],
        })
    rows.sort(key=lambda r: (-r["papers"], -r["senior_author"], r["display_name"]))
    return rows


def add_to_roster(rows, wanted):
    by_name = {norm_name(r["display_name"]): r for r in rows} | {r["slug"]: r for r in rows}
    picked, missing = [], []
    for w in wanted:
        r = by_name.get(norm_name(w)) or by_name.get(w)
        (picked if r else missing).append(r or w)
    if missing:
        sys.exit(f"not in candidates.csv: {', '.join(missing)}")
    new_file = not ROSTER.exists()
    with open(ROSTER, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ROSTER_FIELDS, extrasaction="ignore")
        if new_file:
            w.writeheader()
        for r in picked:
            w.writerow({**r, "vn_since": r["first_year"] if r["first_year"] > FIRST_YEAR else ""})
    print(f"added {len(picked)} to {ROSTER} (approved is empty until you set it to yes)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--add", nargs="+", metavar="NAME", help="append these candidates to roster.csv")
    args = ap.parse_args()

    rows = find(read_jsonl_gz(ACCEPTED), load_roster())
    if args.add:
        return add_to_roster(rows, args.add)
    write_csv(CANDIDATES, ROSTER_FIELDS + EVIDENCE_FIELDS, rows)
    senior = sum(1 for r in rows if r["senior_author"])
    listed = sum(1 for r in rows if r["faculty_page"])
    print(f"{len(rows)} people with a Vietnamese affiliation are not on the roster "
          f"({senior} are last author on at least one paper, {listed} match a faculty page) -> {CANDIDATES}")


if __name__ == "__main__":
    main()
