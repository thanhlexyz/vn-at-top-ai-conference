#!/usr/bin/env python3
"""Fetch Open Text Detector's AI-text share for the ICLR 2027 papers on the site.

Open Text Detector (https://opentextdetector.com) scores the public ICLR 2027 submissions: the share of a paper's
main-text sentences (bibliography and appendices left out) that its detector flags at a 0.1% human false-positive
rate, the site's default view ("body0.1"). A paper with fewer than 50 sentences judged has no figure there, and none
here. Each paper is looked up by its OpenReview forum id; only an item with that exact forum id is taken.

Reads frontend/data/papers.json (build first), writes work/opentextdetector.json (git-ignored):
{forum id: {flagged, sentences, mode, model, fetched, source}}. Resumable; --refresh reads all again.
"""
import argparse
import datetime
import json
import re
import sys
import time
import urllib.parse
import urllib.request

from common import BACKEND, FRONTEND, write_json

OUT = BACKEND / "work" / "opentextdetector.json"
API = "https://opentextdetector.com/backend/v1/browse?"
COLLECTIONS = {("iclr", 2027): "iclr/2027"}
MODE = "body0.1"
MIN_SENTENCES = 50  # the site shows no figure below this


def lookup(collection, forum):
    url = API + urllib.parse.urlencode({"collection": collection, "sort": "title", "page": "0", "q": forum})
    req = urllib.request.Request(url, headers={"User-Agent": "vn-ai-ranking (github.com/thanhlexyz)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        items = json.load(r)["items"]
    return next((i for i in items if i.get("forum_id") == forum), None)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--refresh", action="store_true", help="read every paper again")
    args = ap.parse_args()
    papers = json.loads((FRONTEND / "data" / "papers.json").read_text(encoding="utf-8"))
    known = {} if args.refresh or not OUT.exists() else json.loads(OUT.read_text(encoding="utf-8"))
    todo = {}
    for p in papers:
        m = re.search(r"openreview\.net/forum\?id=([\w-]+)", p["url"] or "")
        if m and (p["venue"], p["year"]) in COLLECTIONS:
            todo[m.group(1)] = COLLECTIONS[(p["venue"], p["year"])]
    missing = []
    for forum, collection in sorted(todo.items()):
        if forum in known:
            continue
        item = lookup(collection, forum)
        counts = (item or {}).get("flags", {}).get(MODE)
        if not counts or counts[1] < MIN_SENTENCES:
            missing.append(forum)
            continue
        known[forum] = {"flagged": counts[0], "sentences": counts[1], "mode": MODE, "model": item.get("flag_model", ""),
                        "fetched": datetime.date.today().isoformat(),
                        "source": f"https://opentextdetector.com/?collection={collection}&q={forum}"}
        print(f"  {forum}: {counts[0]}/{counts[1]} = {100 * counts[0] / counts[1]:.0f}%", file=sys.stderr)
        time.sleep(0.5)
    write_json(OUT, dict(sorted(known.items())))
    print(f"{len(known)} of {len(todo)} papers scored -> {OUT}"
          + (f"; not scored there: {', '.join(missing)}" if missing else ""))


if __name__ == "__main__":
    main()
