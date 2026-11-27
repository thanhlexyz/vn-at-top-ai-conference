import collections
import csv
import datetime
import gzip
import html
import json
import re
import unicodedata
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
CSV_DIR = BACKEND / "data" / "csv"
JSON_DIR = BACKEND / "data" / "json"
FRONTEND = BACKEND.parent / "frontend"
RAW = BACKEND / "raw"
WORK = BACKEND / "work"
ACCEPTED = WORK / "accepted.jsonl.gz"
OPENREVIEW_RAW = RAW / "openreview"

ROSTER = CSV_DIR / "roster.csv"
REVIEW = CSV_DIR / "review.csv"
CANDIDATES = CSV_DIR / "candidates.csv"

FIRST_YEAR = 2020
LAST_YEAR = max(datetime.date.today().year, 2027)
YEARS = list(range(FIRST_YEAR, LAST_YEAR + 1))

VENUES = [
    {"key": "iclr", "name": "ICLR", "full_name": "International Conference on Learning Representations",
     "rejections": "full"},
    {"key": "neurips", "name": "NeurIPS", "full_name": "Conference on Neural Information Processing Systems",
     "rejections": "partial"},
    {"key": "icml", "name": "ICML", "full_name": "International Conference on Machine Learning",
     "rejections": "none"},
    {"key": "cvpr", "name": "CVPR", "full_name": "IEEE/CVF Conference on Computer Vision and Pattern Recognition",
     "rejections": "none"},
    {"key": "iccv", "name": "ICCV", "full_name": "IEEE/CVF International Conference on Computer Vision",
     "rejections": "none"},
    {"key": "eccv", "name": "ECCV", "full_name": "European Conference on Computer Vision",
     "rejections": "none"},
    {"key": "acl", "name": "ACL", "full_name": "Annual Meeting of the Association for Computational Linguistics",
     "rejections": "none"},
    {"key": "emnlp", "name": "EMNLP", "full_name": "Conference on Empirical Methods in Natural Language Processing",
     "rejections": "none"},
    {"key": "aaai", "name": "AAAI", "full_name": "AAAI Conference on Artificial Intelligence",
     "rejections": "none"},
    {"key": "ijcai", "name": "IJCAI", "full_name": "International Joint Conference on Artificial Intelligence",
     "rejections": "none"},
    {"key": "icra", "name": "ICRA", "full_name": "IEEE International Conference on Robotics and Automation",
     "rejections": "none"},
    {"key": "iros", "name": "IROS", "full_name": "IEEE/RSJ International Conference on Intelligent Robots and Systems",
     "rejections": "none"},
    {"key": "rss", "name": "RSS", "full_name": "Robotics: Science and Systems",
     "rejections": "none"},
]
VENUE_KEYS = [v["key"] for v in VENUES]

