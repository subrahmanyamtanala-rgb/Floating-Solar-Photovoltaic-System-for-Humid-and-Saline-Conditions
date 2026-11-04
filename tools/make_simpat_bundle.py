"""Build the submission bundle for Simulation Modelling Practice and Theory (Elsevier).

    python tools/make_simpat_bundle.py

Run after ./reproduce.sh (or at least after paper_simpat/main.pdf and cover_letter.pdf are built).
Produces submission/SIMPAT_submission_bundle/ and submission/SIMPAT_submission_bundle.zip:

  01_manuscript.pdf                       compiled manuscript (line-numbered preprint)
  02_cover_letter.pdf
  03_highlights.docx / .txt               separate editable highlights file
  04_declaration_of_competing_interest.docx / .txt
  05_figures/Fig01_model_chain.pdf ...    one vector file per figure, numbered in order of appearance
  06_latex_source/                        self-contained source: flat main.tex, references.bib, main.bbl,
                                          figure files; compiles with pdflatex + bibtex (elsarticle class)
  README_SUBMISSION.txt                   which file goes into which upload slot, and final checks

The LaTeX source is verified by compiling it in an empty temporary directory.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "paper_simpat"
OUT = ROOT / "submission" / "SIMPAT_submission_bundle"

FIG_ORDER = [  # (file in paper_simpat/figures, name in bundle), in order of appearance after Fig. 1
    ("climate.pdf", "Fig02_climate.pdf"),
    ("module_temperature.pdf", "Fig03_module_temperature.pdf"),
    ("degradation.pdf", "Fig04_degradation.pdf"),
    ("lifetime.pdf", "Fig05_lifetime_energy.pdf"),
    ("thresholds.pdf", "Fig06_thresholds.pdf"),
    ("ensemble.pdf", "Fig07_weather_ensemble.pdf"),
    ("uncertainty.pdf", "Fig08_parameter_uncertainty.pdf"),
    ("convergence.pdf", "Fig09_convergence.pdf"),
    ("sobol.pdf", "Fig10_sobol.pdf"),
]

HIGHLIGHTS = [
    "Coupled hourly simulation links FPV cooling, humidity, salt soiling, PID, corrosion",
    "Sub-models agree with pvlib to 3e-12; Monte Carlo statistics converge at 1,000 runs",
    "Freshwater FPV lifetime gain is conditional: positive in 75% of parameter samples",
    "Saline FPV shows a lifetime energy penalty across most of the parameter space",
    "Sobol indices rank float heat loss, land dust and salt deposition as key drivers",
]

COMPETING = ("The author declares that there are no known competing financial interests or personal "
             "relationships that could have appeared to influence the work reported in this paper.")


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def flatten_tex() -> str:
    """main.tex with every \\input of generated macros inlined and figure names replaced."""
    tex = (SRC / "main.tex").read_text()

    def inline(m):
        path = (SRC / m.group(1)).resolve()
        body = path.read_text().rstrip("\n")
        return f"%% ---- inlined from {path.relative_to(ROOT)} ----\n{body}\n%% ---- end ----"

    tex = re.sub(r"\\input\{([^}]+\.tex)\}", lambda m: inline(m), tex)
    for src, dst in FIG_ORDER:
        tex = tex.replace("{" + src + "}", "{" + dst + "}")
    tex = tex.replace("\\graphicspath{{figures/}}", "\\graphicspath{{figures/}}")
    # remove the build-diagnostics line (not part of the paper)
    tex = re.sub(r"\\typeout\{LAYOUT[^\n]*\n", "", tex)
    assert "\\input{" not in tex, "unresolved \\input"
    return tex


def tikz_figure(tex: str, workdir: Path) -> Path:
    """Compile Fig. 1 (TikZ model chain) as a standalone vector PDF."""
    m = re.search(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", tex, flags=re.S)
    doc = (
        "\\documentclass[11pt,border=2pt]{standalone}\n\\usepackage[T1]{fontenc}\n\\usepackage{lmodern}\n"
        "\\usepackage{amsmath,amssymb}\n\\usepackage{tikz}\n\\usetikzlibrary{arrows.meta,positioning}\n"
        "\\newcommand{\\RHs}{\\mathit{RH}_{\\mathrm{s}}}\n\\begin{document}\n" + m.group(0) + "\n\\end{document}\n"
    )
    (workdir / "fig01.tex").write_text(doc)
    r = run(["pdflatex", "-interaction=nonstopmode", "fig01.tex"], workdir)
    if r.returncode != 0:
        raise SystemExit("Fig. 1 standalone build failed:\n" + r.stdout[-2000:])
    return workdir / "fig01.pdf"


def write_docx(path: Path, title: str, paragraphs: list[str], bullets: bool = False):
    import docx

    d = docx.Document()
    d.add_heading(title, level=1)
    for p in paragraphs:
        d.add_paragraph(p, style="List Bullet" if bullets else None)
    d.save(path)


def verify_latex(src_dir: Path) -> int:
    """Compile the bundled source in an empty directory; return the page count."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        shutil.copytree(src_dir, tmp / "src")
        d = tmp / "src"
        for cmd in (["pdflatex", "-interaction=nonstopmode", "main.tex"], ["bibtex", "main"],
                    ["pdflatex", "-interaction=nonstopmode", "main.tex"],
                    ["pdflatex", "-interaction=nonstopmode", "main.tex"]):
            r = run(cmd, d)
        log = (d / "main.log").read_text(errors="ignore")
        if r.returncode != 0 or "undefined" in re.sub(r"\n", " ", "\n".join(
                l for l in log.splitlines() if "Warning" in l and "undefined" in l)):
            raise SystemExit("Bundled LaTeX source does not compile cleanly:\n" + log[-3000:])
        info = run(["pdfinfo", "main.pdf"], d).stdout
        return int(re.search(r"Pages:\s+(\d+)", info).group(1))


