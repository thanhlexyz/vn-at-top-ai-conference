"""AI-text score of each paper, read from the paper's own PDF.

For every paper entry of the site (accepted, rejected, withdrawn), this finds the PDF, caches it in raw/pdf/, takes the
running text between the abstract and the reference list (`common.paper_body`, saved to work/ai_text/ for a look) and
scores it with the MELD detector (`meld_scorer.py`, weights installed by fetch_detector_model.py). One row per paper
goes to work/ai_scores.csv; rows already there are kept unless --refresh. The body text of each paper stays in
work/ai_text/ (git-ignored: several are rejected or withdrawn submissions), so a better detector can score the same
texts again with --from-text --refresh. Papers whose PDF is not public are listed
with the reason and no score. Nothing is aggregated per professor or institution.

    python3 fetch_detector_model.py          # once
    python3 score_ai_text.py                 # all papers; --only iclr-2025 or part of a title; --limit 5; --no-score
"""
import argparse
import csv
import gzip
import json
import os
import re
import subprocess
import time
import urllib.request

import verify_affiliations as va
from common import BACKEND, FRONTEND, WORK, ACCEPTED, DETECTOR_REVISION, detector_dir, norm_title, paper_body

PDF_DIR = BACKEND / "raw" / "pdf"
TEXT_DIR = WORK / "ai_text"
OUT = WORK / "ai_scores.csv"
FIELDS = ["venue", "year", "title", "status", "source", "words", "tokens", "sentences", "flagged_sentences",
          "flagged_pct", "score", "p_ai", "flagged", "truncated", "model", "error"]
MIN_WORDS = 300          # shorter running text is not scored (the detector asks for about 100 words at least)
USER_AGENT = "vn-ai-ranking/1.0 (+https://github.com/thanhlexyz/vn-at-top-ai-conference)"


def stem(p):
    return f"paper-{p['venue']}-{p['year']}-{norm_title(p['title'])[:40]}"


