#!/usr/bin/env bash
# Regenerate every result, table and figure of the study and the manuscript.
#   ./reproduce.sh            (about 3 minutes)
# Seeds: baseline weather 42, weather ensemble 1-20, Monte Carlo 2024 (see paper/generated/parameters.json).
set -euo pipefail
cd "$(dirname "$0")"

python3 -m pytest -q                       # unit and regression tests
python3 -m fpv_analysis --out results      # report, CSV tables, report figures
python3 paper/make_paper_assets.py         # paper numbers, tables, figures, Monte Carlo
cd paper
latexmk -pdf -interaction=nonstopmode main.tex
latexmk -pdf -interaction=nonstopmode response_to_reviewers_r2.tex   # round-1 letter is kept frozen as a PDF
echo "Done: paper/main.pdf, paper/response_to_reviewers_r2.pdf, results/REPORT.md"
