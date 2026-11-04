# Figure quality audit

Criteria: text >= 7 pt at print size (super/subscripts >= 5 pt); no stroke < 0.25 pt; vector or raster >= 300 dpi; fonts embedded, no Type 3; width <= text block.

## IEEE (paper/)

| Figure | Size (mm) | Scale | Min text (pt) | Min script (pt) | Min line (pt) | Raster | Fonts | Result |
|---|---|---|---|---|---|---|---|---|
| `paper/figures/climate.pdf` | 89 x 74 | 1.00 | 7.0 | 5.6 | 0.50 | vector | embedded | PASS |
| `paper/figures/module_temperature.pdf` | 89 x 61 | 1.00 | 7.0 | - | 0.50 | vector | embedded | PASS |
| `paper/figures/losses.pdf` | 89 x 79 | 1.00 | 7.0 | - | 0.30 | vector | embedded | PASS |
| `paper/figures/monthly_pr.pdf` | 89 x 56 | 1.00 | 7.0 | - | 0.50 | vector | embedded | PASS |
| `paper/figures/soiling.pdf` | 89 x 76 | 1.00 | 7.0 | - | 0.50 | vector | embedded | PASS |
| `paper/figures/degradation.pdf` | 89 x 69 | 1.00 | 7.0 | - | 0.50 | vector | embedded | PASS |
| `paper/figures/lifetime.pdf` | 89 x 58 | 1.00 | 7.0 | - | 0.50 | vector | embedded | PASS |
| `paper/figures/thresholds.pdf` | 89 x 58 | 1.00 | 7.0 | 5.6 | 0.50 | vector | embedded | PASS |
| `paper/figures/sensitivity.pdf` | 182 x 66 | 1.00 | 7.0 | - | 0.60 | vector | embedded | PASS |
| `paper/figures/ensemble.pdf` | 89 x 56 | 1.00 | 7.0 | - | 0.50 | vector | embedded | PASS |
| `paper/figures/uncertainty.pdf` | 182 x 69 | 1.00 | 7.0 | - | 0.30 | vector | embedded | PASS |
| `paper/figures/convergence.pdf` | 89 x 61 | 1.00 | 7.0 | - | 0.50 | vector | embedded | PASS |

Compiled manuscript `paper/main.pdf`: 46 fonts, all embedded, no Type 3.

## Elsevier SIMPAT (paper_simpat/)

| Figure | Size (mm) | Scale | Min text (pt) | Min script (pt) | Min line (pt) | Raster | Fonts | Result |
|---|---|---|---|---|---|---|---|---|
| `paper_simpat/figures/climate.pdf` | 90 x 74 | 1.00 | 7.0 | 5.6 | 0.50 | vector | embedded | PASS |
| `paper_simpat/figures/module_temperature.pdf` | 90 x 61 | 1.00 | 7.0 | - | 0.50 | vector | embedded | PASS |
| `paper_simpat/figures/degradation.pdf` | 90 x 69 | 1.00 | 7.0 | - | 0.50 | vector | embedded | PASS |
| `paper_simpat/figures/lifetime.pdf` | 90 x 58 | 1.00 | 7.0 | - | 0.50 | vector | embedded | PASS |
| `paper_simpat/figures/thresholds.pdf` | 90 x 58 | 1.00 | 7.0 | 5.6 | 0.50 | vector | embedded | PASS |
| `paper_simpat/figures/ensemble.pdf` | 90 x 56 | 1.00 | 7.0 | - | 0.50 | vector | embedded | PASS |
| `paper_simpat/figures/uncertainty.pdf` | 137 x 69 | 1.00 | 7.0 | - | 0.30 | vector | embedded | PASS |
| `paper_simpat/figures/convergence.pdf` | 90 x 61 | 1.00 | 7.0 | - | 0.50 | vector | embedded | PASS |
| `paper_simpat/figures/sobol.pdf` | 137 x 74 | 1.00 | 7.0 | - | 0.30 | vector | embedded | PASS |

Compiled manuscript `paper_simpat/main.pdf`: 50 fonts, all embedded, no Type 3.


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
`\scriptsize` (7 pt) in IEEEtran and `\footnotesize` (9 pt) in elsarticle.
