# Vietnam at top AI conferences

A static site that shows, for a hand-approved list of professors and lecturers in Vietnam, how many papers they
submitted, had accepted and had rejected at ICLR, NeurIPS, ICML, CVPR and ACL since 2020.

**Website: <https://thanhlexyz.github.io/vn-at-top-ai-conference/>**

- `backend/` Python scripts that collect the records and write the site's data files.
- `frontend/` Hugo site (own layouts, no theme; one small script for sorting and keyboard scrolling) that renders those files.

Needs Python 3.10+, Hugo 0.156+ and, for the OpenReview step only, `pip install openreview-py`.

## Everyday use

```
make data         # public accepted-paper lists -> candidates.csv -> frontend/data/   (no login)
make openreview   # OpenReview submissions of the approved people, then rebuild        (login)
make homepages    # save the professors' own pages, list what they say about the five venues
make run          # hugo serve, http://localhost:1313
make build        # static site in frontend/public/, local settings
make publish      # public site to GitHub Pages
make test         # checks of the counting rules
```

`make openreview` reads `OPENREVIEW_USERNAME` and `OPENREVIEW_PASSWORD` from the environment and asks
for whatever is missing. It is the only source of rejected and withdrawn papers. Until it has been run,
the ICLR numbers come from the old cache in `backend/iclr_cache/`, and each professor's page says so.

`make data` reuses the downloads in `backend/raw/`. `make refresh` downloads them again, for example
after a conference has published its papers.

## Publishing

`make publish` builds the public site and pushes it to the `gh-pages` branch of the `origin` repository,
which GitHub Pages serves. It first prints every warning that is still open in the data, then publishes
anyway; the warnings stay visible as yellow boxes on the pages.

One-time setup on GitHub, for the repository behind `origin`:

1. Make the repository public (Settings > General > Change visibility). GitHub Pages on a free plan
   works only for public repositories. Everything tracked becomes public with it: `roster.csv` and its
   notes, `review.csv`, `self_reported.csv`, the old ICLR cache and the blog draft.
2. Run `make publish` once, so the `gh-pages` branch exists.
3. Settings > Pages > Build and deployment: "Deploy from a branch", branch `gh-pages`, folder `/ (root)`.

The address and the public settings are in `frontend/publish.toml`, which is laid over `hugo.toml`:
`baseURL` (GitHub serves a project site at `https://<account>.github.io/<repository>/`), `local = false`
so search engines may index it, and `showNonAcceptedTitles`. If the repository is renamed or moved, change
`baseURL` there.

The Candidates page and the blog draft are Hugo drafts. `make run` shows them; `make build` and
`make publish` leave them out. The `gh-pages` branch holds generated files only and is replaced on each
publish, so nothing should be committed to it by hand.

## The three files you edit

**`backend/roster.csv`** decides who is on the site. One row per person:

| column | meaning |
|---|---|
| `approved` | `yes` puts the person on the site once they have a counted submission, accepted or not, `no` keeps them off for good (they are listed on the local Not tracked page, with `notes` as the reason), empty means waiting |
| `display_name`, `name_variants` | every spelling and word order the person publishes under, separated by `;` |
| `institution`, `institution_short` | used to check the affiliation printed on a paper |
| `rank` | shown on the person's page |
| `vn_since` | first year at a Vietnamese institution; papers before it are not counted. Empty means 2020 or earlier |
| `openreview_ids` | the person's OpenReview profile IDs, separated by `;`. Only confirmed ones |
| `to_confirm` | anything still unverified; shown as a warning on the person's page |

**`backend/review.csv`** holds matches the scripts cannot settle: a paper carries a professor's name, but
the list has no affiliations (ACL, CVPR before 2023 and in 2026) or names another Vietnamese institution.
The build appends such rows. Write `yes` or `no` in the `decision` column and run `make data` again.

