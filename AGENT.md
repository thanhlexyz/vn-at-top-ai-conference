# AGENT.md: how to operate and maintain this site

You are maintaining a public, bilingual (Vietnamese at `/`, English at `/en/`) Hugo site that counts papers of
lecturers and professors in Vietnam at eight AI conferences. The maintainer gives short requests in plain words; this
file tells you how to carry them out. Read it before changing anything.

Live site: <https://thanhlexyz.github.io/vn-at-top-ai-conference/>

## Layout

- `backend/`: Python scripts that collect records and write the site data. `build_site_data.py` is the core.
- `frontend/`: Hugo site, own layouts (no theme), data in `frontend/data/*.json`, strings in `frontend/i18n/{en,vi}.toml`,
  one small `static/site.js` (sorting, cups, pinned columns, graph hover, feedback e-mail).
- `makefile`: `data`, `openreview`, `affiliations`, `homepages`, `refresh`, `run`, `build`, `publish`, `test`.

Run Python with the environment that has `openreview-py` installed, passed to make as `PYTHON=<python>`.
OpenReview credentials come from the environment variables `OPENREVIEW_USERNAME` and `OPENREVIEW_PASSWORD`, which
the maintainer sets in their shell profile; if a non-interactive shell does not have them, load that profile in the
same command before running the script. Never print, log or commit the password.

## The usual cycle

1. Edit the hand-kept files (below), or code.
2. `cd backend && <python> build_site_data.py` (or `make data`): rebuilds `frontend/data/` and the page stubs.
3. `make build` (must show no warnings) and `make test PYTHON=<python>` (must pass).
4. Look at what changed: diff the numbers you expected to move, and take headless screenshots
   (`chromium --headless --screenshot`, served with `python3 -m http.server` from `frontend/public`) of the pages
   you touched, in both languages and, for colours, in dark mode (`--blink-settings=preferredColorScheme=0`).
   For behaviour in `site.js` (sorting, cups), test with a temporary copy of the page that clicks and reports back.
5. Commit, push, publish (see Git and publishing). Then confirm on the live site with `curl`.

Do not stop at a passing build: say what changed in numbers, and anything uncertain.

## Hand-kept files

| file | what it holds |
|---|---|
| `backend/roster.csv` | everyone considered: `approved` (`yes` on the site, `no` checked and left off with the reason in `notes`, empty = waiting), name forms, institution, `rank` (as on OpenReview), `vn_since`, `openreview_ids`, `homepage`, `pages`, `to_confirm`, `notes`, `slug`, `name_vi`, `role`, `role_vi`, `role_source`. CRLF line endings; edit with Python `csv`, never `sed` (fields with commas break). |
| `backend/review.csv` | uncertain matches; the build appends rows, a human answer goes in `decision` (`yes`/`no`) with a dated `note`. |
| `backend/self_reported.csv` | papers from professors' pages, co-authors' pages and announcements; `track` is `main` or `findings`. |
| `backend/unofficial_news.txt` | the text of announcements that unofficial acceptances come from. |
| `backend/affiliations.csv` | per-author affiliations read from the PDF where a list prints none (`fetch_affiliations.py`, each row checked by hand, `checked=yes`). |
| `backend/affiliation_fixes.csv` | one author's affiliation as the paper prints it, where the list differs (virtual sites copy author profiles). |
| `backend/images.csv` | photos and logos, with source page and a dated note. |
| `backend/institution_names.csv` | Vietnamese names of institutions, confirmed by the maintainer. |
| `backend/scholar.json` | Google Scholar snapshots (`fetch_scholar.py`). |
| `backend/venue_rates.csv` | acceptance rates the conferences report, per year, with source and `official`/`secondary`. |
| `backend/faculty.csv`, `pioneers.csv` | staff lists and press-known pioneers, for the local Candidates page. |

`backend/raw/` and `backend/work/` are git-ignored: downloads, PDFs, screenshots the maintainer gives you.

## Counting rules (the About page states them; keep both in sync)

- Venues: ICLR, NeurIPS, ICML, CVPR, ICCV (odd years), ECCV (even years), ACL, EMNLP; years 2020 on, conference years.
- People: Vietnamese lecturers, assistant/associate professors, professors whose main post is at a university in
  Vietnam. Not students, researchers or industry staff. To join, a person needs at least one counted submission:
  an accepted paper, an ICLR record (rejected/withdrawn/desk-rejected counts) or a Findings paper. Workshop papers
  alone do not qualify.
- A paper counts from `vn_since`; main track only (no workshops, position papers, D&B, journal tracks).
- **Findings** = rejected from the main track at any conference, and also listed as a workshop paper.
- **Institution rule:** an accepted official paper counts for a person only if the paper lists them at their roster
  institution, as printed on the paper (the PDF wins over a virtual site, which copies profiles). A paper written
  only at a company or institute (e.g. Qualcomm AI Research, which is the former VinAI) does not count. Papers that
  print no affiliation (unofficial ones, lists without affiliations) count.
