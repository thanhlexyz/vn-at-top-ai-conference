"""Builds everything for the video from the site's data, so the narration and the charts follow the data.

    python3 video/make_assets.py            # numbers, script, subtitles, slides, YouTube text, PNG frames
    python3 video/make_assets.py --no-png   # everything except the PNG frames

Reads frontend/data/{blog,papers,professors}.json (run `make data` first) and video/scenes.json.
Writes, under video/:
    numbers.json          every figure the video quotes, raw and formatted for Vietnamese and English
    script.md             storyboard: scene, time, frame, on-screen text, Vietnamese narration, English line
    narration.vi.txt      the narration alone, for reading aloud
    subtitles.en.srt      English subtitles, timed from an estimated speaking rate (re-time after recording)
    subtitles.vi.srt      Vietnamese captions, same timing
    youtube.md            title options, description with chapters and sources, thumbnail wording
    slides/NN-name.html   one 1920x1080 page per frame
    slides/index.html     all frames as a deck: arrow keys to page, N for the narration, F for full screen
    charts/NN-name.svg    the chart of each frame alone, scalable
    frames/NN-name.png    1920x1080 screenshots of the slides (needs chromium)
"""
import collections
import datetime
import html
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "frontend" / "data"
OUT = ROOT / "video" / "long-draft"
SITE = "https://thanhlexyz.github.io/vn-at-top-ai-conference/"

# ICLR's own figures, also quoted in the blog post
ICLR_ALL = {"rate_2025": 32.1, "rate_2026": 27.4, "withdrawn_2026": 5042, "submissions_2026": 19525,
            "source": "https://blog.iclr.cc/2026/03/31/a-retrospective-on-the-iclr-2026-review-process/"}

VENUES = ["iclr", "neurips", "icml", "cvpr", "acl"]
VENUE_NAME = {"iclr": "ICLR", "neurips": "NeurIPS", "icml": "ICML", "cvpr": "CVPR", "acl": "ACL"}
VENUE_COLOR = {"iclr": "#2a78d6", "neurips": "#eb6834", "icml": "#1baf7a", "cvpr": "#eda100", "acl": "#e87ba4"}
DASH = ' stroke-dasharray="4 10"'
ACC, NOT, VN, ABROAD = "#2a78d6", "#e34948", "#1baf7a", "#eb6834"
INK, INK2, MUTED, GRID, SURFACE = "#1d1d1f", "#4a4a4f", "#77777c", "#e4e3df", "#fcfcfb"
FONT = "'Noto Sans', 'DejaVu Sans', sans-serif"
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
             "October", "November", "December"]

SYLLABLES_PER_SECOND = 3.0   # calm Vietnamese narration; re-time the subtitles after recording
PAUSE_AFTER_LINE = 0.6
PAUSE_AFTER_SCENE = 0.8


# ---------------------------------------------------------------- numbers

def fmt_num(x, lang, decimals=None):
    """A number in Vietnamese (1.234,5) or English (1,234.5) style."""
    if decimals is None:
        decimals = 0 if float(x).is_integer() else 1
    s = f"{x:,.{decimals}f}"
    if lang == "vi":
        s = s.replace(",", "\0").replace(".", ",").replace("\0", ".")
    return s


def fmt_pct(x, lang, decimals=None):
    return fmt_num(x, lang, decimals) + "%"


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def compute():
    blog, papers, profs = load("blog.json"), load("papers.json"), load("professors.json")
    pooled = blog["pooled"]
    by_slug = {p["slug"]: p for p in profs}
    accepted = [p for p in papers if p["status"] == "accepted"]

    def owners(p):
        return [by_slug[o["slug"]] for o in p["professors"] if o["slug"] in by_slug]

    per_venue_year = {v: {y: 0 for y in range(2020, 2027)} for v in VENUES}
    for p in accepted:
        per_venue_year[p["venue"]][p["year"]] += 1
    unofficial_venue_2026 = collections.Counter(p["venue"] for p in accepted if p["year"] == 2026 and p["unofficial"])
    new_2026 = sum(1 for p in accepted if p["year"] == 2026 and owners(p)
                   and all((o["vn_since"] or 0) >= 2023 for o in owners(p)))
    unofficial_2026 = sum(1 for p in accepted if p["year"] == 2026 and p["unofficial"])

    neurips = next(t for t in blog["trend"] if t["venue"] == "neurips")["years"]
    iclr = pooled["iclr"]
    top = sorted(profs, key=lambda p: (-p["accepted"], -p["official"], p["name"]))
    built = datetime.datetime.fromtimestamp((DATA / "blog.json").stat().st_mtime, datetime.timezone.utc).date()

    raw = {
        "data_date": built.isoformat(),
        "people": pooled["professors"],
        "accepted": pooled["accepted"],
        "unofficial": pooled["own_page"],
        **{f"acc_{y}": pooled["accepted_by_year"][str(y)] for y in range(2020, 2027)},
        "unofficial_2026": unofficial_2026,
        "new_2026": new_2026,
        "neurips_vn_first": pooled["neurips_first"]["vietnam"],
        "neurips_vn_last": pooled["neurips_last"]["vietnam"],
        "neurips_share_first": 100 * pooled["neurips_first"]["vietnam"] / pooled["neurips_first"]["papers"],
        "neurips_share_last": 100 * pooled["neurips_last"]["vietnam"] / pooled["neurips_last"]["papers"],
        "iclr_submitted": iclr["submitted"],
        "iclr_accepted": iclr["accepted"],
        "iclr_not_accepted": iclr["not_accepted"],
        "iclr_rate": 100 * iclr["accepted"] / iclr["submitted"],
        "iclr_per_accept": iclr["submitted"] / iclr["accepted"],
        "iclr_later": iclr["later"],
        "iclr_all_2025": ICLR_ALL["rate_2025"],
        "iclr_all_2026": ICLR_ALL["rate_2026"],
        "iclr_withdrawn_2026": ICLR_ALL["withdrawn_2026"],
        "iclr_submissions_2026": ICLR_ALL["submissions_2026"],
        "projected_accepted": pooled["projected_accepted"],
        "projected_submissions": pooled["projected_submissions"],
        "projected_rate": 100 * pooled["projected_accepted"] / pooled["projected_submissions"],
        "projected_per_accept": pooled["projected_submissions"] / pooled["projected_accepted"],
        "avg_authors": float(pooled["avg_authors"]),
        "avg_authors_vietnam": float(pooled["avg_authors_vietnam"]),
        "avg_authors_abroad": float(pooled["avg_authors_abroad"]),
        "papers_with_foreign_author": pooled["papers_with_foreign_author"],
        "team_papers": pooled["team_papers"],
        **{f"top{k + 1}_name": p["name"] for k, p in enumerate(top[:8])},
        **{f"top{k + 1}_accepted": p["accepted"] for k, p in enumerate(top[:8])},
    }

    def formatted(lang):
        f = {}
        for k, v in raw.items():
            if k == "data_date":
                f[k] = f"{built.day}/{built.month}/{built.year}" if lang == "vi" else f"{built.day} {MONTHS_EN[built.month - 1]} {built.year}"
            elif k.endswith("_name"):
                f[k] = v
            elif "share" in k:
                f[k] = fmt_pct(v, lang, 2)
            elif k.endswith("_rate") or k.startswith("iclr_all") or k == "iclr_rate":
                f[k] = fmt_pct(v, lang, 0 if k in ("iclr_rate", "projected_rate") else 1)
            elif k.endswith("per_accept"):
                f[k] = fmt_num(v, lang, 1)
            elif k.startswith("avg_"):
                f[k] = fmt_num(v, lang, 1)
            else:
                f[k] = fmt_num(v, lang, 0)
        return f

    series = {
        "per_venue_year": per_venue_year,
        "unofficial_venue_2026": dict(unofficial_venue_2026),
        "neurips_vietnam": [{"year": y["year"], "papers": y["vietnam"], "share": 100 * y["vietnam"] / y["papers"],
                             "provisional": y["provisional"]} for y in neurips],
        "top": [{"name": p["name"], "institution": p["institution_short"], "official": p["official"],
                 "unofficial": p["own_page"]} for p in top[:8]],
    }
    return {"raw": raw, "vi": formatted("vi"), "en": formatted("en"), "series": series,
            "sources": {"site": SITE, "iclr_all": ICLR_ALL["source"]}}


