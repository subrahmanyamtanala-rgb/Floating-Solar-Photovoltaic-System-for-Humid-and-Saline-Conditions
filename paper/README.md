# Manuscript: IEEE Transactions format

`main.tex` (revised after peer review) is written with the official `IEEEtran` journal class and formatted for *IEEE Transactions on
Sustainable Energy*. `main.pdf` is the compiled manuscript.

Every result in the paper is a LaTeX macro defined in `generated/numbers.tex`. Every figure in `figures/` is a vector
PDF. Both are produced by one script, so the paper stays consistent with the model:

```bash
# from the repository root
python paper/make_paper_assets.py      # simulations, 20-seed ensemble, sensitivity grid, figures, numbers.tex
cd paper && latexmk -pdf main.tex      # needs TeX Live with IEEEtran, siunitx, tikz, xurl
# or simply: ./reproduce.sh  (tests, report, paper assets, manuscript and response letter)
```

| File | Content |
|---|---|
| `main.tex` | Manuscript |
| `references.bib` | Bibliography (IEEEtran.bst) |
| `response_to_reviewers_r3.tex` | Point-by-point reply to the third review (uses the same generated numbers) |
| `response_to_reviewers_r1.pdf`, `_r2.pdf` | Replies to the first and second reviews, frozen as submitted |
| `make_paper_assets.py` | Builds `figures/*.pdf`, `generated/*.tex` (numbers and table rows), the Monte Carlo, the threshold and mitigation studies, and `generated/parameters.json` |

Check before submission: the author list and affiliation, the target journal in `\markboth`, the biography, and the
bibliographic details of each reference against the original sources. The 19 references added in the revision
(e.g. `ajmal2025`, `lindholm2021`, `hacke2015`) list first author, title, venue and year only: add volume, pages and
DOI from the publisher pages before submission.
