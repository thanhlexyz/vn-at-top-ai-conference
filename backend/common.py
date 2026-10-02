"""Shared configuration and pure helpers for the conference-statistics pipeline.

Nothing in this file touches the network, so all of it can be unit-tested (see tests/).
"""
import csv
import datetime
import gzip
import html
import json
import re
import unicodedata
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
FRONTEND = BACKEND.parent / "frontend"
RAW = BACKEND / "raw"  # downloaded source files, re-creatable
WORK = BACKEND / "work"  # intermediate files, re-creatable
ACCEPTED = WORK / "accepted.jsonl.gz"  # every accepted paper of the five venues, normalized
OPENREVIEW_RAW = RAW / "openreview"  # one <slug>.json per person, written by fetch_openreview.py
LEGACY_PAPERS = BACKEND / "iclr_cache" / "papers.csv"  # cache of the old iclr_author_stats.py

ROSTER = BACKEND / "roster.csv"  # hand-edited: who is on the site
REVIEW = BACKEND / "review.csv"  # uncertain matches; the build appends rows, you fill in `decision`
CANDIDATES = BACKEND / "candidates.csv"  # generated: people found but not on the roster

FIRST_YEAR = 2020
LAST_YEAR = datetime.date.today().year
YEARS = list(range(FIRST_YEAR, LAST_YEAR + 1))

# `rejections` says what the venue makes public:
#   full    - every submission and its outcome (ICLR)
#   partial - rejected papers only when the authors opted in (NeurIPS)
#   none    - accepted papers only
VENUES = [
    {"key": "iclr", "name": "ICLR", "full_name": "International Conference on Learning Representations",
     "rejections": "full"},
    {"key": "neurips", "name": "NeurIPS", "full_name": "Conference on Neural Information Processing Systems",
     "rejections": "partial"},
    {"key": "icml", "name": "ICML", "full_name": "International Conference on Machine Learning",
     "rejections": "none"},
    {"key": "cvpr", "name": "CVPR", "full_name": "IEEE/CVF Conference on Computer Vision and Pattern Recognition",
     "rejections": "none"},
    {"key": "acl", "name": "ACL", "full_name": "Annual Meeting of the Association for Computational Linguistics",
     "rejections": "none"},
]
VENUE_KEYS = [v["key"] for v in VENUES]
VENUE_NAME = {v["key"]: v["name"] for v in VENUES}

NOT_ACCEPTED = ("rejected", "withdrawn", "desk_rejected")  # shown together as "not accepted"
STATUS_LABEL = {"accepted": "accepted", "rejected": "rejected", "withdrawn": "withdrawn",
                "desk_rejected": "desk-rejected", "unknown": "unknown"}


# ---------------------------------------------------------------- text normalization

def strip_accents(s):
    s = s.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm_name(s):
    """'Nguyễn Phi-Lê ' -> 'nguyen phi le'. Used to compare author names."""
    s = strip_accents(html.unescape(s or ""))
    return " ".join(re.sub(r"[^A-Za-z0-9]+", " ", s).lower().split())


def name_key(s):
    """Key that ignores word order and middle initials: 'Khoa D. Doan' and 'Doan Khoa' group together."""
    tokens = norm_name(s).split()
    full = [t for t in tokens if len(t) > 1]
    return " ".join(sorted(full if len(full) >= 2 else tokens))


def norm_title(s):
    """Key for comparing paper titles across sources (case, punctuation and LaTeX insensitive)."""
    s = strip_accents(html.unescape(s or ""))
    s = re.sub(r"\\[a-zA-Z]+|\\.", "", s)
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", strip_accents(s).lower()).strip("-")


# ---------------------------------------------------------------- Vietnamese institutions

