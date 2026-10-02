"""Writes the Slides deck (project/deck.json + project/slides/*.html) for the Short's story, in the Short's cheerful look.

    python3 video/make_short.py && python3 video/make_deck.py
Then publish the files under ROOT to the deck artifact (see video/artifact-link.txt).
"""
import json
import math
from pathlib import Path

ROOT = Path("/tmp/claude-1000/-home-thanh-Area-misc-vn-at-top-ai-conference/49e48b6a-359b-4563-ad93-7089ac65cd59/scratchpad/deck")
V = Path(__file__).resolve().parent
n = json.loads((V / "short" / "numbers.json").read_text(encoding="utf-8"))
f, r = n["vi"], n["raw"]
spec = json.loads((V / "short.json").read_text(encoding="utf-8"))

INK, INK2, MUTED, WHITE = "#24212b", "#4c4757", "#6f6979", "#ffffff"
ACC, NOT, ABROAD = "#2a78d6", "#e34948", "#eb6834"
BG = {"cover": "#fff1d0", "hook": "#fff1d0", "iclr": "#e5f1ff", "neurips": "#ffece6", "authors": "#efe8ff",
      "team": "#e3f6ec", "end": "#ffd84d"}
FONT = "'Baloo 2', Arial, sans-serif"
FOOT = f"{f['people']} giảng viên, nhà nghiên cứu ở Việt Nam · số liệu đến {f['data_date']}"
SHADOW = "box-shadow:0 14px 0 rgba(36,33,43,0.12)"


def notes(frame):
    lines = [l for l in spec["lines"] if l["frame"] == frame]
    vi = " ".join(l["vi"].format_map(n["vi"]) for l in lines)
    en = " ".join(l["en"].format_map(n["en"]) for l in lines)
    return f"<aside>{vi}\n\n{en}</aside>" if lines else ""


