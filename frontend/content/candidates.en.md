---
title: "Candidates"
layout: "candidates"
draft: true
---

Nobody appears on the site until their row in `backend/roster.csv` says `approved = yes`.
To add people from the list at the bottom, run `python find_candidates.py --add "Name"` in `backend/`,
then fill in `rank`, `vn_since` and `openreview_ids` and set `approved` to `yes`.
People confirmed not to be a lecturer or professor in Vietnam are on the [Not tracked](../not-tracked/) page instead.
This page is a draft, so it is shown by `make run` and left out of `make build` and `make publish`.