# ---------------------------------------------------------------- charts (SVG strings)

def esc(s):
    return html.escape(str(s))


def svg(w, h, body, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-label="{esc(label)}" font-family="{esc(FONT)}">{body}</svg>')


def text(x, y, s, size=28, fill=INK, anchor="start", weight=400):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
            f'font-weight="{weight}">{esc(s)}</text>')


def spread(positions, gap):
    """Moves label y-positions apart so that no two are closer than `gap`, keeping their order."""
    order = sorted(range(len(positions)), key=lambda i: positions[i])
    ys = [positions[i] for i in order]
    for k in range(1, len(ys)):
        ys[k] = max(ys[k], ys[k - 1] + gap)
    out = [0] * len(positions)
    for k, i in enumerate(order):
        out[i] = ys[k]
    return out


def chart_trend(n, lang):
    s = n["series"]["per_venue_year"]
    years = list(range(2020, 2027))
    W, H, left, right, top, bottom = 1680, 680, 70, 230, 20, 120
    pw, ph = W - left - right, H - top - bottom
    peak = max(max(v.values()) for v in s.values())
    step = 5 if peak <= 30 else 10
    ymax = step * math.ceil(peak / step)
    X = lambda i: left + pw * i / (len(years) - 1)
    Y = lambda v: top + ph - ph * v / ymax
    b = []
    for v in range(0, ymax + 1, step):
        b.append(f'<line x1="{left}" x2="{left + pw}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{GRID if v else MUTED}" stroke-width="{1 if v else 1.5}"/>')
        b.append(text(left - 14, Y(v) + 9, v, 24, MUTED, "end"))
    totals = n["raw"]
    for i, y in enumerate(years):
        b.append(text(X(i), top + ph + 40, y, 26, INK2, "middle"))
        b.append(text(X(i), top + ph + 86, n[lang][f"acc_{y}"], 30, INK, "middle", 700))
    b.append(text(left - 14, top + ph + 86, "Tổng" if lang == "vi" else "Total", 24, MUTED, "end"))
    ends = []
    for v in VENUES:
        pts = [(X(i), Y(s[v][y])) for i, y in enumerate(years)]
        solid, last = pts[:-1], pts[-2:]
        provisional = n["series"]["unofficial_venue_2026"].get(v, 0) > 0
        b.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in solid)}" fill="none" stroke="{VENUE_COLOR[v]}" stroke-width="5" stroke-linejoin="round" stroke-linecap="round"/>')
        b.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in last)}" fill="none" stroke="{VENUE_COLOR[v]}" stroke-width="5" stroke-linecap="round"{DASH if provisional else ""}/>')
        for k, (x, y) in enumerate(pts):
            hollow = provisional and k == len(pts) - 1
            b.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" fill="{SURFACE if hollow else VENUE_COLOR[v]}" stroke="{VENUE_COLOR[v] if hollow else SURFACE}" stroke-width="{4 if hollow else 3}"/>')
        ends.append((v, pts[-1][1], s[v][2026]))
    ys = spread([e[1] for e in ends], 40)
    for (v, _, val), y in zip(ends, ys):
        b.append(f'<rect x="{left + pw + 26}" y="{y - 12:.1f}" width="18" height="18" rx="3" fill="{VENUE_COLOR[v]}"/>')
        b.append(text(left + pw + 54, y + 5, f"{VENUE_NAME[v]}  {val}", 28, INK, "start", 600))
    return svg(W, H, "".join(b), "Accepted papers per year and conference")


