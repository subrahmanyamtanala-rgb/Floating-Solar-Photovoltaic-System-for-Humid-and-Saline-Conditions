# Submission package: Simulation Modelling Practice and Theory (Elsevier)

| File | Purpose |
|---|---|
| `main.tex` / `main.pdf` | Manuscript (elsarticle, `preprint,11pt`, line numbers, numbered references `elsarticle-num`) |
| `highlights.txt` | Highlights as a separate file (5 bullets, each ≤ 85 characters) |
| `cover_letter.tex` / `cover_letter.pdf` | Cover letter to the Editor |
| `references.bib` | Bibliography |
| `make_simpat_assets.py` | Journal-specific analyses: pvlib code-to-code verification, Sobol indices, runtime |
| `generated/`, `figures/` | Outputs of `make_simpat_assets.py`; the shared numbers and figures come from `../paper/` |

Rebuild: `./reproduce.sh` from the repository root.

## What changed compared with the IEEE version (`../paper/`)

The SIMPAT version is reframed for a simulation-methodology readership and adds three analyses:

1. **Code-to-code verification** of every established sub-model against pvlib (`generated/verification.csv`).
2. **Sobol variance decomposition** (Saltelli sampling, N = 512, 15,360 parameter vectors × 4 scenarios) using SALib.
3. **Computational cost** of one scenario-year and of the uncertainty experiments.

It also adds:
- a V&V section structured after Sargent (2013);
- an experimental-design table;
- an algorithm block for one scenario evaluation;
- Elsevier declarations (CRediT, competing interests, funding, data availability, generative AI).

## Check against the live Guide for Authors before submitting

The journal's web pages could not be reached from the environment where this package was prepared. The items below
follow common Elsevier practice and **must be confirmed** against the current Guide for Authors:

- [ ] Article type and any length limit; the current PDF is 32 pages in single column with 1.5 spacing.
- [ ] Abstract word limit; the abstract has about 185 words.
- [ ] Number of keywords; there are 6.
- [ ] Highlights: 3–5 bullets, ≤ 85 characters each including spaces.
- [ ] Graphical abstract: required or optional. None is provided yet; Fig. 1 (the model chain) is a candidate.
- [ ] Reference style: numbered (`elsarticle-num`) is used. Switch to `elsarticle-harv` if author–year is required.
- [ ] Exact wording and placement of the generative-AI declaration.
- [ ] Whether a data-availability statement and a CRediT statement are required at submission.
- [ ] Line numbers and double spacing for review. The `review` option was replaced by `preprint` + 1.5 spacing because
      the double-spaced title page overflowed; restore `review` if double spacing is mandatory.

## Author actions

- [ ] Confirm the author name, affiliation, CRediT roles and funding statement.
- [ ] Do not submit while the IEEE version of this work is under review elsewhere: dual submission is not permitted.
- [ ] Review the generative-AI declaration. It must describe the actual use, and the author is responsible for all
      content. Check that the journal accepts the extent of AI assistance described.
- [ ] Complete volume, pages and DOI for references that list only author, title, venue and year.
- [ ] Make the GitHub repository public, or archive it on Zenodo for a DOI, before submission.
- [ ] Prepare suggested reviewers if the submission system asks for them (none are proposed here).
