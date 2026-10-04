#!/usr/bin/env python3
"""Build the JSON data and the page stubs that the Hugo site in ../frontend renders.

Inputs
    roster.csv                    who is on the site (hand-edited; only rows with approved = yes count)
    review.csv                    uncertain matches; this script appends rows, you fill in `decision`
    work/accepted.jsonl.gz        accepted papers of the eight venues        (fetch_accepted.py)
    raw/openreview/<slug>.json    every OpenReview submission of a person   (fetch_openreview.py)
    candidates.csv                people not on the roster yet              (find_candidates.py)

Counting rules (the site's About page states the same)
    * main conference track only
    * a paper counts from the year the person joined a Vietnamese institution (roster column vn_since)
    * rejected, withdrawn and desk-rejected papers are added up as "not accepted"
    * rejections are complete for ICLR only; NeurIPS has only those its authors chose to make public
    * co-author and topic figures are taken over all counted papers, accepted or not
"""
import collections
import csv
import datetime
import charts
import graph
import difflib
import html
import json
import re

from common import (ACCEPTED, BACKEND, CANDIDATES, FRONTEND, LEGACY_PAPERS, NOT_ACCEPTED, OPENREVIEW_RAW, REVIEW,
                    STATUS_LABEL, VENUE_GROUPS, VENUE_KEYS, VENUE_NAME, VENUES, WORK, YEARS, classify_status, held, in_vietnam,
                    load_roster, name_key, norm_name, norm_title, openreview_venue, presentation, read_csv,
                    read_jsonl_gz, same_institution, slugify, vn_institutions, write_json)

DATA = FRONTEND / "data"
CONTENT = FRONTEND / "content"
REVIEW_FIELDS = ["decision", "professor", "venue", "year", "title", "matched_name", "affiliation", "reason", "url",
                 "note"]
SELF_REPORTED = BACKEND / "self_reported.csv"  # hand-kept: what professors list on their own pages
# A paper placed in Findings was not accepted to the main track, at any conference: it counts as a rejection there,
# and it is also listed and counted with the workshop papers
FINDINGS_NOTE = "placed in Findings, which counts as rejected from the main track and as a workshop paper"
# Tracks that are left out on purpose and listed under "Not counted". Workshop papers have a list of their own
# on the professor's page (workshop_papers), also never counted.
TRACK_REASON = {"datasets_benchmarks": "Datasets & Benchmarks track", "position": "position-paper track",
                "findings": "Findings track", "journal": "journal track", "blog": "blog-post track",
                "tiny_papers": "Tiny Papers track"}
MAX_CANDIDATES_ON_SITE = 150
AREA_ALIAS = {"Miscellaneous Aspects of Machine Learning": "General Machine Learning"}  # renamed in 2025


# ---------------------------------------------------------------- inputs

class Accepted:
    """The accepted-paper lists, indexed the ways the matching needs."""

    def __init__(self, papers, coverage):
        papers = list(papers)
        self.by_name = collections.defaultdict(list)  # normalized author name -> [(paper, author position)]
        self.by_forum, self.by_title = {}, {}
        self.in_year = collections.defaultdict(list)
        for p in papers:
            self.in_year[(p["venue"], p["year"])].append(p)
            for i, a in enumerate(p["authors"]):
                self.by_name[norm_name(a["name"])].append((p, i))
            if p["forum"]:
                self.by_forum[p["forum"]] = p
            key = (p["venue"], p["year"], norm_title(p["title"]))
            if key not in self.by_title or p["track"] == "main":
                self.by_title[key] = p
        self.coverage = coverage
        self.available = {(c["venue"], c["year"]) for c in coverage if c["papers"]}
        self.provisional = {(c["venue"], c["year"]) for c in coverage if c.get("provisional")}
        self.papers = papers

    def official(self, venue, year, title, forum=""):
        p = self.by_forum.get(forum) if forum else None
        if p and (p["venue"], p["year"]) == (venue, year):
            return p
        return self.by_title.get((venue, year, norm_title(title)))

    def find(self, venue, year, title):
        """Like official(), but also accepts a title that differs a little, as titles on personal pages do."""
        p = self.by_title.get((venue, year, norm_title(title)))
        if p is None:
            key = norm_title(title)
            for other in self.in_year[(venue, year)]:
                k = norm_title(other["title"])
                if (k[:14] == key[:14] or k[-14:] == key[-14:]) and same_title(other["title"], title):
                    return other
        return p


def load_legacy(roster):
    """Rows of the old iclr_author_stats.py cache, per roster slug.

    They are used only while a person has no raw/openreview/<slug>.json, and only if every profile ID the
    old script queried is on the roster now: the old name search sometimes mixed several people.
    """
    people = {re.sub(r"\(.*?\)", "", r["label"]).strip(): r for r in read_csv(LEGACY_PAPERS.parent / "people.csv")}
    by_variant = {v: p for p in roster for v in p["variants"]}
    out = {}
    for label, row in people.items():
        person = by_variant.get(norm_name(label))
        ids = {i for i in row["profile_ids"].split(";") if i}
        if person and ids and ids <= set(person["openreview_ids"]):
            out[person["slug"]] = {"fetched_at": row["fetched_at"], "notes": []}
    for r in read_csv(LEGACY_PAPERS):
        person = by_variant.get(norm_name(re.sub(r"\(.*?\)", "", r["label"])))
        if person and person["slug"] in out:
            out[person["slug"]]["notes"].append({
                "forum": r["forum"], "title": r["title"], "venue": r["venue"], "venueid": r["venueid"],
                "invitations": [], "authors": [a for a in r["authors"].split("; ") if a], "decision": "",
                "legacy_year": int(r["year"]) if r["year"].isdigit() else None})
    return out


def load_openreview(person, legacy):
    """(notes, source, fetched date, stale, own usernames) where source is 'openreview', 'legacy' or 'none'."""
    path = OPENREVIEW_RAW / f"{person['slug']}.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        stale = set(data.get("queried_ids", [])) != set(person["openreview_ids"])
        own_ids = set(data.get("profile_ids", [])) | set(person["openreview_ids"])
        return data.get("notes", []), "openreview", data.get("fetched_at", "")[:10], stale, own_ids
    if person["slug"] in legacy:
        return legacy[person["slug"]]["notes"], "legacy", legacy[person["slug"]]["fetched_at"][:10], False, set()
    return [], "none", "", False, set()


def shared_notes(approved, legacy):
    """Submissions in one professor's OpenReview record that list another approved professor.

    {slug: [{note, owner, exact, name}]}. exact means the other professor's profile ID is on the submission.
    Without IDs on either side (the old cache has names only) the match is by name and has to be confirmed.
    """
    loaded = {p["slug"]: load_openreview(p, legacy) for p in approved}
    out = collections.defaultdict(list)
    for owner in approved:
        for n in loaded[owner["slug"]][0]:
            ids = set(n.get("authorids") or [])
            names = {norm_name(a): a for a in n.get("authors") or []}
            for p in approved:
                if p is owner:
                    continue
                known = set(p["openreview_ids"]) | loaded[p["slug"]][4]
                named = next((names[v] for v in p["variants"] if v in names), None)
                if ids & known:
                    out[p["slug"]].append({"note": n, "owner": owner["name"], "exact": True, "name": named or ""})
                elif named and not (ids and known):  # both sides have IDs and they differ: a namesake
                    out[p["slug"]].append({"note": n, "owner": owner["name"], "exact": False, "name": named})
    return out


def note_venue(note):
    v = openreview_venue(note.get("invitations"), note.get("venueid"))
    if v is None and note.get("legacy_year") and not note.get("venue") and not note.get("venueid"):
        return "iclr", note["legacy_year"], "main"  # the old cache stored ICLR 2020-21 rows without any venue
    return v


def load_self_reported(roster):
    """Papers from personal pages, per roster slug, and the totals that pages announce without titles.

    A paper is filed under the professor whose page lists it and under every other approved professor
    the page names as co-author, so a paper on Hoang Ta's page also reaches Tuan Dam.
    """
    approved = [p for p in roster if p["approved"] == "yes"]
    by_variant = {v: p for p in approved for v in p["variants"]}
    names = {p["slug"]: p["name"] for p in roster}
    papers, announced = collections.defaultdict(list), collections.defaultdict(dict)
    for r in read_csv(SELF_REPORTED):
        slug = r["professor"]
        if slug not in names or not r["year"].isdigit():
            continue
        if not r["title"].strip():
            if r["announced"].strip().isdigit():
                announced[slug][(r["venue"], int(r["year"]))] = r
            continue
        coauthors = [c.strip() for c in r["coauthors"].split(";") if c.strip()]
        row = {**r, "year": int(r["year"]), "track": r["track"].strip() or "main", "owner": names[slug],
               "authors": [names[slug], *coauthors], "label": (r.get("source_label") or "").strip() or "their own page"}
        papers[slug].append({**row, "role": "own"})
        for name in coauthors:
            other = by_variant.get(norm_name(name))
            if other and other["slug"] != slug:
                papers[other["slug"]].append({**row, "role": "coauthor"})
    return papers, announced


def load_review():
    rows = read_csv(REVIEW)
    return rows, {(r["professor"], r["venue"], r["year"], norm_title(r["title"])): r["decision"].strip().lower()
                  for r in rows}


# ---------------------------------------------------------------- matching

def same_title(a, b):
    a, b = norm_title(a), norm_title(b)
    return a == b or difflib.SequenceMatcher(None, a, b).ratio() >= 0.9


def workshop_name(n):
    """Short name of the workshop of an OpenReview note, from its group ID ('ICLR.cc/2025/Workshop/ICBINB')."""
    for s in [n.get("venueid") or "", *(n.get("invitations") or [])]:
        m = re.search(r"/Workshop/([^/]+)", s)
        if m:
            return m.group(1).replace("_", " ")
    return (n.get("venue") or "").strip()