- **Unofficial:** a paper known only from a personal page or announcement counts while the official list is
  provisional or not published; shown as `+N` and tagged unofficial.
- Rejections: complete only for ICLR; public NeurIPS rejections and Findings are also "on record". Hidden rejections
  are estimated per professor from their own ICLR record, `(submitted + 1) / (accepted + 1)`; papers of people with
  no ICLR submissions add no estimate and their acceptance rate is greyed and sorted last. Venue estimates average the
  ratios of each paper's listed authors who have an ICLR record.
- A paper shared by several professors counts for each person, once for an institution or venue.

## Common requests

**"Track `<OpenReview URL>`."** Read the profile (`c.get_profile(id)`: names, history) and its notes. Check
eligibility (above): current post must be lecturer or higher at a university in Vietnam, and there must be a counted
submission. If not eligible, add a row with `approved=no` and the reason, and tell the maintainer. If eligible, add a
roster row (`rank` and `vn_since` from OpenReview, `name_vi` with diacritics only when confirmed), then
`fetch_openreview.py --only <slug>`, rebuild, and report the papers it found.

**Unofficial acceptances** (screenshots, posts, lab pages): add rows to `self_reported.csv` with the source and date;
keep the announcement text in `unofficial_news.txt`; private screenshots stay in `backend/raw/`. Only for people on the
roster; ask before adding a co-author by name only.

**Photos:** from the person's staff page, Scholar or a link the maintainer gives; record it in `images.csv`, raw file
in `backend/raw/images/`, site copy at most 400 px in `frontend/static/img/people/<slug>.jpg`. Crop only when the face
is small in the picture (OpenCV Haar face detection, or by hand); a well-placed portrait stays as it is.

**Roles:** `rank` stays as OpenReview gives it (English, not translated). A leadership role found on official pages goes
in `role`/`role_vi`/`role_source`, shown after the rank. Use the Vietnamese title as the source writes it
(e.g. HUST and Phenikaa schools: "Phó Hiệu trưởng"; faculties: "Phó trưởng khoa"; "Giám đốc"; lab heads: "Trưởng Lab").
English: a deputy head of a school inside a university is "Vice Dean"; "Phó Hiệu trưởng" of a whole university
(e.g. HCMUS) is "Vice Rector". Search in Vietnamese first; only current roles, each with a source URL.

**A wrong match or affiliation:** read the PDF title page (`pdftotext -l 1`; footnotes hold ICML/NeurIPS
affiliations). Wrong person: `review.csv` `no` with the evidence. Wrong affiliation: a row in
`affiliation_fixes.csv`. After affiliation changes, check that no one's accepted count moved unexpectedly (a paper
matched only by affiliation can drop out; confirm it in `review.csv` if it is theirs).

**New conference data:** `make refresh`, then `fetch_affiliations.py` for papers whose list prints no affiliations
(fill and check each row), then `verify_affiliations.py` to check every counted official paper against its PDF;
fix what it flags. NeurIPS PDFs become public only after the conference.

**Text on the site:** every string in both `en.toml` and `vi.toml`, in a professional register; Vietnamese that reads
naturally, not translated word for word. Keep captions short; do not repeat what a legend or the About page already
explains (refer to About instead). Chart colours are CSS tokens defined for light and dark mode.

**Collaboration graphs** (`backend/graph.py`): line length follows shared papers (more papers, closer); no line passes
through a circle; labels never overlap lines or other labels and never leave the drawing; crossings few. After any
change, check crossings and label clearance for both graphs and look at screenshots.

## Git and publishing

- Commit with the repository's own identity and a UTC date: `TZ=UTC git commit ...`, author
  `thanhlexyz <thanhlexyz@users.noreply.github.com>` (repo-local config). End the message with the attribution
  trailer your harness gives (currently `Co-Authored-By: Claude ... <noreply@anthropic.com>`). Never commit with
  the local time zone; check `git log --format=%ad` if unsure.
- `git push origin main`, then `make publish PYTHON=<python>`: it builds with `frontend/publish.toml` and force-pushes
  `frontend/public` to the `gh-pages` branch (GitHub Pages, "Deploy from a branch"). The trailing `gh` steps may fail
  harmlessly if `gh` is missing.
- Never rewrite pushed history without the maintainer's go-ahead.
- The repository is public: no private screenshots, local paths, e-mails or credentials in commits.

## Things to remember

- Qualcomm AI Research in Vietnam is the former VinAI (Vingroup sold it); neither is a university.
- Virtual-site affiliations (ICLR, NeurIPS, ICML, CVPR, ICCV, ECCV) come from author profiles, not from the paper.
- HUST's "HUST" also means Huazhong University in China; match a short name only against the person's own entry.
- Ask the maintainer when a decision is theirs (who is on the list, uncertain identities, rule changes); otherwise
  choose the sensible default and say what you chose.
