.PHONY: install build test lint fmt clean

VENV := .venv
PYTHON := $(VENV)/bin/python

$(VENV):
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"

install: $(VENV)

build:
	$(PYTHON) -c "import h3_harness; print('build: OK')"

test:
	$(PYTHON) -m pytest -x --tb=short -q

test-full:
	$(PYTHON) -m pytest -x -v

lint:
	$(PYTHON) -m ruff check src/ tests/

fmt:
	$(PYTHON) -m ruff format src/ tests/

clean:
	rm -rf $(VENV) __pycache__ src/h3_harness/__pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

all: install lint build test
