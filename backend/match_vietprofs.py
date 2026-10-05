"""Finds which co-authors outside Vietnam (the "Co-authors outside Vietnam" table of the Candidates page) have a
profile on VietProfs (https://vietprofs.roars.dev, a directory of Vietnamese professors worldwide), and writes
proposals to vietprofs.csv. A row counts on the International cooperation page only when `checked` is `yes`;
check that the university on the papers is the one VietProfs lists for the same person.

The directory is read from the site's public data.json and kept only in raw/vietprofs/ (not committed): its licence
(CC BY-NC-ND) does not allow passing the data on, so vietprofs.csv holds only the profile id of each match.
Run after a build (it reads frontend/data/candidates.json).
"""
import json
import urllib.request

from common import BACKEND, FRONTEND, name_key, norm_name, read_csv, write_csv

URL = "https://vietprofs.roars.dev/data.json"
RAW = BACKEND / "raw" / "vietprofs" / "data.json"
CSV = BACKEND / "vietprofs.csv"
FIELDS = ["name", "affiliation", "vp_id", "vp_name", "vp_university", "country", "checked", "note"]
STOP = {"university", "of", "the", "and", "institute", "college", "de", "at"}


def words(s):
    return {w for w in norm_name(s).split() if w not in STOP}


def main():
    if not RAW.exists():
        RAW.parent.mkdir(parents=True, exist_ok=True)
        RAW.write_bytes(urllib.request.urlopen(URL, timeout=60).read())
    directory = json.loads(RAW.read_text(encoding="utf-8"))
    known = {r["name"]: r for r in read_csv(CSV)} if CSV.exists() else {}
    foreign = json.loads((FRONTEND / "data" / "candidates.json").read_text(encoding="utf-8"))["foreign"]
    by_id = {r["id"]: r for r in directory}
    rows = list(known.values())
    for r in rows:   # the country is added to rows made before the column existed
        r["country"] = r.get("country") or by_id.get(r["vp_id"], {}).get("country", "")
    for f in foreign:
        if f["name"] in known:
            continue
        tokens = set(norm_name(f["name"]).split())
        for r in directory:
            names = [norm_name(n).split() for n in (r["name"].split(" - ")[0], r.get("vietnameseName", "")) if n]
            if any(tokens <= set(n) for n in names) and words(f["affiliation"]) & words(r["university"]):
                rows.append({"name": f["name"], "affiliation": f["affiliation"], "vp_id": r["id"],
                             "vp_name": r["name"], "vp_university": r["university"],
                             "country": r.get("country", ""), "checked": "", "note": ""})
                break
    write_csv(CSV, FIELDS, rows)
    print(f"{len(rows)} rows in vietprofs.csv; {sum(r['checked'] == 'yes' for r in rows)} checked")


if __name__ == "__main__":
    main()