DECISION_DATES = {
    "aaai":    {2020: "2019-11-10", 2021: "2020-12-01", 2022: "2021-12-01", 2023: "2022-11-18", 2024: "2023-12-09",
                2025: "2024-12-09", 2026: "2025-11-08"},
    "ijcai":   {2020: "2020-04-20", 2021: "2021-04-30", 2022: "2022-04-20", 2023: "2023-04-19", 2024: "2024-04-16",
                2025: "2025-04-29", 2026: "2026-04-29"},
    "iclr":    {2020: "2019-12-19", 2021: "2021-01-12", 2022: "2022-01-24", 2023: "2023-01-21", 2024: "2024-01-16",
                2025: "2025-01-22", 2026: "2026-01-26"},
    "neurips": {2020: "2020-09-25", 2021: "2021-09-28", 2022: "2022-09-14", 2023: "2023-09-21", 2024: "2024-09-25",
                2025: "2025-09-18", 2026: "2026-09-24"},
    "icml":    {2020: "2020-06-01", 2021: "2021-05-08", 2022: "2022-05-14", 2023: "2023-04-24", 2024: "2024-05-01",
                2025: "2025-05-01", 2026: "2026-05-01"},
    "cvpr":    {2020: "2020-02-23", 2021: "2021-02-28", 2022: "2022-03-02", 2023: "2023-02-27", 2024: "2024-02-26",
                2025: "2025-02-26", 2026: "2026-02-20"},
    "iccv":    {2021: "2021-07-22", 2023: "2023-07-13", 2025: "2025-06-25"},
    "eccv":    {2020: "2020-07-03", 2022: "2022-07-03", 2024: "2024-07-01", 2026: "2026-06-25"},
    "acl":     {2020: "2020-04-03", 2021: "2021-05-05", 2022: "2022-02-23", 2023: "2023-05-01", 2024: "2024-05-15",
                2025: "2025-05-15", 2026: "2026-04-15"},
    "emnlp":   {2020: "2020-09-14", 2021: "2021-08-25", 2022: "2022-10-06", 2023: "2023-10-07", 2024: "2024-09-20",
                2025: "2025-08-20", 2026: "2026-08-20"},
    "icra":    {2020: "2020-01-21", 2021: "2021-02-28", 2022: "2022-01-31", 2023: "2023-01-16", 2024: "2024-01-29",
                2025: "2025-01-27", 2026: "2026-01-31"},
    "iros":    {2020: "2020-06-30", 2021: "2021-06-30", 2022: "2022-06-30", 2023: "2023-06-30", 2024: "2024-06-30",
                2025: "2025-06-30", 2026: "2026-06-16"},
    "rss":     {2020: "2020-05-11", 2021: "2021-05-10", 2022: "2022-04-15", 2023: "2023-04-22", 2024: "2024-05-10",
                2025: "2025-04-10", 2026: "2026-04-27"},
}


RECENT_MONTHS = 12


def recent_from(today=None):
    today = today or datetime.date.today()
    month = today.year * 12 + today.month - 1 - RECENT_MONTHS
    return f"{month // 12}-{month % 12 + 1:02d}-01"


RECENT_FROM = recent_from()


def is_recent(venue, year):
    return DECISION_DATES.get(venue, {}).get(year, "9999") >= RECENT_FROM


def held(venue, year):
    return not ((venue == "iccv" and year % 2 == 0) or (venue == "eccv" and year % 2 == 1))
VENUE_NAME = {v["key"]: v["name"] for v in VENUES}
VENUE_GROUPS = [{"key": "ai", "name": "AI", "venues": ["aaai", "ijcai"]},
                {"key": "ml", "name": "ML", "venues": ["iclr", "neurips", "icml"]},
                {"key": "cv", "name": "CV", "venues": ["cvpr", "iccv", "eccv"]},
                {"key": "nlp", "name": "NLP", "venues": ["acl", "emnlp"]},
                {"key": "rb", "name": "RB", "venues": ["icra", "iros", "rss"]}]
for _g in VENUE_GROUPS:
    _g["names"] = [VENUE_NAME[k] for k in _g["venues"]]

NOT_ACCEPTED = ("rejected", "withdrawn", "desk_rejected")
STATUS_LABEL = {"accepted": "accepted", "rejected": "rejected", "withdrawn": "withdrawn",
                "desk_rejected": "desk-rejected", "unknown": "unknown"}


def strip_accents(s):
    s = s.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm_name(s):
    s = strip_accents(html.unescape(s or ""))
    return " ".join(re.sub(r"[^A-Za-z0-9]+", " ", s).lower().split())


def name_key(s):
    tokens = norm_name(s).split()
    full = [t for t in tokens if len(t) > 1]
    return " ".join(sorted(full if len(full) >= 2 else tokens))


ACRONYMS = {"LLM": "LLM", "LLMS": "LLMs", "LARS": "LARS", "AI": "AI", "3D": "3D", "2D": "2D", "GNN": "GNN", "GNNS": "GNNs",
            "RL": "RL", "RLVR": "RLVR", "VLA": "VLA", "VLM": "VLM", "VLMS": "VLMs", "NLP": "NLP", "OOD": "OOD", "GAN": "GAN",
            "CNN": "CNN", "ML": "ML", "MLP": "MLP", "DPO": "DPO", "SGD": "SGD", "EEG": "EEG", "CT": "CT", "PET": "PET",
            "LORA": "LoRA", "VIT": "ViT", "VITS": "ViTs", "QA": "QA", "RAG": "RAG"}