def chart_neurips(n, lang):
    rows = n["series"]["neurips_vietnam"]
    W, H, left, top, bottom = 1680, 640, 40, 60, 130
    ph = H - top - bottom
    band = (W - 2 * left) / len(rows)
    bw = band * 0.46
    peak = max(r["papers"] for r in rows)
    b = [f'<line x1="{left}" x2="{W - left}" y1="{top + ph}" y2="{top + ph}" stroke="{MUTED}" stroke-width="1.5"/>']
    for i, r in enumerate(rows):
        cx = left + band * (i + 0.5)
        h = ph * r["papers"] / peak
        x, y = cx - bw / 2, top + ph - h
        rr = min(6, h)
        d = (f"M{x:.1f},{top + ph} V{y + rr:.1f} Q{x:.1f},{y:.1f} {x + rr:.1f},{y:.1f} H{x + bw - rr:.1f} "
             f"Q{x + bw:.1f},{y:.1f} {x + bw:.1f},{y + rr:.1f} V{top + ph} Z")
        if r["provisional"]:
            b.append(f'<path d="{d}" fill="{SURFACE}" stroke="{ABROAD}" stroke-width="4" stroke-dasharray="10 8"/>')
        else:
            b.append(f'<path d="{d}" fill="{ABROAD}"/>')
        b.append(text(cx, y - 16, r["papers"], 34, INK, "middle", 700))
        b.append(text(cx, top + ph + 42, r["year"], 26, INK2, "middle"))
        b.append(text(cx, top + ph + 84, fmt_pct(r["share"], lang, 2), 26, MUTED, "middle"))
    b.append(text(left, top + ph + 120, ("Tỉ lệ trên tổng số bài track chính của NeurIPS. Năm 2026: danh sách chính thức chưa đầy đủ."
                                         if lang == "vi" else
                                         "Share of all NeurIPS main-track papers. 2026: the official list is still incomplete."), 22, MUTED))
    return svg(W, H, "".join(b), "NeurIPS main-track papers with an author in Vietnam")


def stat_tile(x, y, w, big, of, label, part, whole, color):
    b = [text(x, y + 120, big, 140, INK, "start", 700),
         text(x + 12 + 88 * len(str(big)), y + 120, f"/ {of}", 56, MUTED, "start", 400)]
    bar_y, bar_h = y + 170, 26
    pw = (w - 2) * part / whole
    b.append(f'<rect x="{x}" y="{bar_y}" width="{pw:.1f}" height="{bar_h}" rx="4" fill="{color}"/>')
    b.append(f'<rect x="{x + pw + 2:.1f}" y="{bar_y}" width="{w - pw - 2:.1f}" height="{bar_h}" rx="4" fill="{GRID}"/>')
    for k, line in enumerate(label):
        b.append(text(x, bar_y + 80 + 42 * k, line, 32, INK2))
    return "".join(b)


def chart_2026(n, lang):
    r, f = n["raw"], n[lang]
    W, H = 1680, 560
    if lang == "vi":
        a = ["chưa có trong danh sách chính thức,", "chỉ có trên trang cá nhân hoặc thông báo"]
        c = ["của những người bắt đầu làm việc", "ở Việt Nam từ năm 2023"]
    else:
        a = ["not in an official list yet,", "known from personal pages or announcements"]
        c = ["by people who started working", "in Vietnam in 2023 or later"]
    b = stat_tile(0, 20, 760, f["unofficial_2026"], f["acc_2026"], a, r["unofficial_2026"], r["acc_2026"], NOT)
    b += stat_tile(900, 20, 760, f["new_2026"], f["acc_2026"], c, r["new_2026"], r["acc_2026"], ABROAD)
    return svg(W, H, b, "Two caveats about the 2026 count")


def pie(cx, cy, rad, slices):
    """slices: [(value, fill, stroke or None, dash)] drawn clockwise from 12 o'clock with a 3px surface gap."""
    total = sum(s[0] for s in slices) or 1
    a = -math.pi / 2
    b = []
    for value, fill, stroke, dash in slices:
        share = value / total
        e = a + 2 * math.pi * share
        x1, y1 = cx + rad * math.cos(a), cy + rad * math.sin(a)
        x2, y2 = cx + rad * math.cos(e), cy + rad * math.sin(e)
        extra = f' stroke="{stroke}" stroke-width="4" stroke-dasharray="{dash}"' if stroke else f' stroke="{SURFACE}" stroke-width="4"'
        b.append(f'<path d="M{cx:.1f},{cy:.1f} L{x1:.1f},{y1:.1f} A{rad},{rad} 0 {int(share > 0.5)} 1 {x2:.1f},{y2:.1f} Z" fill="{fill}"{extra}/>')
        a = e
    return "".join(b)


def pie_legend(x, y, rows):
    b = []
    for k, (color, big, small, outline) in enumerate(rows):
        yy = y + k * 120
        if outline:
            b.append(f'<rect x="{x}" y="{yy - 26}" width="30" height="30" rx="4" fill="{SURFACE}" stroke="{color}" stroke-width="4"/>')
        else:
            b.append(f'<rect x="{x}" y="{yy - 26}" width="30" height="30" rx="4" fill="{color}"/>')
        b.append(text(x + 48, yy, big, 44, INK, "start", 700))
        b.append(text(x + 48, yy + 42, small, 28, INK2))
    return "".join(b)


def hbar_compare(x, y, w, rows):
    """rows: [(label, percent, formatted, color)] on a shared 0-100% scale."""
    b = []
    for k, (label, pct, shown, color) in enumerate(rows):
        yy = y + k * 96
        b.append(text(x, yy, label, 28, INK2))
        bw = w * pct / 100
        b.append(f'<rect x="{x}" y="{yy + 14}" width="{bw:.1f}" height="34" rx="4" fill="{color}"/>')
        b.append(text(x + bw + 14, yy + 42, shown, 32, INK, "start", 700))
    return "".join(b)


