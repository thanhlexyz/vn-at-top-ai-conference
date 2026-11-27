import datetime
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from common import FRONTEND, VENUE_GROUPS, WORK, norm_title, slugify


def _timeouts():
    import requests

    original = requests.Session.request

    def request(self, *args, **kwargs):
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = 60
        return original(self, *args, **kwargs)
    requests.Session.request = request


_timeouts()

PDF_DIR = WORK / "pdf"
OUT = WORK / "challenges"
FORUMS = WORK / "challenge_forums.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; paper archive script)"}
OPENREVIEW = {"iclr", "neurips", "icml"}
AREA = {v: g["key"] for g in VENUE_GROUPS for v in g["venues"]}
SKIP_FIELDS = {"title", "authors", "authorids", "pdf", "supplementary_material", "code_of_ethics", "submission_guidelines",
               "reciprocal_reviewing", "anonymous_url", "no_acknowledgement_section", "venue", "venueid", "_bibtex",
               "paperhash", "keywords", "primary_area", "TLDR", "abstract", "flagged_for_ethics_review"}
KINDS = [("Decision", ("Decision",)), ("Meta-review", ("Meta_Review",)), ("Review", ("Official_Review",))]
SECTION = re.compile(r"^\s*(?:\d+(?:\.\d+)?\.?\s+|[A-Z]\.?\s+)?(limitations?(?: and future (?:work|directions))?|future work|"
                     r"future directions?|conclusions?(?: and future work)?|discussion(?: and limitations)?|"
                     r"concluding remarks|open problems?|broader impacts?)\s*$", re.I | re.M)
NEXT = re.compile(r"^\s*(?:\d+(?:\.\d+)?\.?\s+[A-Z]|references\s*$|acknowledg|appendix|[A-Z]\s+[A-Z][a-z]+)", re.M)
ADMIT = re.compile(r"\b(?:future work|left (?:as|for) future|remains? (?:an )?open|open (?:problem|question|challenge)|"
                   r"we (?:do not|don't|cannot|can not) (?:yet )?(?:handle|support|scale|address)|limitation|"
                   r"is (?:still )?(?:limited|restricted) to|does not scale|beyond the scope|we leave)\b", re.I)
REVIEW_FIELDS = re.compile(r"\*\*(Metareview|Weaknesses|Questions|Limitations|Summary of weaknesses|Requested changes|"
                           r"Review|Main review|Strengths and weaknesses|Additional comments on reviewer discussion):\*\*"
                           r"\s*(.*?)(?=\n\*\*[A-Z][\w ]+:\*\*|\n## |\Z)", re.S)
PAPER_CHARS, REVIEW_CHARS = 3000, 3000


def paper_id(p):
    return f"{p['venue']}{p['year']}-{slugify(p['title'])[:60]}"


def get(url, timeout=120):
    for wait in (20, 60, 0):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code != 429 or not wait:
                print(f"    {url}: {e}", file=sys.stderr)
                return None
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as e:
            print(f"    {url}: {e}", file=sys.stderr)
            return None


def is_pdf(data):
    return bool(data) and data[:5] == b"%PDF-"


def forum_of(p):
    m = re.search(r"openreview\.net/(?:forum|pdf)\?id=([\w-]+)", p.get("url") or "")
    return m.group(1) if m else ""


def direct_urls(p):
    url = p.get("url") or ""
    out = []
    if "aclanthology.org" in url:
        out.append(url.rstrip("/") + ".pdf")
    m = re.match(r"https?://www\.ijcai\.org/proceedings/(\d{4})/(\d+)", url)
    if m:
        out.append(f"https://www.ijcai.org/proceedings/{m[1]}/{int(m[2]):04d}.pdf")
    if "openaccess.thecvf.com" in url and url.endswith(".html"):
        out.append(url.replace("/html/", "/papers/").replace(".html", ".pdf"))
    m = re.match(r"https?://proceedings\.mlr\.press/(v\d+)/([\w-]+)\.html", url)
    if m:
        out.append(f"https://proceedings.mlr.press/{m[1]}/{m[2]}/{m[2]}.pdf")
    return out


