---
title: "Candidates"
layout: "candidates"
draft: true
---

Candidates waiting for validation or manual review before being added to the public roster.
Faculty members appear on the public site once their entry in `backend/roster.csv` is set to `approved = yes`.
To evaluate candidates, use `python find_candidates.py --add "Name"` in `backend/`, verify their position, appointment year (`vn_since`), and OpenReview profile ID.
Individuals confirmed not to be faculty at a university in Vietnam are cataloged on the [Not tracked](../not-tracked/) page.
*(This draft page is visible during local development with `make run` and omitted from public production builds).*