def chart_iclr(n, lang):
    r, f = n["raw"], n[lang]
    W, H = 1680, 620
    b = pie(270, 300, 250, [(r["iclr_accepted"], ACC, None, ""), (r["iclr_not_accepted"], NOT, None, "")])
    vi = lang == "vi"
    b += pie_legend(590, 230, [
        (ACC, f"{f['iclr_accepted']} {'bài được nhận' if vi else 'accepted'}", f"{f['iclr_rate']} {'số bài nộp' if vi else 'of submissions'}", False),
        (NOT, f"{f['iclr_not_accepted']} {'bị từ chối hoặc rút' if vi else 'rejected or withdrawn'}", ("trên tổng " if vi else "of ") + f["iclr_submitted"] + (" bài nộp" if vi else " submitted"), False)])
    b += text(1220, 150, "Tỉ lệ nhận" if vi else "Acceptance rate", 32, INK, "start", 700)
    b += hbar_compare(1220, 220, 360, [
        ("Nhóm này, ICLR 2020–2026" if vi else "This group, ICLR 2020–2026", r["iclr_rate"], f["iclr_rate"], ACC),
        ("Toàn ICLR 2025" if vi else "All of ICLR 2025", r["iclr_all_2025"], f["iclr_all_2025"], MUTED),
        ("Toàn ICLR 2026" if vi else "All of ICLR 2026", r["iclr_all_2026"], f["iclr_all_2026"], MUTED)])
    return svg(W, H, b, "ICLR submissions of the group")