def same_paper(a, b):
    """same_title, or the same name before the colon ('UniCon: ...'), which a retitled paper keeps."""
    short_a, short_b = norm_title(a.partition(":")[0]), norm_title(b.partition(":")[0])
    return same_title(a, b) or (":" in a and ":" in b and len(short_a) >= 4 and short_a == short_b)


def person_records(person, acc, legacy, decisions, queue, warnings, skipped, own=(), borrowed=()):
    """Every paper of one person at the eight venues, before the counting rules are applied."""
    notes, source, fetched, stale, own_ids = load_openreview(person, legacy)
    recs = []

    def existing(venue, year, title, workshop=False):
        # a workshop version and a conference version of the same paper are two different records
        return next((r for r in recs if (r["venue"], r["year"]) == (venue, year) and same_title(r["title"], title)
                     and (r["track"] == "workshop") == workshop), None)

    def add_note(n, match, own_ids, borrowed=False):
        v = note_venue(n)
        if v is None or v[1] not in YEARS or v[2] == "other":
            return
        venue, year, track = v
        status = classify_status(n.get("venue"), n.get("venueid"), n.get("invitations"), n.get("decision"))
        if re.search(r"\bFindings\b", n.get("venue") or ""):   # "CVPR 2026 Findings", "EMNLP 2023 Findings"
            track, status = "findings", "accepted"
        if track in ("workshop", "findings"):   # listed for reference only: no official list to check, no outcome inferred
            if existing(venue, year, n["title"], workshop=True) or (track == "findings" and existing(venue, year, n["title"])):
                return
            recs.append({"venue": venue, "year": year, "track": track, "title": n["title"].strip(), "status": status,
                         "note": "", "pres": "", "workshop": "Findings" if track == "findings" else workshop_name(n),
                         "url": f"https://openreview.net/forum?id={n['forum']}" if n.get("forum") else "",
                         "authors": n.get("authors") or [], "match": match, "borrowed": borrowed,
                         "people": [{"name": a, "aff": ""} for a in n.get("authors") or []], "self": None, "topic": ""})
            return
        official = acc.official(venue, year, n["title"], n.get("forum", "")) if track == "main" else None
        note = ""
        if official:
            if status in NOT_ACCEPTED:
                warnings.append(f"{person['name']}: '{n['title'][:60]}' ({VENUE_NAME[venue]} {year}) is labelled "
                                f"{status} on OpenReview but is in the accepted list; counted as accepted")
            status = "accepted"
        elif status == "accepted" and track == "main" and (venue, year) in acc.available:
            warnings.append(f"{person['name']}: '{n['title'][:60]}' ({VENUE_NAME[venue]} {year}) reads as accepted "
                            f"on OpenReview but was not found in the accepted list; check it by hand")
        elif status == "unknown" and (venue, year) in acc.available:
            status, note = "rejected", "outcome inferred: no decision on record and not in the accepted list"
        if existing(venue, year, n["title"]):
            return
        names = n.get("authors") or []
        people = official["authors"] if official else [{"name": a, "aff": ""} for a in names]
        ids = n.get("authorids") or []
        mine = [i for i, a in enumerate(ids) if a in own_ids] if len(ids) == len(people) else []
        recs.append({"venue": venue, "year": year, "track": track, "title": n["title"].strip(), "status": status,
                     "note": note, "pres": (official or {}).get("pres") or
                     (presentation(n.get("venue")) if status == "accepted" else ""),
                     "url": f"https://openreview.net/forum?id={n['forum']}" if n.get("forum") else
                     (official or {}).get("url", ""),
                     "authors": names or [a["name"] for a in people], "match": match, "borrowed": borrowed,
                     "people": people, "self": mine[0] if mine else None, "topic": (official or {}).get("topic", "")})

    # 1. OpenReview submissions, matched by profile ID: the only source of rejected and withdrawn papers
    for n in notes:
        add_note(n, "OpenReview profile", own_ids)

    #    ... and submissions in the OpenReview record of a colleague on the roster that list this person.
    #    With a profile ID on the submission that is exact; with a name only it needs a yes in review.csv.
    seen = {n.get("forum") for n in notes}
    for b in borrowed:
        n, v = b["note"], note_venue(b["note"])
        if n.get("forum") in seen or v is None or v[1] not in YEARS or v[2] != "main":
            continue
        seen.add(n.get("forum"))
        if b["exact"]:
            add_note(n, f"OpenReview profile, found in the record of {b['owner']}", set(person["openreview_ids"]), True)
            continue
        venue, year, _ = v
        decision = decisions.get((person["slug"], venue, str(year), norm_title(n["title"])))
        if decision == "yes":
            add_note(n, f"named in the OpenReview record of {b['owner']}, confirmed by hand", set(), True)
        elif decision != "no" and in_vietnam(person, year) and not existing(venue, year, n["title"]) \
                and not acc.official(venue, year, n["title"], n.get("forum", "")):
            queue.append({"decision": "", "professor": person["slug"], "venue": venue, "year": str(year),
                          "title": n["title"].strip(), "matched_name": b["name"], "affiliation": "",
                          "url": f"https://openreview.net/forum?id={n['forum']}" if n.get("forum") else "",
                          "reason": f"named as co-author in the OpenReview record of {b['owner']}; the professor's "
                                    f"own record has not been fetched, so the match is by name only"})

    # 2. accepted-paper lists, matched by name: needs the affiliation printed on the paper, or your yes
    seen = set()
    for variant in person["variants"]:
        for paper, i in acc.by_name.get(variant, ()):
            if id(paper) in seen:
                continue
            seen.add(id(paper))
            venue, year = paper["venue"], paper["year"]
            rec = existing(venue, year, paper["title"])
            if rec:  # already known from OpenReview; the official list settles track and outcome
                rec.update(status="accepted", track=paper["track"], pres=paper["pres"] or rec["pres"],
                           people=paper["authors"], self=i, topic=paper.get("topic", ""))
                continue
            aff = paper["authors"][i]["aff"]
            decision = decisions.get((person["slug"], venue, str(year), norm_title(paper["title"])))
            listed = any(o["role"] == "own" and (o["venue"], o["year"]) == (venue, year)
                         and same_title(o["title"], paper["title"]) for o in own)
            abroad = person["vn_since"] is None and aff and not vn_institutions(aff)
            if listed and decision != "no" and not abroad:
                match = "name, and listed on their own page"
            elif same_institution(aff, person):
                match = "name and affiliation"
                if not in_vietnam(person, year) and paper["track"] == "main":
                    warnings.append(f"{person['name']}: '{paper['title'][:60]}' ({VENUE_NAME[venue]} {year}) already "
                                    f"lists {person['institution_short']}, but vn_since is {person['vn_since']}; "
                                    f"check vn_since in roster.csv")
            elif decision == "yes":
                match = "name, confirmed by hand"
            else:
                relevant = decision != "no" and paper["track"] == "main" and in_vietnam(person, year)
                if relevant and aff and not vn_institutions(aff):
                    # same name at a foreign institution: almost always somebody else, so it is only logged
                    skipped.append(f"{person['name']}: skipped '{paper['title'][:60]}' ({VENUE_NAME[venue]} {year}), "
                                   f"author '{paper['authors'][i]['name']}' is listed at {aff}")
                elif relevant:
                    queue.append({"decision": "", "professor": person["slug"], "venue": venue, "year": str(year),
                                  "title": paper["title"], "matched_name": paper["authors"][i]["name"],
                                  "affiliation": aff, "url": paper["url"],
                                  "reason": f"affiliation on the paper is not {person['institution_short']}" if aff
                                  else "the source lists no affiliations"})
                continue
            recs.append({"venue": venue, "year": year, "track": paper["track"], "title": paper["title"],
                         "status": "accepted", "note": "", "pres": paper["pres"], "url": paper["url"],
                         "authors": [a["name"] for a in paper["authors"]], "match": match,
                         "people": paper["authors"], "self": i, "topic": paper.get("topic", "")})
    # 3. papers on personal pages: the professor's own, or a colleague's that names them as co-author.
    #    They confirm a paper of an official list, or stand in for a list that is not complete yet.
    for row in own:
        venue, year, title = row["venue"], row["year"], row["title"].strip()
        if venue not in VENUE_KEYS or year not in YEARS or existing(venue, year, title) or any(
                (r["venue"], r["year"]) == (venue, year) and same_paper(r["title"], title) for r in recs):
            continue
        decision = decisions.get((person["slug"], venue, str(year), norm_title(title)))
        if decision == "no":
            continue
        where = row["label"] if row["role"] == "own" else f"the page of {row['owner']}, as co-author"
        official = acc.find(venue, year, title)
        if official:
            decision = decision or decisions.get((person["slug"], venue, str(year), norm_title(official["title"])))
            if decision == "no":
                continue
            affs = [a["aff"] for a in official["authors"] if a["aff"]]
            if person["vn_since"] is None and decision != "yes" and affs and not any(
                    same_institution(a, person) for a in affs):
                if official["track"] == "main":
                    warnings.append(f"{person['name']}: '{title[:60]}' ({VENUE_NAME[venue]} {year}) is on {where}, but "
                                    f"no author is listed at {person['institution_short']} and vn_since is not "
                                    f"set; not counted")
                continue
            if row["role"] == "own" or decision == "yes":
                recs.append({"venue": venue, "year": year, "track": official["track"], "title": official["title"],
                             "status": "accepted", "note": "", "pres": official["pres"], "url": official["url"],
                             "authors": [a["name"] for a in official["authors"]], "match": f"listed on {where}",
                             "people": official["authors"], "self": None, "topic": official.get("topic", "")})
            elif official["track"] == "main" and in_vietnam(person, year):
                queue.append({"decision": "", "professor": person["slug"], "venue": venue, "year": str(year),
                              "title": official["title"], "matched_name": "", "affiliation": "",
                              "url": official["url"],
                              "reason": f"named as co-author on the page of {row['owner']}, but no author in the "
                                        f"official list has a name form of the roster"})
            continue
        if row["track"] == "main" and (venue, year) in acc.available and (venue, year) not in acc.provisional:
            warnings.append(f"{person['name']}: {where} lists '{title[:60]}' at {VENUE_NAME[venue]} {year}, but the "
                            f"official list of that year does not have it; not counted")
            continue
        people = [{"name": n, "aff": ""} for n in row["authors"]]
        mine = [i for i, a in enumerate(people) if norm_name(a["name"]) in person["variants"]]
        recs.append({"venue": venue, "year": year, "track": row["track"], "title": title, "status": "accepted",
                     "note": "", "pres": "", "url": row["source_url"], "authors": row["authors"],
                     "match": f"listed on {where}; not in the official list yet", "people": people,
                     "self": mine[0] if mine else None, "topic": "", "unofficial": True})
    return recs, source, fetched, stale