def openalex_urls(title):
    q = urllib.parse.urlencode({"search": title, "per-page": 5, "select": "title,best_oa_location,locations",
                                **({"api_key": os.environ["OPENALEX_API_KEY"]} if os.environ.get("OPENALEX_API_KEY") else {})})
    data = get(f"https://api.openalex.org/works?{q}", timeout=60)
    out = []
    if not data:
        return out
    for w in json.loads(data).get("results", []):
        if norm_title(w.get("title") or "") != norm_title(title):
            continue
        for loc in [w.get("best_oa_location") or {}, *(w.get("locations") or [])]:
            u = (loc or {}).get("pdf_url")
            if u and "ojs.aaai.org" not in u and "ieeexplore" not in u and u not in out:
                out.append(u.replace("arxiv.org/abs/", "arxiv.org/pdf/"))
    return out


def arxiv_urls(title):
    q = urllib.parse.urlencode({"search_query": f'ti:"{re.sub(r"[^A-Za-z0-9 ]", " ", title)}"', "max_results": 5})
    data = get(f"https://export.arxiv.org/api/query?{q}", timeout=60)
    time.sleep(3)
    out = []
    for entry in re.findall(r"<entry>(.*?)</entry>", (data or b"").decode("utf-8", "ignore"), re.S):
        t = re.search(r"<title>(.*?)</title>", entry, re.S)
        i = re.search(r"<id>http://arxiv\.org/abs/([^<]+)</id>", entry)
        if t and i and norm_title(re.sub(r"\s+", " ", t.group(1))) == norm_title(title):
            out.append(f"https://arxiv.org/pdf/{i.group(1)}")
    return out


def fetch_pdfs(papers):
    have, got, missing = 0, 0, []
    for p in papers:
        dest = PDF_DIR / AREA[p["venue"]] / f"{paper_id(p)}.pdf"
        if dest.exists() and is_pdf(dest.read_bytes()[:5]):
            have += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        done = False
        for stage in (direct_urls, lambda p: openalex_urls(p["title"]), lambda p: arxiv_urls(p["title"])):
            for url in stage(p):
                data = get(url)
                time.sleep(3 if "arxiv.org" in url else 1)
                if is_pdf(data):
                    dest.write_bytes(data)
                    got += 1
                    done = True
                    print(f"  {paper_id(p)}: {url}", file=sys.stderr)
                    break
            if done:
                break
        if not done:
            missing.append(p)
    print(f"PDFs: {have} already there, {got} downloaded, {len(missing)} missing", file=sys.stderr)
    for p in missing:
        print(f"  missing: {p['venue_name']} {p['year']} | {p['title'][:80]} | {p.get('url')}", file=sys.stderr)


def val(x):
    return x.get("value") if isinstance(x, dict) else x


def invitations(n):
    return getattr(n, "invitations", None) or [getattr(n, "invitation", "") or ""]


def review_markdown(p, forum, notes):
    sections = []
    for heading, suffixes in KINDS:
        picked = [n for n in notes if n.id != n.forum and any(i.endswith(s) for i in invitations(n) for s in suffixes)]
        picked.sort(key=lambda n: getattr(n, "cdate", 0) or getattr(n, "tcdate", 0) or 0)
        for k, n in enumerate(picked, 1):
            lines = [f"## {heading if len(picked) == 1 else f'{heading} {k}'}"]
            for field, value in n.content.items():
                body = val(value)
                body = ", ".join(map(str, body)) if isinstance(body, list) else str(body or "").strip()
                if field in SKIP_FIELDS or not body:
                    continue
                lines.append(f"**{field.replace('_', ' ').capitalize()}:** {body}")
            sections.append("\n\n".join(lines))
    if not sections:
        return ""
    return (f"# {p['title']}\n\n{p['venue_name']} {p['year']} ({p['status']}) · https://openreview.net/forum?id={forum}"
            f" · fetched {datetime.date.today().isoformat()}\n\n" + "\n\n".join(sections) + "\n")