SMALL_WORDS = {"a", "an", "the", "and", "or", "but", "for", "nor", "of", "in", "on", "at", "to", "by", "via", "with", "from",
               "as", "vs", "into", "over", "under"}


def nice_title(title):
    letters = [c for c in title if c.isalpha()]
    if not letters or sum(c.isupper() for c in letters) < 0.7 * len(letters):
        return title

    def word(w, first):
        if w.upper() in ACRONYMS:
            return ACRONYMS[w.upper()]
        if not first and w.lower() in SMALL_WORDS:
            return w.lower()
        return w[:1].upper() + w[1:].lower()
    out, first = [], True
    for token in re.split(r"(\s+)", title):
        if not token.strip():
            out.append(token)
            continue
        parts = re.split(r"(-)", token)
        out.append("".join(p if p == "-" else word(p, first and k == 0) for k, p in enumerate(parts)))
        first = token.endswith(":")
    return "".join(out)


def norm_title(s):
    s = strip_accents(html.unescape(s or ""))
    s = re.sub(r"\\[a-zA-Z]+|\\.", "", s)
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", strip_accents(s).lower()).strip("-")


VN_INSTITUTIONS = [
    (r"vin ?uni", "VinUniversity", "VinUni", True),
    (r"vin ?ai\b", "VinAI Research", "VinAI", False),
    (r"vin ?big ?data|vingroup big data", "VinBigData", "VinBigData", False),
    (r"cinnamon ?(ai|lab)", "Cinnamon AI", "Cinnamon AI", False),
    (r"nvidia.*(viet ?nam|ho chi minh|ha ?noi)", "NVIDIA Vietnam", "NVIDIA", False),
    (r"vinbrain|vinfast|vingroup|vin ?robotics|vinmotion|vintech", "Vingroup", "Vingroup", False),
    (r"ha ?noi university of science (and |& )?tech|\bsoict\b|bach khoa ha ?noi",
     "Hanoi University of Science and Technology", "HUST", True),
    (r"university of science and technology of ha ?noi|\busth\b",
     "University of Science and Technology of Hanoi", "USTH", True),
    (r"ha ?noi (university|institute) of industry|\bhaui\b|dai hoc cong nghiep ha ?noi",
     "Hanoi University of Industry", "HaUI", True),
    (r"ha ?noi university of science\b(?! (and |& )?tech)|vnu university of science|vnu\W+hus\b",
     "VNU University of Science, Hanoi", "VNU-HUS", True),
    (r"ho chi minh (city )?university of technology and education|university of technical education\W+ho chi minh",
     "Ho Chi Minh City University of Technology and Education", "HCMUTE", True),
    (r"\bhcmut\b|ho chi minh (city )?university of technology(?! and education)|bach khoa",
     "Ho Chi Minh City University of Technology, VNU-HCM", "HCMUT", True),
    (r"\bhcmus\b|university of science\W+(vnu|vietnam national|ho chi minh|hcm)"
     r"|ho chi minh (city )?university of science\b|(vnu\W?hcm|vnuhcm)\W+university of science"
     r"|university of science\b(?! (and |& )?tech)[^;|]{0,80}?ho chi minh",
     "University of Science, VNU-HCM", "HCMUS", True),
    (r"university of information technology\W+(vnu|vietnam|ho chi minh|hcm)|\buit\b\W+(vnu|ho chi minh|hcm)",
     "University of Information Technology, VNU-HCM", "UIT", True),
    (r"international university\W+(vnu|vietnam national|ho chi minh|hcm)",
     "International University, VNU-HCM", "HCMIU", True),
    (r"university of engineering and technology\W+(vnu|vietnam|ha ?noi)|vnu\W+(university of engineering|uet)"
     r"|viet ?nam national university\W+university of engineering",
     "VNU University of Engineering and Technology", "VNU-UET", True),
    (r"fpt university", "FPT University", "FPT University", True),
    (r"\bfpt\b", "FPT Software AI Center", "FPT", False),
    (r"posts (and|&) telecom(munications?|\.)? inst(itute|\.)? (of )?tech|\bptit\b",
     "Posts and Telecommunications Institute of Technology", "PTIT", True),
    (r"phenikaa", "Phenikaa University", "Phenikaa", True),
    (r"ton duc thang", "Ton Duc Thang University", "TDTU", True),
    (r"duy tan univ", "Duy Tan University", "Duy Tan", True),
    (r"ho chi minh (city )?university of economics|university of economics\W+ho chi minh|\bueh\b",
     "University of Economics Ho Chi Minh City", "UEH", True),
    (r"ho chi minh (city )?university of education", "Ho Chi Minh City University of Education", "HCMUE", True),
    (r"ha ?noi national university of education", "Hanoi National University of Education", "HNUE", True),
    (r"national economics university", "National Economics University", "NEU", True),
    (r"ha ?noi medical university", "Hanoi Medical University", "HMU", True),
    (r"le quy don", "Le Quy Don Technical University", "LQDTU", True),
    (r"thuy ?loi univ", "Thuyloi University", "TLU", True),
    (r"thang ?long univ", "Thang Long University", "DHTL", True),
    (r"can tho university(?! of)", "Can Tho University", "CTU", True),
    (r"hue university", "Hue University", "Hue University", True),
    (r"eastern international univ", "Eastern International University", "EIU", True),
    (r"university of da ?nang|da ?nang university", "University of Danang", "UDN", True),
    (r"rmit\b.*viet ?nam", "RMIT University Vietnam", "RMIT Vietnam", True),
    (r"fulbright university viet ?nam", "Fulbright University Vietnam", "Fulbright VN", True),
    (r"vietnam\w* german university|vietnamese-german", "Vietnamese-German University", "VGU", True),
    (r"viettel", "Viettel", "Viettel", False),
    (r"\bvietai\b", "VietAI", "VietAI", False),
    (r"viet ?nam academy of science and technology", "Vietnam Academy of Science and Technology", "VAST", True),
    (r"viet ?nam national university\W+(ho chi minh|hcm)|\bvnu\W?hcm\b|\bvnuhcm\b",
     "Vietnam National University, Ho Chi Minh City", "VNU-HCM", True),
    (r"viet ?nam national university|\bvnu\b", "Vietnam National University, Hanoi", "VNU", True),
]
_VN_COMPILED = [(re.compile(p, re.I), full, short, uni) for p, full, short, uni in VN_INSTITUTIONS]
_VN_GENERIC = re.compile(r"viet ?nam\b|\bha ?noi\b|ho chi minh|\bsaigon\b|\bda ?nang\b|\bcan tho\b|\bthai nguyen\b"
                         r"|\bquy nhon\b|\bnha trang\b|\bhai ?phong\b|\bthu dau mot\b", re.I)


