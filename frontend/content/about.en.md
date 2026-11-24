---
title: "About"
toc: true
---

**Vietnam AIRankings** is an open-source, data-driven project that tracks publications by Vietnamese university faculty at premier international artificial intelligence conferences.

In computer science, peer-reviewed flagship conferences are the primary venues for publishing cutting-edge research. By tracking publications from 2020 onward across the top 10 conferences in AI, Machine Learning, Computer Vision, and Natural Language Processing, this site aims to provide a transparent, objective overview of academic AI research originating from universities in Vietnam.

## Scope & Data Collection

### Tracked Conferences
We track ten flagship venues from 2020 onward, grouped into four subfields following [CSRankings](https://csrankings.org/): **AI** (AAAI, IJCAI), **ML** (ICLR, NeurIPS, ICML), **CV** (CVPR, ICCV in odd years, ECCV in even years), and **NLP** (ACL, EMNLP).

Only full-length Main Track papers (Long Papers) are counted. Short papers, workshops, position papers, Datasets & Benchmarks tracks, journal tracks, blog posts, and Tiny Papers are excluded from the main counts and listed separately under "Not main track" on profile pages. Papers accepted to *Findings* are counted alongside main-track rejections and listed with workshop papers.

### Tracked Researchers
We track Vietnamese lecturers, assistant professors, associate professors, and full professors whose primary appointment is currently at a university in Vietnam. Lecturers (*Giảng viên*) are included because Associate Professor and Professor titles in Vietnam are conferred by a centralized national council under criteria distinct from international tenure tracks, and many lecturers lead labs and advise PhD students just as Assistant or Associate Professors do abroad.

Students, foreign faculty, and researchers based solely at corporate labs or non-university institutes are excluded. The roster is curated by hand. A researcher appears once verified and having at least one counted submission (accepted or rejected) at the ten venues.

Papers count starting from the year a researcher joined a Vietnamese university. An accepted paper counts only if the camera-ready PDF explicitly lists the researcher at their Vietnamese university. A paper from an earlier post at another university in Vietnam also counts, if the researcher's OpenReview profile shows a lecturer or higher post there in that year; papers from a student post never count. Papers written solely under corporate or institute affiliations (e.g., Qualcomm AI Research / former VinAI) without a university affiliation do not count.

### Official Proceedings & OpenReview
Accepted papers are collected from official conference portals and proceedings (see table below).

{{< coverage >}}

† Official lists omit author affiliations. Affiliations for listed professors' papers are verified by hand from the PDF title pages (and excluded from affiliation-based metrics when unavailable).
‡ Preliminary list published prior to the conference and still being updated.

### Author Matching & Provisional Papers
OpenReview papers are matched directly by confirmed profile ID. Proceedings entries are matched by author name and count automatically if the printed affiliation matches the professor's university. If a paper lists another Vietnamese institution or the venue list omits affiliations (`†`), it is verified by hand. If a paper lists only foreign institutions, the author is treated as a namesake. While an official list is still incomplete{{< provisional >}}, verified announcements from faculty or lab pages are counted provisionally as `+N` with an "unofficial" badge until formal proceedings and OpenReview records are published.

## Scoring Methodology

### Faculty Score
Each accepted paper is worth `1 / N` (where `N` is the total number of authors) to each listed professor on the paper, following the [CSRankings](https://csrankings.org/) fractional model. A professor's score is the sum of their fractional shares across all qualifying papers.

### Institution Score
Faculty scores are summed within each of the four subfields (AI, ML, CV, NLP). The institution's overall score is the geometric mean across the four areas of `(Area Score + 1)`—the 4th root of their product. Adding 1 keeps a subfield with zero papers from zeroing out the entire score, while the geometric mean rewards balanced research strength across subfields.

### Authorship Roles and Lab Mentoring
Institution and professor pages also feature two stricter charts tracking accepted papers where the institution accounts for the **first author** or **more than half (>50%) of the authors**. Prospective graduate students and research interns choosing an advisor should pay close attention to this breakdown: it offers an important signal of how a professor works. A high proportion of lead-author and majority-institution papers generally indicates that the professor invests significant time directly mentoring students within their own lab, whereas a record dominated by external affiliations often reflects broader collaborative networks where primary day-to-day mentoring may occur outside.

## Submissions & Rejection Estimates

### Transparency of Review Outcomes
Conferences differ significantly in what submission data and review outcomes they disclose:

| Venue | Accepted Papers | Rejected and Withdrawn Submissions |
|:---|:---|:---|
| **ICLR** | Public | Public for all submissions |
| **NeurIPS** | Public | Public only when authors opt in |
| **ACL, EMNLP, CVPR** | Public | Not public (except for papers published in the Findings track) |
| **ICML, ICCV, ECCV, AAAI, IJCAI** | Public | Not public |

Venues such as ACL, EMNLP, and CVPR do not disclose rejections directly, but publishing in the Findings track reveals that a paper was not accepted to the Main Track (without exposing the rest of the rejected submissions). Consequently, comprehensive submission and rejection records exist only for ICLR. In our tables, recorded **Rejected** counts combine reviewer rejections, withdrawals, desk rejections, and Findings papers, while **Submitted** is accepted plus rejected. A professor who submits frequently to ICLR will thus show more recorded rejections than one who does not submit to ICLR.

### Estimating Submissions at Non-Disclosing Venues
To provide a more balanced view on each professor's yearly timeline chart, unseen rejections at non-disclosing venues are projected from the professor's own ICLR record using Laplace smoothing:

{{< ratio-eq >}}

For instance, 9 ICLR submissions and 1 acceptance gives `(9 + 1) / (1 + 1) = 5`, meaning each paper accepted at another venue is estimated to represent 5 submissions (defaulting to 1 if a professor has no ICLR submissions). Adding 1 avoids division by zero and stabilizes small sample sizes. This is a statistical projection of submission attempts: a paper rejected at one conference and accepted at the next counts as two attempts.

Importantly, this projection only applies to venues where submissions are certain because the researcher has at least one accepted paper. For example, if a professor has 1 accepted paper at AAAI and a submission record at ICLR, we extrapolate their submissions at AAAI. If they have no accepted papers at AAAI, no submissions are estimated for that venue because there is no evidence that they submitted there.

{{% ai-only %}}
## AI-Generated Text Scanning

Each scanned paper displays two experimental metrics from [MELD](https://huggingface.co/anon-review-meld-2026/meld) (v8, MIT license), an open ~1B-parameter encoder detector run locally on the main body text extracted via `pdftotext` (abstract to references/acknowledgments, dropping blocks under 15 words and papers under 300 words):

- **% AI Sentences:** Share of main-body sentences (8+ tokens) scoring above the detector's 1% false-positive threshold on general human text.
- **p_AI:** Holistic document score (0–100%) from the mean of the top quartile of token scores.

**How to interpret:** These are model estimates of text patterns, not proof of authorship or research quality. Because LLM-assisted proofreading and copy-editing are now widespread, `p_AI` approaches 100% on most 2025–2026 papers globally, so `% AI sentences` is the more informative indicator. Equations, tables, code, and heavy editing can also shift scores.
{{% /ai-only %}}

## Credits & Resources

This project was conceived, designed, and curated by **Thanh Le** ([thanhle.xyz](http://thanhle.xyz)), built with the assistance of [Claude](https://www.anthropic.com/claude), with writing and editorial revisions assisted by [Gemini](https://gemini.google.com/). I created this site out of personal curiosity to offer a transparent reference for the Vietnamese academic community and anyone following AI research in Vietnam.

The code and data are open source on [GitHub](https://github.com/thanhlexyz/vn-at-top-ai-conference). If you find this site useful, please consider giving it a ⭐ on GitHub, and feel free to submit corrections on the [Feedback](../feedback/) page. Visitor statistics use [GoatCounter](https://www.goatcounter.com/), which sets no cookies and stores no personal data.

**Acknowledgements:**
- **Dr. [Vo Sy Nam](https://vingen.vinbigdata.org/teams/vo-sy-nam/):** For insightful feedback and suggesting the pre-/post-2026 split on the [Venues](../venues/) page.
- **Prof. [Huynh Thi Thanh Binh](../professors/huynh-thi-thanh-binh/):** For suggesting the addition of EMNLP, ICCV, ECCV, AAAI, and IJCAI, as well as the CSRankings subfield grouping.
- **Prof. [ThanhVu Nguyen](https://tvn.roars.dev/):** Whose academic tools inspired this site:
  - [CS Picks](https://cspicks.roars.dev/) — compares US computer science faculty and universities by research strengths and NSF funding.
  - [CS Conferences](https://cspicks.roars.dev/csconfs.html) — tracks submission deadlines and dates for computer science conferences.
  - [VietProfs](https://vietprofs.roars.dev/) — directory of Vietnamese professors and academics worldwide.
