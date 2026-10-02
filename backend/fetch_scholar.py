#!/usr/bin/env python3
"""A one-time snapshot of each professor's Google Scholar profile: citations, h-index, i10-index and
citations per year.

    python3 fetch_scholar.py            # find the profiles and read them -> scholar.json

A profile is used only when it comes from a trustworthy link: the Google Scholar field of the professor's
own OpenReview profile, or a link to Scholar on their homepage or staff page in the roster. Google Scholar
refuses name searches from scripts, so a professor without such a link gets no Scholar figures. The
snapshot is not refreshed by `make data`; run this script again to update it.
"""
import datetime
import html
import json
import os
import re
import subprocess
import sys
import time

from common import BACKEND, OPENREVIEW_RAW, load_roster, norm_name

OUT = BACKEND / "scholar.json"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
SCHOLAR_ID = re.compile(r"scholar\.google\.[a-z.]+/citations\?(?:[^\"'<> ]*&(?:amp;)?)?user=([A-Za-z0-9_-]{12})")


def get(url):
    return subprocess.run(["curl", "-sL", "--max-time", "40", "-A", UA, url], capture_output=True).stdout.decode("utf-8", "ignore")


def from_openreview():
    """Scholar IDs written on the professors' OpenReview profiles (needs the OpenReview login)."""
    import openreview
    from fetch_openreview import login
    v2, _ = login()
    found = {}
    for p in load_roster():
        if p["approved"] != "yes":
            continue
        f = OPENREVIEW_RAW / f"{p['slug']}.json"
        ids = [pr["id"] for pr in json.loads(f.read_text()).get("profiles", [])] if f.exists() else p["openreview_ids"][:1]
        for pid in ids:
            try:
                g = v2.get_profile(pid).content.get("gscholar") or ""
            except Exception:
                continue
            m = SCHOLAR_ID.search(g)
            if m:
                found[p["slug"]] = (m.group(1), f"OpenReview profile {pid}")
                break
            time.sleep(0.5)
    return found


def from_pages():
    """Scholar IDs linked from the homepages and staff pages on the roster."""
    found = {}
    for p in load_roster():
        if p["approved"] != "yes":
            continue
        pages = [x for x in [p["homepage"], *p["pages"]] if x]
        f = OPENREVIEW_RAW / f"{p['slug']}.json"
        if f.exists():
            pages += [pr["homepage"] for pr in json.loads(f.read_text()).get("profiles", []) if pr.get("homepage")]
        for page in dict.fromkeys(pages):
            m = SCHOLAR_ID.search(get(page))
            if m:
                found[p["slug"]] = (m.group(1), page)
                break
    return found


def read_profile(user):
    h = get(f"https://scholar.google.com/citations?hl=en&user={user}")
    if "gsc_prf_in" not in h:
        return None
    text = lambda m: html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""
    table = [int(x) for x in re.findall(r'<td class="gsc_rsb_std">(\d+)</td>', h)]
    since = re.search(r'<th class="gsc_rsb_sth">Since (\d{4})</th>', h)
    years = [int(y) for y in re.findall(r'<span class="gsc_g_t"[^>]*>(\d{4})</span>', h)]
    counts = [int(c) for c in re.findall(r'<span class="gsc_g_al">(\d+)</span>', h)]
    # a year without citations has no bar; the bars carry their year's position in z-index order
    bars = re.findall(r'<a href="[^"]*"[^>]*class="gsc_g_a"[^>]*style="[^"]*z-index:(\d+)[^"]*"[^>]*><span class="gsc_g_al">(\d+)</span>', h)
    by_year = {}
    if bars and years:
        last = years[-1]
        for z, c in bars:
            by_year[last - int(z) + 1] = int(c)
    elif len(years) == len(counts):
        by_year = dict(zip(years, counts))
    return {
        "user": user, "url": f"https://scholar.google.com/citations?user={user}",
        "name": text(re.search(r'<div id="gsc_prf_in">(.*?)</div>', h)),
        "affiliation": text(re.search(r'<div class="gsc_prf_il">(.*?)</div>', h)),
        "citations": table[0] if len(table) > 0 else 0, "citations_since": table[1] if len(table) > 1 else 0,
        "h_index": table[2] if len(table) > 2 else 0, "h_index_since": table[3] if len(table) > 3 else 0,
        "i10_index": table[4] if len(table) > 4 else 0, "i10_index_since": table[5] if len(table) > 5 else 0,
        "since": int(since.group(1)) if since else None,
        "by_year": {str(y): by_year.get(y, 0) for y in range(min(by_year), max(by_year) + 1)} if by_year else {},
    }


def main():
    found = from_pages()
    if os.environ.get("OPENREVIEW_USERNAME"):
        for slug, v in from_openreview().items():
            found.setdefault(slug, v)
    data = json.loads(OUT.read_text()) if OUT.exists() else {}
    today = datetime.date.today().isoformat()
    for slug, (user, source) in sorted(found.items()):
        prof = read_profile(user)
        if not prof:
            print(f"  {slug}: profile {user} could not be read", file=sys.stderr)
            continue
        person = next(p for p in load_roster() if p["slug"] == slug)
        mine = set(norm_name(" ".join([person["name"], *person["variants"], person.get("name_vi", "")])).split())
        if len(mine & set(norm_name(prof["name"]).split())) < 2:   # a co-author's or advisor's profile linked from the page
            print(f"  {slug}: skipped {user}, the profile is {prof['name']}", file=sys.stderr)
            continue
        data[slug] = {**prof, "found_on": source, "fetched": today}
        print(f"  {slug}: {prof['name']} | {prof['affiliation'][:50]} | cited by {prof['citations']}, h {prof['h_index']}", file=sys.stderr)
        time.sleep(4)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(data)} profiles -> {OUT}")


if __name__ == "__main__":
    main()