def apply_rules(person, recs):
    """(counted, excluded, workshop): counted papers, papers listed as not counted, and workshop papers."""
    counted, excluded, workshop = [], [], []
    for r in recs:
        if r["track"] == "findings":   # a rejection from the main track, and a paper like a workshop paper
            workshop.append({**r, "track": "workshop", "status": "accepted", "workshop": "Findings"})
            r = {**r, "track": "main", "status": "rejected", "note": FINDINGS_NOTE}
        if r["track"] == "workshop":
            workshop.append(r)
        elif r["track"] != "main":
            if r["track"] in TRACK_REASON:
                excluded.append({**r, "reason": TRACK_REASON[r["track"]]})
        elif not in_vietnam(person, r["year"]):
            excluded.append({**r, "reason": f"before {person['vn_since']}, when they joined a Vietnamese institution"})
        elif r["status"] == "unknown":
            excluded.append({**r, "reason": "outcome not known yet"})
        else:
            counted.append(r)
    return counted, excluded, workshop


def mark_later_acceptance(recs, acc):
    """Note on each not-accepted paper whether the same title was accepted later at one of the eight venues.

    Titles often change between submissions, so this finds only some of the resubmissions.
    """
    # main track only: an acceptance in Findings or a workshop is not one of the counted venues
    accepted = [r for r in recs if r["status"] == "accepted" and r.get("track", "main") == "main"]
    for r in recs:
        r["later"] = ""
        if r["status"] not in NOT_ACCEPTED:
            continue
        found = [a for a in accepted if (a["year"], VENUE_KEYS.index(a["venue"])) > (r["year"], -1)
                 and a is not r and same_title(a["title"], r["title"])]
        if not found:  # an accepted paper that was not matched to this person, for example at ACL
            found = [p for v in VENUE_KEYS for y in YEARS if y >= r["year"]
                     for p in [acc.by_title.get((v, y, norm_title(r["title"])))] if p and p["track"] == "main"]
        if found:
            first = min(found, key=lambda a: (a["year"], VENUE_KEYS.index(a["venue"])))
            r["later"] = f"{VENUE_NAME[first['venue']]} {first['year']}"


# ---------------------------------------------------------------- aggregation

def tally(records):
    """{venue: {accepted, official, own_page, rejected, withdrawn, desk_rejected, not_accepted, submitted}}."""
    out = {v: dict.fromkeys(["accepted", *NOT_ACCEPTED, "not_accepted", "submitted", "own_page", "official"], 0)
           for v in VENUE_KEYS}
    for r in records:
        t = out[r["venue"]]
        t[r["status"]] += 1
        t["submitted"] += 1
        if r["status"] in NOT_ACCEPTED:
            t["not_accepted"] += 1
        if r["status"] == "accepted":
            t["own_page" if r.get("unofficial") else "official"] += 1  # own_page: from a personal page only
    return out


def summary(records, acc, counts_from=None):
    """Totals and the year-by-year table for a person, an institution or a venue."""
    years = []
    for y in YEARS:
        in_year = [r for r in records if r["year"] == y]
        t = tally(in_year)
        for v in VENUE_KEYS:
            t[v]["available"] = (v, y) in acc.available
            t[v]["held"] = held(v, y)
            t[v]["provisional"] = (v, y) in acc.provisional
        own = sum(v["own_page"] for v in t.values())
        accepted = sum(r["status"] == "accepted" for r in in_year)
        years.append({"year": y, "counts": counts_from is None or y >= counts_from, "venues": t,
                      "accepted": accepted, "own_page": own, "official": accepted - own})
    accepted = sum(r["status"] == "accepted" for r in records)
    own = sum(bool(r.get("unofficial")) for r in records if r["status"] == "accepted")
    return {"accepted": accepted, "own_page": own, "official": accepted - own, "venues": tally(records),
            "years": years}


def split_topic(label):
    """('Deep Learning', 'Generative Models') from 'Deep Learning->Generative Models' or, in 2023 lists, 'a/b'."""
    area, _, sub = label.partition("->") if "->" in label else label.partition("/")
    area = area.strip()
    return AREA_ALIAS.get(area, area), sub.strip()


def same_person(a, b):
    """Two spellings of one name where one abbreviates a word of the other: 'Bui T Duc' and 'Bui Trong Duc'."""
    a, b = norm_name(a).split(), norm_name(b).split()
    return len(a) == len(b) and all(x == y or (len(x) == 1 and y.startswith(x)) or (len(y) == 1 and x.startswith(y))
                                    for x, y in zip(a, b))


def distinct_people(names):
    """One key per person for a list of author names, so a co-author under two spellings is counted once."""
    groups, keys = [], {}  # each group: the spellings of one person
    for name in names:
        group = next((g for g in groups if any(name_key(n) == name_key(name) or same_person(n, name) for n in g)),
                     None)
        if group is None:
            group = []
            groups.append(group)
        group.append(name)
    for group in groups:
        for name in group:
            keys[name] = name_key(group[0])
    return keys


def collaboration(person, counted, workshop=()):
    """Co-author and topic figures over every counted paper of a person, accepted or not.

    Papers that were not accepted come from OpenReview, which gives author names but no affiliations.

    Foreign and other-institution co-authors can only be told apart where the accepted list prints an
    affiliation for each author, and topics only where the conference labels its papers, so each figure
    comes with the number of papers it is based on. Workshop papers enter only the maximum.
    """
    papers = list(counted)
    accepted_sizes = []  # the minimum is taken over accepted papers only, the maximum over every submission
    sizes, foreign, own, other_vn, everyone, elsewhere, abroad = [], [], [], [], set(), set(), set()
    other_inst = []   # per paper: co-authors at another institution, in Vietnam or abroad
    domestic = []     # per paper: co-authors at an institution in Vietnam, the professor's own included
    areas, topics = collections.Counter(), collections.Counter()
    who = distinct_people([a["name"] for r in papers for a in r["people"]])
    for r in papers:
        me = r["self"]
        if me is None:  # from OpenReview only: find the professor by name
            me = next((i for i, a in enumerate(r["people"]) if norm_name(a["name"]) in person["variants"]), None)
        others = [a for i, a in enumerate(r["people"]) if i != me]
        sizes.append(len(others) if me is not None else max(len(others) - 1, 0))
        if r["status"] == "accepted":
            accepted_sizes.append(sizes[-1])
        if me is not None:
            everyone.update(who[a["name"]] for a in others)
        if me is not None and any(a["aff"] for a in r["people"]):
            outside = [a for a in others if a["aff"] and not vn_institutions(a["aff"])]
            foreign.append(len(outside))
            own.append(sum(1 for a in others if same_institution(a["aff"], person)))
            other_inst.append(sum(1 for a in others if a["aff"] and not same_institution(a["aff"], person)))
            domestic.append(sum(1 for a in others if vn_institutions(a["aff"])))
            other_vn.append(sum(1 for a in others if vn_institutions(a["aff"]) and not same_institution(a["aff"], person)))
            abroad.update(who[a["name"]] for a in outside)
            elsewhere.update(who[a["name"]] for a in others if a["aff"] and not same_institution(a["aff"], person))
        if r["topic"]:
            area, sub = split_topic(r["topic"])
            areas[area] += 1
            topics[(area, sub)] += 1

    def mean(xs):
        return f"{sum(xs) / len(xs):.1f}" if xs else ""

    widest = list(sizes)
    for r in workshop:   # OpenReview names only: leave the professor out by name
        names = [a["name"] for a in r["people"]]
        mine = sum(1 for a in names if norm_name(a) in person["variants"])
        widest.append(len(names) - max(mine, 1) if names else 0)

    return {
        "papers": len(papers), "avg_coauthors": mean(sizes), "distinct_coauthors": len(everyone),
        "min_coauthors": min(accepted_sizes) if accepted_sizes else "", "max_coauthors": max(widest) if widest else "",
        "papers_with_affiliations": len(foreign), "avg_foreign": mean(foreign),
        "avg_same_institution": mean(own), "avg_other_vietnam": mean(other_vn), "avg_other_institution": mean(other_inst), "avg_domestic": mean(domestic),
        "elsewhere": len(elsewhere) if foreign else "", "elsewhere_abroad": len(elsewhere & abroad),
        "elsewhere_vietnam": len(elsewhere - abroad),
        "papers_with_topic": sum(areas.values()), "topic_areas": len(areas) if areas else "",
        "areas": [{"area": a, "papers": n} for a, n in areas.most_common()],
        "topics": [{"area": a, "topic": t, "papers": n} for (a, t), n in sorted(topics.items(), key=lambda x: (-x[1], x[0]))],
    }