**`frontend/hugo.toml`** has two switches for the local site: `showNonAcceptedTitles` (list the titles of
rejected and withdrawn papers, or only count them) and `local` (asks search engines not to index the
site). `frontend/publish.toml` sets both for the public site.

## Adding people

`backend/candidates.csv` lists authors with a Vietnamese affiliation on accepted papers who are not on
the roster, those with the most accepted papers first. The Candidates page of the local site shows the same list.

```
cd backend
python fetch_openreview.py --candidates 60          # optional: look up their OpenReview positions
python find_candidates.py --add "Khoa D Doan"       # copy a candidate into roster.csv
python fetch_openreview.py --search "Khoa D Doan"   # find the right ~ID
```

Then fill in `rank`, `vn_since` and `openreview_ids` in `roster.csv`, set `approved` to `yes`, and run
`make openreview`. People who publish only at ACL, or at CVPR before 2023, never show up as candidates,
because those lists have no affiliations; add them to `roster.csv` by hand.

## Two more hand-kept files

**`backend/faculty.csv`** holds names and titles copied from university staff pages (VinUniversity CECS,
HUST SoICT, VNU-UET Faculty of IT, HCMUT CSE, read on 2026-09-30). `find_candidates.py` uses it to mark
candidates who are listed as faculty of the institution named on their papers. Add rows for other
universities in the same format.

**`backend/self_reported.csv`** holds the papers that professors list on their own pages, one row per
paper, with the address and the date it was read. `make homepages` saves the pages named in the `pages`
column of `roster.csv` and writes every line that mentions one of the five venues to
`backend/work/homepage_hits.txt`; copying papers from there into the file is done by hand, because the
pages are too different to parse safely. A page that only announces a number gets a row with an empty
title and the number in `announced`.

What the build does with a row:

- The paper is in an official list: it counts for the professor whose page lists it, even under a name
  form the roster does not know. A colleague's page that names a professor as co-author only puts the
  paper into `review.csv`.
- The paper is in no official list and the list of that year is not complete yet (published before the
  conference, today NeurIPS 2026): it is counted as **unofficial**, shown as `+N` next to the official
  number and tagged "unofficial" with the page it comes from. This also holds for a professor named as co-author.
- The paper is in no official list of a complete year: not counted, and written to
  `backend/work/build_report.txt`.

## Counting rules

The About page of the site states them in full. In short: main conference track only; a paper counts
from `vn_since`; rejected, withdrawn and desk-rejected papers are added up as "not accepted"; rejections
are complete for ICLR only, partial for NeurIPS, and not public for ICML, CVPR and ACL. The co-author and
topic columns are taken over all counted papers, accepted or not. The chart on a professor's page estimates the unseen
rejections at the other venues from that professor's own ICLR record; it is a projection and the page says so.

A list that a conference publishes before it takes place can be incomplete. Such a venue-year is marked
with + in the tables, and its counts are a lower bound until `make refresh` picks up the final list.

Identity is the weak point. OpenReview records are matched by profile ID and are exact once the ID is
right. Everything else is matched by name plus the affiliation on the paper, so a wrong or missing name
variant loses papers, and a namesake at the same institution would be counted. Check each professor's
paper list before publishing anything.

## Files the scripts write

| path | content |
|---|---|
| `backend/raw/` | downloads, gzip-compressed; `raw/openreview/<slug>.json` holds a person's submissions |
| `backend/work/accepted.jsonl.gz` | every accepted paper of the five venues, one per line |
| `backend/work/build_report.txt` | warnings, and same-name papers from foreign institutions that were skipped |
| `backend/candidates.csv` | people found but not on the roster |
| `frontend/data/*.json` | what the templates render; `blog.json` has every figure the blog draft quotes |
| `frontend/content/{professors,institutions,venues}/*.md` | one stub per page, rewritten on every build |

`backend/iclr_author_stats.py` is the first script and is no longer used; `fetch_openreview.py`
replaces it.
