"""Builds the YouTube Short (vertical, under a minute) from the site's data. No person is named.

    python3 video/make_short.py            # numbers, script, subtitles, slides, YouTube text, PNG frames
    python3 video/make_short.py --no-png   # everything except the PNG frames

Reads frontend/data/{blog,papers,professors}.json and backend/work/accepted.jsonl.gz (run `make data` first),
and the narration in video/short.json. Writes under video/short/:
    numbers.json        every figure the Short uses, raw and formatted (Vietnamese, English), with how it was computed
    script.md           storyboard: time, frame, on-screen text, Vietnamese narration, English subtitle
    narration.vi.txt    the narration alone, for recording
    subtitles.en.srt    English subtitles timed from an estimated speaking rate (re-time after recording)
    subtitles.vi.srt    Vietnamese captions, same timing
    youtube.md          title, description with method and sources, pinned-comment text
    slides/NN-name.html one 1080x1920 page per frame; slides/index.html pages through them (arrows, N = narration)
    frames/NN-name.png  1080x1920 screenshots (needs chromium)
"""
import collections
import datetime
import gzip
import html
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "frontend" / "data"
OUT = ROOT / "video" / "short"
SITE = "https://thanhlexyz.github.io/vn-at-top-ai-conference/"
sys.path.insert(0, str(ROOT / "backend"))
from common import name_key, norm_title, same_institution, vn_institutions  # noqa: E402

W, H = 1080, 1920
ACC, NOT, NOT_PALE, ABROAD = "#2a78d6", "#e34948", "#f4c2c1", "#eb6834"
INK, INK2, MUTED, GRID, SURFACE = "#24212b", "#4c4757", "#7a7484", "#ffffff", "#fffaf0"
FONT = "'Baloo 2', 'Noto Sans', 'Noto Color Emoji', sans-serif"
FONTS = "https://fonts.googleapis.com/css2?family=Baloo+2:wght@500;600;700;800&display=block"
BG = {"hook": "#fff1d0", "iclr": "#e5f1ff", "neurips": "#ffece6", "authors": "#efe8ff", "end": "#ffd84d"}
SYLLABLES_PER_SECOND = 3.4   # brisk Short narration
PAUSE_AFTER_LINE = 0.4


# ---------------------------------------------------------------- numbers

def fmt(x, lang, decimals=0):
    s = f"{x:,.{decimals}f}"
    return s.replace(",", "\0").replace(".", ",").replace("\0", ".") if lang == "vi" else s


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def round_to(x, step):
    return int(step * round(x / step))