def authorship(records, institution):
    """Stricter counts for an institution page: accepted papers whose authors are mostly from the
    institution, and accepted papers whose first author is. Only papers from a list that prints an
    affiliation for each author can be judged; the others are counted in `unknown`."""
    accepted = [r for r in records if r["status"] == "accepted"]
    judged = [r for r in accepted if any(a["aff"] for a in r["people"])]

    def table(rows):
        years = [{"year": y, "venues": {v: sum(1 for r in rows if (r["venue"], r["year"]) == (v, y)) for v in VENUE_KEYS},
                  "total": sum(1 for r in rows if r["year"] == y)} for y in YEARS]
        return {"years": years, "venues": {v: sum(1 for r in rows if r["venue"] == v) for v in VENUE_KEYS},
                "total": len(rows)}

    def at_home(a):
        return same_institution(a["aff"], institution)

    majority = [r for r in judged if 2 * sum(at_home(a) for a in r["people"]) > len(r["people"])]
    first = [r for r in judged if at_home(r["people"][0])]
    by_year = [{"year": y, "accepted": sum(r["year"] == y for r in accepted), "judged": sum(r["year"] == y for r in judged),
                "majority": sum(r["year"] == y for r in majority), "first": sum(r["year"] == y for r in first)}
               for y in YEARS]
    return {"majority": table(majority), "first_author": table(first), "judged": len(judged),
            "unknown": len(accepted) - len(judged), "by_year": by_year}


AUTHOR_CHART_TEXT = {
    "en": {"first": "First author from {inst}", "majority": "Most authors from {inst}",
           "first_other": "First author elsewhere", "majority_other": "Most authors elsewhere",
           "unknown": "No affiliations in the source", "aria": "Accepted papers per year: {what}",
           "tip": "{year}: {n} {what}"},
    "vi": {"first": "Tác giả đầu cùng {inst}", "majority": "Đa số tác giả cùng {inst}",
           "first_other": "Tác giả đầu ở đơn vị khác", "majority_other": "Đa số tác giả ở đơn vị khác",
           "unknown": "Nguồn không ghi đơn vị", "aria": "Bài được nhận theo năm: {what}",
           "tip": "{year}: {n} bài {what}"},
}


def authorship_svg(by_year, kind, inst, counts_from=None, lang="en"):
    """One stacked column per year of accepted papers: from the institution (first author or most authors,
    by `kind`), from elsewhere, and papers whose source prints no affiliations (cannot be judged)."""
    w = AUTHOR_CHART_TEXT[lang]
    width, height, left, right, top, bottom = 640, 260, 40, 12, 46, 30
    plot_w, plot_h = width - left - right, height - top - bottom
    peak = max((r["accepted"] for r in by_year), default=0)
    step = next(s for s in (1, 2, 5, 10, 20, 25, 50, 100) if peak / s <= 5)
    top_value = max(step, step * -(-peak // step))
    base = top + plot_h
    labels = [("own-inst", w[kind].format(inst=inst)), ("other-inst", w[kind + "_other"]), ("unjudged", w["unknown"])]
    out = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" '
           f'aria-label="{html.escape(w["aria"].format(what=labels[0][1]))}">']
    x = left
    for cls, text in labels:
        out.append(f'<rect class="{cls}" x="{x}" y="8" width="12" height="12"/>'
                   f'<text class="label" x="{x + 18}" y="18">{html.escape(text)}</text>')
        x += 30 + 6.4 * len(text)
    value = 0
    while value <= top_value:
        y = base - value / top_value * plot_h
        out.append(f'<line class="{"axis" if value == 0 else "grid"}" x1="{left}" y1="{y:.1f}" x2="{width - right}" '
                   f'y2="{y:.1f}"/><text class="tick" x="{left - 6}" y="{y + 4:.1f}" text-anchor="end">{value}</text>')
        value += step
    band = plot_w / len(by_year)
    bar = min(24, band * 0.5)
    for k, r in enumerate(by_year):
        cx = left + band * (k + 0.5)
        counts = counts_from is None or r["year"] >= counts_from
        out.append(f'<text class="{"tick" if counts else "tick off"}" x="{cx:.1f}" y="{base + 18}" '
                   f'text-anchor="middle">{r["year"]}</text>')
        if not counts or not r["accepted"]:
            continue
        home = r[kind]
        parts = [(cls, v, text) for (cls, text), v in zip(labels, (home, r["judged"] - home, r["accepted"] - r["judged"])) if v > 0]
        low = base
        for n, (cls, v, text) in enumerate(parts):
            high = low - v / top_value * plot_h
            h = max(low - high - (2 if n else 0), 0.5)
            y, xx = low - (2 if n else 0) - h, cx - bar / 2
            rnd = min(4, h) if n == len(parts) - 1 else 0
            shape = (f'M{xx:.1f},{y + h:.1f} V{y + rnd:.1f} Q{xx:.1f},{y:.1f} {xx + rnd:.1f},{y:.1f} H{xx + bar - rnd:.1f} '
                     f'Q{xx + bar:.1f},{y:.1f} {xx + bar:.1f},{y + rnd:.1f} V{y + h:.1f} Z')
            out.append(f'<path class="{cls}" d="{shape}"><title>{html.escape(w["tip"].format(year=r["year"], n=v, what=text[:1].lower() + text[1:]))}</title></path>')
            low = high
        out.append(f'<text class="value" x="{cx:.1f}" y="{low - 6:.1f}" text-anchor="middle">{r["accepted"]}</text>')
    out.append("</svg>")
    return "".join(out)


def authorship_charts(entry, inst, counts_from=None):
    a = entry["authorship"] if "authorship" in entry else entry
    return {kind: {"svg": authorship_svg(a["by_year"], kind, inst, counts_from, "en"),
                   "svg_vi": authorship_svg(a["by_year"], kind, inst, counts_from, "vi")} for kind in ("first", "majority")}


INSTITUTION_CHART_TEXT = {"en": {"inst": "the institution", "aria": "Accepted papers per institution: {what}",
                                  "tip": "{name}: {n} {what}"},
                          "vi": {"inst": "trường", "aria": "Bài được nhận theo trường: {what}", "tip": "{name}: {n} bài {what}"}}


def institution_svg(institutions, kind, peak, lang="en"):
    """One horizontal stacked bar per institution, the most blue first: accepted papers with the first author (or most
    authors, by `kind`) from the institution, from elsewhere, and papers that cannot be judged. Every bar is as long as
    the institution's accepted papers on one scale shared by both charts, so only the blue part moves between them."""
    w, t = AUTHOR_CHART_TEXT[lang], INSTITUTION_CHART_TEXT[lang]
    width, name_w, right, top, row_h, bar_h = 640, 80, 64, 34, 26, 14
    labels = [("own-inst", w[kind].format(inst=t["inst"])), ("other-inst", w[kind + "_other"]), ("unjudged", w["unknown"])]
    def home_of(i):
        return i.get("authorship", i)["majority" if kind == "majority" else "first_author"]["total"]

    institutions = sorted(institutions, key=lambda i: (-home_of(i), -i["accepted"], i["short"]))   # most blue first
    height = top + row_h * len(institutions) + 4
    scale = (width - name_w - right) / (peak or 1)
    out = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" '
           f'aria-label="{html.escape(t["aria"].format(what=labels[0][1]))}">']
    x = 0
    for cls, text in labels:
        out.append(f'<rect class="{cls}" x="{x}" y="8" width="12" height="12"/>'
                   f'<text class="label" x="{x + 18}" y="18">{html.escape(text)}</text>')
        x += 30 + 6.4 * len(text)
    for k, i in enumerate(institutions):
        y = top + k * row_h
        name = i["name_vi"] if lang == "vi" else i["name"]
        a, home = i.get("authorship", i), home_of(i)
        out.append(f'<text class="value" x="{name_w - 8}" y="{y + bar_h - 2}" text-anchor="end">'
                   f'<title>{html.escape(name)}</title>{html.escape(i["short"])}</text>')
        parts = [(cls, v, text) for (cls, text), v in zip(labels, (home, a["judged"] - home, i["accepted"] - a["judged"])) if v > 0]
        xx = name_w
        for n, (cls, v, text) in enumerate(parts):
            seg = max(v * scale - (2 if n < len(parts) - 1 else 0), 1)
            tip = t["tip"].format(name=name, n=v, what=text[:1].lower() + text[1:])
            out.append(charts._bar(cls, xx, y, seg, bar_h, tip, round_end=n == len(parts) - 1))
            xx += seg + 2
        out.append(f'<text class="value" x="{xx + 4:.1f}" y="{y + bar_h - 2}">{home} / {i["accepted"]}</text>')
    out.append(f'<line class="axis" x1="{name_w}" y1="{top - 4}" x2="{name_w}" y2="{height - 4}"/></svg>')
    return "".join(out)


def institution_charts(institutions):
    shown = [i for i in institutions if i["accepted"]]
    peak = max((i["accepted"] for i in shown), default=0)
    out = {kind: {"svg": institution_svg(shown, kind, peak, "en"), "svg_vi": institution_svg(shown, kind, peak, "vi")}
           for kind in ("first", "majority")}
    out["none"] = [i["slug"] for i in institutions if not i["accepted"]]
    return out


def unique(records):
    seen = {}
    for r in records:
        seen.setdefault((r["venue"], r["year"], norm_title(r["title"])), r)
    return list(seen.values())


def page_entry(r, people=None):
    e = {"year": r["year"], "venue": r["venue"], "venue_name": VENUE_NAME[r["venue"]], "title": r["title"],
         "url": r["url"], "status": r["status"], "status_label": STATUS_LABEL[r["status"]], "pres": r["pres"],
         "authors": ", ".join(r["authors"]), "match": r["match"], "note": r.get("note", ""),
         "reason": r.get("reason", ""), "later": r.get("later", ""), "unofficial": bool(r.get("unofficial")),
         "workshop": r.get("workshop", "")}
    if people is not None:
        e["professors"] = people
    return e


