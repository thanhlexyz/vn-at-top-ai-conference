PYTHON ?= python3

install:
	sudo pacman -S hugo
	pip install openreview-py

data:
	cd backend/code && $(PYTHON) fetch_accepted.py && $(PYTHON) find_candidates.py && $(PYTHON) build_site_data.py

openreview:
	cd backend/code && $(PYTHON) fetch_openreview.py && $(PYTHON) build_site_data.py

affiliations:
	cd backend/code && $(PYTHON) fetch_affiliations.py && $(PYTHON) build_site_data.py

homepages:
	cd backend/code && $(PYTHON) fetch_homepages.py

refresh:
	cd backend/code && $(PYTHON) fetch_accepted.py --refresh && $(PYTHON) find_candidates.py && $(PYTHON) build_site_data.py

run:
	cd frontend && hugo serve --buildDrafts --noHTTPCache --disableFastRender

build:
	rm -rf frontend/public
	cd frontend && hugo

PAGES_REPO ?= thanhlexyz/vn-at-top-ai-conference
PAGES_REMOTE ?= $(shell git remote get-url origin)
GIT_NAME := $(shell git config user.name)
GIT_EMAIL := $(shell git config user.email)

publish:
	@cd backend/code && $(PYTHON) open_flags.py
	rm -rf frontend/public
	cd frontend && hugo --config hugo.toml,publish.toml
	touch frontend/public/.nojekyll
	cd frontend/public && git init -q -b gh-pages && git add -A \
		&& TZ=UTC git -c user.name="$(GIT_NAME)" -c user.email="$(GIT_EMAIL)" commit -q -m "site of $$(date -u +%F)" \
		&& git push -f $(PAGES_REMOTE) gh-pages
	rm -rf frontend/public/.git
	-gh api -X POST repos/$(PAGES_REPO)/pages/builds --jq .status
	-gh run watch --repo $(PAGES_REPO) --exit-status \
		$$(gh run list --repo $(PAGES_REPO) --branch gh-pages --limit 1 --json databaseId --jq '.[0].databaseId')

test:
	cd backend/code && $(PYTHON) -m unittest discover -s tests

clean:
	rm -rf frontend/public frontend/resources backend/work