def waffle(x, y, counts, cols, cell, gap):
    """counts: [(n, fill)] laid out row by row."""
    b, k = [], 0
    for value, fill in counts:
        for _ in range(value):
            cx, cy = x + (k % cols) * (cell + gap), y + (k // cols) * (cell + gap)
            b.append(f'<rect x="{cx}" y="{cy}" width="{cell}" height="{cell}" rx="4" fill="{fill}"/>')
            k += 1
    return "".join(b)


def chart_peraccept(n, lang):
    r, f = n["raw"], n[lang]
    vi = lang == "vi"
    W, H = 1680, 640
    b = text(0, 230, f["iclr_per_accept"], 260, NOT, "start", 700)
    b += text(10, 310, "bài nộp cho mỗi bài ICLR được nhận" if vi else "submissions per accepted ICLR paper", 40, INK, "start", 600)
    cols, cell, gap = 13, 52, 8
    x0 = 1680 - cols * (cell + gap) + gap
    b += waffle(x0, 40, [(r["iclr_accepted"], ACC), (r["iclr_not_accepted"], NOT)], cols, cell, gap)
    rows = math.ceil(r["iclr_submitted"] / cols)
    yb = 40 + rows * (cell + gap) + 40
    b += text(x0, yb, (f"Mỗi ô là một bài nộp ICLR: {f['iclr_accepted']} được nhận (xanh), {f['iclr_not_accepted']} không (đỏ)" if vi else
                       f"Each square is one ICLR submission: {f['iclr_accepted']} accepted (blue), {f['iclr_not_accepted']} not (red)"), 24, INK2)
    b += text(10, 420, (f"Ở ICLR 2026, {f['iclr_withdrawn_2026']} trên {f['iclr_submissions_2026']} bài nộp đã bị rút." if vi else
                        f"At ICLR 2026, {f['iclr_withdrawn_2026']} of {f['iclr_submissions_2026']} submissions were withdrawn."), 32, INK2)
    return svg(W, H, b, "Submissions per accepted ICLR paper")


def chart_estimate(n, lang):
    r, f = n["raw"], n[lang]
    vi = lang == "vi"
    W, H = 1680, 640
    est_not = r["projected_submissions"] - r["projected_accepted"]
    b = text(40, 40, "ICLR: đếm được" if vi else "ICLR: counted", 34, INK, "start", 700)
    b += pie(260, 300, 210, [(r["iclr_accepted"], ACC, None, ""), (r["iclr_not_accepted"], NOT, None, "")])
    b += text(520, 250, f"{f['iclr_rate']}", 56, INK, "start", 700)
    b += text(520, 296, "được nhận" if vi else "accepted", 28, INK2)
    b += text(520, 340, f"{f['iclr_accepted']} / {f['iclr_submitted']}", 28, MUTED)
    b += text(900, 40, "Cả năm hội nghị: ước tính" if vi else "All five conferences: estimated", 34, INK, "start", 700)
    b += pie(1120, 300, 210, [(r["projected_accepted"], ACC, None, ""), (est_not, "#f4c2c1", NOT, "12 8")])
    b += text(1380, 250, f"{f['projected_rate']}", 56, INK, "start", 700)
    b += text(1380, 296, "được nhận" if vi else "accepted", 28, INK2)
    b += text(1380, 340, f"{f['projected_accepted']} / ~{f['projected_submissions']}", 28, MUTED)
    b += text(40, 600, ("Phần đỏ nhạt là ước tính: tỉ lệ ICLR của từng người áp cho bốn hội nghị còn lại. Một bài của hai người được tính hai lượt."
                        if vi else
                        "The pale red part is an estimate: each person's ICLR rate applied to the other four. A paper of two people counts twice."), 24, MUTED)
    return svg(W, H, b, "Accepted against not accepted, counted and estimated")


def chart_teams(n, lang):
    r, f = n["raw"], n[lang]
    vi = lang == "vi"
    W, H = 1680, 640
    b = text(0, 60, (f"{f['avg_authors']} tác giả trên mỗi bài được nhận" if vi else f"{f['avg_authors']} authors per accepted paper"), 40, INK, "start", 700)
    unit = 1500 / r["avg_authors"]
    wv, wa = r["avg_authors_vietnam"] * unit, r["avg_authors_abroad"] * unit
    b += f'<rect x="0" y="100" width="{wv - 2:.1f}" height="70" rx="6" fill="{VN}"/>'
    b += f'<rect x="{wv + 2:.1f}" y="100" width="{wa - 2:.1f}" height="70" rx="6" fill="{ABROAD}"/>'
    b += text(16, 220, f"{f['avg_authors_vietnam']} {'ở Việt Nam' if vi else 'in Vietnam'}", 34, INK, "start", 700)
    b += text(wv + 18, 220, f"{f['avg_authors_abroad']} {'ở nước ngoài' if vi else 'abroad'}", 34, INK, "start", 700)
    cols, cell, gap = 20, 40, 7
    b += waffle(0, 300, [(r["papers_with_foreign_author"], ABROAD), (r["team_papers"] - r["papers_with_foreign_author"], GRID)], cols, cell, gap)
    xr = cols * (cell + gap) + 60
    b += text(xr, 380, f"{f['papers_with_foreign_author']} / {f['team_papers']}", 96, INK, "start", 700)
    b += text(xr, 440, "bài có ít nhất một đồng tác giả ở nước ngoài" if vi else "papers with at least one co-author abroad", 32, INK2)
    b += text(xr, 486, "(trong các bài có thông tin đơn vị)" if vi else "(among papers with known affiliations)", 26, MUTED)
    return svg(W, H, b, "Authors per accepted paper by where they work")


def chart_top(n, lang):
    rows = n["series"]["top"]
    vi = lang == "vi"
    W, row_h, bar_h, name_w = 1680, 66, 40, 440
    H = 70 + row_h * len(rows)
    peak = max(r["official"] + r["unofficial"] for r in rows)
    scale = (W - name_w - 240) / peak
    b = [f'<rect x="{name_w}" y="4" width="22" height="22" rx="4" fill="{ACC}"/>',
         text(name_w + 32, 23, "danh sách chính thức" if vi else "official lists", 24, INK2),
         f'<rect x="{name_w + 330}" y="4" width="22" height="22" rx="4" fill="{SURFACE}" stroke="{ACC}" stroke-width="3"/>',
         text(name_w + 362, 23, "trang cá nhân, thông báo (chưa chính thức)" if vi else "personal pages, announcements (unofficial)", 24, INK2)]
    for k, r in enumerate(rows):
        y = 60 + k * row_h
        b.append(text(name_w - 20, y + 30, r["name"], 30, INK, "end", 600))
        b.append(text(name_w - 20, y + 30, "", 24, MUTED, "end"))
        wo = r["official"] * scale
        b.append(f'<rect x="{name_w}" y="{y}" width="{max(wo - 2, 0):.1f}" height="{bar_h}" rx="4" fill="{ACC}"/>')
        x = name_w + wo
        if r["unofficial"]:
            wu = r["unofficial"] * scale
            b.append(f'<rect x="{x + 2:.1f}" y="{y + 2}" width="{wu - 4:.1f}" height="{bar_h - 4}" rx="4" fill="{SURFACE}" stroke="{ACC}" stroke-width="3"/>')
            x += wu
        total = r["official"] + r["unofficial"]
        b.append(text(x + 14, y + 31, f"{total}   {r['institution']}", 28, INK2))
    return svg(W, H, "".join(b), "Most accepted papers")


# ---------------------------------------------------------------- frames

FRAMES = ["title", "scope", "trend", "neurips", "y2026", "iclr", "peraccept", "estimate", "teams", "top", "takeaway", "end"]


def frame_content(name, n):
    """(heading, subheading, body html, chart svg or None, footnote) for one frame, in Vietnamese."""
    CHIPS = "".join(f'<span style="background:{VENUE_COLOR[v]}">{VENUE_NAME[v]}</span>' for v in VENUES)
    f = n["vi"]
    src = f"Nguồn: danh sách chính thức của hội nghị, OpenReview, trang cá nhân · số liệu đến {f['data_date']}"
    if name == "title":
        body = (f'<div class="hero-title">Có dễ để có bài ở<br>hội nghị AI hàng đầu<br>khi làm việc tại Việt Nam?</div>'
                f'<div class="hero-sub">Phía sau những tin “được nhận”</div>'
                f'<div class="chips">{CHIPS}</div>')
        return "", "", body, None, ""
    if name == "scope":
        body = (f'<div class="scope"><div class="big">{f["people"]}</div>'
                f'<div><div class="lead">giảng viên và nhà nghiên cứu<br>tại các trường, viện ở Việt Nam</div>'
                f'<div class="chips">{CHIPS}</div>'
                f'<ul><li>2020 – 2026, chỉ tính bài ở track chính</li>'
                f'<li>Mỗi người có ít nhất một bài được nhận</li>'
                f'<li>{f["accepted"]} bài được nhận, {f["unofficial"]} trong đó chưa chính thức</li></ul></div></div>')
        return "Dữ liệu", "", body, None, src
    if name == "trend":
        return ("Số bài được nhận mỗi năm", "Theo hội nghị; nét đứt: NeurIPS 2026 gồm cả bài chưa có trong danh sách chính thức",
                "", chart_trend(n, "vi"), src)
    if name == "neurips":
        return ("Bài NeurIPS có tác giả ở Việt Nam", "Mọi bài track chính có ít nhất một tác giả thuộc cơ sở ở Việt Nam, không chỉ nhóm này",
                "", chart_neurips(n, "vi"), "Nguồn: danh sách bài của NeurIPS (neurips.cc) · số liệu đến " + f["data_date"])
    if name == "y2026":
        return (f"{f['acc_2026']} bài năm 2026: hai lưu ý", "", "", chart_2026(n, "vi"), src)
    if name == "iclr":
        return ("ICLR: nơi duy nhất thấy được bài bị từ chối", "Mọi bài nộp ICLR của nhóm, 2020–2026",
                "", chart_iclr(n, "vi"), "Nguồn: OpenReview; tỉ lệ toàn ICLR: blog.iclr.cc · số liệu đến " + f["data_date"])
    if name == "peraccept":
        return ("Mỗi bài được nhận, bao nhiêu lần nộp?", "", "", chart_peraccept(n, "vi"),
                "Nguồn: OpenReview; số bài rút ở ICLR 2026: blog.iclr.cc · số liệu đến " + f["data_date"])
    if name == "estimate":
        return ("Nếu bốn hội nghị kia cũng công khai bài bị từ chối", "Ước tính từ tỉ lệ ICLR của từng người",
                "", chart_estimate(n, "vi"), src)
    if name == "teams":
        return ("Ai đứng sau mỗi bài", "Đơn vị của các tác giả trên bài được nhận", "", chart_teams(n, "vi"), src)
    if name == "top":
        return ("Nhiều bài được nhận nhất", "Số bài được nhận 2020–2026; số liệu từng người, kể cả bài nộp ICLR, có trên trang web",
                "", chart_top(n, "vi"), src)
    if name == "takeaway":
        body = (f'<div class="points">'
                f'<div><b>Bị từ chối là chuyện bình thường</b><span>ICLR: {f["iclr_accepted"]} trên {f["iclr_submitted"]} bài nộp được nhận ({f["iclr_rate"]})</span></div>'
                f'<div><b>Nhiều lần nộp cho một bài</b><span>≈ {f["iclr_per_accept"]} lần nộp mỗi bài ở ICLR; ước tính ≈ {f["projected_per_accept"]} cho cả năm hội nghị</span></div>'
                f'<div><b>Nhiều đồng tác giả, thường có cộng sự nước ngoài</b><span>{f["avg_authors"]} tác giả mỗi bài; {f["papers_with_foreign_author"]} trên {f["team_papers"]} bài có người ở nước ngoài</span></div>'
                f'</div>')
        return "Phía sau mỗi tin “được nhận”", "", body, None, src
    if name == "end":
        body = (f'<ul class="caveats"><li>Danh sách người được chọn thủ công, không phải mẫu đại diện</li>'
                f'<li>Bài bị từ chối chỉ nhìn thấy được ở ICLR</li>'
                f'<li>Bài được ghép theo hồ sơ OpenReview và theo tên; có thể sót hoặc nhầm người trùng tên</li>'
                f'<li>Đếm bài không nói lên chất lượng của bài</li></ul>'
                f'<div class="url">{esc(SITE.removeprefix("https://").rstrip("/"))}</div>'
                f'<div class="urlnote">Cách tính, số liệu từng người và danh sách bài</div>')
        return "Lưu ý", "", body, None, ""
    raise KeyError(name)


CSS = f"""
@page {{ size: 1920px 1080px; margin: 0; }}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; background: {SURFACE}; }}
body {{ font-family: {FONT}; color: {INK}; }}
.frame {{ position: relative; width: 1920px; height: 1080px; padding: 84px 120px 0; overflow: hidden; background: {SURFACE}; }}
.frame h1 {{ font-size: 62px; line-height: 1.15; margin: 0; font-weight: 700; letter-spacing: -0.01em; }}
.frame .subh {{ font-size: 30px; color: {INK2}; margin-top: 14px; }}
.frame .chart {{ position: absolute; left: 120px; right: 120px; top: 260px; bottom: 110px; display: flex; align-items: center; justify-content: center; }}
.frame .chart svg {{ max-width: 100%; max-height: 100%; height: auto; }}
.frame .foot {{ position: absolute; left: 120px; right: 120px; bottom: 44px; font-size: 22px; color: {MUTED}; }}
.frame .mark {{ position: absolute; right: 120px; bottom: 44px; font-size: 22px; color: {MUTED}; }}
.hero-title {{ font-size: 92px; font-weight: 800; line-height: 1.12; margin-top: 130px; letter-spacing: -0.015em; }}
.hero-sub {{ font-size: 44px; color: {INK2}; margin-top: 36px; }}
.chips {{ display: flex; gap: 14px; margin-top: 54px; }}
.chips span {{ color: #fff; font-weight: 700; font-size: 30px; padding: 10px 24px; border-radius: 8px; }}
.scope {{ display: flex; gap: 80px; align-items: flex-start; margin-top: 80px; }}
.scope .big {{ font-size: 360px; font-weight: 800; line-height: 0.9; color: {ACC}; letter-spacing: -0.03em; }}
.scope .lead {{ font-size: 52px; font-weight: 700; line-height: 1.2; }}
.scope ul {{ font-size: 34px; color: {INK2}; margin: 44px 0 0; padding-left: 1.1em; line-height: 1.6; }}
.points {{ margin-top: 70px; display: grid; gap: 44px; }}
.points div {{ border-left: 10px solid {ACC}; padding-left: 36px; }}
.points div:nth-child(1) {{ border-color: {NOT}; }}
.points div:nth-child(3) {{ border-color: {ABROAD}; }}
.points b {{ display: block; font-size: 52px; }}
.points span {{ display: block; font-size: 34px; color: {INK2}; margin-top: 8px; }}
.caveats {{ font-size: 40px; line-height: 1.55; margin: 60px 0 0; padding-left: 1.1em; color: {INK2}; }}
.url {{ font-size: 54px; font-weight: 700; color: {ACC}; margin-top: 70px; }}
.urlnote {{ font-size: 32px; color: {INK2}; margin-top: 10px; }}
"""


def frame_html(name, n, index):
    h, sub, body, chart, foot = frame_content(name, n)
    parts = [f'<section class="frame" id="f{index:02d}" data-name="{name}">']
    if h:
        parts.append(f"<h1>{esc(h)}</h1>")
    if sub:
        parts.append(f'<div class="subh">{esc(sub)}</div>')
    parts.append(body)
    if chart:
        parts.append(f'<div class="chart">{chart}</div>')
    if foot:
        parts.append(f'<div class="foot">{esc(foot)}</div>')
    parts.append("</section>")
    return "".join(parts)


def page(title, inner, extra_css="", script=""):
    return (f'<!doctype html><html lang="vi"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(title)}</title>'
            f"<style>{CSS}{extra_css}</style></head><body>{inner}{script}</body></html>")


DECK_CSS = """
html, body { height: 100%; overflow: hidden; background: #111; }
.deck { position: fixed; inset: 0; display: flex; align-items: center; justify-content: center; }
.deck .frame { position: absolute; transform-origin: center center; display: none; }
.deck .frame.on { display: block; }
.notes { position: fixed; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,.82); color: #fff; font-size: 26px;
         line-height: 1.45; padding: 18px 28px; display: none; max-height: 40vh; overflow: auto; }
.notes.on { display: block; }
.notes .en { color: #bbb; font-size: 21px; margin-top: 6px; }
.count { position: fixed; top: 10px; right: 16px; color: #888; font: 16px sans-serif; }
"""

DECK_JS = """
<script>
const frames = [...document.querySelectorAll('.deck .frame')];
const notes = document.querySelector('.notes');
let i = 0;
function fit() {
  const s = Math.min(innerWidth / 1920, innerHeight / 1080);
  frames.forEach(f => f.style.transform = `scale(${s})`);
}
function show(k) {
  i = Math.max(0, Math.min(frames.length - 1, k));
  frames.forEach((f, j) => f.classList.toggle('on', j === i));
  const n = NOTES[frames[i].dataset.name] || [];
  notes.innerHTML = n.map(l => `<div>${l.vi}</div><div class="en">${l.en}</div>`).join('<hr style="border-color:#333">');
  document.querySelector('.count').textContent = `${i + 1} / ${frames.length}`;
  history.replaceState(null, '', '#' + (i + 1));
}
addEventListener('resize', fit);
addEventListener('keydown', e => {
  if (['ArrowRight', 'PageDown', ' '].includes(e.key)) show(i + 1);
  else if (['ArrowLeft', 'PageUp'].includes(e.key)) show(i - 1);
  else if (e.key === 'Home') show(0);
  else if (e.key === 'End') show(frames.length - 1);
  else if (e.key === 'n' || e.key === 'N') notes.classList.toggle('on');
  else if (e.key === 'f' || e.key === 'F') document.documentElement.requestFullscreen?.();
});
addEventListener('click', () => show(i + 1));
fit(); show((parseInt(location.hash.slice(1)) || 1) - 1);
</script>
"""


# ---------------------------------------------------------------- narration, timing, subtitles

def spoken_syllables(line):
    """Rough count of spoken Vietnamese syllables; numbers are read out as several syllables."""
    count = 0
    for tok in line.split():
        digits = re.sub(r"\D", "", tok)
        if digits:
            count += max(1, round(len(digits.lstrip("0") or "0") * 1.6)) + ("%" in tok) * 2 + ("," in tok.strip(",.")) * 1
        elif re.search(r"\w", tok):
            count += 1
    return count


def fill(template, values):
    return template.format_map(values)


def timeline(scenes, n):
    t, out = 0.0, []
    for s in scenes:
        start = t
        lines = []
        for ln in s["lines"]:
            vi, en = fill(ln["vi"], n["vi"]), fill(ln["en"], n["en"])
            dur = spoken_syllables(vi) / SYLLABLES_PER_SECOND
            lines.append({**ln, "vi": vi, "en": en, "start": t, "end": t + dur})
            t += dur + PAUSE_AFTER_LINE
        t += PAUSE_AFTER_SCENE
        out.append({**s, "lines": lines, "start": start, "end": t})
    return out, t


def clock(sec, srt=False):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}" if srt else f"{m}:{s:02d}"


