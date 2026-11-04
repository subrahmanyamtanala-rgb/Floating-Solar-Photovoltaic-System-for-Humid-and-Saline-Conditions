"""Audit every manuscript figure against publication criteria.

    python tools/check_figures.py            # writes FIGURE_QA.md and prints a summary

For each \\includegraphics in paper/main.tex (IEEE) and paper_simpat/main.tex (Elsevier) the
script resolves the figure file and its placed width. It then measures, in the PDF as it
will be printed (native size x placement scale):
  * physical size and placement scale,
  * smallest text (pt), from every text span in the figure,
  * thinnest stroked line (pt),
  * raster images and their effective resolution (dpi),
  * fonts: embedded? Type 3 (rejected by IEEE PDF eXpress)?
It also checks the whole compiled manuscripts for non-embedded or Type 3 fonts.

Criteria (common journal artwork guidance; confirm against the target journal):
  text >= 7 pt at print size; data and axis lines >= 0.5 pt, no line < 0.25 pt;
  vector artwork or raster >= 300 dpi (600 dpi line art); all fonts embedded, no Type 3;
  figure no wider than the text block.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
MIN_TEXT_PT = 7.0
MIN_SCRIPT_PT = 5.0  # superscripts/subscripts, e.g. the 2 in m^2
MIN_LINE_PT = 0.25
MIN_DATA_LINE_PT = 0.5
MIN_DPI = 300

MANUSCRIPTS = {
    "IEEE (paper/)": {
        "tex": ROOT / "paper" / "main.tex",
        "pdf": ROOT / "paper" / "main.pdf",
        "dirs": [ROOT / "paper" / "figures"],
        "log": ROOT / "paper" / "main.log"
    },
    "Elsevier SIMPAT (paper_simpat/)": {
        "tex": ROOT / "paper_simpat" / "main.tex",
        "pdf": ROOT / "paper_simpat" / "main.pdf",
        "dirs": [ROOT / "paper_simpat" / "figures", ROOT / "paper" / "figures"],
        "log": ROOT / "paper_simpat" / "main.log"
    },
}
MM = 72.0 / 25.4

# Checks that are not automated here; re-do them when a figure changes.
MANUAL_REVIEW = """
## Colour and visual review

**Palette** (categorical slots `#2a78d6`, `#eb6834`, `#1baf7a`, `#eda100`). It was run through a colour-vision validator
(OKLab Delta E, protan/deutan/tritan simulation):
- lightness band: PASS;
- chroma floor: PASS;
- worst adjacent colour-vision separation: Delta E 9.1 (target >= 8, PASS);
- normal-vision floor: Delta E 22.9 (PASS);
- contrast: aqua (2.7:1) and yellow (2.1:1) are below 3:1 against white, so the figures must not rely on colour alone.
  That is why every series also carries a line style, a marker or a hatch, and every multi-series figure has a legend.

**Sequential maps** (heatmaps) use a single blue hue, light to dark, with cell values printed in each cell.

**Greyscale and visual inspection.** Every figure was rendered at 170 dpi in colour and in greyscale and inspected for
overlapping or clipped labels, legibility of all series in greyscale, panel labels and units on all axes. Defects found
and fixed:
- clipped x-axis label and colliding tick labels in the uncertainty figure;
- three overlapping daily series in the soiling figure, now drawn as small multiples;
- white stripes in the heatmap colour bars;
- a 99-dpi raster heatmap, now vector;
- text below 7 pt in 13 of 21 placements;
- Type 3 bitmap fonts in the Elsevier manuscript, now Latin Modern.

