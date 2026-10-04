# Manuscript: IEEE Transactions format

`main.tex` is written with the official `IEEEtran` journal class and formatted for *IEEE Transactions on
Sustainable Energy*. `main.pdf` is the compiled manuscript.

Every result in the paper is a LaTeX macro defined in `generated/numbers.tex`. Every figure in `figures/` is a vector
PDF. Both are produced by one script, so the paper stays consistent with the model:

```bash
# from the repository root
python paper/make_paper_assets.py      # simulations, 20-seed ensemble, sensitivity grid, figures, numbers.tex
cd paper && latexmk -pdf main.tex      # needs TeX Live with IEEEtran, siunitx, tikz, xurl
```

| File | Content |
|---|---|
| `main.tex` | Manuscript |
| `references.bib` | Bibliography (IEEEtran.bst) |
| `make_paper_assets.py` | Builds `figures/*.pdf`, `generated/numbers.tex`, `generated/ensemble.csv` |

Check before submission: the author list and affiliation, the target journal in `\markboth`, the biography, and the
bibliographic details of each reference against the original sources.
