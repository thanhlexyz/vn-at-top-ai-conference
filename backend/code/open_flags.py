import json

from common import FRONTEND

professors = json.loads((FRONTEND / "data" / "professors.json").read_text(encoding="utf-8"))
meta = json.loads((FRONTEND / "data" / "meta.json").read_text(encoding="utf-8"))
flagged = [p for p in professors if p["flags"]]
print(f"Data of {meta['generated_date']}: {len(professors)} professors, {meta['papers']} papers.")
if flagged:
    print(f"{len(flagged)} professors go out with a warning box on their page:")
    for p in flagged:
        print(f"  {p['name']}")
        for flag in p["flags"]:
            print(f"      - {flag}")
if meta["pending_review"]:
    print(f"{meta['pending_review']} uncertain matches in review.csv have no answer yet; they are not counted.")