def dots(groups, cols, cell, gap, label):
    total = sum(c for c, _, _ in groups)
    w, h = cols * (cell + gap) - gap, math.ceil(total / cols) * (cell + gap) - gap
    out, k = [], 0
    for count, fill, dashed in groups:
        for _ in range(count):
            cx, cy = (k % cols) * (cell + gap) + cell / 2, (k // cols) * (cell + gap) + cell / 2
            if dashed:
                out.append(f'<circle cx="{cx}" cy="{cy}" r="{cell / 2 - 1.5}" fill="none" stroke="{fill}" stroke-width="3" stroke-dasharray="5 4"/>')
            else:
                out.append(f'<circle cx="{cx}" cy="{cy}" r="{cell / 2}" fill="{fill}"/>')
            k += 1
    return (f'<svg aria-label="{label}" width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">'
            + "".join(out) + "</svg>")


def key(items):
    cells = []
    for color, label, dashed in items:
        sw = f"border:3px dashed {color}" if dashed else f"background:{color}"
        cells.append(f'<div style="display:flex;flex-direction:row;align-items:center;gap:12px">'
                     f'<div style="width:30px;height:30px;border-radius:50%;{sw}"></div>'
                     f'<p style="font-size:30px;font-weight:600;color:{INK2}">{label}</p></div>')
    return f'<div style="display:flex;flex-direction:row;gap:36px;align-items:center">{"".join(cells)}</div>'


def pill(text_):
    return (f'<div style="display:flex;flex-direction:row"><p style="font-size:34px;font-weight:700;color:{WHITE};'
            f'background:{INK};padding:8px 28px 2px;border-radius:999px">{text_}</p></div>')


def foot():
    return f'<p style="position:absolute;left:128px;bottom:64px;width:1664px;font-size:24px;font-weight:600;color:{MUTED}">{FOOT}</p>'


def section(sid, body, frame=None, padding="128px 128px 160px", extra=""):
    return (f'<section id="{sid}" data-transition="push" style="background:{BG[sid]};color:{INK};font-family:{FONT};'
            f'padding:{padding};display:flex;flex-direction:column;{extra}">{body}{notes(frame) if frame else ""}</section>\n')


slides = {}

slides["cover"] = section("cover", f"""
{pill("ICLR · NeurIPS · ICML · CVPR · ACL")}
<div style="flex:1"></div>
<h1 style="font-size:132px;font-weight:800;line-height:1.0">Khoe bài NeurIPS,<br><span style="color:{NOT}">nhưng đã trượt<br>bao nhiêu bài? 🤔</span></h1>
<div style="flex:1"></div>
<p style="font-size:34px;font-weight:600;color:{INK2}">{f['people']} giảng viên, nhà nghiên cứu ở Việt Nam · 2020–2026</p>
""", padding="128px")

slides["hook"] = section("hook", f"""
<div style="display:flex;flex-direction:row">
<h1 style="font-size:112px;font-weight:800;line-height:1.05;background:{WHITE};padding:48px 64px 32px;border-radius:56px;transform:rotate(-3deg);{SHADOW}">“Lab mình có bài NeurIPS!” 🎉</h1>
</div>
<h1 style="font-size:112px;font-weight:800;line-height:1.05;color:{NOT}">Còn bị từ chối bao nhiêu bài? 🤔</h1>
""", frame="hook", padding="128px", extra="justify-content:center;gap:110px")

slides["iclr"] = section("iclr", f"""
{pill("ICLR · 2020–2026")}
<div style="flex:1;display:flex;flex-direction:row;align-items:center;gap:96px">
<div style="display:flex;flex-direction:column;gap:4px;width:620px">
<h1 style="font-size:210px;font-weight:800;line-height:1"><span style="color:{ACC}">{f['iclr_accepted']}</span> / {f['iclr_submitted']}</h1>
<p style="font-size:48px;font-weight:700;color:{INK2}">bài nộp được nhận</p>
</div>
<div style="display:flex;flex-direction:column;gap:32px">
{dots([(r["iclr_accepted"], ACC, False), (r["iclr_not_accepted"], NOT, False)], 13, 56, 10, "ICLR: 13 of 61 submissions accepted")}
{key([(ACC, "được nhận", False), (NOT, "bị từ chối, rút", False)])}
</div>
</div>
{foot()}
""", frame="iclr")

slides["neurips"] = section("neurips", f"""
{pill("NeurIPS 2026")}
<div style="flex:1;display:flex;flex-direction:row;align-items:center;gap:72px">
<div style="display:flex;flex-direction:column;gap:36px;width:640px">
<h1 style="font-size:116px;font-weight:800;line-height:1.0"><span style="color:{ACC}">{f['neurips_2026']}</span> bài<br>được nhận 🎉</h1>
<div style="display:flex;flex-direction:row">
<div style="display:flex;flex-direction:column;background:{WHITE};padding:28px 40px 18px;border-radius:36px;transform:rotate(-2.5deg);{SHADOW}">
<p style="font-size:60px;font-weight:800;color:{NOT};line-height:1.1">≈ {f['rejections_low']}–{f['rejections_high']} bài trượt 😅</p>
<p style="font-size:30px;font-weight:600;color:{MUTED}">ước tính</p>
</div>
</div>
</div>
<div style="display:flex;flex-direction:column;gap:30px">
{dots([(r["neurips_2026"], ACC, False), (r["rejections_low"], NOT, False), (r["rejections_high"] - r["rejections_low"], NOT, True)], 22, 34, 8, "NeurIPS 2026: 33 accepted, about 60 to 120 rejected (estimate)")}
{key([(ACC, "được nhận", False), (NOT, "trượt", False), (NOT, "ước tính cao", True)])}
<p style="font-size:28px;font-weight:600;color:{INK2}">* chưa tính người chưa có bài nào được nhận</p>
</div>
</div>
{foot()}
""", frame="neurips")


def metric(value, label, color, lead=""):
    bar = 400
    filled = round(bar * value / r["judged"])
    word = (f'<p style="font-size:48px;font-weight:800;color:{NOT};line-height:1">{lead}</p>' if lead
            else '<p style="font-size:48px;line-height:1">&#160;</p>')
    return (f'<div style="flex:1;display:flex;flex-direction:column;gap:18px;background:{WHITE};padding:44px 48px;border-radius:40px;{SHADOW}">'
            + word
            + f'<h2 style="font-size:100px;font-weight:800;line-height:1">{value}<span style="color:{MUTED};font-weight:700"> / {f["judged"]}</span></h2>'
            f'<p style="font-size:38px;font-weight:700;color:{INK2};line-height:1.15">{label}</p>'
            f'<div style="width:{bar}px;height:28px;border-radius:14px;background:#ece8f3;display:flex;flex-direction:row">'
            f'<div style="width:{filled}px;height:28px;border-radius:14px;background:{color}"></div></div></div>')


slides["authors"] = section("authors", f"""
{pill("Ai viết các bài được nhận? ✍️")}
<p style="font-size:34px;font-weight:600;color:{INK2}">{f['judged']}/{f['accepted_total']} bài có ghi đơn vị · 5 hội nghị · 2020–2026</p>
<div style="flex:1"></div>
<div style="display:flex;flex-direction:row;gap:36px">
{metric(r['first_own'], 'tác giả đầu<br>cùng trường', ACC, 'chỉ')}
{metric(r['majority_own'], 'đa số tác giả<br>cùng trường', ACC, 'chỉ')}
{metric(r['majority_abroad'], 'đa số tác giả<br>ở nước ngoài', ABROAD)}
</div>
<div style="flex:1"></div>
{foot()}
""", frame="authors", extra="gap:20px")

slides["team"] = section("team", f"""
<div style="flex:1;display:flex;flex-direction:row;align-items:center;gap:110px">
<div style="display:flex;flex-direction:column;gap:8px">
<h1 style="font-size:250px;font-weight:800;line-height:1">{f['authors_mean']}</h1>
<p style="font-size:48px;font-weight:700;color:{INK2}">👥 tác giả mỗi bài · tối đa {f['authors_max']}</p>
</div>
<div style="display:flex;flex-direction:column;gap:16px;background:{WHITE};padding:48px 56px 36px;border-radius:44px;transform:rotate(2deg);{SHADOW}">
<h2 style="font-size:104px;font-weight:800;line-height:1">{f['accepted_total']} → <span style="color:{ACC}">{f['person_credits']}</span></h2>
<p style="font-size:38px;font-weight:700;color:{INK2}">bài → lượt “có bài” 🎉</p>
</div>
</div>
{foot()}
""")

slides["end"] = section("end", f"""
<h1 style="font-size:140px;font-weight:800;line-height:1.0">Bị từ chối vẫn<br>nhiều hơn được nhận.</h1>
<div style="display:flex;flex-direction:row">
<h2 style="font-size:96px;font-weight:800;line-height:1.1;background:{WHITE};padding:40px 60px 26px;border-radius:48px;transform:rotate(2deg);{SHADOW}">Chưa có bài? Đừng mặc cảm 💪</h2>
</div>
""", frame="end", padding="128px", extra="justify-content:center;gap:80px")

order = list(slides)
deck = {"v": 4, "createdOnFiles": {"v": 1, "at": "2026-10-01T12:25:28Z"}, "lists": "css",
        "title": "Khoe bài NeurIPS, nhưng đã trượt bao nhiêu bài?", "order": order,
        "sections": {"s1": {"description": "Câu hỏi", "start": "cover"},
                     "s2": {"description": "Số liệu: ICLR, NeurIPS, tác giả", "start": "iclr"},
                     "s3": {"description": "Kết", "start": "end"}},
        "faces": {"baloo-2": {"family": "Baloo 2",
                              "href": "https://fonts.googleapis.com/css2?family=Baloo+2:wght@500;600;700;800&display=swap"}},
        "designSystems": []}
(ROOT / "project" / "slides").mkdir(parents=True, exist_ok=True)
(ROOT / "project" / "deck.json").write_text(json.dumps(deck, ensure_ascii=False, indent=1), encoding="utf-8")
for sid, html in slides.items():
    (ROOT / "project" / "slides" / f"{sid}.html").write_text(html, encoding="utf-8")
print(order)