def cues(text_, start, end, limit):
    """Splits a line into subtitle cues of at most `limit` characters, timed by their share of the characters."""
    parts = []
    for sentence in re.split(r"(?<=[.?!])\s+", text_.strip()):
        while len(sentence) > limit:
            cut = max((m.end() for m in re.finditer(r"[,:;]\s", sentence[:limit])), default=0)
            if not cut:
                cut = sentence.rfind(" ", 0, limit) + 1
            parts.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if sentence:
            parts.append(sentence)
    total = sum(len(p) for p in parts) or 1
    t, out = start, []
    for p in parts:
        d = (end - start) * len(p) / total
        out.append((t, t + d, p))
        t += d
    return out


def wrap2(s, width=42):
    """Two subtitle lines at most, broken near the middle."""
    if len(s) <= width:
        return s
    mid = len(s) // 2
    left, right = s.rfind(" ", 0, mid + 1), s.find(" ", mid)
    cut = left if right == -1 or (left != -1 and mid - left <= right - mid) else right
    return s[:cut] + "\n" + s[cut + 1:]


def srt(timed, lang):
    out, k = [], 1
    for s in timed:
        for ln in s["lines"]:
            for a, b, p in cues(ln[lang], ln["start"], ln["end"], 84):
                out.append(f"{k}\n{clock(a, True)} --> {clock(b, True)}\n{wrap2(p)}\n")
                k += 1
    return "\n".join(out)


