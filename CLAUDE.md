# CLAUDE.md: how to operate and maintain this site

You are maintaining a public, bilingual (Vietnamese at `/`, English at `/en/`) Hugo site that counts papers of
lecturers and professors in Vietnam at ten AI conferences, grouped as CSRankings does. The maintainer gives short requests in plain words; this
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
| `backend/roster.csv` | everyone considered: `approved` (`yes` on the site, `no` checked and left off with the reason in `notes`, empty = waiting), name forms, institution, `rank` (as on OpenReview), `vn_since`, `openreview_ids`, `homepage`, `pages`, `to_confirm`, `notes`, `slug`, `name_vi`, `role`, `role_vi`, `role_source`, `page_note`, `page_note_vi`. CRLF line endings; edit with Python `csv`, never `sed` (fields with commas break). |
| `backend/review.csv` | uncertain matches; the build appends rows, a human answer goes in `decision` (`yes`/`no`) with a dated `note`. |
| `backend/self_reported.csv` | papers from professors' pages, co-authors' pages and announcements; `track` is `main` or `findings`. |
| `backend/unofficial_news.txt` | the text of announcements that unofficial acceptances come from. |
| `backend/affiliations.csv` | per-author affiliations read from the PDF where a list prints none (`fetch_affiliations.py`, each row checked by hand, `checked=yes`). |
| `backend/affiliation_fixes.csv` | one author's affiliation as the paper prints it, where the list differs (virtual sites copy author profiles). |
| `backend/images.csv` | photos and logos, with source page and a dated note. |
| `backend/institution_names.csv` | Vietnamese names of institutions, confirmed by the maintainer. |
| `backend/scholar.json` | Google Scholar snapshots (`fetch_scholar.py`). |
| `backend/vietprofs.csv` | co-authors abroad with a profile on VietProfs (<https://vietprofs.roars.dev>, Vietnamese professors worldwide): `match_vietprofs.py` proposes rows from the Candidates table, `checked=yes` once name and university agree; the International cooperation page draws only these. VietProfs' data is CC BY-NC-ND: read it into `raw/` only, commit just the profile ids. |
| `backend/venue_rates.csv` | acceptance rates the conferences report, per year, with source and `source_kind` (`official`/`secondary`); the build pools all years. |
| `backend/faculty.csv`, `pioneers.csv` | staff lists (also used by `find_candidates.py` to mark candidates) and press-known pioneers, for the local Candidates page. |

`backend/raw/` and `backend/work/` are git-ignored: downloads, PDFs, screenshots the maintainer gives you.
`work/build_report.txt` lists warnings and skipped namesakes after each build. Page stubs in
`frontend/content/{professors,institutions,venues}/` are rewritten on every build: never edit them by hand.
`make data` also runs `fetch_accepted.py` (may download) and `find_candidates.py` (rewrites `candidates.csv`).
The local-only pages (Candidates, Not tracked) are drafts, but their data (`candidates.json`, `candidates.csv`,
`attempted.json`) is tracked in the public repository.

## Counting rules (the About page states them; keep both in sync)

- Venues, grouped as CSRankings does (`VENUE_GROUPS` in `common.py`): AI (AAAI, IJCAI), ML (ICLR, NeurIPS, ICML),
  CV (CVPR, ICCV in odd years, ECCV in even years), NLP (ACL, EMNLP; NAACL is not tracked, being CORE rank A and not A*); years 2020 on, conference years (IJCAI-PRICAI 2020 met in January 2021 and is 2020). AAAI main
  track = the "AAAI Technical Track on ..." sections of ojs.aaai.org issues; IJCAI = the "Main Track" section of
  ijcai.org/proceedings; ACL = the long-paper volumes, never the short-paper ones (no short papers anywhere); the volumes that mix long and short (ACL 2020, EMNLP) cannot be split, so check each counted paper there by its page count in the bib (long papers run 12 pages and more with references); not Findings. The AAAI and IJCAI lists, like ACL and EMNLP,
  print no affiliations: their name matches go through `fetch_affiliations.py` (which also reads the matches waiting
  in `review.csv`) before the institution rule can apply. AAAI and IJCAI publish no rejections.
- People: Vietnamese lecturers, assistant/associate professors, professors whose main post is at a university in
  Vietnam. Not students, researchers or industry staff. To join, a person needs at least one counted submission:
  an accepted paper, an ICLR record (rejected/withdrawn/desk-rejected counts) or a Findings paper. Workshop papers
  alone do not qualify.
- A paper counts from `vn_since`; main track only (no workshops, position papers, D&B, journal tracks).
- **Findings** = rejected from the main track at any conference, and also listed as a workshop paper.
- **Institution rule:** an accepted official paper counts for a person only if the paper lists them at their roster
  institution, as printed on the paper (the PDF wins over a virtual site, which copies profiles). A paper written
  only at a company or institute (e.g. Qualcomm AI Research, which is the former VinAI) does not count. Papers that
  print no affiliation (unofficial ones, lists without affiliations) count. Ways it passes (`at_institution`,
  `same_institution`): the institution's known names (`vn_institutions` in `common.py`), its parent national university
  (`PARENT`), its full name as a substring, its short name as a word in the person's own entry ("VinAI & HUST"), and a
  bare "University of Science" for HCMUS or VNU-HUS. If the person cannot be found on the paper, it counts.
  `affiliation_fixes.csv` rows apply only with `checked=yes`; `affiliations.csv` applies only when the list prints no
  affiliation at all and the authors match name by name.
- **Unofficial:** a paper known only from a personal page or announcement counts while the official list is
  provisional or not published; shown as `+N` and tagged unofficial. A paper in an official list is unofficial too while
  the venue-year is in `UNVERIFIED` in `build_site_data.py` (today NeurIPS 2026): its authors cannot be confirmed on
  OpenReview until the submissions are public, so only a paper from the person's own OpenReview record is official.
  Remove the venue-year from `UNVERIFIED` once OpenReview publishes it (then refresh and run `verify_affiliations.py`).
  The exemption keeps official any match that starts with "OpenReview profile", which includes exact-ID papers found
  in a colleague's record.
- **Provisional lists:** only ICLR, NeurIPS and ICML lists of the current year (`LAST_YEAR`, today's year in `common.py`)
  can be provisional (fewer than half the entries have a start time, `fetch_accepted.is_provisional`). On 1 January the
  year rolls over: `YEARS` gains the new year and the before/from split moves. Hard-coded 2026 to update together:
  `UNVERIFIED`, `neurips_2026_only` in `build_site_data.py`, and the heading of `not-tracked.html`.
- **Matching** (`person_records`): OpenReview records by profile ID first (an OpenReview "rejected" paper that is in an
  accepted list counts as accepted; an unknown outcome becomes rejected when that list exists). Then accepted lists by
  name, exactly against `norm_name` of every roster name form (no fuzziness: add every printed form to
  `name_variants`). A name match counts if the paper is on the person's own page, or the printed affiliation is their
  institution (a match before `vn_since` raises a warning), or `review.csv` says `yes`; otherwise it is queued, and a
  namesake printed only abroad goes to `build_report.txt`. Lists without affiliations (ACL, EMNLP, CVF open access,
  ecva.net) therefore need the own page or a `yes`.
- **`review.csv` limits:** `no` blocks only queued matches and own- or colleague-page rows. It does not stop a paper
  matched through the person's own OpenReview record (fix `openreview_ids`) or a same-name match at the same
  institution. `yes` does not override the institution rule.
- Rejections: complete only for ICLR; public NeurIPS rejections and Findings are also "on record". Hidden rejections
  are estimated per professor from their own ICLR record, `(submitted + 1) / (accepted + 1)`; papers of people with
  no ICLR submissions add no estimate and their acceptance rate is greyed and sorted last. Venue estimates average the
  ratios of each paper's listed authors who have an ICLR record.
- A paper shared by several professors counts for each person, once for an institution or venue. The front-page
  overview adds up the per-professor estimates, so a shared paper is counted for each of its professors there.
- An approved person with no counted record is hidden (the build prints the name); a public NeurIPS rejection is enough.
- **Estimates:** per professor, the ICLR ratio applies only when the ICLR record is complete; each year adds
  `max(elsewhere * (ratio - 1) - rejections on record elsewhere, 0)`. Institutions use their pooled ICLR record.
  Venues: ICLR is counted; elsewhere the rate uses only papers with an author who has an ICLR record.
- **Authorship charts:** "majority" = strictly more than half of all authors at the institution; "first" = the first
  author. Only papers with at least one printed affiliation are judged.
- **Co-author figures:** averages over all counted papers; the minimum over accepted papers; the maximum also over
  workshop papers; affiliation figures need the person found on the paper and an affiliation printed.
- **Institution collaboration** (graph and the co-author institutions on institution pages): a paper links the roster
  institutions of its listed professors, plus Vietnamese institutions printed on it that have nobody on the list
  (companies, institutes such as VinAI or FPT). An institution with professors on the list joins a paper only through
  one of them, never through a student or untracked co-author, so its shared papers are always among its own
  professors' papers.

## International cooperation

The page (`layouts/_default/international.html`, data `international.json` from `international_graph` in `build_site_data.py`)
joins the co-authors outside Vietnam with 5 or more counted papers together with the professors on the list (the
Candidates table "Co-authors outside Vietnam", `FOREIGN_MIN_PAPERS`) and a checked row in `vietprofs.csv`. Authors link
to VietProfs, professors to their page here; each author carries the flag of the country VietProfs lists.

## Tables, sorting and cups (`frontend/static/site.js`, `partials/professor-table.html`)

- "x +y" (official, unofficial) sorts as x + y; among equal totals, more official papers first. The default order of
  the professor, institution and venue tables follows the same rule (`professors.sort`, `institutions.sort`, and the
  sort in `venues/list.html`), so the cups match the order on load.
- Cups (gold, silver, bronze) go to the top three distinct values of the sorted column; ties share a cup and the next
  value takes the next cup. Sorted largest first, zero gets none; sorted smallest first, zero is the best value.
  Sorted by a text column, there are none. Cups appear on the front page, the Institutions list and institution pages
  with at least 4 professors (not on the Venues list); the front page and institution pages show the pinned `#`
  column. The institution bar charts draw their cups at build time (`podium` in `build_site_data.py`).
- Cells marked `data-last` always sort to the bottom and get no cup: the acceptance rate of people with no ICLR
  submissions, and the co-author and own-institution columns of people with no accepted paper (shown greyed).
- Numbers never wrap (`td:not(.l)`); captions and notes stay short and refer to About for definitions.

## Professor pages

- Links come from `homepage`, `pages` and the OpenReview profile; `person_links` labels each by its address
  (staff page, Scholar, DBLP, LinkedIn, ...).
- `page_note` / `page_note_vi` (roster, Markdown) show a box of sourced facts under the links. Facts only, each with
  its source; never a characterisation or a suspicion about a person.

## Common requests

**"Track `<OpenReview URL>`."** Read the profile (`c.get_profile(id)`: names, history) and its notes. Check
eligibility (above): current post must be lecturer or higher at a university in Vietnam, and there must be a counted
submission. If not eligible, add a row with `approved=no` and the reason, and tell the maintainer. If eligible, add a
roster row with `approved=yes` (`rank` and `vn_since` from OpenReview, `name_vi` with diacritics only when confirmed),
then `fetch_openreview.py --only <slug>` (it refuses rows that are not approved), rebuild, and report the papers.

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
affiliations). Wrong person: `review.csv` `no` with the evidence (see its limits above). Wrong affiliation: a row in
`affiliation_fixes.csv`. After affiliation changes, check that no one's accepted count moved unexpectedly (a paper
matched only by affiliation can drop out; confirm it in `review.csv` if it is theirs).

