---
title: "About"
toc: true
---

**Vietnam AIRankings** is an open-source, data-driven project that tracks publications by Vietnamese university faculty at premier international artificial intelligence and robotics conferences.

In computer science, peer-reviewed flagship conferences are the primary conferences for publishing cutting-edge research. By tracking publications from 2020 onward across 13 top conferences in AI, Machine Learning, Computer Vision, Natural Language Processing, and Robotics, this site aims to provide a transparent, objective overview of academic AI research originating from universities in Vietnam.

## Scope & Data Collection

### Tracked Conferences
We track thirteen flagship conferences from 2020 onward, grouped into five subfields following [CSRankings](https://csrankings.org/): **AI** (AAAI, IJCAI), **ML** (ICLR, NeurIPS, ICML), **CV** (CVPR, ICCV in odd years, ECCV in even years), **NLP** (ACL, EMNLP), and **RB**, robotics (ICRA, IROS, RSS).

Only full-length Main Track papers (Long Papers) are counted. Short papers, workshops, position papers, Datasets & Benchmarks tracks, journal tracks, blog posts, and Tiny Papers are excluded from the main counts and listed separately under "Not main track" on profile pages. Papers accepted to *Findings* are counted alongside main-track rejections and listed with workshop papers. For ICRA and IROS, the counted papers are those in the conference proceedings, as CSRankings counts them. Journal papers presented at these conferences (for example, RA-L papers) are not counted.

### Tracked Professors
We track Vietnamese lecturers, assistant professors, associate professors, and full professors whose primary appointment is currently at a university in Vietnam. Lecturers (*Giảng viên*) are included because Associate Professor and Professor titles in Vietnam are conferred by a centralized national council under criteria distinct from international tenure tracks, and many lecturers lead labs and advise PhD students just as Assistant or Associate Professors do abroad.

Students, foreign faculty, and researchers based solely at corporate labs or non-university institutes are excluded. The roster is curated by hand. A professor appears once verified and having at least one counted submission (accepted or rejected) at the thirteen conferences.

Papers count starting from the year a professor joined a Vietnamese university. An accepted paper counts only if the camera-ready PDF explicitly lists the professor at their Vietnamese university. Papers from an earlier appointment at another university in Vietnam also count, provided the professor held a faculty position (lecturer or higher) there that year. In contrast, papers published while the author was a student or PhD candidate do not count. Papers written solely under corporate or institute affiliations without an accompanying university affiliation are also excluded.

### Official Proceedings & OpenReview
Accepted papers are collected from official conference portals and proceedings (see the charts below).

{{< coverage >}}

A hollow point (†) marks a year whose official list omits author affiliations. Affiliations for listed professors' papers are verified by hand from the PDF title pages (and excluded from affiliation-based metrics when unavailable).
‡ Preliminary list published prior to the conference and still being updated.

### Author Matching & Provisional Papers
OpenReview papers are matched directly by confirmed profile ID. Proceedings entries are matched by author name and count automatically if the printed affiliation matches the professor's university. If a paper lists another Vietnamese institution or the conference list omits affiliations (`†`), it is verified by hand. If a paper lists only foreign institutions, the author is treated as a namesake. While an official list is still incomplete{{< provisional >}}, verified announcements from faculty or lab pages are counted provisionally as `+N` with an "unofficial" badge until formal proceedings and OpenReview records are published.

## Scoring Methodology

### Faculty Score
Each accepted paper is worth `1 / N` (where `N` is the total number of authors) to each listed professor on the paper, following the [CSRankings](https://csrankings.org/) fractional model. A professor's score is the sum of their fractional shares across all qualifying papers.

### University Score
Faculty scores are summed within each of the five subfields (AI, ML, CV, NLP, RB). The university's overall score is the geometric mean across the five areas of `(Area Score + 1)`—the 5th root of their product. Adding 1 keeps a subfield with zero papers from zeroing out the entire score, while the geometric mean rewards balanced research strength across subfields.

### Authorship Roles and Lab Mentoring
University and professor pages also feature two stricter charts tracking accepted papers where the university accounts for the **first author** or **more than half (>50%) of the authors**. Prospective graduate students and research interns choosing an advisor should pay close attention to this breakdown: it offers an important signal of how a professor works. A high proportion of lead-author and majority-university papers generally indicates that the professor invests significant time directly mentoring students within their own lab, whereas a record dominated by external affiliations often reflects broader collaborative networks where primary day-to-day mentoring may occur outside.

## Submissions & Rejection Estimates

### Transparency of Review Outcomes
Conferences differ significantly in what submission data and review outcomes they disclose:

| Conference | Accepted Papers | Rejected and Withdrawn Submissions |
|:---|:---|:---|
| **ICLR** | Public | Public for all submissions |
| **NeurIPS** | Public | Public only when authors opt in |
| **ACL, EMNLP, CVPR** | Public | Not public (except for papers published in the Findings track) |
| **ICML, ICCV, ECCV, AAAI, IJCAI, ICRA, IROS, RSS** | Public | Not public |

Conferences such as ACL, EMNLP, and CVPR do not disclose rejections directly, but publishing in the Findings track reveals that a paper was not accepted to the Main Track (without exposing the rest of the rejected submissions). Consequently, comprehensive submission and rejection records exist only for ICLR. In our tables, recorded **Rejected** counts combine reviewer rejections, withdrawals, desk rejections, and Findings papers, while **Submitted** is accepted plus rejected. A professor who submits frequently to ICLR will thus show more recorded rejections than one who does not submit to ICLR.

### Estimating Submissions at Non-Disclosing Conferences
To provide a more balanced view on each professor's yearly timeline chart, unseen rejections at non-disclosing conferences are projected from the professor's own ICLR record using Laplace smoothing:

{{< ratio-eq >}}

For instance, 9 ICLR submissions and 1 acceptance gives `(9 + 1) / (1 + 1) = 5`, meaning each paper accepted at another conference is estimated to represent 5 submissions (defaulting to 1 if a professor has no ICLR submissions). Adding 1 avoids division by zero and stabilizes small sample sizes. This is a statistical projection of submission attempts: a paper rejected at one conference and accepted at the next counts as two attempts.

Importantly, this projection only applies to conferences where submissions are certain because the professor has at least one accepted paper. For example, if a professor has 1 accepted paper at AAAI and a submission record at ICLR, we extrapolate their submissions at AAAI. If they have no accepted papers at AAAI, no submissions are estimated for that conference because there is no evidence that they submitted there.

## Research directions

The [Research directions](../research/) page answers a question that rankings cannot: *what does each professor actually work on, and where is their work still unfinished?* It is written for undergraduate and master's students, PhD applicants and researchers from other fields, and it is built only from public material: the papers on this site (accepted and rejected), their abstracts and own limitation sections, and the public OpenReview reviews.

### What it shows

- **A list of topics.** The topics come from one shared list that we built from the calls for papers of the conferences tracked here (the subject areas each conference asks authors to choose from), merged into 19 topics. Pick a topic and the list shows who works on it, ranked by their [CSRankings score](#scoring-methodology) in that topic (accepted papers only).
- **A page per professor.** It opens with a short overview and a summary of the open challenges, then goes topic by topic. Each topic has a short description, the questions it leaves open (what the authors say they have not solved, and verbatim quotes from public reviews) and the papers, each with the problem, the idea, what it reports and links to the paper, its official source and OpenReview.
- **A figure per professor.** One dot per paper by topic and year, with curves where a paper cites an earlier one of the same professor, so you can see how a line of work developed.

### How it can help you

- **Choosing a supervisor.** The topic summaries and scores show what a professor works on and how much of their output sits in each topic, which a name or a university does not tell you. A professor with many papers in a topic you like, in recent years, is a stronger match than a famous name in another area. The papers listed under each topic are the place to read before you write to them.
- **Choosing a thesis topic.** Every open question marks a point that the authors or reviewers say is not yet solved, such as a setting that was not tested, a cost the method adds, or a baseline reviewers asked for. For a student, those are concrete places to help a supervisor: start from a question, read the linked paper, and propose a small, well-defined piece of work.
- **Writing a better email.** Citing a specific paper and one of its open questions shows that you have read the work.

### Limits

The pages are summaries, not evaluations. They contain no scores of papers or reviewers and no opinion about whether a direction is worthwhile. Papers whose text or reviews we could not obtain are described from their abstracts only, and many papers, such as those at AAAI and ICRA, have no public reviews. Experts in a field know where it is heading and which problems are worth pursuing, and may weigh strengths and weaknesses differently; use these pages as a starting point and talk to the people involved.

## Credits & Resources

This project was conceived, designed, and curated by **Thanh Le** ([thanhle.xyz](http://thanhle.xyz)), built with the assistance of [Claude](https://www.anthropic.com/claude), with writing and editorial revisions assisted by [Gemini](https://gemini.google.com/). I created this site out of personal curiosity to offer a transparent reference for the Vietnamese academic community and anyone following AI research in Vietnam.

The code and data are open source on [GitHub](https://github.com/thanhlexyz/vn-at-top-ai-conference). If you find this site useful, please consider giving it a ⭐ on GitHub, and feel free to submit corrections on the [Feedback](../feedback/) page. Visitor statistics use [GoatCounter](https://www.goatcounter.com/), which sets no cookies and stores no personal data.

**Acknowledgements:**
- **Dr. [Vo Sy Nam](https://vingen.vinbigdata.org/teams/vo-sy-nam/):** For insightful feedback and suggesting a recent view of the numbers, now the **Last year** view that the tables and graphs open on, starting from the [front page](../).
- **Prof. [Huynh Thi Thanh Binh](../professors/huynh-thi-thanh-binh/):** For suggesting the addition of EMNLP, ICCV, ECCV, AAAI, and IJCAI, as well as the CSRankings subfield grouping.
- **Prof. [ThanhVu Nguyen](https://tvn.roars.dev/):** Whose academic tools inspired this site:
  - [CS Picks](https://cspicks.roars.dev/) — compares US computer science faculty and universities by research strengths and NSF funding.
  - [CS Conferences](https://cspicks.roars.dev/csconfs.html) — tracks submission deadlines and dates for computer science conferences.
  - [VietProfs](https://vietprofs.roars.dev/) — directory of Vietnamese professors and academics worldwide.
