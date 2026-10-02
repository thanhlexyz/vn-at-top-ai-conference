---
title: "About"
---

## Author

This site is made by **Thanh Le** ([thanhle.xyz](https://thanhle.xyz)). The code and data are public on [GitHub](https://github.com/thanhlexyz/vn-at-top-ai-conference). Corrections are warmly welcome on the [Feedback](../feedback/) page.


## What is counted

- **Venues:** ICLR, NeurIPS, ICML, CVPR and ACL, from 2020 on. Years are conference years, so an ICLR 2026 paper was submitted in autumn 2025.
- **People:** Vietnamese lecturers, assistant professors, associate professors and professors whose main post is now at a university in Vietnam. Students, researchers at companies or institutes, and faculty from other countries are not tracked. Lecturers are included because the titles of associate professor and professor in Vietnam are conferred by a national council and are harder to obtain than in most other countries, so many lecturers do the work an assistant or associate professor does elsewhere. The list is kept by hand, and nobody appears before their entry has been approved and they have at least one counted submission at the five venues, accepted or not.
- **Only while in Vietnam:** a paper counts from the year the professor joined a Vietnamese institution. Earlier years are greyed out on the professor's page.
- **Main track only:** workshops, Findings (ACL, CVPR), position-paper tracks (ICML, NeurIPS), the NeurIPS Datasets & Benchmarks track, journal tracks, ICLR blog posts and Tiny Papers are left out. A professor's page lists such papers under "Not main track".
- **Rejected** adds up papers rejected by reviewers, withdrawn and desk-rejected. **Submitted** is accepted plus rejected.

## Co-authors and topics

These figures are taken over all of a professor's counted papers, accepted or not. Rejected papers come from OpenReview, which gives author names but no affiliations, so they enter the first figure only.

- **Co-authors per paper:** the average number of other authors on a paper.
- **Min and max:** the fewest co-authors on a single accepted paper, and the most co-authors on a single paper, accepted or not. A minimum of 0 means a paper written alone.
- **Foreign co-authors per paper:** the average number of other authors whose affiliation on the paper names no Vietnamese institution. An author who lists both a Vietnamese and a foreign institution is not foreign.
- **Co-authors at other institutions:** the number of different co-authors whose affiliation on the paper is not the professor's own institution, in Vietnam or abroad.
- **Topic areas:** the number of different top-level areas among the topic labels the conference gave the papers, for example "Deep Learning" or "Reinforcement Learning".

The two affiliation figures use only papers from lists that print an affiliation for each author, so ACL papers, and CVPR papers before 2023 and in 2026, are left out of them.
Topic labels exist only for ICLR and ICML from 2024 and for NeurIPS from 2023 to 2025. The label sets differ between conferences and years, and the authors choose the label, so two papers on the same subject can carry different labels.
Each professor's page says how many papers a figure is based on.

## The chart of submitted and accepted papers

Each professor's page has a chart of papers per year. Two parts of it are counted: the accepted papers at all five venues, and the rejected ICLR papers. The third part is an estimate of the papers that NeurIPS, ICML, CVPR and ACL did not accept, which nobody outside can see.

The estimate is made professor by professor, from their own ICLR record:

submissions per accepted paper = (ICLR submitted + 1) / (ICLR accepted + 1)

With 9 ICLR submissions and 1 accepted, that is 10 / 2 = 5, so each paper accepted elsewhere is taken to stand for 5 submissions. Adding 1 on both sides is the usual way to estimate attempts per success from a short record: the result stays finite when nothing was accepted, and one paper more or less does not swing it. A professor with no ICLR submissions gets 1, so the chart adds nothing for them.

This is a projection, not a measurement. It assumes the other venues treated the professor's papers as ICLR did, and it counts attempts: a paper rejected at one conference and accepted at the next appears twice.

## Stricter counts on institution pages

An institution page has two more tables. One counts an accepted paper only when more than half of its authors list the institution. The other counts it only when the first author does. Both use papers from lists that print an affiliation for each author, so ACL papers, CVPR papers before 2023 and in 2026, and papers known only from personal pages are left out; the page says how many.

## What each venue makes public

| Venue | Accepted papers | Rejected and withdrawn papers |
|:---|:---|:---|
| ICLR | public | public for every submission |
| NeurIPS | public | public only when the authors opted in |
| ICML | public | not public |
| CVPR | public | not public |
| ACL | public | not public |

Submitted and rejected numbers therefore exist for ICLR only.
A professor who sends most papers to ICLR will show more rejections here than one who sends them to ICML or CVPR, whatever their real acceptance rates are.
The NeurIPS rejections that are public appear on the professor's page and on the NeurIPS page, marked as partial. They are not in the table on the front page.

Even ICLR is not complete: a withdrawn paper can be removed or left anonymous, and then it cannot be found.

## Sources

- **Accepted papers:** the conference virtual sites (iclr.cc, neurips.cc, icml.cc, cvpr.thecvf.com), the CVF Open Access lists for CVPR, and the ACL Anthology volumes of long and short papers.
- **ICLR submissions and outcomes, NeurIPS public rejections:** OpenReview, queried with each professor's own profile ID.

Main-track accepted papers read per venue and year:

{{< coverage >}}

† The list gives author names without affiliations.
‡ The list was published before the conference and is still being filled. In September 2026 the NeurIPS 2026 list lacked papers that their authors had already announced, which is why papers from personal pages are added for it.

## Papers from personal pages

The professors' own pages are read as well, and what they list is kept in `self_reported.csv` with the address and the date. They are used in three ways.

- A paper on a professor's own page that is also in an official list counts as theirs, even when the name on the paper is not a form the roster knows.
- When an official list is not complete yet, a paper from a personal page is counted although the list does not have it. This applies to a list published before its conference, which today means NeurIPS {{< stat "pooled.neurips_last.year" >}}. Such a paper is **unofficial**: it appears as +N after the official number and carries the tag "unofficial", with the page it comes from, until the conference publishes it.
- A paper on a colleague's page that names a listed professor as co-author is treated the same way for that professor when it is not in an official list yet. If it is in an official list, it waits for a yes or no by hand.

For a year whose official list is complete, a paper that only a personal page mentions is not counted. It is usually a workshop paper, another track or another year, and it is written to the build report.

A page that only announces a number ("five papers accepted") adds nothing to the counts. The professor's page says so when the number is higher than what could be identified.

## How a paper is matched to a professor

1. OpenReview records are matched by profile ID, which is exact once the ID has been confirmed.
2. In the accepted lists, a paper is matched by author name. It counts automatically only when the affiliation printed on the paper is the professor's institution.
3. If the paper names another Vietnamese institution, or the list has no affiliations, the match waits for a yes or no by hand.
4. If the paper names only a foreign institution, the author is treated as a different person with the same name.

## Limits

- A paper published under a name form that is not on the roster is missed.
- For ACL, and for CVPR before 2023 and in 2026, there are no affiliations, so every match needs a decision by hand.
- The Vietnam rule works by year. A paper that appeared in the year of the move counts, even if it was submitted before the move.
- For ICLR 2020 and 2021, OpenReview keeps the decision in a separate record. Where that record has not been read, the outcome is inferred from the accepted list, and the paper is marked.
- A paper with two listed professors counts once for each of them, and once in the totals of an institution or a venue.
- Counts say nothing about author order, contribution or the quality of a paper.

## Updating

The data is rebuilt with `make data` in the project folder. `make openreview` fetches the OpenReview records and needs a login. The README describes both.

## Visitors

The public site counts visits with [GoatCounter](https://www.goatcounter.com/), which sets no cookies and keeps no personal data about visitors: only the page, the referring site, the browser, the screen size and the country derived from the address, which is not stored.