def paper_order(r):
    return -r["year"], VENUE_KEYS.index(r["venue"]), r["title"].lower()


def ratio(a, b, pattern="{:.1f}"):
    return pattern.format(a / b) if b else ""


def blog_charts(pooled, rows, by_venue):
    """The figures of the blog post, as SVG. Professors without ICLR records are left out of the ICLR
    figures, where an empty bar would read as 'never rejected', and a professor needs three papers with
    known affiliations to appear in the co-author figure, so one large paper does not set the scale."""
    i = pooled["iclr"]
    outcome = [("s1", "accepted"), ("not", "rejected or withdrawn")]

    def top(candidates, key, n=10):
        """The ten largest by `key`, shown smallest first."""
        return sorted(sorted(candidates, key=key, reverse=True)[:n], key=key)

    known = top([r for r in rows if r["iclr_complete"] and r["iclr"]["submitted"]], lambda r: r["iclr"]["submitted"])
    teams = top([r for r in rows if r["collab"]["papers_with_affiliations"] >= 3],
                lambda r: sum(float(r["collab"][k]) for k in ("avg_same_institution", "avg_other_vietnam", "avg_foreign")))
    busy = top([r for r in rows if r["projection"]], lambda r: int(r["projection"]["total"]))
    hidden = pooled["projected_submissions"] - pooled["projected_accepted"]
    return {
        "outcomes": charts.pies(
            "Accepted and rejected: ICLR as counted, all eight venues as estimated",
            [("ICLR, counted", [("s1", "accepted", i["accepted"]), ("not", "rejected or withdrawn", i["not_accepted"])]),
             ("All eight venues, estimated", [("s1", "accepted", pooled["projected_accepted"]),
                                             ("not", "rejected or withdrawn", hidden)])]),
        "iclr_each": charts.stacked_rows(
            "ICLR submissions per professor by outcome",
            [(r["name"], [r["iclr"]["accepted"], r["iclr"]["not_accepted"]]) for r in known], outcome),
        "trend": charts.lines(
            "Accepted papers of the listed professors per conference and year", YEARS,
            [(f"v{n + 1}", VENUE_NAME[v], by_venue[v]) for n, v in enumerate(VENUE_KEYS)]),
        "teams": charts.stacked_rows(
            "Co-authors per accepted paper, by where they work",
            [(r["name"], [float(r["collab"]["avg_same_institution"]), float(r["collab"]["avg_other_vietnam"]),
                          float(r["collab"]["avg_foreign"])]) for r in teams],
            [("s1", "own institution"), ("s2", "elsewhere in Vietnam"), ("s3", "abroad")]),
        "attempts": charts.stacked_rows(
            "Accepted papers and the submissions behind them, per professor",
            [(r["name"], [r["projection"]["accepted"], r["iclr"]["not_accepted"] if r["iclr_complete"] else 0,
                          int(r["projection"]["estimated"])]) for r in busy],
            [("s1", "accepted"), ("not", "rejected at ICLR"), ("hollow", "rejected elsewhere, estimated")]),
    }


def blog_data(professors, papers, acc, pages, announced):
    """Everything the blog post quotes, so that its numbers follow the data instead of being typed in."""
    complete = {p["slug"] for p in professors if p["iclr_complete"]}
    iclr = dict.fromkeys(["submitted", "accepted", *NOT_ACCEPTED, "not_accepted", "later"], 0)
    by_year = collections.Counter()
    for r in papers:
        if r["venue"] == "iclr" and any(o["slug"] in complete for o in r["_owners"]):
            iclr["submitted"] += 1
            iclr[r["status"]] += 1
            by_year[r["year"]] += 1
            if r["status"] in NOT_ACCEPTED:
                iclr["not_accepted"] += 1
                iclr["later"] += bool(r.get("later"))
    accepted = [r for r in papers if r["status"] == "accepted"]
    teams = [r["people"] for r in accepted if any(a["aff"] for a in r["people"])]
    in_vn = [sum(1 for a in t if vn_institutions(a["aff"])) for t in teams]
    abroad = [sum(1 for a in t if a["aff"] and not vn_institutions(a["aff"])) for t in teams]
    busiest = max(by_year, key=by_year.get) if by_year else 0
    pooled = {
        "professors": len(professors), "professors_with_iclr": len(complete),
        "iclr": {**iclr, "rate": ratio(100 * iclr["accepted"], iclr["submitted"], "{:.0f}%"),
                 "per_accept": ratio(iclr["submitted"], iclr["accepted"]),
                 "not_per_accept": ratio(iclr["not_accepted"], iclr["accepted"]),
                 "busiest_year": busiest, "busiest_year_submitted": by_year.get(busiest, 0)},
        "accepted": len(accepted), "own_page": sum(bool(r.get("unofficial")) for r in accepted),
        # per professor, so the post can quote one person's figures by slug
        "people": {p["slug"]: {"accepted": p["accepted"], "judged": p["authorship"]["judged"],
                               "majority": p["authorship"]["majority"]["total"],
                               "first_author": p["authorship"]["first_author"]["total"]} for p in professors},
        "accepted_by_year": {str(y): sum(r["year"] == y for r in accepted) for y in YEARS},
        "iclr_largest": max((p["venues"]["iclr"] for p in professors if p["iclr_complete"]),
                            key=lambda t: t["submitted"], default={}),
        "accepted_by_venue": {v: sum(r["venue"] == v for r in accepted) for v in VENUE_KEYS},
        # the estimates on the professors' pages added up; a paper of two professors is in both
        "projected_accepted": sum(p["projection"]["accepted"] for p in professors if p["projection"]),
        "projected_submissions": sum(int(p["projection"]["total"]) for p in professors if p["projection"]),
        "projected_rate": ratio(100 * sum(p["projection"]["accepted"] for p in professors if p["projection"]),
                                sum(int(p["projection"]["total"]) for p in professors if p["projection"]), "{:.0f}%"),
        "team_papers": len(teams), "avg_authors": ratio(sum(len(t) for t in teams), len(teams)),
        "avg_authors_vietnam": ratio(sum(in_vn), len(teams)), "avg_authors_abroad": ratio(sum(abroad), len(teams)),
        "papers_with_foreign_author": sum(1 for n in abroad if n),
    }

    rows = []
    for p in professors:
        i, c = p["venues"]["iclr"], p["collab"]
        rows.append({
            "slug": p["slug"], "name": p["name"], "institution_short": p["institution_short"],
            "accepted": p["accepted"], "iclr_complete": p["iclr_complete"], "iclr": i,
            "iclr_rate": ratio(100 * i["accepted"], i["submitted"], "{:.0f}%") if p["iclr_complete"] else "",
            "iclr_per_accept": ratio(i["submitted"], i["accepted"]) if p["iclr_complete"] else "",
            "later": sum(1 for e in p["not_accepted_papers"] if e["venue"] == "iclr" and e["later"]),
            "collab": c, "unconfirmed": bool(p["flags"]),
            "projection": {k: p["projection"][k] for k in ("ratio", "accepted", "estimated", "total")}
            if p["projection"] else None,
        })

    trend = []
    for v in ("iclr", "neurips", "icml"):  # the lists that print an affiliation for every author, every year
        years = []
        for y in YEARS:
            main = [p for p in acc.papers if (p["venue"], p["year"], p["track"]) == (v, y, "main")]
            vn = sum(1 for p in main if any(vn_institutions(a["aff"]) for a in p["authors"]))
            years.append({"year": y, "papers": len(main), "vietnam": vn, "provisional": (v, y) in acc.provisional,
                          "share": ratio(100 * vn, len(main), "{:.2f}%")})
        trend.append({"venue": v, "name": VENUE_NAME[v], "years": years})

    neurips = next(t for t in trend if t["venue"] == "neurips")["years"]
    pooled["neurips_first"], pooled["neurips_last"] = neurips[0], neurips[-1]

    # what the professors' own pages say about NeurIPS, next to the official main-track list
    own_pages, own_years = [], set()
    for p in professors:
        mine = [o for o in pages.get(p["slug"], []) if o["role"] == "own"]
        claims = {y: c for (v, y), c in announced.get(p["slug"], {}).items() if v == "neurips"}
        if not mine and not announced.get(p["slug"]):
            continue
        cells = []
        for y in YEARS:
            listed = sum(1 for o in mine if (o["venue"], o["year"]) == ("neurips", y))
            claim = int(claims[y]["announced"]) if y in claims else 0
            neurips = p["years"][y - YEARS[0]]["venues"]["neurips"]
            other = sum(1 for e in p["excluded_papers"] if (e["venue"], e["year"], e["status"]) == ("neurips", y, "accepted"))
            cells.append({"year": y, "announced": max(listed, claim) or "", "counted": neurips["official"],
                          "own_page": neurips["own_page"], "other_track": other,
                          "detail": claims[y]["note"] if y in claims else ""})
            if max(listed, claim):
                own_years.add(y)
        first = (mine or list(announced[p["slug"]].values()))[0]
        own_pages.append({"slug": p["slug"], "name": p["name"], "source_url": first["source_url"],
                          "fetched": first["fetched"], "neurips": cells,
                          "announced_total": sum(int(c["announced"] or 0) for c in cells)})
    own_pages.sort(key=lambda r: -r["announced_total"])
    for o in own_pages:
        o["neurips"] = [c for c in o["neurips"] if c["year"] in own_years]
    listed_somewhere = {o["slug"] for o in own_pages}
    return {"pooled": pooled, "rows": rows, "trend": trend, "own_pages": own_pages, "own_years": sorted(own_years),
            "charts": blog_charts(pooled, rows, {v: [sum(1 for r in accepted if (r["venue"], r["year"]) == (v, y))
                                                             for y in YEARS] for v in VENUE_KEYS}),
            "without_page": [p["name"] for p in professors if p["slug"] not in listed_somewhere]}