**New conference data:** `make refresh`, then `fetch_affiliations.py` for papers whose list prints no affiliations
(fill and check each row; `--scan aaai ijcai` also reads papers with two or more Vietnamese family names and
keeps those whose title page names a university in Vietnam, so that `find_candidates.py`, which applies the checked
rows, lists their authors on the Candidates page), then `verify_affiliations.py` to check every counted official paper against its PDF;
fix what it flags. NeurIPS PDFs become public only after the conference.

**Text on the site:** every string in both `en.toml` and `vi.toml`, in a professional register; Vietnamese that reads
naturally, not translated word for word. Keep captions short; do not repeat what a legend or the About page already
explains (refer to About instead). Surfaces, grid and text are CSS tokens defined for light and dark mode; the chart
and table hues (accepted green, rejected red, graph colours) are fixed and checked on both. Some English strings from
the build are parsed by templates (a reason starting with `before `, a track ending in ` track`): keep that wording.

**Collaboration graphs** (`backend/graph.py`): line length follows shared papers (more papers, closer); no line passes
through a circle; labels never overlap lines or other labels and never leave the drawing; crossings few. After any
change, check crossings and label clearance for both graphs and look at screenshots. They use every counted
submission (rejected and withdrawn included) plus workshop papers from the Vietnam years, and feed the co-author
lists. Researcher colours: HUST red, VinUni blue, HCMUS cyan, the next two largest institutions green and amber, the
rest grey. `networkx` is used for planar starts and Kamada-Kawai; without it the layout differs. Small groups go
under the main drawing: a chain as a short column, a group with one person linked to all others (`fan_hub`) as a fan
(hub on the left, its label to its left, the others in a column to its right). The number on a line sits where no
other line, circle, number or name label touches it (`weight_spots`, run again after the name labels); a name label
takes a side or a corner of its circle, whichever touches the fewest lines.