def fetch_reviews(papers):
    from fetch_openreview import login

    v2, v1 = login()
    clients = [c for c in (v2, v1) if c is not None]
    saved = 0
    for p in papers:
        forum = forum_of(p)
        dest = PDF_DIR / AREA[p["venue"]] / f"{paper_id(p)}.md"
        if not forum or dest.exists():
            saved += dest.exists()
            continue
        notes = []
        for c in clients:
            try:
                notes = c.get_all_notes(forum=forum)
            except Exception as e:
                print(f"    {forum}: {str(e)[:80]}", file=sys.stderr)
            if notes:
                break
        md = review_markdown(p, forum, notes)
        if md:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(md, encoding="utf-8")
            saved += 1
        print(f"  {paper_id(p)}: {'reviews' if md else 'no public reviews'}", file=sys.stderr)
        time.sleep(0.5)
    print(f"reviews saved for {saved} papers", file=sys.stderr)


def fetch_openreview_pdfs(papers):
    from fetch_openreview import login

    v2, _ = login()
    got = 0
    for p in papers:
        dest = PDF_DIR / AREA[p["venue"]] / f"{paper_id(p)}.pdf"
        if dest.exists():
            continue
        try:
            data = v2.get_pdf(forum_of(p))
        except Exception as e:
            print(f"    {paper_id(p)}: {str(e)[:80]}", file=sys.stderr)
            data = None
        if is_pdf(data):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            got += 1
        time.sleep(1)
    print(f"OpenReview PDFs: {got} downloaded", file=sys.stderr)


def squash(text):
    return re.sub(r"\s+", " ", text).strip()


def paper_text(pdf):
    run = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, timeout=120)
    text = run.stdout.decode("utf-8", "ignore")
    cut = re.search(r"^\s*references\s*$", text, re.I | re.M)
    body = text[:cut.start()] if cut else text
    parts = []
    for m in SECTION.finditer(body):
        rest = body[m.end():m.end() + 4000]
        stop = NEXT.search(rest, 200)
        parts.append(f"[{m.group(1).strip()}] " + squash(rest[:stop.start()] if stop else rest))
    parts.sort(key=lambda x: not re.match(r"\[(limitation|future|open problem|discussion)", x, re.I))
    admits = [x for x in re.split(r"(?<=[.!?])\s+", squash(body)) if len(x) < 600 and ADMIT.search(x)]
    seen, out = set(), []
    for s in parts + admits:
        if s[:80] not in seen:
            seen.add(s[:80])
            out.append(s)
    return " … ".join(out)[:PAPER_CHARS]


def review_text(md):
    text = md.read_text(encoding="utf-8", errors="ignore")
    seen, out = set(), []
    for k, v in REVIEW_FIELDS.findall(text):
        v = squash(v)
        if v[:120] in seen:
            continue
        seen.add(v[:120])
        out.append(f"[{k}] {v[:700]}")
    return " … ".join(out)[:REVIEW_CHARS]


TOPIC_COLORS = ["tc0", "tc1", "tc2", "tc3", "tc4", "tc5"]
STOPWORDS = set("""a an the and or of for in on to by via with from as at is are be been this that these those we our it its their
which while where when what how than then such can may also into over under between based using use used new novel approach
approaches method methods model models paper propose proposed show shows results result data task tasks learning framework
existing however both each more most other only one two three first via through across without within about large significantly
state art performance achieve achieves improve improves improved study work works problem problems different set even often
well high low further many several various strong without while including include provide provides make makes thus extensive
experiments experimental demonstrate demonstrates benchmark benchmarks effective efficient""".split())


def reference_text(pdf):
    run = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, timeout=120)
    text = run.stdout.decode("utf-8", "ignore")
    m = re.search(r"^\s*references\s*$", text, re.I | re.M)
    return norm_title(text[m.end():] if m else text[-60000:])


