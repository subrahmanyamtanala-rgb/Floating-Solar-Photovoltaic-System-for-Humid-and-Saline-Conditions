"""Command-line entry point: ``python -m fpv_analysis``."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from . import plots
from .climate import load_weather_csv, synthetic_weather
from .config import Site, default_scenarios, with_mitigation
from .report import write_report
from .sensitivity import humidity_salinity_grid
from .simulation import run_all


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--weather", help="hourly weather CSV (default: synthetic Visakhapatnam year)")
    ap.add_argument("--out", default="results", help="output directory")
    ap.add_argument("--seed", type=int, default=42, help="seed for the synthetic weather")
    ap.add_argument("--no-sensitivity", action="store_true", help="skip the humidity x salinity sweep")
    args = ap.parse_args(argv)

    t0 = time.time()
    site = Site()
    weather = load_weather_csv(args.weather) if args.weather else synthetic_weather(site, seed=args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    base = default_scenarios()
    scenarios = base + [with_mitigation(s) for s in base]
    results = run_all(weather, scenarios, site)

    summary = pd.DataFrame([r.kpis for r in results]).set_index("scenario")
    summary.to_csv(out / "summary.csv", float_format="%.4f")
    monthly = pd.concat({r.scenario.key: r.monthly for r in results[: len(base)]}, names=["scenario", "month"])
    monthly.to_csv(out / "monthly.csv", float_format="%.4f")
    lifetime = pd.DataFrame({r.scenario.key: r.lifetime_kwh / 1000.0 for r in results})
    lifetime.index = lifetime.index + 1
    lifetime.index.name = "year"
    lifetime.to_csv(out / "lifetime_energy_mwh.csv", float_format="%.3f")

    if args.no_sensitivity:
        grid = humidity_salinity_grid(weather, base[2], dewpoint_offsets=(1.5,), salinity=(1.0,), site=site)
    else:
        grid = humidity_salinity_grid(weather, base[2], site=site)
    grid.to_csv(out / "sensitivity_fpv_saline.csv", index=False, float_format="%.4f")

    figs = plots.all_figures(weather, results, grid, out / "figures")
    write_report(out / "REPORT.md", site, weather, results, grid, figs, weather_source=args.weather or "synthetic")
    print(f"Wrote {out / 'REPORT.md'}, {len(figs)} figures and CSV tables in {time.time() - t0:.1f}s")
    print(summary[["energy_mwh", "performance_ratio", "temp_module_daytime_mean", "deg_total_pct_yr",
                   "lifetime_energy_mwh", "lcoe_inr_kwh"]].round(3).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
