# Build the final report.
#
#   make            build main.pdf (pdflatex twice)
#   make data       rerun the rule's experiments against a live BuildSim, then redraw the charts
#   make compare    rerun the language-model comparison (about an hour; needs the endpoint), then redraw
#   make charts     redraw images/chart_*.png from experiments/results/results.json
#   make diagrams   re-render images/*.mmd to png and svg (needs the helper browser, see below)
#   make clean      remove LaTeX intermediates
#
# pdflatex exits non-zero because of the class's babel "swedish" warning, which
# is harmless here, so its exit code is ignored and the PDF is checked instead.
#
# The charts are PNGs drawn by firelab/experiments/plot_results.py with matplotlib;
# `make data` and `make charts` both refresh them, then `make` rebuilds the PDF.

PDFLATEX := pdflatex -interaction=nonstopmode
DOC      := main
PY       := ../.venv/bin/python
ROOT     := ../..

.PHONY: all data compare charts diagrams clean distclean

all: $(DOC).pdf
	@echo "==> $(DOC).pdf ready"

$(DOC).pdf: $(DOC).tex sections/*.tex images/*.png
	-$(PDFLATEX) $(DOC).tex > /dev/null
	-$(PDFLATEX) $(DOC).tex > /dev/null
	@rm -f $(DOC).aux $(DOC).log $(DOC).out $(DOC).toc $(DOC).bcf $(DOC).run.xml

data:
	cd $(ROOT) && firelab/.venv/bin/python -m firelab.experiments.run_experiments
	cd $(ROOT) && firelab/.venv/bin/python -m firelab.experiments.containment
	cd $(ROOT) && firelab/.venv/bin/python firelab/experiments/plot_results.py

compare:
	cd $(ROOT) && firelab/.venv/bin/python firelab/experiments/compare_detectors.py
	cd $(ROOT) && firelab/.venv/bin/python firelab/experiments/plot_results.py

charts:
	cd $(ROOT) && firelab/.venv/bin/python firelab/experiments/plot_results.py


# Mermaid: serve images/ on :8765, start a headless Chrome with remote debugging on
# :9333, then run the render script. The Chrome command is in images/render.mjs.
diagrams:
	cd images && node render.mjs

clean:
	rm -f $(DOC).aux $(DOC).log $(DOC).out $(DOC).toc $(DOC).bcf $(DOC).run.xml

distclean: clean
	rm -f $(DOC).pdf