def citations(mine):
    out = []
    by_year = {x["id"]: x["year"] for x in mine}
    keys = {x["id"]: norm_title(x["title"]) for x in mine}
    for x in mine:
        pdf = PDF_DIR / AREA[x["venue"]] / f"{x['id']}.pdf"
        if not pdf.exists():
            continue
        refs = reference_text(pdf)
        for y in mine:
            if y["id"] != x["id"] and len(keys[y["id"]]) > 25 and keys[y["id"]] in refs and by_year[y["id"]] <= by_year[x["id"]]:
                out.append({"from": x["id"], "to": y["id"]})
    return out


def topic_words(groups, mine, cache, n=6):
    import collections
    import math

    def words(text):
        ws = [w for w in re.findall(r"[a-z][a-z0-9-]{2,}", text.lower()) if w not in STOPWORDS]
        return ws + [f"{a} {b}" for a, b in zip(ws, ws[1:])]
    docs = []
    for g in groups:
        text = " ".join(x["title"] + " " + (cache.get(x["id"]) or "") for x in mine if x["id"] in g["papers"])
        docs.append(collections.Counter(words(text)))
    df = collections.Counter(w for d in docs for w in d)
    out = []
    for d in docs:
        scored = {w: c * math.log(1 + len(docs) / df[w]) * (1.6 if " " in w else 1) for w, c in d.items() if c >= 2}
        top = sorted(scored.items(), key=lambda kv: -kv[1])
        picked = []
        for w, v in top:
            if any(w in q or q in w for q, _ in picked):
                continue
            picked.append((w, v))
            if len(picked) == n:
                break
        m = picked[0][1] if picked else 1
        out.append([{"word": w, "share": round(100 * v / m)} for w, v in picked])
    return out


def is_other(g):
    return g["title"].lower().startswith("other")


def order_topics(groups, mine, cache, cites):
    import collections
    import math

    year = {x["id"]: x["year"] for x in mine}
    rest = [g for g in groups if not is_other(g)]
    other = [g for g in groups if is_other(g)]
    if len(rest) < 3:
        return sorted(rest, key=lambda g: -sum(year[i] for i in g["papers"]) / len(g["papers"])) + other

    def vec(g):
        text = " ".join(x["title"] + " " + (cache.get(x["id"]) or "") for x in mine if x["id"] in g["papers"])
        return collections.Counter(w for w in re.findall(r"[a-z][a-z0-9-]{3,}", text.lower()) if w not in STOPWORDS)
    vecs = {id(g): vec(g) for g in rest}
    df = collections.Counter(w for v in vecs.values() for w in v)

    def weight(v):
        return {w: c * math.log(1 + len(rest) / df[w]) for w, c in v.items()}
    wv = {k: weight(v) for k, v in vecs.items()}

    def cos(a, b):
        num = sum(a[w] * b.get(w, 0) for w in a)
        den = math.sqrt(sum(x * x for x in a.values())) * math.sqrt(sum(x * x for x in b.values())) or 1
        return num / den
    topic_of = {i: id(g) for g in rest for i in g["papers"]}
    linked = collections.Counter()
    for e in cites:
        a, b = topic_of.get(e["from"]), topic_of.get(e["to"])
        if a and b and a != b:
            linked[frozenset((a, b))] += 1
    recency = {id(g): sum(year[i] for i in g["papers"]) / len(g["papers"]) for g in rest}
    lo, hi = min(recency.values()), max(recency.values())
    fresh = {k: (v - lo) / ((hi - lo) or 1) for k, v in recency.items()}
    order = [max(rest, key=lambda g: (fresh[id(g)], len(g["papers"])))]
    left = [g for g in rest if g is not order[0]]
    while left:
        last = id(order[-1])
        nxt = max(left, key=lambda g: cos(wv[last], wv[id(g)]) + 0.15 * linked[frozenset((last, id(g)))] + 0.25 * fresh[id(g)])
        order.append(nxt)
        left.remove(nxt)
    return order + other


