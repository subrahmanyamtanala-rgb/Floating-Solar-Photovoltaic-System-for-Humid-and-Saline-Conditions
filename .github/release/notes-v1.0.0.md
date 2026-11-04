First public release of **fpv_analysis**, an open simulation framework for the lifetime performance of floating
photovoltaic (FPV) systems in hot, humid and saline environments. It also includes the manuscripts built from it.

## Highlights
- **Coupled model:** one over-water microclimate drives module temperature, dew, dust and sea-salt soiling, and four
  module-degradation mechanisms: temperature–humidity, salt-assisted PID, chloride corrosion and intrinsic ageing.
  These feed 25-year energy and LCOE.
- **Verified:** the established sub-models agree with pvlib to within 3×10⁻¹².
- **Uncertainty:** a weather ensemble, a 28-parameter Monte Carlo checked for convergence to 5,000 samples, and Sobol
  indices.
- **Reproducible:** `./reproduce.sh` regenerates every number, table and figure. Package versions are pinned in
  `requirements-lock.txt`.

## Key results (Visakhapatnam, India; model-based scenario predictions)
| 25-year energy vs. land PV | Baseline | Monte Carlo median (95 % interval) |
|---|---|---|
| Freshwater FPV | +2.1 % | +1.5 % (−3.6 % to +6.3 %) |
| Saline FPV | −4.3 % | −5.1 % (−11.5 % to +0.7 %) |

The freshwater benefit is conditional on the floats' thermal performance and on the humidity increase over the water.
The saline penalty holds across most of the plausible parameter space.

## Attached files
- `manuscript-ieee.pdf`: IEEE Transactions version
- `manuscript-simpat.pdf`: Simulation Modelling Practice and Theory version
- `cover-letter-simpat.pdf`, `response-to-reviewers-r1/r2/r3.pdf`
- `FIGURE_QA.md`: figure audit report

## Quick start
```bash
pip install -r requirements.txt
python -m fpv_analysis          # simulation report in results/
python -m pytest -q             # 24 tests
./reproduce.sh                  # everything, including the manuscripts (needs TeX Live)
```

Licensed under MIT. See `CITATION.cff` for how to cite.