def main():
    for f in ("main.pdf", "cover_letter.pdf", "main.bbl"):
        if not (SRC / f).exists():
            raise SystemExit(f"paper_simpat/{f} missing - build the manuscript first (./reproduce.sh)")
    if OUT.exists():
        shutil.rmtree(OUT)
    figs = OUT / "05_figures"
    latex = OUT / "06_latex_source"
    for d in (figs, latex / "figures"):
        d.mkdir(parents=True)

    shutil.copy(SRC / "main.pdf", OUT / "01_manuscript.pdf")
    shutil.copy(SRC / "cover_letter.pdf", OUT / "02_cover_letter.pdf")

    (OUT / "03_highlights.txt").write_text("Highlights\n\n" + "\n".join(f"- {h}" for h in HIGHLIGHTS) + "\n")
    write_docx(OUT / "03_highlights.docx", "Highlights", HIGHLIGHTS, bullets=True)
    (OUT / "04_declaration_of_competing_interest.txt").write_text(
        "Declaration of competing interest\n\n" + COMPETING + "\n")
    write_docx(OUT / "04_declaration_of_competing_interest.docx", "Declaration of competing interest", [COMPETING])

    tex = flatten_tex()
    with tempfile.TemporaryDirectory() as tmp:
        fig1 = tikz_figure(tex, Path(tmp))
        shutil.copy(fig1, figs / "Fig01_model_chain.pdf")
    for src, dst in FIG_ORDER:
        shutil.copy(SRC / "figures" / src, figs / dst)
        shutil.copy(SRC / "figures" / src, latex / "figures" / dst)

    (latex / "main.tex").write_text(tex)
    shutil.copy(SRC / "references.bib", latex / "references.bib")
    shutil.copy(SRC / "main.bbl", latex / "main.bbl")
    pages = verify_latex(latex)

    for h in HIGHLIGHTS:
        assert len(h) <= 85, h
    readme = f"""SUBMISSION BUNDLE - Simulation Modelling Practice and Theory (Elsevier)
Manuscript: "Verified coupled simulation and uncertainty analysis of floating photovoltaic lifetime
performance in humid and saline environments" - Subrahmanyam Tanala (ANITS)

UPLOAD MAP (Elsevier Editorial Manager; item names may differ slightly)
  Manuscript (PDF for review) ..... 01_manuscript.pdf ({pages} pages, line numbers)
  LaTeX source files .............. everything in 06_latex_source/ (main.tex, references.bib, main.bbl,
                                    figures/*.pdf). Upload as individual files if no zip is accepted.
  Cover letter .................... 02_cover_letter.pdf
  Highlights ...................... 03_highlights.docx (editable; .txt copy included). 5 bullets, each <= 85 characters.
  Declaration of interest ......... 04_declaration_of_competing_interest.docx. Elsevier may ask you to create
                                    this with its online declaration tool instead; use the same text.
  Figures ......................... 05_figures/Fig01 ... Fig10 (vector PDF, one per figure, in order of
                                    appearance; text >= 7 pt at print size, fonts embedded; see FIGURE_QA.md).
  Graphical abstract .............. NOT INCLUDED. Optional for most Elsevier journals; if required,
                                    Fig01_model_chain.pdf is the natural starting point.

ALREADY INSIDE THE MANUSCRIPT
  Abstract (~185 words), 6 keywords, highlights, CRediT authorship statement, declaration of competing
  interest, funding statement, data availability (GitHub + Zenodo DOI 10.5281/zenodo.23949684),
  declaration of generative AI use, appendix with all Monte Carlo parameters.

CHECK BEFORE PRESSING SUBMIT (the Guide for Authors could not be read from the build environment)
  [ ] Article type, length, abstract and keyword limits in the current Guide for Authors.
  [ ] Whether double spacing is required for review (bundle uses 1.5 spacing with line numbers).
  [ ] Reference style (numbered, elsarticle-num) - switch to elsarticle-harv if author-year is required.
  [ ] Author name, affiliation, ORCID, CRediT roles, funding statement.
  [ ] Generative-AI declaration describes your actual use and is acceptable to the journal.
  [ ] The same work is NOT under review elsewhere (e.g. the IEEE version) - no dual submission.
  [ ] GitHub repository is public; Zenodo record metadata matches the paper.
  [ ] Suggested reviewers (not provided).
  [ ] Volume/pages/DOI completed for references that list only author, title, venue and year.

The LaTeX source in 06_latex_source/ was verified to compile in an empty directory with
pdflatex + bibtex using the elsarticle class (TeX Live).
"""
    (OUT / "README_SUBMISSION.txt").write_text(readme)
    shutil.copy(ROOT / "FIGURE_QA.md", OUT / "FIGURE_QA.md")

    zpath = OUT.with_suffix(".zip")
    if zpath.exists():
        zpath.unlink()
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(OUT.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(OUT.parent))
    print(f"Bundle: {zpath.relative_to(ROOT)} ({zpath.stat().st_size / 1e6:.1f} MB); LaTeX source verified, {pages} pages")


if __name__ == "__main__":
    main()
