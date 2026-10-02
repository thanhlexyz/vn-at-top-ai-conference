---
title: "Not tracked"
layout: "not-tracked"
draft: true
---

People confirmed not to be a lecturer or professor at a university in Vietnam, so they are not tracked.
"Checked by hand" are the rows of `backend/roster.csv` with `approved = no`, with the `notes` column as the
reason. "Not at a university" are authors whose papers name only a company or institute. Neither group appears
on the [Candidates](../candidates/) page.
This page is a draft, so it is shown by `make run` and left out of `make build` and `make publish`.