# (pattern, full name, short name, is_university). First match wins, so specific entries come first.
VN_INSTITUTIONS = [
    (r"vin ?uni", "VinUniversity", "VinUni", True),
    (r"vin ?ai\b", "VinAI Research", "VinAI", False),
    (r"vin ?big ?data|vingroup big data", "VinBigData", "VinBigData", False),
    (r"vinbrain|vinfast|vingroup|vin ?robotics|vinmotion|vintech", "Vingroup", "Vingroup", False),
    (r"ha ?noi university of science (and |& )?tech|\bsoict\b|bach khoa ha ?noi",
     "Hanoi University of Science and Technology", "HUST", True),
    (r"university of science and technology of ha ?noi|\busth\b",
     "University of Science and Technology of Hanoi", "USTH", True),
    (r"ha ?noi university of science\b(?! (and |& )?tech)|vnu university of science|vnu\W+hus\b",
     "VNU University of Science, Hanoi", "VNU-HUS", True),
    (r"ho chi minh (city )?university of technology and education|university of technical education\W+ho chi minh",
     "Ho Chi Minh City University of Technology and Education", "HCMUTE", True),
    (r"\bhcmut\b|ho chi minh (city )?university of technology(?! and education)|bach khoa",
     "Ho Chi Minh City University of Technology, VNU-HCM", "HCMUT", True),
    (r"\bhcmus\b|university of science\W+(vnu|vietnam national|ho chi minh|hcm)"
     r"|ho chi minh (city )?university of science\b|(vnu\W?hcm|vnuhcm)\W+university of science",
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
    (r"posts (and|&) telecommunications? institute of technology|\bptit\b",
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
    (r"can tho university(?! of)", "Can Tho University", "CTU", True),
    (r"hue university", "Hue University", "Hue University", True),
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
    """Every Vietnamese institution named in an affiliation string, as (full name, short name, is_university)."""
    a = strip_accents(html.unescape(affiliation or "")).strip()
    if not a:
        return []
    found = [(full, short, uni) for rx, full, short, uni in _VN_COMPILED if rx.search(a)]
    if any(short in _VNU_HCM for _, short, _ in found):  # "VNU" alone means Hanoi only when HCM is not named
        found = [f for f in found if f[1] != "VNU"]
    if not found and _VN_GENERIC.search(a):
        found = [(a, a, True)]
    return found


def vn_institution(affiliation):
    """The first Vietnamese institution in an affiliation string, or None if there is none."""
    found = vn_institutions(affiliation)
    return found[0] if found else None


# A paper often names only the national university; that still counts as the member school.
PARENT = {"VNU-UET": "VNU", "VNU-HUS": "VNU", "HCMUS": "VNU-HCM", "HCMUT": "VNU-HCM", "UIT": "VNU-HCM",
          "HCMIU": "VNU-HCM"}


def same_institution(affiliation, person):
    """True if the affiliation printed on a paper names the institution the roster gives for this person."""
    mine = {person["institution_short"], PARENT.get(person["institution_short"])}
    if any(short in mine or full == person["institution"] for full, short, _ in vn_institutions(affiliation)):
        return True
    wanted = norm_name(person["institution"])
    return bool(wanted) and wanted in norm_name(affiliation)


# ---------------------------------------------------------------- tracks

def virtual_track(title, sourceurl, event_type, file_has_source):
    """Track of one row of a neurips.cc / icml.cc / iclr.cc / cvpr.thecvf.com virtual-site listing.

    `file_has_source` is True when the listing carries a sourceurl for its papers (2022 and later).
    In those files a row without one is a session container, a Findings paper or a duplicate oral.
    """
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
    if re.search(r"/\d{4}/Conference", src) or "cmt3.research.microsoft.com" in src:
        return "main"
    if not src and not file_has_source:
        return "main"
    return "other"


_OR_GROUP = re.compile(r"(ICLR\.cc|NeurIPS\.cc|ICML\.cc|thecvf\.com/CVPR|aclweb\.org/ACL)/(\d{4})/([A-Za-z_]+)(/[A-Za-z_]+)?")
_OR_VENUE = {"ICLR.cc": "iclr", "NeurIPS.cc": "neurips", "ICML.cc": "icml",
             "thecvf.com/CVPR": "cvpr", "aclweb.org/ACL": "acl"}


def openreview_venue(invitations, venueid=""):
    """(venue key, year, track) of an OpenReview note, or None if it is not one of the five venues."""
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


# ---------------------------------------------------------------- submission outcomes

def classify_status(venue="", venueid="", invitations=(), decision=""):
    """Outcome of an OpenReview submission: accepted, rejected, withdrawn, desk_rejected or unknown.

    Label conventions seen so far (venue string / venueid):
      API v2, 2024+    'ICLR 2025 Poster' / ICLR.cc/2025/Conference
                       'Submitted to ICLR 2025' / .../Conference/Rejected_Submission
                       'ICLR 2026 Conference Withdrawn Submission' / .../Withdrawn_Submission
                       'ICLR 2026 Conference Desk Rejected Submission' / .../Desk_Rejected_Submission
      API v1, 2022-23  'ICLR 2022 Poster' (accepted) but 'ICLR 2022 Submitted' (rejected)
      API v1, 2020-21  no venue at all: the outcome is in the forum's Decision reply (`decision`).
    """
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
    """'Accept (spotlight)' -> 'spotlight'. Empty for plain posters."""
    t = (text or "").lower()
    if "oral" in t or "talk" in t or "top-5%" in t or "top 5%" in t:
        return "oral"
    if "spotlight" in t or "top-25%" in t or "top 25%" in t:
        return "spotlight"
    if "highlight" in t:
        return "highlight"
    return ""


# ---------------------------------------------------------------- roster

ROSTER_FIELDS = ["approved", "display_name", "name_variants", "institution", "institution_short", "rank",
                 "vn_since", "openreview_ids", "homepage", "pages", "to_confirm", "notes", "slug",
                 "name_vi"]  # the name in Vietnamese, with diacritics, shown on the Vietnamese site


def _split(value):
    return [x.strip() for x in (value or "").split(";") if x.strip()]


def load_roster(path=ROSTER):
    """Rows of roster.csv as dicts, with list and int fields parsed. Order of the file is kept."""
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
                "name_forms": [name, *_split(row.get("name_variants"))],   # as written, for display
                "institution": (row.get("institution") or "").strip(),
                "institution_short": (row.get("institution_short") or "").strip()
                or (row.get("institution") or "").strip(),
                "rank": (row.get("rank") or "").strip(),
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
    """'Only while in Vietnam': a paper counts from the year the person joined a Vietnamese institution."""
    return person["vn_since"] is None or int(year) >= person["vn_since"]


# ---------------------------------------------------------------- small I/O helpers

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