# ---------------------------------------------------------------- submissions per year, estimated

def projection(p):
    """Papers submitted and accepted per year for one professor, with the unknown part estimated.

    Submissions are public for ICLR only. For the other venues the papers that were not accepted are
    estimated from the accepted ones and the professor's own ICLR record, case by case:

        submissions per accepted paper = (ICLR submitted + 1) / (ICLR accepted + 1)

    The +1 on both sides is the usual way to estimate "attempts per success" from a short record: it
    stays finite when nothing was accepted, it does not swing on one paper, and with no ICLR
    submissions at all it gives 1, so nothing is added for a professor whose rejections are unknown.
    """
    i = p["venues"]["iclr"]
    submitted, accepted = (i["submitted"], i["accepted"]) if p["iclr_complete"] else (0, 0)
    ratio = (submitted + 1) / (accepted + 1)
    rows = []
    for y in p["years"]:
        if not y["counts"]:
            rows.append({"year": y["year"], "counts": False})
            continue
        iclr = y["venues"]["iclr"]
        known = iclr["not_accepted"] if p["iclr_complete"] else 0
        elsewhere = y["accepted"] - (iclr["accepted"] if p["iclr_complete"] else 0)
        estimated = elsewhere * (ratio - 1)
        rows.append({"year": y["year"], "counts": True, "accepted": y["accepted"], "iclr_not_accepted": known,
                     "estimated": estimated, "total": y["accepted"] + known + estimated})
    counted = [r for r in rows if r["counts"]]
    if not any(r["total"] for r in counted):
        return None
    out = {"basis": "own" if submitted else "none", "ratio": f"{ratio:.1f}",
           "ratio_submitted": submitted, "ratio_accepted": accepted,
           "accepted": sum(r["accepted"] for r in counted), "total": f"{sum(r['total'] for r in counted):.0f}",
           "estimated": f"{sum(r['estimated'] for r in counted):.0f}",
           "svg": projection_svg(p["name"], rows), "svg_vi": projection_svg(p["name"], rows, "vi")}
    out["rows"] = [{**r, "estimated": f"{r['estimated']:.0f}", "total": f"{r['total']:.0f}"} if r["counts"] else r
                   for r in rows]
    return out


def overview(professors, acc):
    """The front-page figures: accepted papers and the papers behind them, all listed professors together.

    The per-professor estimates (see `projection`) are added up, so a paper of two listed professors is
    counted for each, as on their own pages."""
    years = {y: {"accepted": 0, "recorded": 0, "estimated": 0.0} for y in YEARS}
    for p in professors:
        for r in (p["projection"] or {}).get("rows", []):
            if r["counts"]:
                years[r["year"]]["accepted"] += r["accepted"]
                years[r["year"]]["recorded"] += r["iclr_not_accepted"]
                years[r["year"]]["estimated"] += float(r["estimated"])
    rows = [{"year": y, **v, "estimated": round(v["estimated"])} for y, v in years.items()]
    total = {k: sum(r[k] for r in rows) for k in ("accepted", "recorded", "estimated")}
    provisional = sorted({y for v, y in acc.provisional})
    keys = ["accepted", "recorded", "estimated"]
    out = {
        "total": total, "rows": rows, "provisional": provisional,
        "provisional_lists": [f"{VENUE_NAME[v]} {y}" for v, y in sorted(acc.provisional)],
        "submissions": sum(total.values()),
    }
    for lang, suffix in (("en", ""), ("vi", "_vi")):
        w = CHART_TEXT[lang]
        named = [("acc", w["s_acc"]), ("not", w["s_not"]), ("est", w["s_est"])]
        out["pie" + suffix] = charts.pies(w["pie_label"], [(w["pie_title"], [(c, n, total[k]) for (c, n), k in zip(named, keys)])])
        out["stack" + suffix] = charts.stacked_area(
            w["stack_label"], YEARS, [(c, n, [r[k] for r in rows]) for (c, n), k in zip(named, keys)],
            provisional=provisional, short={w["s_not"]: w["short_not"], w["s_est"]: w["short_est"]},
            words={"total": w["total"], "incomplete": w["incomplete"]})
    return out


# the words drawn inside the charts, per site language
CHART_TEXT = {
    "en": {"aria": "Papers submitted and accepted per year by {name}; the numbers are in the table below",
           "acc": "Accepted", "not": "Rejected at ICLR", "est": "Rejected elsewhere, estimated",
           "tip_acc": "{n} accepted", "tip_not": "{n} rejected at ICLR", "tip_est": "about {n} rejected elsewhere (estimate)",
           "about": "about ", "pie_label": "Accepted, recorded rejected and estimated rejected papers, all listed professors",
           "pie_title": "All years and venues", "stack_label": "Accepted, recorded rejected and estimated rejected papers per year",
           "s_acc": "accepted", "s_not": "rejected at ICLR, recorded", "s_est": "rejected elsewhere, estimated",
           "short_not": "recorded", "short_est": "estimated", "total": "total", "incomplete": "list still being completed"},
    "vi": {"aria": "Số bài nộp và được nhận theo năm của {name}; số liệu ở bảng bên dưới",
           "acc": "Được nhận", "not": "Bị từ chối ở ICLR", "est": "Bị từ chối ở nơi khác, ước tính",
           "tip_acc": "{n} bài được nhận", "tip_not": "{n} bài bị từ chối ở ICLR", "tip_est": "khoảng {n} bài bị từ chối ở nơi khác (ước tính)",
           "about": "~", "pie_label": "Bài được nhận, bị từ chối đếm được và bị từ chối ước tính, tất cả giảng viên trong danh sách",
           "pie_title": "Mọi năm và hội nghị", "stack_label": "Bài được nhận, bị từ chối đếm được và ước tính theo năm",
           "s_acc": "được nhận", "s_not": "bị từ chối ở ICLR, đếm được", "s_est": "bị từ chối ở nơi khác, ước tính",
           "short_not": "đếm được", "short_est": "ước tính", "total": "tổng", "incomplete": "danh sách còn đang bổ sung"},
}


