# AGENT.md: how to operate and maintain this site

You are maintaining a public, bilingual (Vietnamese at `/`, English at `/en/`) Hugo site that counts papers of
lecturers and professors in Vietnam at thirteen AI and robotics conferences, grouped as CSRankings does. The maintainer gives short requests in plain words; this
file tells you how to carry them out. Read it before changing anything. It is the only instruction file: keep it up to date
when the code or the rules change.

Live site: <https://thanhlexyz.github.io/vn-at-top-ai-conference/>

## Layout

Naming (the maintainer's choice, 2026-11-25), in both languages and in the addresses: **universities**
(`/universities/`, formerly `/institutions/`), **conferences** (`/conferences/`, formerly `/venues/`), **professors**,
and the professors' graph is **Domestic cooperation** (`/domestic/`, formerly `/graph-people/` and `/graph-professors/`),
the counterpart of International cooperation. Old addresses redirect (Hugo aliases; `write_stubs(..., former=...)`).
"Institutions" stays only where companies and institutes are included (the co-author institutions on university pages).
Internal names (data files such as `institutions.json`, `venues.json`, `graph_people.json`, `img/people/`) are unchanged.


The top level holds only `backend/`, `frontend/`, `README.md`, `makefile`, `AGENT.md`, `LICENSE` and `.gitignore`.

- `backend/code/`: Python scripts that collect records and write the site data (`build_site_data.py` is the core), and
  `backend/code/tests/`. Run scripts from `backend/code/`.
- `backend/data/csv/`: the tables (hand-kept and generated), `backend/data/json/`: snapshots kept in the repository
  (`scholar.json`, `reviews.json`, `submission_numbers.json`). Paths come from `common.py` (`CSV_DIR`, `JSON_DIR`).
- `frontend/`: Hugo site, own layouts (no theme), data in `frontend/data/*.json`, strings in `frontend/i18n/{en,vi}.toml`,
  one small `static/site.js` (sorting, cups, pinned columns, graph hover, feedback e-mail).
- `makefile`: `data`, `openreview`, `affiliations`, `homepages`, `refresh`, `run`, `build`, `publish`, `test`.
- README figures live in `frontend/static/readme/` (screenshots of the built site, in English, light mode).

**No comments in the code** (the maintainer's rule, 2026-11-25): no comments or docstrings in Python, the makefile,
templates (`{{/* */}}`, `<!-- -->`), JavaScript, CSS, TOML, SVG or `.gitignore`. Explanations belong in this file; commit 4118d8b is the last one with the old code comments.
Command-line help texts are strings, not comments, and stay. Keep only code the current site uses: delete unused
scripts, tables, functions, templates, i18n strings, CSS rules and static files (git history keeps them).

Run Python with the environment that has `openreview-py` installed, passed to make as `PYTHON=<python>`.
OpenReview credentials come from the environment variables `OPENREVIEW_USERNAME` and `OPENREVIEW_PASSWORD`, which
the maintainer sets in their shell profile; if a non-interactive shell does not have them, load that profile in the
same command before running the script. Never print, log or commit the password.

## The usual cycle

1. Edit the hand-kept files (below), or code.
2. `cd backend/code && <python> build_site_data.py` (or `make data`): rebuilds `frontend/data/` and the page stubs.
   A full build takes about 10 minutes, almost all of it the Domestic cooperation layout. When the graph's input has not
   changed (no new paper with two or more professors, no roster change), run `build_site_data.py --keep-graph` (about
   15 s): it keeps `graph_people.json`. Run the full build only when the maintainer asks or the graph must change.
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
| `backend/data/csv/roster.csv` | everyone considered: `approved` (`yes` on the site, `no` checked and left off with the reason in `notes`, empty = waiting), name forms, institution, `rank` (as on OpenReview), `vn_since`, `openreview_ids`, `homepage`, `pages`, `to_confirm`, `notes`, `slug`, `name_vi`, `role`, `role_vi`, `role_source`, `page_note`, `page_note_vi`. CRLF line endings; edit with Python `csv`, never `sed` (fields with commas break). |
| `backend/data/csv/review.csv` | uncertain matches; the build appends rows, a human answer goes in `decision` (`yes`/`no`) with a dated `note`. |
| `backend/data/csv/self_reported.csv` | papers from professors' pages, co-authors' pages and announcements; `track` is `main` or `findings`. |
| `backend/data/csv/affiliations.csv` | per-author affiliations read from the PDF where a list prints none (`fetch_affiliations.py`, each row checked by hand, `checked=yes`). |
| `backend/data/csv/affiliation_fixes.csv` | one author's affiliation as the paper prints it, where the list differs (virtual sites copy author profiles). |
| `backend/data/csv/images.csv` | photos and logos, with source page and a dated note. |
| `backend/data/csv/institution_names.csv` | Vietnamese names of institutions, confirmed by the maintainer. |
| `backend/data/json/scholar.json` | Google Scholar snapshots (`fetch_scholar.py`). |
| `backend/data/csv/vietprofs.csv` | co-authors abroad with a profile on VietProfs (<https://vietprofs.roars.dev>, Vietnamese professors worldwide): `match_vietprofs.py` proposes rows from the Candidates table, `checked=yes` once name and university agree; the International cooperation page draws only these. VietProfs' data is CC BY-NC-ND: read it into `raw/` only, commit just the profile ids. |
| `backend/data/csv/venue_rates.csv` | acceptance rates the conferences report, per year, with source and `source_kind` (`official`/`secondary`); the build pools all years. |
| `backend/data/csv/faculty.csv` | staff lists, used by `find_candidates.py` to mark candidates on the local Candidates page. |

`backend/raw/` and `backend/work/` are git-ignored: downloads, PDFs, screenshots the maintainer gives you.
`work/build_report.txt` lists warnings and skipped namesakes after each build. Page stubs in
`frontend/content/{professors,universities,venues}/` are rewritten on every build: never edit them by hand.
`make data` also runs `fetch_accepted.py` (may download) and `find_candidates.py` (rewrites `candidates.csv`).
The local-only pages (Candidates, Not tracked) are drafts, but their data (`candidates.json`, `candidates.csv`,
`attempted.json`) is tracked in the public repository.

## Counting rules (the About page states them; keep both in sync)

- Venues, grouped as CSRankings does (`VENUE_GROUPS` in `common.py`): AI (AAAI, IJCAI), ML (ICLR, NeurIPS, ICML),
  CV (CVPR, ICCV in odd years, ECCV in even years), NLP (ACL, EMNLP; NAACL is not tracked, being CORE rank A and not A*),
  RB, robotics (ICRA, IROS, RSS; added 2026-11-26 at the maintainer's request); years 2020 on, conference years (IJCAI-PRICAI 2020 met in January 2021 and is 2020). AAAI main
  track = the "AAAI Technical Track on ..." sections of ojs.aaai.org issues; IJCAI = the "Main Track" section of
  ijcai.org/proceedings; ACL = the long-paper volumes, never the short-paper ones (no short papers anywhere); the volumes that mix long and short (ACL 2020, EMNLP) cannot be split, so check each counted paper there by its page count in the bib (long papers run 12 pages and more with references); not Findings. The AAAI and IJCAI lists, like ACL and EMNLP,
  print no affiliations: their name matches go through `fetch_affiliations.py` (which also reads the matches waiting
  in `review.csv`) before the institution rule can apply. AAAI and IJCAI publish no rejections.
- **Robotics lists** (`fetch_accepted.py`): ICRA and IROS = the papers DBLP lists on the proceedings page of the year
  (`dblp_toc`, DBLP's SPARQL service at sparql.dblp.org; dblp.org itself answers scripts with a bot check, do not get
  around it), which is what CSRankings counts: RA-L and other journal papers presented there are not in it. RSS = the
  index page of roboticsproceedings.org (`parse_rss`). The affiliations are the publisher's, read from OpenAlex by DOI
  prefix (`openalex_affiliations`, cached in `raw/openalex/`; `OPENALEX_API_KEY` is set only in the maintainer's
  interactive shell, so run a download as `zsh -ic 'python fetch_accepted.py'`). The metadata sometimes drops the
  country or the parent university ("University of Information Technology", "RMIT University"): when a tracked
  professor's paper is skipped for that, read the title page (arXiv) and add an `affiliation_fixes.csv` row. ICRA and
  IROS PDFs are behind IEEE's paywall, so `verify_affiliations.py` reports them as "no PDF"; RSS PDFs are open. None
  of the three publishes rejections. The `DECISION_DATES` of ICRA 2022, IROS 2022-2026 and RSS 2021-2023 and 2026 are
  from the conference sites; the other robotics dates are approximate (they only order the Papers page).
- People: Vietnamese lecturers, assistant/associate professors, professors whose main post is at a university in
  Vietnam. Not students, researchers or industry staff. To join, a person needs at least one counted submission:
  an accepted paper, an ICLR record (rejected/withdrawn/desk-rejected counts) or a Findings paper. Workshop papers
  alone do not qualify.
- A paper counts from `vn_since`; main track only (no workshops, position papers, D&B, journal tracks).
- **Findings** = rejected from the main track at any conference, and also listed as a workshop paper.
  Sources: the ACL Anthology Findings volumes (`{year}.findings-acl` from 2021, `{year}.findings-emnlp` from 2020;
  `fetch_accepted.py`, track `findings`, long papers only: 12 pages or more in the bib), the professors' OpenReview
  records (CVPR 2026 Findings, EMNLP Findings on OpenReview) and `self_reported.csv`. Their name matches go through
  `review.csv` and `fetch_affiliations.py` like the main track.
- **Institution rule:** an accepted official paper counts for a person only if the paper lists them at their roster
  institution, as printed on the paper (the PDF wins over a virtual site, which copies profiles). A paper written
  only at a company or institute (e.g. Qualcomm AI Research, which is the former VinAI) does not count. Papers that
  print no affiliation (unofficial ones, lists without affiliations) count. Ways it passes (`at_institution`,
  `same_institution`): the institution's known names (`vn_institutions` in `common.py`), its parent national university
  (`PARENT`), its full name as a substring, its short name as a word in the person's own entry ("VinAI & HUST"), and a
  bare "University of Science" for HCMUS or VNU-HUS. If the person cannot be found on the paper, it counts.
  It also passes at an earlier university in Vietnam (`at_past_post`): the person's OpenReview history has a staff post
  (`post_class` "staff": lecturer or higher) there covering the paper's year; a student post never counts (rule set by
  the maintainer on 2026-11-24).
  `affiliation_fixes.csv` rows apply only with `checked=yes`; `affiliations.csv` applies only when the list prints no
  affiliation at all and the authors match name by name.
- **Unofficial:** a paper known only from a personal page or announcement counts while the official list is
  provisional or not published; shown as `+N` and tagged unofficial. A paper in an official list is unofficial too while
  the venue-year is in `UNVERIFIED` in `build_site_data.py` (empty since 2026-11-20, when NeurIPS 2026 became public): its authors cannot be confirmed on
  OpenReview until the submissions are public, so only a paper from the person's own OpenReview record is official.
  Remove the venue-year from `UNVERIFIED` once OpenReview publishes it (then refresh and run `verify_affiliations.py`).
  The exemption keeps official any match that starts with "OpenReview profile", which includes exact-ID papers found
  in a colleague's record.
- **Provisional lists:** only ICLR, NeurIPS and ICML lists of the current year (`LAST_YEAR`, today's year in `common.py`)
  can be provisional (fewer than half the entries have a start time, `fetch_accepted.is_provisional`). On 1 January the
  year rolls over: `YEARS` gains the new year. Hard-coded 2026 to update together:
  `neurips_2026_only` in `build_site_data.py`, and the heading of `not-tracked.html`.
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
- **ICLR projection** (`iclr_projection`, ICLR venue chart only): while the current year is under review (its accepted
  list not out), the column shows the rejections on record plus a projection, captioned only as a projection (the
  maintainer does not want the method on the site). Each withdrawn paper stands for 1 / (withdrawal share) submissions,
  accepted at its professors' rate: withdrawal share from each professor's own previous three ICLR years, acceptance
  from the previous year, both pulled toward the group's by 2 papers. Papers whose professors did not submit to ICLR the
  year before count as one rejection only.
  When `work/under_review.json` exists (match_under_review.py), the projected acceptances are instead the matched
  submissions with a mean review score above 2.6 (`ACCEPT_SCORE`, the maintainer's threshold); only the count is public.
- **Authorship charts:** "majority" = strictly more than half of all authors at the institution; "first" = the first
  author. Only papers with at least one printed affiliation are judged.
- **Co-author figures:** averages over all counted papers; the minimum over accepted papers; the maximum also over
  workshop papers; affiliation figures need the person found on the paper and an affiliation printed.
- **Institution collaboration** (the co-author institutions on university pages, `institution_links.json` from
  `graph.institution_links`; there is no institution graph any more, removed 2026-11-25): a paper links the roster
  institutions of its listed professors, plus Vietnamese institutions printed on it that have nobody on the list
  (companies, institutes such as VinAI or FPT). An institution with professors on the list joins a paper only through
  one of them, never through a student or untracked co-author, so its shared papers are always among its own
  professors' papers.

## International cooperation

The page (`layouts/_default/international.html`, data `international.json` from `international_graph` in `build_site_data.py`)
joins the co-authors outside Vietnam with 5 or more counted papers together with the professors on the list (the
Candidates table "Co-authors outside Vietnam", `FOREIGN_MIN_PAPERS`) and a checked row in `vietprofs.csv`. Authors link
to VietProfs, professors to their page here; each author carries the flag of the country VietProfs lists. Co-authors run from
most papers down; professors sit at the average height of their co-authors (fewest crossings).

## AI score (Open Text Detector)

The MELD detector was removed on 2026-11-25 in commit 4118d8b (its parent, 8d2670f, still has it). Only Open Text Detector figures remain.

- ICLR 2027 only: `fetch_opentextdetector.py` reads <https://opentextdetector.com>'s public
  browse API by OpenReview forum id (exact `forum_id` match only) and keeps the site's default view, `flags["body0.1"]`
  (main text, 0.1% human false-positive rate; no figure under 50 sentences), in `work/opentextdetector.json`. The build
  writes `frontend/data/otd_scores.json` (tracked: public since 2026-11-16, at the maintainer's request); the Papers page
  shows it as the "AI score" column with `showOtdScores` (true in both `hugo.toml` and `publish.toml`). Per paper only.
- The Papers page's "Submission ID" (the OpenReview submission number, read by `fetch_reviews.py` into `submission_numbers.json`),
  "Review scores" (score(confidence), from `fetch_reviews.py` into `reviews.json`) and "AI score" columns are
  `data-extra`: hidden until the reader presses "More columns".

## Research directions (`/research/`, `/research/<professor>/`; internal names still say "challenges": `open_challenges.py`, `frontend/data/challenges*.json`, `work/challenges/`)

Public pages, objective and data-driven: every statement traces to a paper's abstract, its own text or its public
OpenReview reviews; reviewer concerns are verbatim quotes (checked word for word at merge, unmatched quotes dropped);
no praise or opinion. Written at the level of a computer-science undergraduate. Built from the Papers page only (never
from under-review submissions).
- `/research/`: each professor with a short focus line, ✅ when written from the full material, 🚧 otherwise.
- `/research/<slug>/`: portrait; overview and open-challenges paragraphs covering the three top topics; a
  topic × year figure (dots = papers, curves = citations between the professor's papers, found in the PDFs'
  reference lists); then topics ordered by their CSRankings score (sum of 1/N authors over the topic's papers, shown
  in the heading), each with a folded description, topic words, folded open questions (every topic has some) and
  folded papers (problem, idea, reported results, what the authors leave open, reviewer quotes, outcome tag).
- Professor pages quote the two paragraphs and link to the challenge page.
- The filter on `/research/` uses ONE topic list synthesised from the official calls for papers of the 13 tracked
  conferences (`frontend/data/challenge_topics.json`: 34 topics, each with the conferences whose CFP terms it merges, plus the
  CFP addresses shown under the filter). Sources: ICLR/NeurIPS/ICML/CVPR/ECCV/ACL/EMNLP/ICRA/IROS 2026, ICCV 2025,
  AAAI-27 (the 2026 edition lists none); IJCAI's CFP has no topic list (its special tracks and the AI-and-Health,
  Social-Good, Robotics lists were used); RSS publishes none; the IEEE and AAAI sites block scripts, so those pages came
  through a summarising fetch tool. Rebuild by collecting the CFPs into `backend/work/cfp/*.json`, merging them into
  `topics.json` (every CFP term in exactly one topic), then labelling each professor topic (`topic_lines.txt` →
  `topic_areas.json`, 1-3 keys each); `merge` reads both. The list is sorted by the score of a professor's topics in the
  chosen filter, counting accepted papers only; professors with a zero score are folded behind a button.
- A professor page's topics ARE the shared topic list (no free-form topics): each paper gets exactly one topic
  (`paper_labels_*.json`, an agent reads title, problem and technique), a professor's topic section is the group of
  their papers in that topic, scored by the sum of 1/N authors, sections ordered by score. Topic merges decided by the
  maintainer live in `backend/data/json/topic_merges.json` (`open_challenges.py taxonomy` rebuilds the list,
  `regroup` writes the per-professor inputs, agents write `topics2/part_<slug>.json`). Co-authors see the same text for
  a shared paper: groups with identical paper sets are unified at merge (`unify`), overlapping ones are harmonized by an
  agent (`harmonize_out.json`). `/research/` shows each professor's per-topic summary: all of them (best topic
  first) with no filter, only the chosen topic's with a filter.
- The summary paragraphs describe the work by topic ("Work on <what>" + one `[phrase](paper-id)` link marker per
  sentence, turned into `#paper-id` links by `linkify`), never naming papers or methods, so a reader with no context
  understands them.
- Vietnamese text calls a professor "thầy/cô + given name" (`polite` in `open_challenges.py`, titles from
  `backend/work/challenges/honorifics.json`, judged from the portraits); without a photo or a Vietnamese name form the
  full name stays.

`backend/code/open_challenges.py <step>`: `pdfs` (non-OpenReview PDFs: ACL Anthology, IJCAI, CVF, then OpenAlex and
arXiv by exact title; AAAI and IEEE only through arXiv), `orpdfs` (OpenReview PDFs through the logged-in API; the
account is rate limited, run one worker), `reviews` (OpenReview reviews as Markdown), `about` (abstracts), `full
<slugs>` (one bundle per professor in `backend/work/challenges/full/`: abstract, the paper's own limitations text, path
of the reviews file), `merge` (agent output `final/chunk_<slug>.json` and `topics/part_<slug>.json` into
`frontend/data/challenges.json`, `challenges_people.json` and the content pages). A professor is written when all of
their PDFs are in; the agent brief is kept with the session (fields: per paper problem/technique/strength/authors/
reviewers quotes; per professor intro and topics with gist, open_gist, summary, open items, papers). PDFs, bundles
and agent output stay in the git-ignored `backend/work/`. Never mention scores, decisions, originality allegations or
discussion-period dates; a missing PDF never means a paper states no limitations.

## ICLR submissions under review

Hand matches go in `work/under_review_decisions.json`: `{"add": <arXiv id or page address>, "professors": [slugs]}` for a
submission the automatic match misses (a page address when a professor's own page lists it as under review), `drop`
for a namesake.
A name match is skipped when OpenAlex puts that preprint author at a different known Vietnamese institution than the
professor's (`elsewhere`, printed as a namesake); `professors` in a decision removes a namesake from a shared paper.
`match_under_review.py` matches ICLR submissions still under review to public preprints by title (OpenAlex, an author in
Vietnam), with the submission number, review scores, their mean (above 2.6 = potential accept, `ACCEPT_SCORE`) and the
Open Text Detector share. The data (`work/under_review.json`, `frontend/data/under_review.json`) is git-ignored: the
repository never holds it. What shows, as the maintainer decided on 2026-11-25:
- local build (`local` true): everything, with professor names and the preprint link; the Candidates page lists the
  other authors in Vietnam on those preprints who are not on the roster;
- published build: Papers page rows with title, scores, AI share and the potential tag, professors shown as "redacted",
  no preprint link; professor pages show "ICLR 2027 · under review · redacted" only; the Venues table counts them; the
  ICLR chart's 2027 bar is counted from them (potential accepts, recorded rejections, potential rejects); each potential
  accept counts as an unofficial +1 in every counting table and in the score (`potential_records`: title, co-authors
  and links redacted in the data files); a mean above 3.3 is tagged potential spotlight.
The maintainer accepted that a title can be searched to find the preprint's authors.

## Score

The front-page and institution tables are ordered by CSRankings' adjusted count: each accepted paper (official and
unofficial) is worth 1 / (number of authors) to each listed professor; an institution's score adds up its
professors' scores in each of the five areas, combined as CSRankings does: the geometric mean over AI, ML, CV, NLP, RB of
(area count + 1) (`score_areas` and `score` in `build_site_data.py`).
The front table marks each professor's rank change (▲n / ▼n; the beginner mark for anyone with no accepted paper
outside it, i.e. new to the list) against the same ranking
without the papers of `RANK_BASELINE` in `build_site_data.py`: today "potential", the potential ICLR 2027
acceptances (`potential_records`); when ICLR's decisions arrive, set it to the next venue-year with results. Shown only for professors with accepted papers.
It is explained in About and in two callouts: the professor score on the front page, the institution score on the Institutions page; keep them in step.

## Tables, sorting and cups (`frontend/static/site.js`, `partials/professor-table.html`)

- "x +y" (official, unofficial) sorts as x + y; among equal totals, more official papers first. The default order of
  the professor, institution and venue tables follows the same rule (`professors.sort`, `institutions.sort`, and the
  sort in `venues/list.html`), so the cups match the order on load.
- Two tracked professors with the same name are shown as "Name (ABBR)" everywhere (`shown_name` in
  `build_site_data.py`, from `institution_short`); the slug and matching keep the plain name.
- The cooperation graph pages (layouts `graph` and `international`) use the full window width (`main.wide`, as on
  awesome-nnv); every other page keeps the 72rem column. Each SVG is drawn at most at its own size (`--w`), so labels stay
  14px next to the 16px text. The domestic graph is laid out on the 1000-wide canvas and then `graph.pack` moves whole
  clusters (main cluster left, the rest beside it, then rows) on a `PAGE_WIDTH` (1500) canvas; clusters other than the
  main one are shrunk to at most `span` (400) so they fit beside it. `pack` only translates, so it can be rerun on a
  saved layout without the 10-minute layout.
- Total ⇄ Last year also on the Universities list (`institutions[].recent`), the Conferences list (`venues[].recent`,
  `partials/venue-cells.html`; venues with no paper are hidden there but still tracked), the professor table on each
  university page (with only "Accepted at" and Total shown, the rest behind "More columns") and both graphs: edges carry
  `recent` and `recent_width` (`graph_recent`, rewritten on every build, also with `--keep-graph`), nodes `recent_degree`
  or `recent`; the `graph-period` button hides what has no last-year paper (`.r0`).
- The front page opens on the all-time totals. Clicking the "Total" heading flips the five Total columns (score,
  accepted, rejected, submitted and rate, estimated) to "Last year" and re-sorts by that score (ties keep the all-time
  order); clicking "Last year" flips back. Last year means papers decided on or after `RECENT_FROM` in `common.py`, the
  first of the month 12 months before the build (undated papers such as ICLR 2027 potential count); the figures are
  `recent` in professors.json (`recent_totals`, same estimate as `projection` with the all-time ICLR ratio). The cells
  carry the other period in `data-alt*` attributes (`partials/recent-cells.html`, `period-cell.html`); the rank arrows
  have a last-year version too (`rank_change_recent`, same ICLR baseline, `partials/rank-mark.html`). The
  front table has no own-university or co-author columns; "Accepted at" is behind "More columns". In the text, say "last year", not "12 months".
- Cups (gold, silver, bronze) go to the top three distinct values of the sorted column; ties share a cup and the next
  value takes the next cup. Sorted largest first, zero gets none; sorted smallest first, zero is the best value.
  Sorted by a text column, there are none. Cups appear on the front page, the Institutions list and institution pages
  with at least 4 professors (not on the Venues list); the front page and institution pages show the pinned `#`
  column. The institution bar charts draw their cups at build time (`podium` in `build_site_data.py`).
- Cells marked `data-last` always sort to the bottom and get no cup: the acceptance rate of people with no ICLR
  submissions, and the co-author and own-institution columns of people with no accepted paper (shown greyed).
- Numbers never wrap (`td:not(.l)`); captions and notes stay short and refer to About for definitions.
- The front table starts with the professors who have an accepted paper (official or unofficial); the rest (`more-row`,
  accepted = 0) open with "+ Show N professors with no accepted paper yet" under the table. Hidden rows take no `#` number
  and no cup (`renumber`, `podium` in `site.js`); without JavaScript every row shows.
- Hidden columns (`data-extra`) open with a quiet text control at the table's top-right ("+ Show N more columns",
  tooltip naming the hidden headings), inside a `.table-box` as wide as the table; the control's `aria-controls`
  names its table's `id`.

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
private screenshots stay in `backend/raw/`. Only for people on the
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
fix what it flags. Add the venue-year's notification date to `DECISION_DATES` in `common.py`: the Papers page lists
the newest decisions first (the build warns about a venue-year with accepted papers and no date); within one
conference and date, by mean review score, then mean reviewer confidence (highest first), papers without scores last
(`decision_order`). The under-review rows sort by goodpapers.org's acceptance chance where known, then the same way.
The chances are hand-kept in `work/acceptance_chance.csv` (`forum,chance,checked,note`; git-ignored): goodpapers.org
sits behind a Vercel bot check, so they are read in a browser, never by a script. `match_under_review.py --chances`
merges them without fetching anything; the "Acceptance chance" column (hidden until "More columns") links each row there. NeurIPS PDFs become public only after the conference.

Since November 2026 `ojs.aaai.org` answers scripts with a bot check, so AAAI PDFs cannot be downloaded by a script (do
not try to get around it; the maintainer can save PDFs by hand). IJCAI is unaffected: `fetch_affiliations.py --scan ijcai
--min-names 1` reads every paper with at least one Vietnamese family name (default 2), and a download that is not a PDF
is skipped, never cached. For AAAI (and as a cross-check for IJCAI), and for ICRA, IROS and RSS, run `scan_openalex.py`: OpenAlex lists the authors in
Vietnam of every paper, with the affiliation as printed (`work/openalex_vn.csv`). They are leads: look up each one's
OpenReview profile, and do not suggest anyone whose profile says they are a student.

The local Candidates page starts with **To validate**: the people the maintainer decides about, merged from
`staff_leads.csv` (`scan_openalex.py --leads`), candidates whose OpenReview post is lecturer or higher at a university
in Vietnam (`fetch_openreview.py --candidates N`, then `find_candidates.py`; OpenReview allows about 126 profile searches
per half hour) and lecturers with an ICLR record (`iclr_only.csv`), most papers first. Students are never listed. A yes
is a roster row with `approved = yes`, a no a row with `approved = no` and the reason (decided by OpenReview ID, so the
name leaves the list). Everything else on the page is a closed checklist line that opens to its table.
`scan_openalex.py --leads` rewrites `staff_leads.csv` but keeps the rows with `source = by hand` (people the scan cannot
find: no OpenReview profile, or a paper outside the scanned lists). A hand row needs the evidence of the post: an
OpenReview ID, or a `staff_page` address when there is no profile; it leaves the list once the person is on the roster.

**Both languages, always:** the Vietnamese site (`/`) mirrors the English one (`/en/`). Any change to a page, whether
text added, removed or reworded, a section, a caption, a column or a layout change, is made in both languages in the
same commit: `en.toml` and `vi.toml`, `*.en.md` and `*.vi.md`. Then compare the two built pages
(`frontend/public/en/...` against `frontend/public/...`) before committing; the maintainer reads the Vietnamese page.

**Text on the site:** every string in both `en.toml` and `vi.toml`, in a professional register; Vietnamese that reads
naturally, not translated word for word. Keep captions short; do not repeat what a legend or the About page already
explains (refer to About instead). Surfaces, grid and text are CSS tokens defined for light and dark mode; the chart
and table hues (accepted green, rejected red, graph colours) are fixed and checked on both. Some English strings from
the build are parsed by templates (a reason starting with `before `, a track ending in ` track`): keep that wording.

**Collaboration graphs** (`backend/code/graph.py`; the professors' graph is Domestic cooperation at `/domestic/`): line length follows shared
papers only loosely (more papers, closer; the maintainer allowed relaxing it on 2026-11-25 so that labels and crossings
come first); it also links professors who share an ICLR submission under review (`under_review_links`, no titles, the
maintainer's decision of 2026-11-25); no line passes
through a circle (`repair` ends each layout: a seeded search moves circles off lines they are not on, inside the
group's area, at the cost of a crossing if need be); labels never overlap lines or other labels and never leave the drawing; crossings few. After any
change, check crossings and label clearance and look at screenshots. Hovering a circle lights it, its links and its
neighbours; hovering a university in the legend (dot, logo or name) lights that university's professors, their one-hop
neighbours, the links between them and the legend entries of the universities reached (`site.js`).
**Search and zoom** (both cooperation pages; `partials/graph-tools.html`, the last two blocks of `site.js`; taken from
the maintainer's awesome-nnv site, 2026-11-26): the search box pins a person (`svg.pin`), so the highlight stays until
the box is cleared; it matches the name shown and the other language's form (`data-name`, `data-alt`), without
accents, whole words before prefixes before substrings. Zoom rewrites the SVG `viewBox`, never the data:
Ctrl/⌘ + wheel (and trackpad pinch) zooms about the pointer, a plain wheel scrolls the page, the +/−/Reset buttons
show only with JavaScript, zoom 1–6×, pan clamped to the drawing; a drag pans only after 4 px and only when zoomed,
so a click on a circle still opens the page. They use every counted
submission (rejected and withdrawn included) plus workshop papers from the Vietnam years, and feed the co-author
lists. Researcher colours: HUST red, VinUni blue, HCMUS cyan (logo hues), the next three institutions ochre, green
and purple, the three after them rings of those colours (never a brand colour as a ring), the rest grey; the six
fills pass the dataviz palette checks in both modes (`graph.py`). Groups of 5 or more get their own band. `networkx` is used for planar starts and Kamada-Kawai; without it the layout differs. Small groups go
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
- Publish (`make publish`) only when the maintainer says so in the current request ("ship" means commit, push and publish); a publish request does not carry
  over to later requests.
- Never rewrite pushed history without the maintainer's go-ahead.
- The repository is public: no private screenshots, local paths, e-mails or credentials in commits.

## Entity Page Writing Guidelines & Templates (Professors, Universities, Venues)

The introductory text on entity pages (`/professors/<slug>/`, `/universities/<slug>/`, `/conferences/<slug>/` or `/venues/<slug>/`) must be smooth, natural, and human-friendly.
Past AI-generated text was overly dense, robotic, and read like a mechanical dump of database fields. When writing or updating these pages (via layout templates and `i18n/{vi,en}.toml`), follow these principles and templates strictly.

The site tracks thirteen conferences since 2026-11-26: where the templates below say "ten" / "mười", the site's
strings say "thirteen" / "mười ba", and "AI conferences" is plain "conferences".

### Core Writing Principles
1. **Human Academic Register:** Write as a professional academic editor presenting a scholar, university, or conference. Sentences must be complete, active, and conversational rather than telegraphic dumps of numbers.
2. **Avoid Densely Packed Subjects:** Never build sentences around heavy, convoluted noun phrases with nested conditions. Keep subjects light and clear.
3. **No Semicolons (`;`):** Do not use semicolons in prose; use natural commas or separate sentences.
4. **Eliminate Disjointed Fragments:** Avoid abruptly inserting robotic time splits (e.g. do not write "80 bài được nhận trước năm 2027, 1 bài từ năm 2027" or "Tại ICLR: 5 bài nộp, 0 bài được chấp nhận, 5 bài bị từ chối"). Weave numbers naturally into sentences.
5. **Clean Presentation of Caveats & Estimates:** Unofficial papers, name variants, and statistical estimates should be mentioned gracefully rather than through heavy bracketed formulas.

---

### 1. Professor Pages (`/professors/<slug>/`)

#### Template Structure
- **Line 1 (Academic Affiliation & Role):**
  - **VI:** `[Chức danh / Vị trí], [Tên trường]. Công tác tại một trường đại học ở Việt Nam từ năm [Năm].`
  - **EN:** `[Title / Rank], [University]. Affiliated with a Vietnamese university since [Year].`
  - *If alternate names exist:*
    - **VI:** `<br><span class="note">Tên khác trên bài báo: [Danh sách tên].</span>`
    - **EN:** `<br><span class="note">Also published as: [List of names].</span>`

- **Paragraph 2 (Publications & Peer Review Record):**
  - **Sentence 1 (Accepted publications):**
    - **VI:** `Trong giai đoạn công tác tại Việt Nam, [tác giả / giảng viên] có [N] bài báo chính thức được nhận tại mười hội nghị hàng đầu [nếu có bài chưa chính thức: (bao gồm [X] bài trong kỷ yếu và [Y] bài công bố sớm)].`
    - **EN:** `While based in Vietnam, [the researcher / Dr. Name] has published [N] accepted papers across the ten tracked flagship conferences [if unofficial: (including [X] in official proceedings and [Y] provisional announcements)].`
  - **Sentence 2 (OpenReview / ICLR & Other Rejection Data):**
    - **VI:** `[Nếu có hồ sơ ICLR]: Về dữ liệu phản biện công khai, tác giả đã nộp [A] bài tại ICLR ([B] bài được nhận và [C] bài không được nhận) [nếu có bài bị từ chối ghi nhận ở hội nghị khác: cùng [D] bài bị từ chối công khai hoặc thuộc Findings tại [Các hội nghị]].`
    - **EN:** `[If ICLR record]: Based on public review records, they have submitted [A] papers to ICLR ([B] accepted, [C] rejected or withdrawn) [if other rejections: alongside [D] recorded rejections or Findings papers at [Venues]].`

#### Example: Tuan Dam (`tuan-dam`)
- **Before (Dense & Robotic):**
  > Lecturer, Đại học Bách khoa Hà Nội. Công tác tại Việt Nam từ năm 2024.
  > Tên khác trên các bài báo: Tuan Dam, Tuan Quang Dam, Tuan Q. Dam, Quang Tuan Dam
  > Từ năm 2024, giảng viên có 12 bài báo được chấp nhận tại mười hội nghị hàng đầu. 12 bài được nhận trước năm 2027, 0 bài từ năm 2027. Tại ICLR: 5 bài nộp, 0 bài được chấp nhận, 5 bài bị từ chối. Bài bị từ chối có ghi nhận ở các hội nghị khác (bài bị từ chối công khai và bài được xếp vào Findings): NeurIPS 2.
- **After (Human-friendly & Smooth):**
  > Lecturer, Đại học Bách khoa Hà Nội. Công tác tại một trường đại học ở Việt Nam từ năm 2024.
  > Tên khác trên bài báo: Tuan Dam, Tuan Quang Dam, Tuan Q. Dam, Quang Tuan Dam.
  >
  > Trong giai đoạn công tác tại Việt Nam, giảng viên có 12 bài báo được nhận tại mười hội nghị AI hàng đầu. Về dữ liệu phản biện công khai, tác giả đã nộp 5 bài tại ICLR (5 bài không được nhận), cùng 2 bài thuộc Findings hoặc bị từ chối công khai tại NeurIPS.

---

### 2. University / Institution Pages (`/universities/<slug>/`)

#### Template Structure
- **Paragraph 1 (Roster & Core Output):**
  - **Sentence 1 (Faculty count & Accepted total):**
    - **VI:** `Hiện có [N] giảng viên của [Tên trường] nằm trong danh sách theo dõi, với tổng cộng [M] bài báo được nhận tại mười hội nghị hàng đầu [nếu có bài chưa chính thức: (bao gồm [X] bài chính thức và [Y] bài công bố sớm)].`
    - **EN:** `[University Name] has [N] tracked faculty members with a combined total of [M] accepted papers across the ten tracked AI conferences [if unofficial: (including [X] in official proceedings and [Y] provisional announcements)].`
  - **Sentence 2 (De-duplication rule):**
    - **VI:** `Công trình có nhiều giảng viên trong trường cùng tham gia chỉ tính một lần cho trường.`
    - **EN:** `Papers co-authored by multiple faculty members within the university are counted once toward the institution total.`

- **Paragraph 2 (Review Profile & Projection):**
  - **Sentence 1 (ICLR public records):**
    - **VI:** `Về lịch sử nộp bài công khai tại ICLR, các tác giả của trường đã nộp [A] bài ([B] bài được nhận và [C] bài bị từ chối).`
    - **EN:** `In public OpenReview records at ICLR, faculty from the institution have submitted [A] papers ([B] accepted, [C] rejected).`
  - **Sentence 2 (Statistical estimate across confidential venues):**
    - **VI:** `Dựa trên tỷ lệ chấp nhận tại ICLR, ước tính trường có thêm khoảng [D] lượt bài không được nhận tại các hội nghị bảo mật thông tin phản biện.`
    - **EN:** `Extrapolating from this ICLR record, the institution is projected to have approximately [D] unobserved rejections across confidential venues.`

#### Example: HUST (`hust`)
- **Before (Dense & Robotic):**
  > Trường có 15 giảng viên trong danh sách, với 81 bài được chấp nhận tại mười hội nghị, trong đó 1 bài chỉ được công bố trên trang công khai của giảng viên hoặc phòng thí nghiệm (chưa chính thức). 80 bài được nhận trước năm 2027, 1 bài từ năm 2027. Tại ICLR: 39 bài nộp, 7 bài được chấp nhận, 32 bài bị từ chối. Nếu tính cả số bài bị từ chối không được công khai tại các hội nghị khác (ước tính dựa trên kết quả ICLR nêu trên), tổng số bài bị từ chối vào khoảng 328 bài. Một bài có nhiều giảng viên của trường chỉ được tính một lần.
- **After (Human-friendly & Smooth):**
  > Hiện có 15 giảng viên của Đại học Bách khoa Hà Nội nằm trong danh sách theo dõi, với tổng cộng 81 bài báo được nhận tại mười hội nghị hàng đầu (gồm 80 bài chính thức và 1 bài công bố sớm). Công trình có nhiều giảng viên trong trường cùng tham gia chỉ tính một lần cho trường.
  >
  > Về lịch sử nộp bài công khai tại ICLR, các tác giả của trường đã nộp 39 bài (7 bài được nhận và 32 bài bị từ chối). Dựa trên tỷ lệ chấp nhận tại ICLR, ước tính trường có thêm khoảng 328 lượt bài không được nhận tại các hội nghị bảo mật thông tin phản biện.

---

### 3. Conference / Venue Pages (`/conferences/<slug>/` or `/venues/<slug>/`)

#### Template Structure
- **Paragraph 1 (Venue Overview & Core Output):**
  - **Sentence 1 (Acceptance total):**
    - **VI:** `Tại [Tên hội nghị], các giảng viên trong danh sách theo dõi có tổng cộng [N] bài báo được nhận kể từ năm 2020.`
    - **EN:** `At [Venue Name], tracked faculty from universities in Vietnam have authored a total of [N] accepted papers since 2020.`
  - **Sentence 2 (De-duplication rule):**
    - **VI:** `Công trình có nhiều giảng viên trong nước đồng tác giả được tính một lần cho hội nghị.`
    - **EN:** `Papers co-authored by multiple listed faculty are counted once toward the venue total.`

- **Paragraph 2 (Transparency Policy & Rejections):**
  - **Case A: Full disclosure (ICLR):**
    - **VI:** `[Tên hội nghị] công khai toàn bộ bài nộp và kết quả phản biện trên OpenReview, cho phép thống kê chính xác cả số bài được nhận lẫn số bài bị từ chối.`
    - **EN:** `[Venue Name] discloses all submissions and review outcomes on OpenReview, allowing exact tracking of both accepted and rejected submissions.`
  - **Case B: Partial disclosure (NeurIPS):**
    - **VI:** `[Tên hội nghị] công khai các bài được nhận, trong khi bài bị từ chối chỉ xuất hiện khi tác giả chủ động chia sẻ. Do đó, số bài bị từ chối được ghi nhận đại diện cho mức tối thiểu.`
    - **EN:** `[Venue Name] publishes accepted papers, while rejected submissions are public only if authors opt in. The recorded rejections therefore represent a lower bound.`
  - **Case C: Confidential rejections (CVPR, ICML, ICCV, ECCV, ACL, EMNLP, AAAI, IJCAI):**
    - **VI:** `[Tên hội nghị] chỉ công khai danh sách bài được nhận và bảo mật toàn bộ bài bị từ chối (ngoại trừ các bài công bố ở Findings). Vì vậy, số bài nộp và lượt từ chối tại đây được ước tính gián tiếp dựa trên dữ liệu ICLR của các tác giả.`
    - **EN:** `[Venue Name] publishes accepted papers only and keeps rejections confidential (except for papers published in Findings). Total submissions and unseen rejections are projected using each author's ICLR submission record.`

#### Example: NeurIPS (`neurips`)
- **Before (Dense & Robotic):**
  > NeurIPS công khai các bài được chấp nhận. Bài bị từ chối chỉ được công khai khi tác giả lựa chọn, vì vậy số bài bị từ chối dưới đây là con số tối thiểu và không có số liệu về số bài nộp. Số liệu được tính cho các giảng viên trong danh sách; một bài có nhiều giảng viên trong danh sách chỉ được tính một lần. 57 bài được nhận trước năm 2027, 0 bài từ năm 2027.
- **After (Human-friendly & Smooth):**
  > Tại NeurIPS, các giảng viên trong danh sách theo dõi có tổng cộng 57 bài báo được nhận kể từ năm 2020. Công trình có nhiều giảng viên trong nước đồng tác giả được tính một lần cho hội nghị.
  >
  > NeurIPS công khai các bài được nhận, trong khi bài bị từ chối chỉ xuất hiện khi tác giả chủ động chia sẻ. Do đó, số bài bị từ chối được ghi nhận đại diện cho mức tối thiểu. Số bài nộp bổ sung tại đây được ước tính gián tiếp theo lịch sử nộp bài ICLR của các tác giả (trung bình khoảng 3.1 lượt nộp cho mỗi bài được nhận).

---

### Technical Implementation Guide for Future Agents
When rewriting entity pages across the site:
1. Update template strings in `frontend/i18n/vi.toml` and `frontend/i18n/en.toml`.
2. Update the layout template files:
   - `frontend/layouts/professors/single.html`
   - `frontend/layouts/universities/single.html`
   - `frontend/layouts/conferences/single.html`
3. Remove or streamline robotic helper templates like `frontend/layouts/partials/split-sentence.html` that inject disjointed year fragments ("X bài trước năm Y, Z bài từ năm Y").
4. Always verify with `make build` (must show zero warnings) and `make test` (all tests must pass).

## Things to remember

- Qualcomm AI Research in Vietnam is the former VinAI (Vingroup sold it); neither is a university.
- Virtual-site affiliations (ICLR, NeurIPS, ICML, CVPR, ICCV, ECCV) come from author profiles, not from the paper.
- HUST's "HUST" also means Huazhong University in China; match a short name only against the person's own entry.
- Ask the maintainer when a decision is theirs (who is on the list, uncertain identities, rule changes); otherwise
  choose the sensible default and say what you chose.