_VNU_HCM = {"HCMUS", "HCMUT", "UIT", "HCMIU", "VNU-HCM"}


def vn_institutions(affiliation):
    a = strip_accents(html.unescape(affiliation or "")).strip()
    if not a:
        return []
    found = [(full, short, uni) for rx, full, short, uni in _VN_COMPILED if rx.search(a)]
    if any(short in _VNU_HCM for _, short, _ in found):
        found = [f for f in found if f[1] != "VNU"]
    if not found and _VN_GENERIC.search(a):
        found = [(a, a, True)]
    return found


_STUDENT_POST = re.compile(r"student|intern\b|undergrad|bachelor|\bms\b|master|phd candidate|research assistant|trainee|"
                           r"apprentice", re.I)
_STAFF_POST = re.compile(r"lecturer|professor|instructor|faculty|dean\b|head\b|director|chair\b|teacher|rector|giảng viên", re.I)
_RESEARCH_POST = re.compile(r"research|scientist|postdoc|engineer|fellow", re.I)


def token_key(name):
    return tuple(sorted(re.findall(r"[a-z]+", strip_accents(name or "").lower())))


def post_class(position):
    if _STUDENT_POST.search(position or ""):
        return "student"
    if _STAFF_POST.search(position or ""):
        return "staff"
    return "researcher" if _RESEARCH_POST.search(position or "") else ""