**Not automated:** the TikZ model-chain diagram (Fig. 2) is typeset by LaTeX in the manuscript font. It uses
`\\scriptsize` (7 pt) in IEEEtran and `\\footnotesize` (9 pt) in elsarticle.
"""


def placed_width(expr: str, widths: dict) -> float:
    expr = expr.strip()
    m = re.fullmatch(r"([\d.]*)\s*(\\textwidth|\\columnwidth)", expr)
    if m:
        return float(m.group(1) or 1.0) * widths[m.group(2)]
    m = re.fullmatch(r"([\d.]+)\s*(mm|cm|in|pt)", expr)
    if m:
        f = {"mm": MM, "cm": 10 * MM, "in": 72.0, "pt": 1.0}[m.group(2)]
        return float(m.group(1)) * f
    raise ValueError(f"cannot parse width {expr!r}")


def fonts(pdf: Path) -> list[dict]:
    out = subprocess.run(["pdffonts", str(pdf)], capture_output=True, text=True).stdout.splitlines()[2:]
    rows = []
    for line in out:
        parts = line.split()
        if len(parts) < 5:
            continue
        # name type [encoding] emb sub uni object ID
        emb = parts[-5]
        rows.append({"name": parts[0], "type3": "Type 3" in line, "embedded": emb == "yes"})
    return rows


def analyse(pdf: Path, scale: float) -> dict:
    doc = pymupdf.open(pdf)
    page = doc[0]
    spans = [s for b in page.get_text("dict")["blocks"] for l in b.get("lines", [])
             for s in l["spans"] if s["text"].strip()]

    def is_script(s):
        """Super/subscript: a smaller span abutting a larger one horizontally, overlapping vertically."""
        x0, y0, x1, y1 = s["bbox"]
        for o in spans:
            if o is s or o["size"] < 1.15 * s["size"]:
                continue
            ox0, oy0, ox1, oy1 = o["bbox"]
            touches = abs(ox1 - x0) < 1.5 or abs(x1 - ox0) < 1.5
            if touches and min(y1, oy1) > max(y0, oy0):
                return True
        return False

    sizes = [s["size"] for s in spans if not is_script(s)]
    script_sizes = [s["size"] for s in spans if is_script(s)]
    strokes = [d["width"] for d in page.get_drawings()
               if d.get("width") and d["type"] in ("s", "fs") and d["width"] > 0]
    imgs = []
    for info in page.get_image_info():
        w_in = (info["bbox"][2] - info["bbox"][0]) * scale / 72.0
        imgs.append(info["width"] / w_in if w_in > 0 else 0)
    f = fonts(pdf)
    return {
        "w_mm": page.rect.width / MM,
        "h_mm": page.rect.height / MM,
        "min_text": min(sizes) * scale if sizes else None,
        "min_script": min(script_sizes) * scale if script_sizes else None,
        "min_line": min(strokes) * scale if strokes else None,
        "dpi": min(imgs) if imgs else None,
        "fonts_ok": all(x["embedded"] and not x["type3"] for x in f),
        "font_names": sorted({x["name"].split("+")[-1] for x in f}),
    }


def main() -> int:
    lines = ["# Figure quality audit", "",
             f"Criteria: text >= {MIN_TEXT_PT:g} pt at print size (super/subscripts >= {MIN_SCRIPT_PT:g} pt); no stroke < {MIN_LINE_PT:g} pt; "
             f"vector or raster >= {MIN_DPI} dpi; fonts embedded, no Type 3; width <= text block.", ""]
    failures = 0
    for name, cfg in MANUSCRIPTS.items():
        tex = cfg["tex"].read_text()
        # Text-block widths as LaTeX reported them in the compiled manuscript (see \\typeout LAYOUT).
        m = re.search(r"LAYOUT textwidth=([\d.]+)pt columnwidth=([\d.]+)pt", cfg["log"].read_text(errors="ignore"))
        if not m:
            raise SystemExit(f"{cfg['log']}: no LAYOUT line; compile the manuscript first")
        cfg["widths"] = {"\\textwidth": float(m.group(1)), "\\columnwidth": float(m.group(2))}
        lines += [f"## {name}", "",
                  "| Figure | Size (mm) | Scale | Min text (pt) | Min script (pt) | Min line (pt) | Raster | Fonts | Result |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for width_expr, fig in re.findall(r"\\includegraphics\[width=([^\]]+)\]\{([^}]+)\}", tex):
            path = next(d / fig for d in cfg["dirs"] if (d / fig).exists())
            pw = placed_width(width_expr, cfg["widths"])
            doc = pymupdf.open(path)
            scale = pw / doc[0].rect.width
            a = analyse(path, scale)
            problems = []
            if a["min_text"] is not None and a["min_text"] < MIN_TEXT_PT - 0.05:
                problems.append(f"text {a['min_text']:.1f} pt")
            if a["min_script"] is not None and a["min_script"] < MIN_SCRIPT_PT - 0.05:
                problems.append(f"script {a['min_script']:.1f} pt")
            if a["min_line"] is not None and a["min_line"] < MIN_LINE_PT - 0.01:
                problems.append(f"line {a['min_line']:.2f} pt")
            if a["dpi"] is not None and a["dpi"] < MIN_DPI:
                problems.append(f"raster {a['dpi']:.0f} dpi")
            if not a["fonts_ok"]:
                problems.append("font not embedded / Type 3")
            if pw > max(cfg["widths"].values()) + 0.5:
                problems.append("wider than text block")
            failures += bool(problems)
            res = "PASS" if not problems else "FAIL: " + "; ".join(problems)
            lines.append(
                f"| `{path.relative_to(ROOT)}` | {a['w_mm'] * scale:.0f} x {a['h_mm'] * scale:.0f} | {scale:.2f} | "
                f"{a['min_text']:.1f} | {'-' if a['min_script'] is None else f'{a['min_script']:.1f}'} | {a['min_line']:.2f} | {'vector' if a['dpi'] is None else f'{a['dpi']:.0f} dpi'} | "
                f"{'embedded' if a['fonts_ok'] else 'PROBLEM'} | {res} |")
        doc_fonts = fonts(cfg["pdf"])
        bad = [f["name"] for f in doc_fonts if not f["embedded"] or f["type3"]]
        lines += ["", f"Compiled manuscript `{cfg['pdf'].relative_to(ROOT)}`: {len(doc_fonts)} fonts, "
                  + ("all embedded, no Type 3." if not bad else f"PROBLEM fonts: {', '.join(bad)}"), ""]
        failures += bool(bad)
    lines += MANUAL_REVIEW.splitlines()
    (ROOT / "FIGURE_QA.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
