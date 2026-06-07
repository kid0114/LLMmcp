PYTHON ?= /opt/homebrew/Caskroom/miniconda/base/envs/mcp-llm/bin/python

install:
	$(PYTHON) -m pip install -e .[dev]

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m mypy .

format:
	$(PYTHON) -m ruff format .

run-search:
	$(PYTHON) scripts/run_search.py

run-fetch:
	$(PYTHON) scripts/run_fetch.py

run-browser:
	$(PYTHON) scripts/run_browser.py

run-local-file:
	$(PYTHON) scripts/run_local_file.py

run-github-search:
	$(PYTHON) scripts/run_github_search.py

run-time:
	$(PYTHON) scripts/run_time.py

run-file-reader:
	$(PYTHON) scripts/run_file_reader.py

run-video:
	$(PYTHON) scripts/run_video.py

run-paper:
	$(PYTHON) scripts/run_paper.py

health:
	$(PYTHON) scripts/health_check.py