def vn_institution(affiliation):
    found = vn_institutions(affiliation)
    return found[0] if found else None


PARENT = {"VNU-UET": "VNU", "VNU-HUS": "VNU", "HCMUS": "VNU-HCM", "HCMUT": "VNU-HCM", "UIT": "VNU-HCM",
          "HCMIU": "VNU-HCM"}


def same_institution(affiliation, person):
    mine = {person["institution_short"], PARENT.get(person["institution_short"])}
    if any(short in mine or full == person["institution"] for full, short, _ in vn_institutions(affiliation)):
        return True
    wanted = norm_name(person["institution"])
    return bool(wanted) and wanted in norm_name(affiliation)


def virtual_track(title, sourceurl, event_type, file_has_source):
    src, ev = sourceurl or "", event_type or ""
    if re.search(r"findings", ev, re.I):
        return "findings"
    if re.search(r"blog", f"{src} {ev}", re.I):
        return "blog"
    if re.search(r"datasets_and_benchmarks|evaluations_and_datasets", src, re.I):
        return "datasets_benchmarks"
    if re.search(r"position_paper", src, re.I) or re.match(r"\s*position\s*:", title or "", re.I):
        return "position"
    if re.search(r"jmlr|tmlr|j2c|journal|ann-stats|projecteuclid|imstat|rescience|reproducibility", f"{src} {ev}", re.I):
        return "journal"
    if re.search(r"/\d{4}/Conference", src) or "cmt3.research.microsoft.com" in src or re.fullmatch(r"[A-Z]+\d{4}", src):
        return "main"
    if not src and not file_has_source:
        return "main"
    return "other"


_OR_GROUP = re.compile(r"(ICLR\.cc|NeurIPS\.cc|ICML\.cc|thecvf\.com/CVPR|thecvf\.com/ICCV|thecvf\.com/ECCV|aclweb\.org/ACL|(?<![\w/])EMNLP)"
                       r"/(\d{4})/([A-Za-z_]+)(/[A-Za-z_]+)?")
_OR_VENUE = {"ICLR.cc": "iclr", "NeurIPS.cc": "neurips", "ICML.cc": "icml",
             "thecvf.com/CVPR": "cvpr", "thecvf.com/ICCV": "iccv", "thecvf.com/ECCV": "eccv", "aclweb.org/ACL": "acl", "EMNLP": "emnlp"}


def openreview_venue(invitations, venueid=""):
    for s in [*(invitations or []), venueid or ""]:
        m = _OR_GROUP.search(s or "")
        if not m:
            continue
        group, year, part, sub = m.group(1), int(m.group(2)), m.group(3), m.group(4) or ""
        if part == "Conference":
            track = "main"
        elif "Workshop" in part:
            track = "workshop"
        elif re.search(r"Datasets_and_Benchmarks|Evaluations_and_Datasets", part + sub):
            track = "datasets_benchmarks"
        elif "Position" in part:
            track = "position"
        elif "Tiny" in part:
            track = "tiny_papers"
        elif "Blog" in part:
            track = "blog"
        else:
            track = "other"
        return _OR_VENUE[group], year, track
    return None


def classify_status(venue="", venueid="", invitations=(), decision=""):
    venue, venueid, decision = venue or "", venueid or "", decision or ""
    text = " ".join([venue, venueid, *(invitations or [])])
    if re.search(r"desk[ _-]?reject", text, re.I):
        return "desk_rejected"
    if re.search(r"withdraw", text, re.I):
        return "withdrawn"
    if re.search(r"reject", decision, re.I):
        return "rejected"
    if re.search(r"accept", decision, re.I):
        return "accepted"
    if venueid.endswith("Rejected_Submission") or re.match(r"\s*Submitted to ", venue) \
            or re.search(r"\b\d{4} Submitted\s*$", venue):
        return "rejected"
    if re.search(r"\b(poster|spotlight|oral|talk|notable|highlight|accept)", venue, re.I):
        return "accepted"
    return "unknown"


