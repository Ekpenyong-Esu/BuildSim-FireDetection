PORT ?= 8090
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
UVICORN := $(VENV)/bin/uvicorn

.PHONY: help deps ui build run dev stop test clean

help:
	@echo "make deps   - create .venv and install Python dependencies"
	@echo "make ui     - install and build the Svelte UI into ui/dist"
	@echo "make build  - deps + ui"
	@echo "make run    - serve the API and the built UI on :$(PORT)"
	@echo "make dev    - API on :$(PORT) with reload, Vite dev server separately"
	@echo "make stop   - stop a detached server started with nohup or &"
	@echo "make test   - run the domain, layering and preset tests"
	@echo "make clean  - remove build artefacts"

$(VENV)/.stamp: requirements.txt
	@if command -v uv >/dev/null 2>&1; then \
		uv venv --allow-existing $(VENV) && VIRTUAL_ENV=$(VENV) uv pip install -r requirements.txt; \
	else \
		python3 -m venv $(VENV) && $(PIP) install --quiet --upgrade pip && \
		$(PIP) install --quiet -r requirements.txt; \
	fi
	@touch $@

deps: $(VENV)/.stamp

ui:
	cd ui && npm install && npm run build

build: deps ui

run: deps
	$(UVICORN) firelab.app.main:app --app-dir .. --host 127.0.0.1 --port $(PORT) \
		--timeout-graceful-shutdown 3

dev: deps
	$(UVICORN) firelab.app.main:app --app-dir .. --host 127.0.0.1 --port $(PORT) \
		--timeout-graceful-shutdown 3 --reload

# For servers with no terminal to interrupt. The bracket stops pkill matching its
# own command line, and pkill returns 1 when nothing matched, which make would treat
# as a failure.
stop:
	@pkill -f "[u]vicorn firelab.app.main" && echo "firelab stopped" || echo "firelab was not running"

test: deps
	$(PY) -m pytest tests -q

clean:
	rm -rf $(VENV) ui/dist ui/node_modules
	find . -name __pycache__ -type d -exec rm -rf {} +