def projection_svg(name, rows, lang="en"):
    """One stacked column per year: accepted, not accepted at ICLR (counted), not accepted elsewhere (estimated).

    The colours are classes styled in static/style.css; every segment carries a <title>, which browsers
    show on hover, and the same numbers are in the table under the chart.
    """
    width, height, left, right, top, bottom = 640, 300, 40, 12, 46, 30
    plot_w, plot_h = width - left - right, height - top - bottom
    peak = max((r["total"] for r in rows if r["counts"]), default=0)
    step = next(s for s in (1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000) if peak / s <= 5)
    top_value = max(step, step * -(-peak // step))
    base = top + plot_h

    def y_of(value):
        return base - value / top_value * plot_h

    w = CHART_TEXT[lang]
    out = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(w["aria"].format(name=name))}">']
    x = left
    for cls in ("acc", "not", "est"):
        out.append(f'<rect class="{cls}" x="{x}" y="8" width="12" height="12"/>'
                   f'<text class="label" x="{x + 18}" y="18">{w[cls]}</text>')
        x += 30 + 6.4 * len(w[cls])
    value = 0
    while value <= top_value:
        y = y_of(value)
        out.append(f'<line class="{"axis" if value == 0 else "grid"}" x1="{left}" y1="{y:.1f}" x2="{width - right}" '
                   f'y2="{y:.1f}"/><text class="tick" x="{left - 6}" y="{y + 4:.1f}" text-anchor="end">{value}</text>')
        value += step
    band = plot_w / len(rows)
    bar = min(24, band * 0.5)
    for k, r in enumerate(rows):
        cx = left + band * (k + 0.5)
        out.append(f'<text class="{"tick" if r["counts"] else "tick off"}" x="{cx:.1f}" y="{base + 18}" '
                   f'text-anchor="middle">{r["year"]}</text>')
        if not r["counts"]:
            continue
        parts = [(cls, v, text) for cls, v, text in [
            ("acc", r["accepted"], w["tip_acc"].format(n=r["accepted"])),
            ("not", r["iclr_not_accepted"], w["tip_not"].format(n=r["iclr_not_accepted"])),
            ("est", r["estimated"], w["tip_est"].format(n=f"{r['estimated']:.0f}"))] if v > 0]
        low = base
        for n, (cls, v, text) in enumerate(parts):
            high = low - v / top_value * plot_h
            h = max(low - high - (2 if n else 0), 0.5)  # a 2px gap in the surface colour separates the segments
            y, x = low - (2 if n else 0) - h, cx - bar / 2
            rnd = min(4, h) if n == len(parts) - 1 else 0  # only the free end of the column is rounded
            shape = (f'M{x:.1f},{y + h:.1f} V{y + rnd:.1f} Q{x:.1f},{y:.1f} {x + rnd:.1f},{y:.1f} H{x + bar - rnd:.1f} '
                     f'Q{x + bar:.1f},{y:.1f} {x + bar:.1f},{y + rnd:.1f} V{y + h:.1f} Z')
            out.append(f'<path class="{cls}" d="{shape}"><title>{r["year"]}: {text}</title></path>')
            low = high
        if r["total"]:
            mark = "" if not r["estimated"] else w["about"]
            out.append(f'<text class="value" x="{cx:.1f}" y="{low - 6:.1f}" text-anchor="middle">'
                       f'{mark}{r["total"]:.0f}</text>')
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------- outputs

def person_links(person):
    """Every public page known for a professor, one entry each: their homepage and other sites, staff and
    publication pages from the roster, each OpenReview profile (merged usernames count as one profile), and
    the DBLP and homepage links their OpenReview profiles give."""
    links, seen = [], set()

    def kind_of(url):
        u = url.lower()
        for pattern, kind in (("aclanthology.org", "acl"), ("dblp.org", "dblp"), ("scholar.google", "scholar"),
                              ("researchgate.net", "researchgate"),
                              ("openreview.net", "openreview"), ("publication", "publications")):
            if pattern in u:
                return kind
        if re.search(r"github\.io|sites\.google|users\.soict|/~|wordpress\.com|\.me/?$|\.info/?$|\.xyz/?$|haxuanson|trongld|khoadoan", u):
            return "homepage"
        return "staff" if re.search(r"\.edu\.vn|vinuni|rmit\.edu|/people/|/staff|/giang-vien|soict\.hust|math\.ac\.vn", u) else "website"

    def add(url, kind=None, label=""):
        key = re.sub(r"^https?://(www\.)?|/+$", "", (url or "").strip().lower())
        if not key or key in seen:
            return
        seen.add(key)
        links.append({"kind": kind or kind_of(url), "url": url.strip(), "label": label})

    add(person["homepage"], {"website": "homepage"}.get(kind_of(person["homepage"] or ""), None))
    f = OPENREVIEW_RAW / f"{person['slug']}.json"
    profiles = json.loads(f.read_text(encoding="utf-8")).get("profiles", []) if f.exists() else []
    known = set()
    for pr in profiles:
        add(f"https://openreview.net/profile?id={pr['id']}", "openreview", pr["id"])
        known |= set(pr.get("usernames", []))
    for pid in person["openreview_ids"]:
        if pid not in known:
            add(f"https://openreview.net/profile?id={pid}", "openreview", pid)
    for page in person["pages"]:
        add(page)
    for pr in profiles:
        add(pr.get("homepage"), "homepage" if kind_of(pr.get("homepage") or "") == "website" else None)
        add(pr.get("dblp"), "dblp")
    return links


def write_stubs(section, items):
    """One content file per page. Everything shown comes from data/, the stub only creates the URL.

    items: (key, title) or (key, title, Vietnamese title)."""
    folder = CONTENT / section
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.md"):
        if not old.name.startswith("_index."):
            old.unlink()
    for key, title, *vi in items:
        for suffix, name in ((".vi.md", vi[0] if vi else title), (".en.md", title)):   # Vietnamese at /, English at /en/
            stub = f"---\ntitle: {json.dumps(name, ensure_ascii=False)}\nkey: {json.dumps(key)}\n---\n"
            (folder / f"{key}{suffix}").write_text(stub, encoding="utf-8")


def main():
    roster = load_roster()
    approved = [p for p in roster if p["approved"] == "yes"]
    coverage = json.loads((WORK / "coverage.json").read_text(encoding="utf-8"))
    acc = Accepted(read_jsonl_gz(ACCEPTED), coverage)
    legacy = load_legacy(roster)
    review_rows, decisions = load_review()
    own_pages, announced = load_self_reported(roster)
    shared = shared_notes(approved, legacy)
    queue, warnings, skipped = [], [], []

    professors, all_counted, hidden, graph_recs = [], [], [], []
    for person in approved:
        recs, source, fetched, stale = person_records(person, acc, legacy, decisions, queue, warnings, skipped,
                                                      own_pages.get(person["slug"], ()),
                                                      shared.get(person["slug"], ()))
        mark_later_acceptance(recs, acc)
        counted, excluded, workshop = apply_rules(person, recs)
        if not counted:
            hidden.append(person["name"])  # on the roster, but shown only once they have a counted submission
            continue
        # without a record of their own, only what a colleague's record happens to show is known
        partial = source == "none" and any(r.get("borrowed") and r["venue"] == "iclr" for r in counted)
        complete = source != "none" or partial
        flags = []   # what is still to confirm is listed on the local Candidates page, not on the public page
        if partial:
            flags.append("Their own OpenReview records have not been fetched. The rejected ICLR papers "
                         "come from the records of co-authors on this site, so there may be more.")
        elif source == "none":
            flags.append("No OpenReview records fetched yet, so only accepted papers are known: "
                         "ICLR submissions and rejections are missing.")
        elif source == "legacy":
            flags.append(f"ICLR records come from a first fetch on {fetched}, which covered ICLR only and did "
                         "not read the decisions of 2020 and 2021. A full fetch will replace them.")
        if stale:
            flags.append("The OpenReview IDs of this professor changed after the last fetch, which has to be repeated.")
        inferred = sum(1 for r in counted if r["note"])
        if inferred:
            flags.append(f"{inferred} outcome(s) inferred because OpenReview had no decision on record.")
        unofficial = sum(1 for r in counted if r.get("unofficial"))
        if unofficial:
            flags.append(f"{unofficial} accepted paper(s) are taken from personal pages and are not in an official "
                         "list yet. They are unofficial until the conference publishes them.")
        for (venue, year), claim in announced.get(person["slug"], {}).items():
            found = sum(1 for r in recs if (r["venue"], r["year"], r["status"]) == (venue, year, "accepted"))
            if int(claim["announced"]) > found and year in YEARS and in_vietnam(person, year):
                flags.append(f"Their page announces {claim['announced']} papers at {VENUE_NAME[venue]} {year}; "
                             f"{found} could be identified.")
        inst_slug = slugify(person["institution_short"])
        s = summary(counted, acc, person["vn_since"])
        professors.append({
            "slug": person["slug"], "name": person["name"], "name_vi": person["name_vi"] or person["name"],
            # the name forms used on papers, shown as "also published as" and given to search engines
            "aliases": [a for a in dict.fromkeys(person["name_forms"]) if norm_name(a) not in
                        {norm_name(person["name"]), norm_name(person["name_vi"] or "")}],
            "institution": person["institution"],
            "institution_short": person["institution_short"], "institution_slug": inst_slug,
            "rank": person["rank"], "homepage": person["homepage"], "vn_since": person["vn_since"] or 0,
            "openreview_ids": person["openreview_ids"], "openreview_source": source, "openreview_fetched": fetched,
            "links": person_links(person),
            "iclr_complete": complete, "flags": flags, **s, "collab": collaboration(person, counted, workshop), "authorship": authorship(counted, person),
            "accepted_papers": [page_entry(r) for r in sorted(counted, key=paper_order) if r["status"] == "accepted"],
            "not_accepted_papers": [page_entry(r) for r in sorted(counted, key=paper_order)
                                    if r["status"] != "accepted"],
            "excluded_papers": [page_entry(r) for r in sorted(excluded, key=paper_order)],
            "workshop_papers": [page_entry(r) for r in sorted(workshop, key=paper_order)],
        })
        all_counted += [{**r, "_who": person} for r in counted]
        # the collaboration graphs use workshop papers too, from the years in Vietnam
        graph_recs += [(r, person["slug"]) for r in counted]
        graph_recs += [(r, person["slug"]) for r in workshop if in_vietnam(person, r["year"])]
    # most accepted first; people with none accepted yet come last, most submissions first
    professors.sort(key=lambda p: (-p["accepted"], -p["venues"]["iclr"]["submitted"] if p["accepted"]
                                   else -sum(v.get("submitted", 0) for v in p["venues"].values()), p["name"]))

    # a paper shared by two professors is one paper for an institution, a venue and the paper list
    owners = collections.defaultdict(list)
    for r in all_counted:
        owners[(r["venue"], r["year"], norm_title(r["title"]))].append(r["_who"])
    papers = unique(all_counted)

    def owned_by(test):
        return [r for r in papers if any(test(p) for p in owners[(r["venue"], r["year"], norm_title(r["title"]))])]

    for p in professors:
        p["projection"] = projection(p)
        p["author_charts"] = authorship_charts(p, p["institution_short"], p["vn_since"] or None)
        # every rejection behind the accepted papers: the ones recorded at ICLR plus the estimate for the other venues
        p["rejected_estimated"] = (round(sum(r["iclr_not_accepted"] + float(r["estimated"])
                                             for r in p["projection"]["rows"] if r["counts"]))
                                   if p["projection"] else None)

    institutions = []
    for slug in sorted({p["institution_slug"] for p in professors}):
        members = [p for p in professors if p["institution_slug"] == slug]
        recs = owned_by(lambda p: slugify(p["institution_short"]) == slug)
        home = {"institution": members[0]["institution"], "institution_short": members[0]["institution_short"]}
        institutions.append({**authorship(recs, home),"slug": slug, "name": members[0]["institution"], "short": members[0]["institution_short"],
                             "professors": [m["slug"] for m in members],
                             "iclr_complete": all(m["iclr_complete"] for m in members),
                             **summary(recs, acc)})
    by_slug = {p["slug"]: p for p in professors}
    for i in institutions:
        # workshop papers of its professors, for reference only; a paper of two of them is one paper
        i["workshop"] = len({(w["venue"], w["year"], norm_title(w["title"]))
                             for m in i["professors"] for w in by_slug[m]["workshop_papers"]})
    for i in institutions:
        # the same estimate as for a professor, from the institution's own ICLR record, so a paper shared by two
        # of its professors counts once: recorded ICLR rejections plus the hidden rejections behind its other papers
        iclr = i["venues"]["iclr"]
        ratio = (iclr["submitted"] + 1) / (iclr["accepted"] + 1)
        elsewhere = i["accepted"] - iclr["accepted"]
        i["rejected_estimated"] = round(iclr["not_accepted"] + elsewhere * (ratio - 1)) if i["accepted"] or iclr["submitted"] else None
    for i in institutions:
        i["author_charts"] = authorship_charts(i, i["short"])
    institutions.sort(key=lambda i: (-i["accepted"], i["name"]))
    # Vietnamese names, confirmed by hand (institution_names.csv); the Vietnamese site shows them
    names_vi = {r["name"]: r["name_vi"] for r in read_csv(BACKEND / "institution_names.csv")}
    for i in institutions:
        i["name_vi"] = names_vi.get(i["name"], i["name"])
    write_json(DATA / "institution_names.json", names_vi)
    write_json(DATA / "institution_charts.json", institution_charts(institutions))

    def with_owners(r):
        who = owners[(r["venue"], r["year"], norm_title(r["title"]))]
        return page_entry(r, [{"slug": p["slug"], "name": p["name"], "name_vi": p["name_vi"]} for p in who])

    venues = []
    for v in VENUES:
        recs = [r for r in papers if r["venue"] == v["key"]]
        venues.append({**v, **summary(recs, acc),
                       "papers": [with_owners(r) for r in sorted(recs, key=paper_order)]})

    # review.csv is append-only from this side, so answers already typed in are never touched
    known = {(r["professor"], r["venue"], r["year"], norm_title(r["title"])) for r in review_rows}
    new = [q for q in queue if (q["professor"], q["venue"], q["year"], norm_title(q["title"])) not in known]
    if new or not REVIEW.exists():
        first = not REVIEW.exists()
        with open(REVIEW, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=REVIEW_FIELDS)
            if first:
                w.writeheader()
            w.writerows(new)
    names = {p["slug"]: p["name"] for p in roster}
    pending = [{**q, "professor_name": names[q["professor"]], "venue_name": VENUE_NAME[q["venue"]]} for q in queue]

    # people whose papers name no university (VinAI, FPT, Vingroup, Viettel...) are not lecturers or
    # professors, so they go to the Not tracked page instead of waiting as candidates
    found = [{**c, "papers": int(c["papers"]), "senior_author": int(c["senior_author"])} for c in read_csv(CANDIDATES)]
    # people whose only papers are at NeurIPS 2026: that year's papers are not on OpenReview yet, so the
    # profile behind the name cannot be checked; they wait on the Not tracked page until they can be
    def neurips_2026_only(c):
        return c["first_year"] == c["last_year"] == "2026" and c["venues"].startswith("NeurIPS ") and "," not in c["venues"]

    candidates = [c for c in found if c["at_university"] == "yes" and not neurips_2026_only(c)]
    companies = [c for c in found if c["at_university"] != "yes"]
    unconfirmed = [c for c in found if c["at_university"] == "yes" and neurips_2026_only(c)]
    shown = candidates[:MAX_CANDIDATES_ON_SITE]
    waiting = [{"name": p["name"], "institution": p["institution_short"], "to_confirm": p["to_confirm"]}
               for p in roster if p["approved"] != "yes" and p["approved"] != "no"]

    # Google Scholar: a one-time snapshot (fetch_scholar.py), shown as it was on the day it was read
    scholar = json.loads((BACKEND / "scholar.json").read_text(encoding="utf-8")) if (BACKEND / "scholar.json").exists() else {}
    for p in professors:
        s = scholar.get(p["slug"])
        if not s:
            p["scholar"] = None
            continue
        years = list(s["by_year"])
        values = [s["by_year"][y] for y in years]
        p["scholar"] = {**{k: v for k, v in s.items() if k != "by_year"},
                        "svg": charts.columns(f"Citations per year, Google Scholar, {s['fetched']}", years, values, "{year}: {n} citations"),
                        "svg_vi": charts.columns(f"Số trích dẫn theo năm, Google Scholar, {s['fetched']}", years, values, "{year}: {n} trích dẫn")}
        if not any(l["kind"] == "scholar" for l in p["links"]):
            p["links"].append({"kind": "scholar", "url": s["url"], "label": ""})

    # pictures checked by hand (images.csv, copied into static/img by fetch_images.py --apply)
    for kind, items, key in (("person", professors, "slug"), ("institution", institutions, "slug"), ("venue", venues, "key")):
        found = {r["key"]: r for r in read_csv(BACKEND / "images.csv") if r["kind"] == kind and r["approved"] == "yes"}
        folder = FRONTEND / "static" / "img" / {"person": "people", "institution": "institutions", "venue": "venues"}[kind]
        for item in items:
            files = sorted(folder.glob(f"{item[key]}.*")) if item[key] in found else []
            item["image"] = f"img/{folder.name}/{files[0].name}" if files else ""
            item["image_source"] = found[item[key]]["source_page"] if files else ""
    write_json(DATA / "overview.json", overview(professors, acc))
    # people in Vietnam with ICLR submissions but no accepted paper (find_iclr_only.py), for the local
    # Candidates page; kept in a separate, git-ignored file because these lists name people who are not on the site
    on_roster = {i for p in roster for i in p["openreview_ids"]}
    attempted = [{**r, "not_accepted": int(r["not_accepted"])} for r in read_csv(BACKEND / "iclr_only.csv")
                 if r["openreview_id"] not in on_roster and not set(r["openreview_id"].split(";")) & on_roster]
    write_json(DATA / "attempted.json", {"people": attempted})
    now = datetime.datetime.now(datetime.timezone.utc)  # UTC, so the data does not show where it was built
    write_json(DATA / "professors.json", professors)
    write_json(DATA / "institutions.json", institutions)
    # rejections behind each venue's accepted papers: counted at ICLR; elsewhere estimated from the ICLR record
    # of everyone listed, (ICLR submitted + 1) / (ICLR accepted + 1) submissions per accepted paper
    pooled = next(v for v in venues if v["key"] == "iclr")["venues"]["iclr"]
    ratio = (pooled["submitted"] + 1) / (pooled["accepted"] + 1)

    def estimated(key, counts):
        if key == "iclr":
            return counts["not_accepted"]
        return round(max(counts["not_accepted"], counts["accepted"] * (ratio - 1)))

    for v in venues:
        v["ratio"] = f"{ratio:.1f}"
        v["rejected_estimated"] = estimated(v["key"], v["venues"][v["key"]])
        for y in v["years"]:
            if y["counts"]:
                y["rejected_estimated"] = estimated(v["key"], y["venues"][v["key"]])
    write_json(DATA / "venues.json", venues)
    shown_by_slug = {p["slug"]: p for p in professors}
    recs_for_graph = [(r, shown_by_slug[s]) for r, s in graph_recs if s in shown_by_slug]
    write_json(DATA / "graph_people.json", graph.researcher_graph(professors, recs_for_graph))
    write_json(DATA / "graph_institutions.json", graph.institution_graph(professors, recs_for_graph))
    write_json(DATA / "papers.json", [with_owners(r) for r in sorted(papers, key=paper_order)])
    for r in papers:
        r["_owners"] = [{"slug": p["slug"]} for p in owners[(r["venue"], r["year"], norm_title(r["title"]))]]
    write_json(DATA / "blog.json", blog_data(professors, papers, acc, own_pages, announced))
    # approved = no: checked and left off for good; `notes` says why
    excluded = [{"name": p["name"], "institution": p["institution_short"], "reason": p["notes"],
                 "homepage": p["homepage"], "openreview_ids": p["openreview_ids"]}
                for p in roster if p["approved"] == "no"]
    write_json(DATA / "candidates.json", {"people": shown, "total": len(candidates), "review": pending,
                                         "waiting": waiting, "excluded": excluded,
                                         "companies": companies, "unconfirmed": unconfirmed,
                                         # hand-kept: faculty in Vietnam known in the press as AI/ML pioneers
                                         "pioneers": read_csv(BACKEND / "pioneers.csv"),
                                         # notes on a professor's record (inferred outcomes, missing records, ...): local only
                                         "flags": [{"slug": p["slug"], "name": p["name"], "text": f} for p in professors for f in p["flags"]],
                                         "to_confirm": [{"slug": p["slug"], "name": p["name"], "institution": p["institution_short"],
                                                         "text": p["to_confirm"]} for p in roster
                                                        if p["approved"] == "yes" and p["to_confirm"]]})
    write_json(DATA / "meta.json", {
        "generated": now.strftime("%Y-%m-%d %H:%M %Z"), "generated_date": now.strftime("%Y-%m-%d"),
        "first_year": YEARS[0], "last_year": YEARS[-1], "years": YEARS,
        "venues": VENUES, "venue_keys": VENUE_KEYS, "venue_groups": VENUE_GROUPS, "coverage": coverage,
        "professors": len(professors), "papers": len(papers),
        "accepted": sum(r["status"] == "accepted" for r in papers),
        "preliminary": any(p["flags"] for p in professors), "pending_review": len(pending),
        "provisional": [{"venue": v, "name": VENUE_NAME[v], "year": y} for v, y in sorted(acc.provisional)],
    })
    write_stubs("professors", [(p["slug"], p["name"], p["name_vi"]) for p in professors])
    write_stubs("institutions", [(i["slug"], i["name"], i["name_vi"]) for i in institutions])
    write_stubs("venues", [(v["key"], v["name"]) for v in venues])

    (WORK / "build_report.txt").write_text("\n".join(warnings + skipped) + "\n", encoding="utf-8")
    print(f"{'professor':24s}{'ICLR sub/acc/not':>18s}" + "".join(f"{VENUE_NAME[v]:>9s}" for v in VENUE_KEYS[1:])
          + f"{'total':>7s}  OpenReview")
    for p in professors:
        i = p["venues"]["iclr"]
        iclr = f"{i['submitted']}/{i['accepted']}/{i['not_accepted']}" if p["iclr_complete"] else f"-/{i['accepted']}/-"
        print(f"{p['name'][:23]:24s}{iclr:>18s}" + "".join(f"{p['venues'][v]['accepted']:9d}" for v in VENUE_KEYS[1:])
              + f"{p['accepted']:7d}  {p['openreview_source']}")
    print(f"\n{len(professors)} professors, {len(papers)} papers -> {DATA.relative_to(BACKEND.parent)}/")
    if hidden:
        print(f"not shown until they have a counted submission: {', '.join(hidden)}")
    if pending:
        print(f"{len(pending)} uncertain matches wait for a yes/no in {REVIEW.name} ({len(new)} new)")
    if skipped:
        print(f"{len(skipped)} same-name papers from foreign institutions skipped, listed in work/build_report.txt")
    for w in warnings:
        print("warning:", w)


if __name__ == "__main__":
    main()