def presentation(text):
    t = (text or "").lower()
    if "oral" in t or "talk" in t or "top-5%" in t or "top 5%" in t:
        return "oral"
    if "spotlight" in t or "top-25%" in t or "top 25%" in t:
        return "spotlight"
    if "highlight" in t:
        return "highlight"
    return ""


ROSTER_FIELDS = ["approved", "display_name", "name_variants", "institution", "institution_short", "rank",
                 "vn_since", "openreview_ids", "homepage", "pages", "to_confirm", "notes", "slug",
                 "name_vi"]


def _split(value):
    return [x.strip() for x in (value or "").split(";") if x.strip()]


def load_roster(path=ROSTER):
    people = []
    if not Path(path).exists():
        return people
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = (row.get("display_name") or "").strip()
            if not name:
                continue
            since = (row.get("vn_since") or "").strip()
            people.append({
                "slug": (row.get("slug") or "").strip() or slugify(name),
                "name": name,
                "variants": sorted({norm_name(v) for v in [name, *_split(row.get("name_variants"))]}),
                "name_forms": [name, *_split(row.get("name_variants"))],
                "institution": (row.get("institution") or "").strip(),
                "institution_short": (row.get("institution_short") or "").strip()
                or (row.get("institution") or "").strip(),
                "rank": (row.get("rank") or "").strip(),
                "role": (row.get("role") or "").strip(), "role_vi": (row.get("role_vi") or "").strip(),
                "role_source": (row.get("role_source") or "").strip(),
                "page_note": (row.get("page_note") or "").strip(), "page_note_vi": (row.get("page_note_vi") or "").strip(),
                "vn_since": int(since) if since.isdigit() else None,
                "openreview_ids": _split(row.get("openreview_ids")),
                "homepage": (row.get("homepage") or "").strip(),
                "pages": _split(row.get("pages")),
                "approved": (row.get("approved") or "").strip().lower(),
                "to_confirm": (row.get("to_confirm") or "").strip(),
                "notes": (row.get("notes") or "").strip(),
                "name_vi": (row.get("name_vi") or "").strip(),
            })
    return people


def in_vietnam(person, year):
    return person["vn_since"] is None or int(year) >= person["vn_since"]


def read_jsonl_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def write_jsonl_gz(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def write_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def write_csv(path, fields, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def read_csv(path):
    if not Path(path).exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def with_pdf_affiliations(papers, warnings):
    fixes = collections.defaultdict(list)
    for r in read_csv(CSV_DIR / "affiliation_fixes.csv"):
        if r["checked"] == "yes":
            fixes[(r["venue"], int(r["year"]), norm_title(r["title"]))].append(r)
    rows = collections.defaultdict(list)
    for r in read_csv(CSV_DIR / "affiliations.csv"):
        if r["checked"] == "yes":
            rows[(r["venue"], int(r["year"]), norm_title(r["title"]))].append(r)
    for p in papers:
        found = rows.get((p["venue"], p["year"], norm_title(p["title"])))
        if found and not any(a["aff"] for a in p["authors"]):
            found = sorted(found, key=lambda r: int(r["position"]))
            if [norm_name(r["author"]) for r in found] != [norm_name(a["name"]) for a in p["authors"]]:
                warnings.append(f"affiliations.csv: the authors of '{p['title'][:60]}' ({VENUE_NAME[p['venue']]} "
                                f"{p['year']}) do not match the list; not used")
            else:
                p["authors"] = [{**a, "aff": r["affiliation"]} for a, r in zip(p["authors"], found)]
        for r in fixes.get((p["venue"], p["year"], norm_title(p["title"])), ()):
            hit = [a for a in p["authors"] if norm_name(a["name"]) == norm_name(r["author"])]
            if not hit:
                warnings.append(f"affiliation_fixes.csv: no author {r['author']} on '{p['title'][:60]}'; not used")
            for a in hit:
                a["aff"] = r["affiliation"]
        yield p