**Photos and Scholar:** a photo shows only with an `images.csv` row (`approved=yes`, right `kind` and `key`) and a file
`static/img/<people|institutions|venues>/<key>.*`. `fetch_images.py --apply` re-resizes from raw downloads and can
overwrite a hand-cropped copy: copy crops by hand instead. `fetch_scholar.py` is a manual snapshot (never run by
`make data`); keep `found_on` and `fetched` in each entry, the build needs them.

**Scripts that read site data:** `fetch_affiliations.py` and `verify_affiliations.py` read
`frontend/data/professors.json`: build first. `verify_affiliations.py` skips papers already in either affiliation CSV
and needs the OpenReview variables; extend its `PMLR_VOLUME` (ICML) and `DOMAINS` maps for new years and institutions.

**Switches:** `local` (hugo.toml) asks search engines not to index, hides analytics and shows record notes;
`showNonAcceptedTitles` lists the titles of rejected papers. `publish.toml` sets the public values.

## Git and publishing

- Commit with the repository's own identity and a UTC date: `TZ=UTC git commit ...`, author
  `thanhlexyz <thanhlexyz@users.noreply.github.com>` (repo-local config). End the message with the attribution
  trailer your harness gives (currently `Co-Authored-By: Claude ... <noreply@anthropic.com>`). Never commit with
  the local time zone; check `git log --format=%ad` if unsure.
- `git push origin main`, then `make publish PYTHON=<python>`: it prints open flags (`open_flags.py`), builds with
  `frontend/publish.toml`, commits the built site in a throwaway repository (UTC date, repository identity) and
  force-pushes it to the `gh-pages` branch (GitHub Pages, "Deploy from a branch"), then asks GitHub Pages to build
  (`gh`). It does not rebuild the data or push `main`: do both first. CSS and JS links carry a content hash.
- Never rewrite pushed history without the maintainer's go-ahead.
- The repository is public: no private screenshots, local paths, e-mails or credentials in commits.

## Things to remember

- Qualcomm AI Research in Vietnam is the former VinAI (Vingroup sold it); neither is a university.
- Virtual-site affiliations (ICLR, NeurIPS, ICML, CVPR, ICCV, ECCV) come from author profiles, not from the paper.
- HUST's "HUST" also means Huazhong University in China; match a short name only against the person's own entry.
- Ask the maintainer when a decision is theirs (who is on the list, uncertain identities, rule changes); otherwise
  choose the sensible default and say what you chose.