def compute():
    blog, papers, profs = load("blog.json"), load("papers.json"), load("professors.json")
    by_slug = {p["slug"]: p for p in profs}
    accepted = [p for p in papers if p["status"] == "accepted"]
    iclr = blog["pooled"]["iclr"]

    # NeurIPS 2026 papers of the people on the list, and the rejections behind them, estimated two ways
    neurips = [p for p in accepted if p["venue"] == "neurips" and p["year"] == 2026]
    pooled_ratio = iclr["submitted"] / iclr["accepted"]
    high = len(neurips) * (pooled_ratio - 1)

    def smoothed(slug):   # the website's per-person estimate: (ICLR submitted + 1) / (ICLR accepted + 1)
        i = by_slug[slug]["venues"]["iclr"]
        return (i["submitted"] + 1) / (i["accepted"] + 1) - 1

    low = sum(sum(smoothed(o["slug"]) for o in p["professors"]) / len(p["professors"]) for p in neurips)

    # where the authors of the accepted papers work, from lists that print an affiliation for each author
    official = {}
    with gzip.open(ROOT / "backend" / "work" / "accepted.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            official[(d["venue"], d["year"], norm_title(d["title"]))] = d
    first, last = collections.Counter(), collections.Counter()
    judged = no_colleague = with_abroad = majority_own = majority_abroad = last_abroad_other = 0
    team_sizes = []
    forms = collections.defaultdict(set)   # every spelling of each listed person's name, from the roster
    with open(ROOT / "backend" / "roster.csv", encoding="utf-8") as fh:
        import csv
        for row in csv.DictReader(fh):
            slug = row.get("slug") or ""
            names = [row["display_name"], *[v for v in row["name_variants"].split(";") if v.strip()]]
            for p in profs:
                if p["name"] == row["display_name"]:
                    forms[p["slug"]] |= {name_key(x) for x in names}

    def listed(author, slug):
        key = name_key(author)
        if key in forms[slug] or key == name_key(by_slug[slug]["name"]):
            return True
        tokens = set(key.split())   # "Khoat Than" is a listed "Than Quang Khoat"
        return len(tokens) >= 2 and any(tokens <= set(f.split()) for f in forms[slug] | {name_key(by_slug[slug]["name"])})

    for p in accepted:
        d = official.get((p["venue"], p["year"], norm_title(p["title"])))
        if not d or not any(a.get("aff") for a in d["authors"]):
            continue
        judged += 1
        owners = [by_slug[o["slug"]] for o in p["professors"]]

        def is_listed(author):
            return any(listed(author, o["slug"]) for o in owners)

        def kind(a):
            aff = a.get("aff") or ""
            if not aff:
                return "unknown"
            if any(same_institution(aff, o) for o in owners):
                return "own"
            return "vietnam" if vn_institutions(aff) else "abroad"

        kinds = [kind(a) for a in d["authors"]]
        team_sizes.append(len(d["authors"]))
        first[kinds[0]] += 1
        last[kinds[-1]] += 1
        last_abroad_other += kinds[-1] == "abroad" and not is_listed(d["authors"][-1]["name"])
        with_abroad += "abroad" in kinds
        majority_own += 2 * kinds.count("own") > len(kinds)
        majority_abroad += 2 * kinds.count("abroad") > len(kinds)
        no_colleague += not any(k == "own" for a, k in zip(d["authors"], kinds) if not is_listed(a["name"]))

    built = datetime.datetime.fromtimestamp((DATA / "blog.json").stat().st_mtime, datetime.timezone.utc).date()
    raw = {
        "people": blog["pooled"]["professors"],
        "iclr_submitted": iclr["submitted"], "iclr_accepted": iclr["accepted"], "iclr_not_accepted": iclr["not_accepted"],
        "iclr_per_accept": pooled_ratio,
        "neurips_2026": len(neurips), "neurips_2026_unofficial": sum(p["unofficial"] for p in neurips),
        "rejections_low": round_to(low, 10), "rejections_high": round_to(high, 10),
        "rejections_low_exact": low, "rejections_high_exact": high,
        "judged": judged, "no_colleague": no_colleague, "last_abroad": last_abroad_other, "with_abroad": with_abroad,
        "first_own": first["own"], "first_abroad": first["abroad"], "first_vietnam": first["vietnam"],
        "majority_own": majority_own, "majority_abroad": majority_abroad,
        "accepted_total": len(accepted),
        "person_credits": sum(p["accepted"] for p in profs),
        "authors_mean": sum(team_sizes) / len(team_sizes), "authors_max": max(team_sizes), "authors_min": min(team_sizes),
    }
    method = {
        "first_own": "Accepted papers with per-author affiliations whose first author lists the listed person's institution (the listed person themself included).",
        "majority_own": "Accepted papers with per-author affiliations on which more than half of the authors list the listed person's institution.",
        "majority_abroad": "Accepted papers with per-author affiliations on which more than half of the authors are at institutions outside Vietnam.",
        "rejections_low": "Sum over this year's NeurIPS papers of (ICLR submitted + 1) / (ICLR accepted + 1) - 1 for the "
                          "people on the paper (averaged when several are), i.e. the website's per-person estimate. "
                          "People without ICLR submissions add nothing.",
        "rejections_high": "NeurIPS 2026 papers x (ICLR submitted / ICLR accepted - 1), the group's pooled ICLR ratio.",
        "no_colleague": "Accepted papers with per-author affiliations on which no author other than the listed person(s) "
                        "is at the listed person's institution.",
        "last_abroad": "Accepted papers with per-author affiliations whose last author is someone other than the listed person and is at an institution outside Vietnam (a company affiliation does not say which country).",
        "with_abroad": "Accepted papers with per-author affiliations with at least one author outside Vietnam.",
    }

    def share_words(k, lang):
        x = raw[k] / raw["judged"]
        if lang == "vi":
            return "Hơn một nửa" if x > 0.5 else "Một nửa" if x == 0.5 else "Gần một nửa" if x >= 0.4 else "Khoảng một phần ba"
        return "More than half" if x > 0.5 else "Half" if x == 0.5 else "Nearly half" if x >= 0.4 else "About a third"

    def formatted(lang):
        out = {k: fmt(v, lang, 1 if k in ("iclr_per_accept", "authors_mean") else 0) for k, v in raw.items() if not k.endswith("_exact")}
        out["no_colleague_words"] = share_words("no_colleague", lang)
        out["last_abroad_words"] = share_words("last_abroad", lang)
        out["data_date"] = f"{built.day}/{built.month}/{built.year}" if lang == "vi" else built.isoformat()
        return out

    return {"raw": raw, "vi": formatted("vi"), "en": formatted("en"), "method": method,
            "first_author": dict(first), "last_author": dict(last)}


# ---------------------------------------------------------------- drawing

def esc(s):
    return html.escape(str(s))


def svg(w, h, body, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
            f'aria-label="{esc(label)}" font-family="{esc(FONT)}">{body}</svg>')


def text(x, y, s, size, fill=INK, anchor="start", weight=400):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
            f'font-weight="{weight}">{esc(s)}</text>')