def figure(groups, mine, cites):
    years = sorted({x["year"] for x in mine})
    longest = max(max(len(g["title"]), len(g.get("title_vi") or "")) for g in groups)
    left, col, row, top = round(min(430, 7.2 * longest + 24)), 120, 46, 34
    width = left + col * len(years) + 20
    pos, rows = {}, []
    for k, g in enumerate(groups):
        y = top + row * k + row / 2
        dots = []
        cell = {}
        for x in mine:
            if x["id"] not in g["papers"]:
                continue
            i = cell.setdefault(x["year"], 0)
            cell[x["year"]] += 1
            cx = left + col * years.index(x["year"]) + col / 2 + (i - 0) * 13 - 13 * (sum(1 for z in mine if z["id"] in g["papers"] and z["year"] == x["year"]) - 1) / 2
            pos[x["id"]] = (round(cx, 1), round(y, 1))
            dots.append({"id": x["id"], "x": round(cx, 1), "y": round(y, 1), "title": x["title"], "label": f"{x['venue_name']} {x['year']}"})
        rows.append({"y": round(y, 1), "color": g["color"], "title": g["title"], "title_vi": g["title_vi"], "dots": dots})
    edges = []
    for e in cites:
        (x1, y1), (x2, y2) = pos[e["from"]], pos[e["to"]]
        bend = -18 if y1 == y2 else 0
        edges.append({"d": f"M{x1},{y1} Q{(x1 + x2) / 2},{(y1 + y2) / 2 + bend - abs(x1 - x2) * 0.12} {x2},{y2}"})
    return {"width": width, "height": round(top + row * len(groups) + 10), "years": [{"year": y, "x": left + col * k + col / 2}
            for k, y in enumerate(years)], "rows": rows, "edges": edges}