# ---------------------------------------------------------------- outputs

def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def on_screen(name, n):
    h, sub, body, chart, foot = frame_content(name, n)
    if h:
        return h + (f" — {sub}" if sub else "")
    plain = re.sub(r"<[^>]+>", " ", body)
    return " ".join(plain.split())[:160]


def script_md(timed, total, n):
    f = n["vi"]
    words = sum(len(ln["vi"].split()) for s in timed for ln in s["lines"])
    out = [f"# Kịch bản video: Có dễ để có bài ở hội nghị AI hàng đầu khi làm việc tại Việt Nam?\n",
           f"Số liệu đến {f['data_date']} (from the site's data, `frontend/data/`). Generated by `video/make_assets.py` from "
           f"`video/scenes.json`: edit the words there, not here.\n",
           f"Length: about {clock(total)} at {SYLLABLES_PER_SECOND:g} syllables per second ({words} words). "
           f"Times are estimates; re-time the subtitles to the recording.\n",
           "Frames: `video/frames/NN-name.png` (1920x1080), deck: `video/slides/index.html` "
           "(arrow keys, N shows the narration, F full screen).\n"]
    for k, s in enumerate(timed, 1):
        opt = " *(optional: cut if the video runs long)*" if s.get("optional") else ""
        out.append(f"\n## {k}. {s['title_vi']} / {s['title_en']} ({clock(s['start'])}–{clock(s['end'])}){opt}\n")
        out.append("| Time | Frame | On screen | Narration (vi) | Subtitle (en) |\n|---|---|---|---|---|")
        for ln in s["lines"]:
            idx = FRAMES.index(ln["frame"]) + 1
            cell = lambda x: x.replace("|", "\\|")
            out.append(f"| {clock(ln['start'])} | `{idx:02d}-{ln['frame']}` | {cell(on_screen(ln['frame'], n))} | "
                       f"{cell(ln['vi'])} | {cell(ln['en'])} |")
    out.append("\n## Numbers used\n")
    out.append("Every figure above is read from `video/numbers.json`, written by the same run:\n")
    for k in sorted(n["vi"]):
        if not k.endswith("_name") and not k.startswith("top"):
            out.append(f"- `{k}`: {n['vi'][k]} (en: {n['en'][k]})")
    return "\n".join(out) + "\n"


