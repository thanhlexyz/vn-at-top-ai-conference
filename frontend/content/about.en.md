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

The [Research directions](../research/) page answers a question that numbers and rankings cannot: *what problems is each professor actively tackling, and what open questions remain?* It is designed for undergraduate and graduate students, prospective PhD applicants, and researchers exploring related areas. All summaries are compiled strictly from public material: papers tracked on this site (both accepted and rejected), their abstracts and author-stated limitations, and public reviews on OpenReview.

### What it shows

- **Shared topic list:** A catalog of 19 unified research topics covering all tracked conferences. Selecting a topic reveals which professors in Vietnam publish in that area, sorted by their [CSRankings score](#scoring-methodology) in that topic (accepted papers only).
- **Dedicated professor pages:** Each profile begins with a concise overview and a summary of open challenges, followed by a breakdown organized by topic. Each topic section describes the problem, the core idea, reported outcomes, open questions (both author-stated limitations and direct quotes from public reviews), and links to the paper's official source and OpenReview page.
- **Citation timeline diagrams:** An interactive chart mapping papers by topic and year. Curves link later papers to earlier publications by the same professor that they cite, helping you visualize how a research direction evolved over time.

### How it can help you

- **Finding a research advisor:** Topic breakdowns and scores highlight where a professor's recent publications actually concentrate, which a faculty directory or university affiliation cannot tell you. A professor who actively publishes in your field of interest is often a much better match than a well-known name working in a different subfield. The papers listed under each topic provide an ideal reading list before reaching out.
- **Selecting a thesis topic:** Every highlighted open question pinpoints an unresolved challenge identified by authors or peer reviewers—such as an untested domain, computational overhead, or baseline comparisons requested during review. For students, these offer concrete starting points: you can begin from an open question, read the linked paper, and propose a well-scoped research contribution.
- **Writing more effective outreach emails:** Citing a specific recent paper and discussing one of its open questions demonstrates to prospective advisors that you have genuinely engaged with their research before reaching out.

### Limitations

These pages provide summaries rather than qualitative evaluations. They contain no subjective ratings of papers or reviewers and offer no verdict on whether a research direction is worthwhile. Papers whose full text or peer reviews were not publicly accessible are summarized based on abstracts alone, and several conferences (such as AAAI and ICRA) do not release public reviews. Researchers working within each field understand where their community is heading and which problems are most impactful, and they may view strengths and limitations differently. We encourage you to use these summaries as a helpful starting point and discuss directions directly with the faculty and groups involved.

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