def waffle(x, y, groups, cols, cell, gap):
    """groups: [(count, fill, outline)]; outline=True draws a dashed hollow square (an estimate)."""
    b, k = [], 0
    for count, fill, outline in groups:
        for _ in range(count):
            cx, cy = x + (k % cols) * (cell + gap), y + (k // cols) * (cell + gap)
            if outline:
                b.append(f'<rect x="{cx + 1.5}" y="{cy + 1.5}" width="{cell - 3}" height="{cell - 3}" rx="{(cell - 3) / 2}" fill="none" '
                         f'stroke="{fill}" stroke-width="3" stroke-dasharray="6 4"/>')
            else:
                b.append(f'<rect x="{cx}" y="{cy}" width="{cell}" height="{cell}" rx="{cell / 2}" fill="{fill}"/>')
            k += 1
    return "".join(b)


def chart_iclr(n):
    r = n["raw"]
    cols, cell, gap = 10, 74, 10
    rows = math.ceil(r["iclr_submitted"] / cols)
    body = waffle(0, 0, [(r["iclr_accepted"], ACC, False), (r["iclr_not_accepted"], NOT, False)], cols, cell, gap)
    return svg(cols * (cell + gap) - gap, rows * (cell + gap) - gap, body, "ICLR submissions: accepted and not")


def chart_neurips(n):
    r = n["raw"]
    cols, cell, gap = 16, 46, 8
    low = r["rejections_low"]
    extra = r["rejections_high"] - low
    total = r["neurips_2026"] + low + extra
    rows = math.ceil(total / cols)
    body = waffle(0, 0, [(r["neurips_2026"], ACC, False), (low, NOT, False), (extra, NOT, True)], cols, cell, gap)
    return svg(cols * (cell + gap) - gap, rows * (cell + gap) - gap, body, "NeurIPS papers and estimated rejections")


def chart_authors(n):
    r, f = n["raw"], n["vi"]
    rows = [(r["first_own"], f"{f['first_own']} / {f['judged']}", "tác giả đầu", "cùng trường", ACC, "chỉ"),
            (r["majority_own"], f"{f['majority_own']} / {f['judged']}", "đa số tác giả", "cùng trường", ACC, "chỉ"),
            (r["majority_abroad"], f"{f['majority_abroad']} / {f['judged']}", "đa số tác giả", "ở nước ngoài", ABROAD, "")]
    width, b, y = 900, [], 0
    for value, big, l1, l2, color, lead in rows:
        word = f'<tspan font-size="64" fill="{NOT}">{lead} </tspan>' if lead else ""
        b.append(f'<text x="0" y="{y + 96}" font-size="104" fill="{INK}" font-weight="800">{word}{esc(big)}</text>')
        b.append(text(540, y + 50, l1, 44, INK2, "start", 600))
        b.append(text(540, y + 100, l2, 44, INK2, "start", 600))
        bw = width * value / r["judged"]
        b.append(f'<rect x="0" y="{y + 126}" width="{width}" height="40" rx="20" fill="{GRID}"/>')
        b.append(f'<rect x="0" y="{y + 126}" width="{bw:.1f}" height="40" rx="20" fill="{color}"/>')
        y += 250
    return svg(width, y - 40, "".join(b), "Where the authors of the accepted papers work")


# ---------------------------------------------------------------- frames

FRAMES = ["hook", "iclr", "neurips", "authors", "end"]


def frame_html(name, n, index):
    f = n["vi"]
    foot = f"{f['people']} giảng viên, nhà nghiên cứu · 2020–2026 · đến {f['data_date']}"
    if name == "hook":
        inner = ('<div class="bubble">Lab mình có<br>bài NeurIPS! 🎉</div>'
                 '<div class="hero2">Còn bị từ chối<br><span class="nw">bao nhiêu bài? 🤔</span></div>')
    elif name == "iclr":
        inner = (f'<div class="pill">ICLR · 2020–2026</div>'
                 f'<div class="big"><span class="acc">{f["iclr_accepted"]}</span> / {f["iclr_submitted"]}</div>'
                 f'<div class="lead">bài nộp được nhận</div>'
                 f'<div class="chart">{chart_iclr(n)}</div>'
                 f'<div class="key"><span class="k"><span class="dot acc-bg"></span>được nhận</span>'
                 f'<span class="k"><span class="dot not-bg"></span>bị từ chối, rút</span></div>')
    elif name == "neurips":
        inner = (f'<div class="pill">NeurIPS 2026</div>'
                 f'<div class="big small-big"><span class="acc">{f["neurips_2026"]}</span> bài <span class="nw">được nhận 🎉</span></div>'
                 f'<div class="sticker">≈ {f["rejections_low"]}–{f["rejections_high"]} bài trượt 😅<span>ước tính</span></div>'
                 f'<div class="chart">{chart_neurips(n)}</div>'
                 f'<div class="key"><span class="k"><span class="dot acc-bg"></span>được nhận</span>'
                 f'<span class="k"><span class="dot not-bg"></span>trượt</span><span class="k"><span class="dot dash"></span>ước tính cao</span></div>'
                 f'<div class="note">* chưa tính người chưa có bài nào được nhận</div>')
    elif name == "authors":
        inner = (f'<div class="pill">Ai viết các bài được nhận? ✍️</div>'
                 f'<div class="lead small">{f["judged"]}/{f["accepted_total"]} bài có ghi đơn vị · 5 hội nghị · 2020–2026</div>'
                 f'<div class="chart tall">{chart_authors(n)}</div>'
                 f'<div class="team">👥 <b>{f["authors_mean"]}</b> tác giả/bài · tối đa <b>{f["authors_max"]}</b></div>')
    elif name == "end":
        inner = ('<div class="hero3">Bị từ chối<br>vẫn nhiều hơn<br>được nhận.</div>'
                 '<div class="sticker big-sticker">Chưa có bài?<br>Đừng mặc cảm 💪</div>')
    else:
        raise KeyError(name)
    return (f'<section class="frame f-{name}" id="f{index:02d}" data-name="{name}" style="background:{BG[name]}">'
            f'<div class="foot">{esc(foot)}</div>{inner}</section>')


CSS = f"""
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; background: {SURFACE}; }}
body {{ font-family: {FONT}; color: {INK}; }}
.frame {{ position: relative; width: {W}px; height: {H}px; padding: 200px 90px 0; overflow: hidden; }}
.foot {{ position: absolute; left: 90px; top: 110px; font-size: 28px; color: {MUTED}; white-space: nowrap; font-weight: 600; }}
.pill {{ display: inline-block; background: {INK}; color: #fff; font-size: 40px; font-weight: 700; padding: 10px 30px 4px;
        border-radius: 999px; }}
.bubble {{ position: relative; display: inline-block; background: #fff; font-size: 104px; font-weight: 800; line-height: 1.05;
          padding: 56px 64px 40px; border-radius: 64px; margin-top: 150px; transform: rotate(-3deg);
          box-shadow: 0 18px 0 rgba(36,33,43,.12); }}
.bubble::after {{ content: ""; position: absolute; left: 120px; bottom: -58px; border: 30px solid transparent;
                 border-top: 34px solid #fff; border-left: 34px solid #fff; }}
.nw {{ white-space: nowrap; }}
.hero2 {{ font-size: 104px; font-weight: 800; line-height: 1.02; margin-top: 150px; color: {NOT}; }}
.hero3 {{ font-size: 124px; font-weight: 800; line-height: 1.0; margin-top: 230px; }}
.big {{ font-size: 170px; font-weight: 800; line-height: 1; margin-top: 40px; }}
.big.small-big {{ font-size: 88px; }}
.lead {{ font-size: 56px; line-height: 1.15; color: {INK2}; margin-top: 4px; font-weight: 700; }}
.lead.small {{ font-size: 38px; font-weight: 600; margin-top: 28px; }}
.acc {{ color: {ACC}; }} .not {{ color: {NOT}; }}
.sticker {{ display: inline-block; background: #fff; color: {NOT}; font-size: 60px; font-weight: 800; line-height: 1.1;
           padding: 26px 40px 16px; border-radius: 36px; margin-top: 30px; transform: rotate(-2.5deg);
           box-shadow: 0 14px 0 rgba(36,33,43,.12); }}
.sticker span {{ display: block; font-size: 32px; color: {MUTED}; font-weight: 600; }}
.big-sticker {{ color: {INK}; font-size: 92px; margin-top: 110px; padding: 44px 56px 30px; transform: rotate(2deg); }}
.chart {{ margin-top: 40px; }}
.chart svg {{ width: 100%; height: auto; display: block; }}
.chart.tall {{ margin-top: 60px; }}
.key {{ font-size: 36px; color: {INK2}; margin-top: 28px; display: flex; flex-wrap: wrap; gap: 10px 34px; font-weight: 600; }}
.k {{ white-space: nowrap; display: inline-flex; align-items: center; gap: 12px; }}
.dot {{ display: inline-block; width: 34px; height: 34px; border-radius: 50%; }}
.acc-bg {{ background: {ACC}; }} .not-bg {{ background: {NOT}; }}
.dot.dash {{ border: 3px dashed {NOT}; }}
.note {{ font-size: 34px; color: {INK2}; margin-top: 26px; font-weight: 600; }}
.team {{ font-size: 50px; color: {INK2}; margin-top: 20px; font-weight: 700; }}
.team b {{ color: {INK}; font-size: 72px; }}
"""

DECK = """
<style>
html, body { height: 100%; overflow: hidden; background: #111; }
.deck { position: fixed; inset: 0; display: flex; align-items: center; justify-content: center; }
.deck .frame { position: absolute; display: none; transform-origin: center; }
.deck .frame.on { display: block; }
.notes { position: fixed; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,.85); color: #fff; font: 22px/1.45 sans-serif;
         padding: 14px 22px; display: none; } .notes.on { display: block; } .notes .en { color: #aaa; font-size: 18px; }
</style>
<script>
const F = [...document.querySelectorAll('.deck .frame')], notes = document.querySelector('.notes'); let i = 0;
const fit = () => F.forEach(f => f.style.transform = `scale(${Math.min(innerWidth / 1080, innerHeight / 1920)})`);
function show(k) { i = Math.max(0, Math.min(F.length - 1, k)); F.forEach((f, j) => f.classList.toggle('on', j === i));
  notes.innerHTML = (NOTES[F[i].dataset.name] || []).map(l => `<div>${l.vi}</div><div class="en">${l.en}</div>`).join(''); }
addEventListener('resize', fit);
addEventListener('keydown', e => { if (['ArrowRight', ' ', 'PageDown'].includes(e.key)) show(i + 1);
  else if (['ArrowLeft', 'PageUp'].includes(e.key)) show(i - 1); else if (e.key.toLowerCase() === 'n') notes.classList.toggle('on'); });
addEventListener('click', () => show(i + 1)); fit(); show(0);
</script>
"""


def page(title, inner, tail=""):
    return (f'<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, '
            f'initial-scale=1"><title>{esc(title)}</title><link rel="stylesheet" href="{FONTS}"><style>{CSS}</style></head><body>{inner}{tail}</body></html>')


# ---------------------------------------------------------------- narration and subtitles

def syllables(line):
    n = 0
    for tok in line.split():
        digits = re.sub(r"\D", "", tok)
        if digits:
            n += max(1, round(len(digits) * 1.6)) + 2 * ("%" in tok) + 2 * ("–" in tok)
        elif re.search(r"\w", tok):
            n += 1
    return n


def clock(sec, srt=False):
    ms = int(round(sec * 1000))
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"00:{m:02d}:{s:02d},{ms:03d}" if srt else f"{m}:{s:02d}"


def split_cue(s, limit=42):
    """Splits text into pieces of at most two subtitle lines, preferring sentence ends, then commas."""
    pieces = []
    for sentence in re.split(r"(?<=[.?!:])\s+", s.strip()):
        while len(sentence) > 2 * limit:
            window = sentence[:2 * limit]
            cut = max((m.end() for m in re.finditer(r"[,;]\s", window)), default=0) or window.rfind(" ") + 1
            pieces.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if sentence:
            pieces.append(sentence)
    merged = []
    for p in pieces:   # no one-word leftovers
        if merged and len(p) < 18 and len(merged[-1]) + len(p) + 1 <= 2 * limit:
            merged[-1] += " " + p
        else:
            merged.append(p)
    return merged


def two_lines(s, limit=42):
    if len(s) <= limit:
        return s
    spaces = [m.start() for m in re.finditer(" ", s)]
    ok = [k for k in spaces if k <= limit and len(s) - k - 1 <= limit] or spaces
    commas = [k for k in ok if s[k - 1] in ",:;"]
    k = min(commas or ok, key=lambda k: abs(k - len(s) / 2))
    return s[:k] + "\n" + s[k + 1:]


def timeline(lines, n):
    t, out = 0.0, []
    for ln in lines:
        vi, en = ln["vi"].format_map(n["vi"]), ln["en"].format_map(n["en"])
        d = syllables(vi) / SYLLABLES_PER_SECOND
        out.append({**ln, "vi": vi, "en": en, "start": t, "end": t + d})
        t += d + PAUSE_AFTER_LINE
    return out, t


def srt(timed, lang):
    out, k = [], 1
    for ln in timed:
        parts = split_cue(ln[lang])
        total = sum(len(p) for p in parts)
        t = ln["start"]
        for p in parts:
            d = (ln["end"] - ln["start"]) * len(p) / total
            out.append(f"{k}\n{clock(t, True)} --> {clock(t + d, True)}\n{two_lines(p)}\n")
            t, k = t + d, k + 1
    return "\n".join(out)


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main():
    n = compute()
    spec = json.loads((ROOT / "video" / "short.json").read_text(encoding="utf-8"))
    timed, total = timeline(spec["lines"], n)
    f, e = n["vi"], n["en"]

    write(OUT / "numbers.json", json.dumps(n, ensure_ascii=False, indent=1))
    write(OUT / "narration.vi.txt", "\n".join(ln["vi"] for ln in timed) + "\n")
    write(OUT / "subtitles.en.srt", srt(timed, "en"))
    write(OUT / "subtitles.vi.srt", srt(timed, "vi"))

    rows = ["| Time | Frame | Narration (vi) | Subtitle (en) |", "|---|---|---|---|"]
    for ln in timed:
        k = FRAMES.index(ln["frame"]) + 1
        rows.append(f"| {clock(ln['start'])} | `{k:02d}-{ln['frame']}` | {ln['vi']} | {ln['en']} |")
    write(OUT / "script.md", f"""# YouTube Short: {spec['title_vi']}

Vertical 1080x1920, about {clock(total)} at {SYLLABLES_PER_SECOND:g} syllables per second. No person is named.
Data as of {f['data_date']}. Generated by `video/make_short.py` from `video/short.json`; edit the words there.
Frames: `video/short/frames/`. Deck for recording: `video/short/slides/index.html` (arrow keys, N = narration).
Times are estimates: re-time the subtitles to the recording.

{chr(10).join(rows)}

## Figures and how they were computed

- ICLR: {f['iclr_submitted']} submissions found on OpenReview, {f['iclr_accepted']} accepted, {f['iclr_not_accepted']} rejected or withdrawn.
- NeurIPS 2026: {f['neurips_2026']} accepted papers of the {f['people']} people, {f['neurips_2026_unofficial']} of them so far only on personal pages or announcements.
- Rejections behind them, low ({f['rejections_low']}, exact {n['raw']['rejections_low_exact']:.1f}): {n['method']['rejections_low']}
- Rejections behind them, high ({f['rejections_high']}, exact {n['raw']['rejections_high_exact']:.1f}): {n['method']['rejections_high']}
- {f['no_colleague']} of {f['judged']}: {n['method']['no_colleague']}
- {f['last_abroad']} of {f['judged']}: {n['method']['last_abroad']}
- {f['with_abroad']} of {f['judged']}: {n['method']['with_abroad']}
- For balance (not in the Short): the first author is at the listed person's own institution on {f['first_own']} of {f['judged']} papers, at another institution in Vietnam on {f['first_vietnam']}, abroad on {f['first_abroad']}; most authors are from the person's institution on {f['majority_own']} of {f['judged']}. Author lists do not say who is a student.
""")

    write(OUT / "youtube.md", f"""# YouTube Short

## Title (Vietnamese, under 100 characters)

1. {spec['titles_vi'][0].format_map(f)}  (recommended)
2. {spec['titles_vi'][1].format_map(f)}
3. {spec['titles_vi'][2].format_map(f)}

## Description

{spec['description_vi'].format_map(f)}

Cách tính:
- ICLR: {f['iclr_submitted']} bài nộp tìm được trên OpenReview, {f['iclr_accepted']} bài được nhận.
- NeurIPS 2026: {f['neurips_2026']} bài được nhận ({f['neurips_2026_unofficial']} bài mới có trên trang cá nhân). Số bài không được nhận phía sau là ước tính: {f['rejections_low']} theo kết quả ICLR của từng người (cách tính trên trang web), {f['rejections_high']} theo tỉ lệ ICLR chung của nhóm.
- Tác giả: {f['judged']} trong {f['accepted_total']} bài được nhận ở 5 hội nghị (2020–2026) có ghi đơn vị của từng tác giả. Trong đó {f['first_own']} bài có tác giả đầu cùng trường với giảng viên, {f['majority_own']} bài có đa số tác giả cùng trường, {f['majority_abroad']} bài có đa số tác giả ở nước ngoài; {f['with_abroad']} bài có ít nhất một đồng tác giả ở nước ngoài. Mỗi bài có trung bình {f['authors_mean']} tác giả, nhiều nhất {f['authors_max']}; một bài có nhiều người trong danh sách được tính cho từng người, nên {f['accepted_total']} bài thành {f['person_credits']} lượt.

Lưu ý: danh sách do người làm trang web tự chọn, không phải mẫu đại diện; chỉ gồm người đã có ít nhất một bài được nhận, nên tổng số lần nộp thật còn cao hơn; đơn vị là công ty không cho biết tác giả ở nước nào; chỉ ICLR công khai đầy đủ bài bị từ chối; bài được gán cho từng người theo hồ sơ OpenReview và theo tên, có thể sót hoặc nhầm; đếm bài không nói lên chất lượng bài.

Số liệu đầy đủ và cách tính: {SITE}

Kịch bản và hình được soạn với sự hỗ trợ của một mô hình ngôn ngữ (Claude); số liệu lấy từ dữ liệu của trang web.

#NeurIPS #ICLR #AI #nghiencuu

## English description

{spec['description_en'].format_map(e)}

Method: ICLR is the only one of the five conferences that publishes every submission with its outcome. NeurIPS rejections are estimated from the group's own ICLR record: {e['rejections_low']} using each person's record (the website's method), {e['rejections_high']} using the group's pooled ICLR ratio. Author figures cover the {e['judged']} of {e['accepted_total']} accepted papers (five conferences, 2020–2026) whose lists give every author's affiliation: first author at the lecturer's university on {e['first_own']}, most authors at the lecturer's university on {e['majority_own']}, most authors abroad on {e['majority_abroad']}; {e['authors_mean']} authors per paper on average, {e['authors_max']} at most.

Caveats: hand-picked list, not a representative sample; only people with at least one accepted paper are listed, so total attempts are higher; a company affiliation does not say which country an author is in; rejections are fully visible at ICLR only; papers are matched by OpenReview profile and name; counting papers says nothing about their quality.

Full data and method: {SITE}

Script and graphics were drafted with the help of a language model (Claude); the figures come from the website's data.
""")

    sections = []
    for k, name in enumerate(FRAMES, 1):
        sec = frame_html(name, n, k)
        sections.append(sec)
        write(OUT / "slides" / f"{k:02d}-{name}.html", page(f"{k:02d} {name}", sec))
    notes = collections.defaultdict(list)
    for ln in timed:
        notes[ln["frame"]].append({"vi": esc(ln["vi"]), "en": esc(ln["en"])})
    write(OUT / "slides" / "index.html", page("Short", f'<div class="deck">{"".join(sections)}</div><div class="notes"></div>',
                                            f"<script>const NOTES = {json.dumps(notes, ensure_ascii=False)};</script>{DECK}"))
    print(f"short: about {clock(total)} of narration, {len(FRAMES)} frames, data of {f['data_date']}")

    if "--no-png" not in sys.argv:
        browser = shutil.which("chromium") or shutil.which("google-chrome")
        if not browser:
            print("chromium not found; skipping PNG frames")
            return
        (OUT / "frames").mkdir(parents=True, exist_ok=True)
        for p in sorted((OUT / "slides").glob("[0-9][0-9]-*.html")):
            png = OUT / "frames" / (p.stem + ".png")
            subprocess.run([browser, "--headless", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                            f"--window-size={W},{H}", "--virtual-time-budget=8000", f"--screenshot={png}", p.as_uri()],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            print("  ", png.relative_to(ROOT))


if __name__ == "__main__":
    main()