def youtube_md(timed, n, yt):
    f, e = n["vi"], n["en"]
    chapters = "\n".join(f"{clock(s['start'])} {s['title_vi']}" for s in timed)
    chapters_en = "\n".join(f"{clock(s['start'])} {s['title_en']}" for s in timed)
    titles = "\n".join(f"{k}. {fill(t, f)}" for k, t in enumerate(yt["titles_vi"], 1))
    titles_en = "\n".join(f"{k}. {fill(t, e)}" for k, t in enumerate(yt["titles_en"], 1))
    thumbs = "\n".join(f"- **{fill(t['big'], f)}** / {fill(t['small'], f)} ({t['note']})" for t in yt["thumbnail"])
    return f"""# YouTube

## Title options

{titles}

English:

{titles_en}

## Thumbnail wording

{thumbs}

Keep the thumbnail to pooled numbers; no faces or names of the people on the list.

## Description (Vietnamese)

{fill(yt['description_vi'], f)}

Trong video:
- Số bài được nhận của nhóm: {f['acc_2020']} (2020) → {f['acc_2024']} (2024) → {f['acc_2025']} (2025) → {f['acc_2026']} (2026)
- ICLR: {f['iclr_submitted']} bài nộp, {f['iclr_accepted']} được nhận ({f['iclr_rate']}), khoảng {f['iclr_per_accept']} lần nộp cho mỗi bài được nhận
- Trung bình {f['avg_authors']} tác giả mỗi bài; {f['papers_with_foreign_author']}/{f['team_papers']} bài có đồng tác giả ở nước ngoài

Chương:
{chapters}

Trang web (cách tính, số liệu từng người, danh sách bài): {SITE}
Bài viết: {SITE}is-it-that-easy/

Nguồn:
- Danh sách bài chính thức: iclr.cc, neurips.cc, icml.cc, CVF Open Access (CVPR), ACL Anthology
- Bài nộp và kết quả ICLR: OpenReview
- Tỉ lệ nhận và số bài rút của toàn ICLR: {ICLR_ALL['source']}
- {f['unofficial']} bài lấy từ trang cá nhân hoặc thông báo của trường (danh sách NeurIPS 2026 chưa đầy đủ)

Lưu ý: danh sách người được chọn thủ công; bài bị từ chối chỉ thấy được ở ICLR; con số cho cả năm hội nghị là ước tính; đếm bài không nói lên chất lượng của bài.

Kịch bản và biểu đồ được soạn với sự hỗ trợ của một mô hình ngôn ngữ (Claude); số liệu lấy từ dữ liệu của trang web.

## Description (English)

{fill(yt['description_en'], e)}

Chapters:
{chapters_en}

Website (method, per-person records, paper lists): {SITE}

Sources: the conferences' official paper lists, OpenReview (ICLR submissions and outcomes), ICLR's own figures ({ICLR_ALL['source']}), and personal pages or university announcements for {e['unofficial']} papers not yet in an official list.

Script and charts were drafted with the help of a language model (Claude); the figures come from the website's data.
"""


def render_png(slides_dir, frames_dir):
    browser = shutil.which("chromium") or shutil.which("google-chrome") or shutil.which("chromium-browser")
    if not browser:
        print("chromium not found; skipping PNG frames")
        return
    frames_dir.mkdir(parents=True, exist_ok=True)
    for page_ in sorted(slides_dir.glob("[0-9][0-9]-*.html")):
        out = frames_dir / (page_.stem + ".png")
        subprocess.run([browser, "--headless", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                        "--window-size=1920,1080", f"--screenshot={out}", page_.as_uri()],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        print("  ", out.relative_to(ROOT))


def main():
    n = compute()
    scenes = json.loads((OUT / "scenes.json").read_text(encoding="utf-8"))
    timed, total = timeline(scenes["scenes"], n)

    write(OUT / "numbers.json", json.dumps(n, ensure_ascii=False, indent=1))
    write(OUT / "script.md", script_md(timed, total, n))
    write(OUT / "narration.vi.txt", "\n\n".join(
        f"[{s['title_vi']}]\n" + "\n".join(ln["vi"] for ln in s["lines"]) for s in timed) + "\n")
    write(OUT / "subtitles.en.srt", srt(timed, "en"))
    write(OUT / "subtitles.vi.srt", srt(timed, "vi"))
    write(OUT / "youtube.md", youtube_md(timed, n, scenes["youtube"]))

    sections = []
    for k, name in enumerate(FRAMES, 1):
        sec = frame_html(name, n, k)
        sections.append(sec)
        write(OUT / "slides" / f"{k:02d}-{name}.html", page(f"{k:02d} {name}", sec))
        chart = frame_content(name, n)[3]
        if chart:
            write(OUT / "charts" / f"{k:02d}-{name}.svg", chart)
    notes = collections.defaultdict(list)
    for s in timed:
        for ln in s["lines"]:
            notes[ln["frame"]].append({"vi": esc(ln["vi"]), "en": esc(ln["en"])})
    deck_script = f"<script>const NOTES = {json.dumps(notes, ensure_ascii=False)};</script>{DECK_JS}"
    write(OUT / "slides" / "index.html",
          page("Video slides", f'<div class="deck">{"".join(sections)}</div><div class="notes"></div><div class="count"></div>',
               DECK_CSS, deck_script))

    print(f"video: about {clock(total)} of narration, {len(FRAMES)} frames, data of {n['vi']['data_date']}")
    if "--no-png" not in sys.argv:
        render_png(OUT / "slides", OUT / "frames")


if __name__ == "__main__":
    main()
