
PYTHON ?= python3

install:
	sudo pacman -S hugo
	pip install openreview-py

# download the public accepted-paper lists (cached), list candidates, rebuild the site data
data:
	cd backend && $(PYTHON) fetch_accepted.py && $(PYTHON) find_candidates.py && $(PYTHON) build_site_data.py

# needs OPENREVIEW_USERNAME and OPENREVIEW_PASSWORD: the only source of rejected and withdrawn papers
openreview:
	cd backend && $(PYTHON) fetch_openreview.py && $(PYTHON) build_site_data.py

# PDFs of accepted papers whose list prints no affiliations; new rows in backend/affiliations.csv are filled and
# marked checked=yes by hand from backend/work/pdf_headers/, then the site data is rebuilt
affiliations:
	cd backend && $(PYTHON) fetch_affiliations.py && $(PYTHON) build_site_data.py

# save the professors' own pages and list their lines about the five venues in backend/work/homepage_hits.txt;
# copying papers from there into backend/self_reported.csv is done by hand
homepages:
	cd backend && $(PYTHON) fetch_homepages.py

# download the accepted-paper lists again, for example after a conference has published its papers
refresh:
	cd backend && $(PYTHON) fetch_accepted.py --refresh && $(PYTHON) find_candidates.py && $(PYTHON) build_site_data.py

# --buildDrafts shows the blog draft; `make build` leaves drafts out
run:
	cd frontend && hugo serve --buildDrafts --noHTTPCache --disableFastRender

build:
	rm -rf frontend/public
	cd frontend && hugo

# Build the public site and push it to the gh-pages branch of the origin repository, which GitHub Pages
# serves (Settings > Pages > Deploy from a branch > gh-pages). The address and the public settings are in
# frontend/publish.toml. Drafts (Candidates, the blog draft) are left out. The gh-pages branch holds
# generated files only and is replaced on every publish.
# The commit is made in a throwaway repository inside frontend/public, which would otherwise fall back
# to the global git identity; it gets this repository's author and a UTC date instead.
PAGES_REPO ?= thanhlexyz/vn-at-top-ai-conference
PAGES_REMOTE ?= $(shell git remote get-url origin)
GIT_NAME := $(shell git config user.name)
GIT_EMAIL := $(shell git config user.email)

publish:
	@cd backend && $(PYTHON) open_flags.py
	rm -rf frontend/public
	cd frontend && hugo --config hugo.toml,publish.toml
	touch frontend/public/.nojekyll
	cd frontend/public && git init -q -b gh-pages && git add -A \
		&& TZ=UTC git -c user.name="$(GIT_NAME)" -c user.email="$(GIT_EMAIL)" commit -q -m "site of $$(date -u +%F)" \
		&& git push -f $(PAGES_REMOTE) gh-pages
	rm -rf frontend/public/.git
	@# ask GitHub Pages to build now instead of waiting for it to notice the push; needs `gh auth login`
	-gh api -X POST repos/$(PAGES_REPO)/pages/builds --jq .status
	-gh run watch --repo $(PAGES_REPO) --exit-status \
		$$(gh run list --repo $(PAGES_REPO) --branch gh-pages --limit 1 --json databaseId --jq '.[0].databaseId')

test:
	cd backend && $(PYTHON) -m unittest discover -s tests

clean:
	rm -rf frontend/public frontend/resources backend/work