def merge_papers(papers):
    entries = {}
    for f in sorted(FINAL.glob("chunk_*.json")):
        entries.update(json.loads(f.read_text(encoding="utf-8")))
    professors = json.loads((FRONTEND / "data" / "professors.json").read_text(encoding="utf-8"))
    summaries = {}
    for f in sorted((OUT / "summary_in").glob("part_*.json")):
        summaries.update(json.loads(f.read_text(encoding="utf-8")))
    abstracts = json.loads(ABSTRACTS.read_text(encoding="utf-8")) if ABSTRACTS.exists() else {}
    topics = {}
    for f in sorted((OUT / "topics").glob("part_*.json")):
        topics.update(json.loads(f.read_text(encoding="utf-8")))
    fields = ("problem", "problem_vi", "technique", "technique_vi", "strength", "strength_vi")
    people, index = {}, []
    for prof in professors:
        mine = []
        for p in papers:
            e = entries.get(paper_id(p))
            if not e or not any(o["slug"] == prof["slug"] for o in p.get("professors") or []):
                continue
            mine.append({"id": paper_id(p), "title": p["title"], "venue": p["venue"], "venue_name": p["venue_name"], "year": p["year"],
                         "status": p["status"], **{k: e.get(k, "") for k in fields},
                         "authors": e.get("authors") or [], "reviewers": e.get("reviewers") or []})
        if not mine:
            continue
        s = summaries.get(prof["slug"], {})
        t = topics.get(prof["slug"], {})
        ids = [x["id"] for x in mine]
        groups, used = [], set()
        has_authors = {x["id"] for x in mine if x["authors"]}
        for g in t.get("topics", []):
            want = set(g.get("papers", [])) - used
            keep = [i for i in ids if i in want]
            used.update(keep)
            opens = []
            for o in g.get("open", [])[:4]:
                if not o.get("text"):
                    continue
                if o.get("source") == "authors" and not has_authors & set(o.get("papers", [])):
                    o = {**o, "source": "reviewers"}
                opens.append(o)
            if keep:
                groups.append({**g, "papers": keep, "open": opens})
        rest = [i for i in ids if i not in used]
        if groups and rest:
            groups.append({"title": "Other work", "title_vi": "Các hướng khác", "summary": "", "summary_vi": "", "open": [],
                           "papers": rest})
        fig = None
        if groups:
            cites = citations(mine)
            groups = order_topics(groups, mine, abstracts, cites)
            for k, g in enumerate(groups):
                g["color"] = TOPIC_COLORS[k] if not is_other(g) and k < len(TOPIC_COLORS) else "tc-other"
            for g, ws in zip(groups, topic_words(groups, mine, abstracts)):
                g["words"] = ws
            fig = figure(groups, mine, cites)
        people[prof["slug"]] = {"name": prof["name"], "name_vi": prof["name_vi"], "institution": prof["institution_short"],
                                "image": prof.get("image") or "", "figure": fig,
                                "overview": t.get("overview") or s.get("overview", ""),
                                "overview_vi": t.get("overview_vi") or s.get("overview_vi", ""),
                                "topics": groups, "papers": mine}
        index.append({"slug": prof["slug"], "name": prof["name"], "name_vi": prof["name_vi"],
                      "institution": prof["institution_short"], "papers": len(mine),
                      **{k: s.get(k, "") for k in ("focus", "focus_vi")}})
    (FRONTEND / "data" / "challenges_people.json").write_text(json.dumps(people, ensure_ascii=False, indent=1), encoding="utf-8")
    shown = {x["id"] for p in people.values() for x in p["papers"]}
    known = {paper_id(p): p for p in papers}
    meta = {"professors": index, "sources": {"papers": len(shown), "date": datetime.date.today().isoformat(),
                                             "with_text": sum(1 for i in shown if (PDF_DIR / AREA[known[i]["venue"]] / f"{i}.pdf").exists()),
                                             "with_reviews": sum(1 for i in shown if (PDF_DIR / AREA[known[i]["venue"]] / f"{i}.md").exists())}}
    (FRONTEND / "data" / "challenges.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    content = FRONTEND / "content" / "challenges"
    content.mkdir(parents=True, exist_ok=True)
    wanted = {}
    for slug, d in people.items():
        for lang, title in (("en", f"Open challenges: {d['name']}"), ("vi", f"Thách thức còn mở: {d['name_vi']}")):
            wanted[f"{slug}.{lang}.md"] = f'---\ntitle: "{title}"\nlayout: "challenge-person"\nprofessor: "{slug}"\n---\n'
    for f in content.glob("*.md"):
        if not f.name.startswith("_index") and f.name not in wanted:
            f.unlink()
    for name, text in wanted.items():
        f = content / name
        if not f.exists() or f.read_text(encoding="utf-8") != text:
            f.write_text(text, encoding="utf-8")
    print(f"{len(people)} professors, {len(shown)} papers", file=sys.stderr)


CHUNKS = OUT / "papers"


def chunks(papers, size=90000):
    CHUNKS.mkdir(parents=True, exist_ok=True)
    for f in CHUNKS.glob("chunk_*.md"):
        f.unlink()
    blocks = []
    for p in papers:
        base = PDF_DIR / AREA[p["venue"]] / paper_id(p)
        own = paper_text(base.with_suffix(".pdf")) if base.with_suffix(".pdf").exists() else ""
        rev = review_text(base.with_suffix(".md")) if base.with_suffix(".md").exists() else ""
        if not own and not rev:
            continue
        block = [f"### {paper_id(p)} | {p['venue_name']} {p['year']} | {p['status']} | {p['title']}"]
        block.append(f"PAPER: {own}" if own else "PAPER: (paper text not available)")
        if rev:
            block.append(f"REVIEWERS: {rev}")
        blocks.append("\n".join(block))
    out, cur, n = [], [], 0
    for b in blocks:
        if cur and n + len(b) > size:
            out.append(cur)
            cur, n = [], 0
        cur.append(b)
        n += len(b)
    if cur:
        out.append(cur)
    for k, c in enumerate(out):
        (CHUNKS / f"chunk_{k}.md").write_text("\n\n".join(c) + "\n", encoding="utf-8")
    print(f"{len(blocks)} papers in {len(out)} chunks -> {CHUNKS}", file=sys.stderr)


ABSTRACTS = OUT / "abstracts.json"
ABOUT = OUT / "about"
ABOUT_FIELDS = re.compile(r"\*\*(Summary|Strengths|Strengths and weaknesses|Summary of contributions|Metareview):\*\*\s*(.*?)"
                          r"(?=\n\*\*[A-Z][\w ]+:\*\*|\n## |\Z)", re.S)


def openalex_abstract(title):
    q = urllib.parse.urlencode({"search": title, "per-page": 5, "select": "title,abstract_inverted_index",
                                **({"api_key": os.environ["OPENALEX_API_KEY"]} if os.environ.get("OPENALEX_API_KEY") else {})})
    data = get(f"https://api.openalex.org/works?{q}", timeout=60)
    for w in (json.loads(data).get("results", []) if data else []):
        inv = w.get("abstract_inverted_index")
        if norm_title(w.get("title") or "") == norm_title(title) and inv:
            words = sorted((k, word) for word, ks in inv.items() for k in ks)
            return " ".join(word for _, word in words)
    return ""


def pdf_abstract(pdf):
    run = subprocess.run(["pdftotext", "-l", "2", str(pdf), "-"], capture_output=True, timeout=60)
    text = squash(run.stdout.decode("utf-8", "ignore"))
    m = re.search(r"\babstract\b[\s.:—-]*(.*?)(?:\b1\.?\s+introduction\b|\bintroduction\b)", text, re.I)
    return (m.group(1) if m else text[:1500])[:2000]


def about(papers, size=90000):
    cache = json.loads(ABSTRACTS.read_text(encoding="utf-8")) if ABSTRACTS.exists() else {}
    for p in papers:
        i = paper_id(p)
        if cache.get(i):
            continue
        cache[i] = openalex_abstract(p["title"])
        if not cache[i]:
            pdf = PDF_DIR / AREA[p["venue"]] / f"{i}.pdf"
            cache[i] = pdf_abstract(pdf) if pdf.exists() else ""
        time.sleep(0.2)
    ABSTRACTS.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    ABOUT.mkdir(parents=True, exist_ok=True)
    for f in ABOUT.glob("chunk_*.md"):
        f.unlink()
    blocks = []
    for p in papers:
        i = paper_id(p)
        md = PDF_DIR / AREA[p["venue"]] / f"{i}.md"
        rev = ""
        if md.exists():
            seen, parts = set(), []
            for k, v in ABOUT_FIELDS.findall(md.read_text(encoding="utf-8", errors="ignore")):
                v = squash(v)
                if v[:120] not in seen:
                    seen.add(v[:120])
                    parts.append(f"[{k}] {v[:600]}")
            rev = " … ".join(parts)[:2500]
        if not cache.get(i) and not rev:
            continue
        block = [f"### {i} | {p['venue_name']} {p['year']} | {p['status']} | {p['title']}",
                 f"ABSTRACT: {cache.get(i) or '(not available)'}"]
        if rev:
            block.append(f"REVIEWERS: {rev}")
        blocks.append("\n".join(block))
    out, cur, n = [], [], 0
    for b in blocks:
        if cur and n + len(b) > size:
            out.append(cur)
            cur, n = [], 0
        cur.append(b)
        n += len(b)
    if cur:
        out.append(cur)
    for k, c in enumerate(out):
        (ABOUT / f"chunk_{k}.md").write_text("\n\n".join(c) + "\n", encoding="utf-8")
    print(f"{sum(1 for v in cache.values() if v)} abstracts; {len(blocks)} papers in {len(out)} chunks -> {ABOUT}", file=sys.stderr)


FINAL = OUT / "final"


def final_chunks(papers, size=110000):
    cache = json.loads(ABSTRACTS.read_text(encoding="utf-8")) if ABSTRACTS.exists() else {}
    drafts = {}
    for f in sorted(CHUNKS.glob("chunk_*.json")):
        drafts.update(json.loads(f.read_text(encoding="utf-8")))
    FINAL.mkdir(parents=True, exist_ok=True)
    for f in FINAL.glob("chunk_*.md"):
        f.unlink()
    blocks = []
    for p in papers:
        i = paper_id(p)
        if not p.get("professors"):
            continue
        md = PDF_DIR / AREA[p["venue"]] / f"{i}.md"
        rev = ""
        if md.exists():
            seen, parts = set(), []
            for k, v in ABOUT_FIELDS.findall(md.read_text(encoding="utf-8", errors="ignore")):
                v = squash(v)
                if v[:120] not in seen:
                    seen.add(v[:120])
                    parts.append(f"[{k}] {v[:500]}")
            rev = " … ".join(parts)[:2000]
        d = drafts.get(i, {})
        if not cache.get(i) and not rev and not d:
            continue
        block = [f"### {i} | {p['venue_name']} {p['year']} | {p['status']} | {p['title']}",
                 f"ABSTRACT: {cache.get(i) or '(not available)'}"]
        if rev:
            block.append(f"REVIEW SUMMARIES: {rev}")
        if d.get("authors"):
            block.append("DRAFT AUTHORS LEAVE OPEN: " + " | ".join(x["text"] for x in d["authors"]))
        if d.get("reviewers"):
            block.append("DRAFT REVIEWER QUESTIONS: " + " | ".join(x["text"] for x in d["reviewers"]))
        blocks.append("\n".join(block))
    out, cur, n = [], [], 0
    for b in blocks:
        if cur and n + len(b) > size:
            out.append(cur)
            cur, n = [], 0
        cur.append(b)
        n += len(b)
    if cur:
        out.append(cur)
    for k, c in enumerate(out):
        (FINAL / f"chunk_{k}.md").write_text("\n\n".join(c) + "\n", encoding="utf-8")
    print(f"{len(blocks)} papers in {len(out)} chunks -> {FINAL}", file=sys.stderr)


def topics_in(papers, size=110000, least=4):
    entries = {}
    for f in sorted(FINAL.glob("chunk_*.json")):
        entries.update(json.loads(f.read_text(encoding="utf-8")))
    professors = json.loads((FRONTEND / "data" / "professors.json").read_text(encoding="utf-8"))
    blocks = []
    for prof in professors:
        mine = [p for p in papers if paper_id(p) in entries and any(o["slug"] == prof["slug"] for o in p.get("professors") or [])]
        if len(mine) < least:
            continue
        lines = [f"## {prof['slug']} | {prof['name']} | {prof['institution_short']}"]
        for p in mine:
            e = entries[paper_id(p)]
            lines.append(f"### {paper_id(p)} | {p['venue_name']} {p['year']} | {p['title']}")
            for k in ("problem", "technique", "strength"):
                if e.get(k):
                    lines.append(f"{k.upper()}: {e[k]}")
            for x in e.get("authors") or []:
                lines.append(f"AUTHORS LEAVE OPEN: {x['text']}")
            for x in e.get("reviewers") or []:
                lines.append(f"REVIEWERS ASKED: {x['text']}")
        blocks.append("\n".join(lines))
    out = OUT / "topics"
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("part_*.md"):
        f.unlink()
    parts, cur, n = [], [], 0
    for b in blocks:
        if cur and n + len(b) > size:
            parts.append(cur)
            cur, n = [], 0
        cur.append(b)
        n += len(b)
    if cur:
        parts.append(cur)
    for k, c in enumerate(parts):
        (out / f"part_{k}.md").write_text("\n\n".join(c) + "\n", encoding="utf-8")
    print(f"{len(blocks)} professors in {len(parts)} parts -> {out}", file=sys.stderr)


def main():
    papers = json.loads((FRONTEND / "data" / "papers.json").read_text(encoding="utf-8"))
    papers = [p for p in papers if p["venue"] in AREA]
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    if step in ("pdfs", "all"):
        fetch_pdfs([p for p in papers if not forum_of(p)])
    if step in ("reviews", "all"):
        fetch_reviews([p for p in papers if p["venue"] in OPENREVIEW])
    if step in ("orpdfs", "all"):
        k, n = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (0, 1)
        fetch_openreview_pdfs([p for i, p in enumerate(q for q in papers if forum_of(q)) if i % n == k])
    if step in ("chunks", "all"):
        chunks(papers)
    if step in ("about", "all"):
        about(papers)
    if step in ("final", "all"):
        final_chunks(papers)
    if step == "topics":
        topics_in(papers)
    if step == "merge":
        merge_papers(papers)


if __name__ == "__main__":
    main()