def fetch(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    data = urllib.request.urlopen(req, timeout=120).read()
    if not data.startswith(b"%PDF"):
        raise ValueError("not a PDF")
    path.write_bytes(data)
    time.sleep(1)


class OpenReviewPDFs:
    """PDFs of OpenReview submissions, through the logged-in API (v2, then the older v1)."""

    def __init__(self):
        self.clients = None

    def get(self, forum):
        if self.clients is None:
            import openreview
            user, password = os.environ["OPENREVIEW_USERNAME"], os.environ["OPENREVIEW_PASSWORD"]
            self.clients = [openreview.api.OpenReviewClient(baseurl="https://api2.openreview.net", username=user, password=password),
                            openreview.Client(baseurl="https://api.openreview.net", username=user, password=password)]
        for client in self.clients:
            for wait in (0, 30, 90, 240):          # OpenReview answers "Too many requests" when pushed
                time.sleep(wait)
                try:
                    data = client.get_attachment(id=forum, field_name="pdf")
                except Exception as exc:
                    if "RateLimit" in str(exc) or "Too many requests" in str(exc):
                        continue
                    break
                if data and data.startswith(b"%PDF"):
                    time.sleep(4)
                    return data
                break
            else:
                raise RuntimeError("OpenReview rate limit")
        return None


def locate(p, listed, openreview):
    """Cache the PDF of paper `p`; returns (path or None, why not)."""
    path = PDF_DIR / f"{stem(p)}.pdf"
    old = PDF_DIR / f"check-{p['venue']}-{p['year']}-{norm_title(p['title'])[:40]}.pdf"
    if path.exists():
        return path, ""
    if old.exists():
        return old, ""
    entry = listed.get((p["venue"], p["year"], norm_title(p["title"])), {})
    url, forum = p["url"], ""
    if "openreview.net/forum?id=" in url:
        forum = url.split("id=")[-1].split("&")[0]
    forum = forum or entry.get("forum", "")
    try:
        if forum:
            data = openreview.get(forum)
            if data:
                path.write_bytes(data)
                return path, ""
            return None, "OpenReview does not serve the PDF"
        link = None
        if "aclanthology.org" in url:
            link = url.rstrip("/") + ".pdf"
        elif "thecvf.com" in url and "/html/" in url:
            link = url.replace("/html/", "/papers/").replace(".html", ".pdf")
        elif p["venue"] in ("cvpr", "iccv"):
            link = va.cvf_pdf(p["venue"], p["year"], p["title"])
        elif p["venue"] == "eccv":
            link = va.ecva_pdf(p["title"])
        elif p["venue"] == "icml":
            link = va.pmlr_pdf(p["year"], p["title"], url)
        elif p["venue"] in ("aaai", "ijcai"):
            link = entry.get("pdf")
        if not link:
            return None, "no public PDF address"
        fetch(link, path)
        return path, ""
    except Exception as exc:
        return None, f"download failed ({str(exc)[:60]})"


SENTENCE_END = re.compile(r"[.!?][\"\u201d\u2019')\]]*\s+|\n\s*\n")
MIN_SENTENCE_TOKENS = 8      # fragments (captions, list items) are too short to judge


def score_text(scorer, text):
    """Document score and share of flagged sentences, from one pass of the detector over the body text.

    Document: as `Scorer.score` (mean of the top quarter of token scores; flagged above the 1% false-positive
    threshold). Sentences: the mean token score of a sentence above that same threshold, as the upstream workbench
    marks its sentences. The threshold is calibrated for whole documents, so the share is an indicator, not a rate."""
    import math
    import torch
    from meld_scorer import canonicalize, top_quantile_mean
    text = canonicalize(text) if scorer.canonical else text
    enc = scorer.tok(text, add_special_tokens=False, truncation=False, return_offsets_mapping=True)
    ids, offsets = enc["input_ids"][:scorer.cap], enc["offset_mapping"][:scorer.cap]
    scores = []
    with torch.no_grad():
        for i in range(0, len(ids), scorer.window):
            w = ids[i:i + scorer.window]
            inp = torch.tensor([[scorer.cls_id, *w, scorer.sep_id]], device=scorer.device)
            _, c_tok, _ = scorer.model.token_scores(inp, torch.ones_like(inp))
            scores += c_tok[0, 1:1 + len(w)].cpu().tolist()
    doc = float(top_quantile_mean(torch.tensor(scores), scorer.rho))
    cuts = sorted({0, len(text), *(m.end() for m in SENTENCE_END.finditer(text))})
    sentences = flagged = 0
    for a, b in zip(cuts, cuts[1:]):
        inside = [v for v, (x, y) in zip(scores, offsets) if y > x and a <= (x + y) / 2 < b]
        if len(inside) >= MIN_SENTENCE_TOKENS:
            sentences += 1
            flagged += sum(inside) / len(inside) > scorer.threshold
    return {"tokens": len(ids), "sentences": sentences, "flagged_sentences": flagged,
            "flagged_pct": round(100 * flagged / sentences, 1) if sentences else "",
            "score": round(doc, 4), "p_ai": round(1 / (1 + math.exp(-doc)), 4), "flagged": "yes" if doc > scorer.threshold else "no",
            "truncated": "yes" if len(enc["input_ids"]) > scorer.cap else ""}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="", help="venue-year (iclr-2025) or part of a title")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--refresh", action="store_true", help="score again papers already in ai_scores.csv")
    ap.add_argument("--no-score", action="store_true", help="only download the PDFs")
    ap.add_argument("--from-text", action="store_true",
                    help="score the saved texts in work/ai_text/ again (a new detector), without any PDF")
    a = ap.parse_args()
    papers = json.load(open(FRONTEND / "data" / "papers.json"))
    if a.only:
        papers = [p for p in papers if a.only.lower() in f"{p['venue']}-{p['year']}" or a.only.lower() in p["title"].lower()]
    listed = {}
    for line in gzip.open(ACCEPTED, "rt"):
        e = json.loads(line)
        listed[(e["venue"], int(e["year"]), norm_title(e["title"]))] = e
    rows = {}
    if OUT.exists():
        for r in csv.DictReader(open(OUT, newline="")):
            rows[(r["venue"], int(r["year"]), norm_title(r["title"]))] = r
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    openreview, scorer, done = OpenReviewPDFs(), None, 0
    for p in papers:
        key = (p["venue"], p["year"], norm_title(p["title"]))
        if key in rows and not a.refresh and not (rows[key]["error"] and "download" in rows[key]["error"]):
            continue
        if a.limit and done >= a.limit:
            break
        done += 1
        row = {"venue": p["venue"], "year": p["year"], "title": p["title"], "status": p["status"], "source": "",
               "words": "", "tokens": "", "sentences": "", "flagged_sentences": "", "flagged_pct": "", "score": "",
               "p_ai": "", "flagged": "", "truncated": "", "model": "", "error": ""}
        saved = TEXT_DIR / f"{stem(p)}.txt"
        if a.from_text:
            path, why = (saved, "") if saved.exists() else (None, "no saved text")
        else:
            path, why = locate(p, listed, openreview)
        if path is None:
            row["error"] = why
        else:
            row["source"] = path.name
            if a.from_text:
                text = saved.read_text()
            else:
                text = paper_body(subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True).stdout)
                saved.write_text(text)
            row["words"] = len(text.split())
            if row["words"] < MIN_WORDS:
                row["error"] = f"under {MIN_WORDS} words of running text"
            elif not a.no_score:
                if scorer is None:
                    from meld_scorer import Scorer
                    scorer = Scorer(str(detector_dir()))
                row.update(score_text(scorer, text))
                row["model"] = f"meld-v8@{DETECTOR_REVISION[:7]}"
        rows[key] = row
        pct = f"{row['flagged_pct']}%" if row["flagged_pct"] != "" else ""
        print(f"{p['venue']:7}{p['year']} {pct or row['error'] or 'downloaded':>8} {row['p_ai']:>7} {p['title'][:60]}", flush=True)
        with open(OUT, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows.values())
    got = [r for r in rows.values() if r["p_ai"]]
    print(f"{len(got)} scored, {sum(1 for r in rows.values() if r['error'])} without a score; see {OUT}")


if __name__ == "__main__":
    main()
