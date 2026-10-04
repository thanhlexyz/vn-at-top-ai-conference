# Vietnam at top AI conferences

A bilingual (Vietnamese / English) static site that counts, for a hand-approved list of lecturers and professors in
Vietnam, the papers they submitted to and had accepted or rejected at AAAI, IJCAI, ICLR, NeurIPS, ICML, CVPR, ICCV, ECCV, ACL,
EMNLP and NAACL since 2020, grouped as CSRankings does (AI, ML, CV, NLP).

**Website: <https://thanhlexyz.github.io/vn-at-top-ai-conference/>**

![Accepted, recorded rejected and estimated rejected papers of all listed professors per year](docs/submissions.png)

*Submissions per year, all listed professors: accepted papers, rejections on record (every ICLR rejection, public
NeurIPS rejections and Findings papers), and the rejections the other venues do not publish, estimated from each
professor's own ICLR record.*

![Researcher collaboration graph: professors on the list joined by the papers they share](docs/researcher-graph.png)

*Who works with whom: each circle is a professor on the list (Vietnamese names), coloured by institution; lines join
people who share papers, shorter for more shared papers.*

The figures are snapshots of the site; the live pages are updated with the data.

## How to maintain it

The site is maintained by asking an AI coding agent (for example Claude Code) to do the work, in plain words. Every
step is described in [CLAUDE.md](CLAUDE.md); Claude Code reads it automatically, and any other agent can be told to
read it first. Typical requests:

- "Track `<OpenReview profile URL>`, he is a lecturer at `<university>`."
- "Add these unofficial acceptances: `<announcement text, screenshot or link>`."
- "`<name>`'s photo is at `<link>`" or "their staff page is `<link>`".
- "This paper is wrong: `<link>`" (wrong person, wrong affiliation, missing paper).
- "Refresh the data" (for example after a conference publishes its accepted papers).
- "Publish."

Check the result on the local site (`make run`, then <http://localhost:1313>) or on the live site after publishing.

## What you need to do yourself

- **Set up once:** Python 3.10+, Hugo 0.156+, `poppler` (`pdftotext`), ImageMagick, and
  `pip install openreview-py opencv-python-headless`.
- **Give your OpenReview login** in the environment as `OPENREVIEW_USERNAME` and `OPENREVIEW_PASSWORD` (OpenReview
  is the only source of rejected papers; the agent never prints them).
- **Decide** what only you can decide: who belongs on the list, and the answers the agent asks for when a match is
  uncertain.
- **Keep private material out of the repository.** The repository is public: everything committed, including
  `backend/roster.csv` and its notes, is visible to everyone. Screenshots and downloads go to the git-ignored
  `backend/raw/`.

## TODO

- [ ] **Track more professors now that AAAI, IJCAI and NAACL are counted** (added 2026-10-05; the staff list was
  not expanded then). The papers of people already on the list are counted, but lecturers in Vietnam who publish
  mainly at these three venues are not on the list yet. Their lists print no affiliations, so `find_candidates.py`
  cannot find them automatically, as it already cannot for ACL, EMNLP, and CVPR before 2023. Ways to find them:
  - the Candidates page (`make run`): since 2026-10-05 it includes authors printed at a university in Vietnam on
    AAAI, IJCAI and NAACL papers with two or more Vietnamese family names (`fetch_affiliations.py --scan`), 166
    people in all; most are students, but some are likely lecturers (e.g. at VNU-UET, UIT);
  - co-authors of professors already on the list, on their AAAI, IJCAI and NAACL papers;
  - staff pages of faculties of computer science and AI in Vietnam (`backend/faculty.csv`).

  For each person found, decide whether they qualify (a lecturer or higher whose main post is at a university in
  Vietnam), then ask the agent to "track" them with their OpenReview profile or staff page.

## Commands, if you want them

```
make run       # local site at http://localhost:1313
make data      # rebuild the data from the cached lists
make test      # checks of the counting rules
make publish   # build the public site and push it to GitHub Pages
```

Feedback from readers arrives as GitHub issues or by e-mail (see the site's Feedback page).
