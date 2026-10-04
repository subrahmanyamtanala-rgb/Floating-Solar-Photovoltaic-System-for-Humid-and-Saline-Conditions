"""Build every number, table and figure used in the IEEE manuscript.

Run from the repository root:

    python paper/make_paper_assets.py

Outputs go to ``paper/figures`` (vector PDF) and ``paper/generated``
(LaTeX macros in ``numbers.tex``).  The manuscript never hard-codes a
result: re-running this script after a model change updates the paper.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fpv_analysis import default_scenarios, run_scenario, synthetic_weather, with_mitigation  # noqa: E402
from fpv_analysis.plots import GRID, INK, INK_2, NEUTRAL, SEQ_BLUE, SERIES, MONTHS  # noqa: E402
from fpv_analysis.sensitivity import humidity_salinity_grid  # noqa: E402

FIG = ROOT / "paper" / "figures"
GEN = ROOT / "paper" / "generated"
COL = 3.5  # IEEE single-column width, inches
DCOL = 7.16  # IEEE double-column width, inches
N_SEEDS = 20

NAMES = {"land": "Land PV", "fpv_fresh": "FPV freshwater", "fpv_saline": "FPV saline"}


def style():
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["STIXGeneral", "Times New Roman", "DejaVu Serif"],
            "mathtext.fontset": "stix",
            "font.size": 8,
            "axes.labelsize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "axes.edgecolor": INK_2,
            "axes.linewidth": 0.6,
            "axes.labelcolor": INK,
            "xtick.color": INK,
            "ytick.color": INK,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": GRID,
            "grid.linewidth": 0.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.frameon": False,
            "lines.linewidth": 1.4,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
            "pdf.fonttype": 42,
        }
    )


def save(fig, name):
    fig.savefig(FIG / name, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


# --------------------------------------------------------------------------- figures
def fig_climate(w):
    m = pd.DataFrame(
        {
            "ghi": w["ghi"].resample("MS").sum() / 1000.0 / w["ghi"].resample("MS").sum().index.days_in_month,
            "temp": w["temp_air"].resample("MS").mean(),
            "rh": w["rh"].resample("MS").mean(),
            "rain": w["precip"].resample("MS").sum(),
        }
    )
    fig, axes = plt.subplots(2, 2, figsize=(COL, 2.6), sharex=True)
    x = np.arange(12)
    specs = [("ghi", "GHI (kWh/m$^2$/day)"), ("temp", "Air temperature ($^\\circ$C)"),
             ("rh", "Relative humidity (%)"), ("rain", "Rainfall (mm)")]
    for ax, (c, lab), tag in zip(axes.flat, specs, "abcd"):
        if c == "rain":
            ax.bar(x, m[c], color=SERIES[0], width=0.7)
        else:
            ax.plot(x, m[c], color=SERIES[0], marker="o", markersize=2.5)
        ax.set_ylabel(lab, fontsize=7)
        ax.set_xticks(x[::2], [MONTHS[i][0] + MONTHS[i][1:3] for i in range(0, 12, 2)])
        ax.text(0.02, 0.97, f"({tag})", transform=ax.transAxes, va="top", fontsize=7)
    fig.tight_layout(pad=0.3, h_pad=0.4, w_pad=0.6)
    save(fig, "climate.pdf")


def fig_temperature(res):
    fig, ax = plt.subplots(figsize=(COL, 2.2))
    for i, k in enumerate(NAMES):
        h = res[k].hourly[res[k].hourly.index.month == 5]
        p = h.groupby(h.index.hour)["temp_module"].mean()
        ax.plot(p.index, p.values, color=SERIES[i], label=NAMES[k])
    air = h.groupby(h.index.hour)["temp_air"].mean()
    ax.plot(air.index, air.values, color=NEUTRAL, linestyle="--", linewidth=1.1, label="Ambient air (land)")
    ax.set_xlim(0, 23)
    ax.set_xticks(range(0, 24, 3))
    ax.set_xlabel("Hour of day (IST)")
    ax.set_ylabel("Module temperature ($^\\circ$C)")
    ax.legend(loc="upper left")
    save(fig, "module_temperature.pdf")


def fig_losses(res):
    names = list(res["land"].losses.keys())
    short = ["IAM", "Spectral", "Soiling", "Dew", "Temperature", "DC (wiring, mismatch,\nmotion, LID)",
             "Inverter + clipping", "Availability"]
    fig, ax = plt.subplots(figsize=(COL, 2.9))
    y = np.arange(len(names))
    hgt = 0.26
    for i, k in enumerate(NAMES):
        ax.barh(y + (i - 1) * hgt, [res[k].losses[n] for n in names], height=hgt * 0.92, color=SERIES[i],
                label=NAMES[k])
    ax.set_yticks(y, short)
    ax.invert_yaxis()
    ax.axvline(0, color=INK_2, linewidth=0.6)
    ax.set_xlabel("Loss (% of preceding stage; negative = gain)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right")
    save(fig, "losses.pdf")


def fig_soiling(res):
    fig, ax = plt.subplots(figsize=(COL, 1.9))
    for i, k in enumerate(NAMES):
        d = res[k].hourly["soiling_ratio"].resample("D").mean()
        ax.plot(d.index, 100 * d.values, color=SERIES[i], linewidth=1.0, label=NAMES[k])
    ax.set_ylabel("Soiling ratio (%)")
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b"))
    ax.legend(ncols=3, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    save(fig, "soiling.pdf")


def fig_monthly_pr(res):
    fig, ax = plt.subplots(figsize=(COL, 2.0))
    x = np.arange(12)
    for i, k in enumerate(NAMES):
        ax.plot(x, res[k].monthly["performance_ratio"].to_numpy(), color=SERIES[i], marker="o", markersize=2.5,
                label=NAMES[k])
    ax.set_xticks(x, [m[:1] for m in MONTHS])
    ax.set_ylabel("Performance ratio")
    ax.legend(ncols=3, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    save(fig, "monthly_pr.pdf")


def fig_degradation(res):
    keys = ["land", "fpv_fresh", "fpv_saline", "land_mitigated", "fpv_fresh_mitigated", "fpv_saline_mitigated"]
    labels = ["Land", "FPV fresh", "FPV saline", "Land (M)", "FPV fresh (M)", "FPV saline (M)"]
    mech = [("deg_base_pct_yr", "Intrinsic"), ("deg_temp_humidity_pct_yr", "Temperature–humidity"),
            ("deg_pid_pct_yr", "PID"), ("deg_corrosion_pct_yr", "Chloride corrosion")]
    fig, ax = plt.subplots(figsize=(COL, 2.4))
    y = np.arange(len(keys))
    left = np.zeros(len(keys))
    for i, (c, n) in enumerate(mech):
        v = np.array([res[k].kpis[c] for k in keys])
        ax.barh(y, v, left=left, color=SERIES[i], height=0.62, label=n, edgecolor="white", linewidth=1.0)
        left += v
    for yi, t in zip(y, left):
        ax.text(t + 0.02, yi, f"{t:.2f}", va="center", fontsize=7)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, left.max() * 1.15)
    ax.set_xlabel("Degradation rate (%/yr)")
    ax.grid(axis="y", visible=False)
    ax.legend(ncols=2, loc="lower center", bbox_to_anchor=(0.45, 1.0))
    save(fig, "degradation.pdf")


def fig_lifetime(res):
    fig, ax = plt.subplots(figsize=(COL, 2.1))
    for i, k in enumerate(NAMES):
        yrs = np.arange(1, 26)
        ax.plot(yrs, res[k].lifetime_kwh / 1e3, color=SERIES[i], label=NAMES[k])
        ax.plot(yrs, res[k + "_mitigated"].lifetime_kwh / 1e3, color=SERIES[i], linestyle=":",
                linewidth=1.1)
    ax.plot([], [], color=NEUTRAL, linestyle=":", linewidth=1.1, label="Mitigated modules")
    ax.set_xlabel("Year of operation")
    ax.set_ylabel("Annual energy (MWh/MWp)")
    ax.set_xlim(1, 25)
    ax.legend(loc="lower left")
    save(fig, "lifetime.pdf")


def fig_sensitivity(grid):
    fig, axes = plt.subplots(1, 2, figsize=(DCOL, 2.3))
    for ax, (col, lab, fmt), tag in zip(
        axes,
        [("deg_total_pct_yr", "Degradation rate (%/yr)", ".2f"),
         ("lifetime_energy_mwh", "25-year energy (MWh/MWp)", ".0f")],
        "ab",
    ):
        piv = grid.pivot(index="dewpoint_offset", columns="salinity", values=col).sort_index(ascending=False)
        cmap = SEQ_BLUE if col == "deg_total_pct_yr" else SEQ_BLUE.reversed()
        im = ax.imshow(piv.values, cmap=cmap, aspect="auto")
        ax.grid(False)
        ax.set_xticks(range(piv.shape[1]), [f"{c:g}$\\times$" for c in piv.columns])
        ax.set_yticks(range(piv.shape[0]), [f"+{i:g}" for i in piv.index])
        ax.set_xlabel("Salt/chloride deposition (multiple of baseline)")
        ax.set_ylabel("Dew-point rise over water (K)")
        lo, hi = np.nanmin(piv.values), np.nanmax(piv.values)
        for (r, c), v in np.ndenumerate(piv.values):
            frac = (v - lo) / (hi - lo + 1e-12)
            dark = frac > 0.45 if col == "deg_total_pct_yr" else frac < 0.55
            ax.text(c, r, format(v, fmt), ha="center", va="center", fontsize=6.5, color="white" if dark else INK)
        cb = fig.colorbar(im, ax=ax, shrink=0.9, pad=0.02)
        cb.outline.set_visible(False)
        cb.ax.tick_params(labelsize=6.5)
        cb.set_label(lab, fontsize=7)
        ax.set_title(f"({tag})", loc="left", fontsize=8)
    fig.tight_layout(pad=0.3, w_pad=1.5)
    save(fig, "sensitivity.pdf")


def fig_ensemble(ens):
    fig, axes = plt.subplots(1, 2, figsize=(COL, 1.9))
    for ax, (col, lab) in zip(axes, [("specific_yield_kwh_kwp", "Year-1 yield vs land (%)"),
                                     ("lifetime_energy_mwh", "25-year energy vs land (%)")]):
        piv = ens.pivot(index="seed", columns="scenario", values=col)
        for i, k in enumerate(["fpv_fresh", "fpv_saline"]):
            d = 100 * (piv[k] / piv["land"] - 1)
            ax.boxplot(d, positions=[i], widths=0.5, patch_artist=True, showfliers=True,
                       boxprops=dict(facecolor=SERIES[i + 1], edgecolor=INK_2, linewidth=0.6),
                       medianprops=dict(color=INK, linewidth=0.9), whiskerprops=dict(linewidth=0.6),
                       capprops=dict(linewidth=0.6), flierprops=dict(markersize=2))
        ax.axhline(0, color=INK_2, linewidth=0.6)
        ax.set_xticks([0, 1], ["FPV\nfresh", "FPV\nsaline"])
        ax.set_ylabel(lab, fontsize=7)
        ax.grid(axis="x", visible=False)
    fig.tight_layout(pad=0.3, w_pad=0.8)
    save(fig, "ensemble.pdf")


# --------------------------------------------------------------------------- numbers
def _macro_name(s: str) -> str:
    out = "".join(ch for ch in s.title() if ch.isalpha())
    return out


def write_numbers(res, grid, ens, weather):
    lines = ["% Auto-generated by paper/make_paper_assets.py - do not edit by hand.", ""]

    def m(name, value):
        lines.append(f"\\newcommand{{\\{name}}}{{{value}}}")

    tags = {"land": "L", "fpv_fresh": "F", "fpv_saline": "S", "land_mitigated": "LM",
            "fpv_fresh_mitigated": "FM", "fpv_saline_mitigated": "SM"}
    fields = {
        "specific_yield_kwh_kwp": ("Yield", "{:.0f}"),
        "performance_ratio": ("PR", "{:.3f}"),
        "cuf_dc_pct": ("CUF", "{:.2f}"),
        "poa_kwh_m2": ("POA", "{:.0f}"),
        "temp_module_daytime_mean": ("Tday", "{:.1f}"),
        "temp_module_max": ("Tmax", "{:.1f}"),
        "temp_module_minus_air_daytime": ("Trise", "{:.1f}"),
        "rh_mean": ("RH", "{:.1f}"),
        "dew_hours": ("Dew", "{:,.0f}"),
        "soiling_ratio_mean": ("SR", "{:.3f}"),
        "deg_base_pct_yr": ("DegBase", "{:.2f}"),
        "deg_temp_humidity_pct_yr": ("DegTH", "{:.2f}"),
        "deg_pid_pct_yr": ("DegPID", "{:.2f}"),
        "deg_corrosion_pct_yr": ("DegCorr", "{:.2f}"),
        "deg_total_pct_yr": ("DegTot", "{:.2f}"),
        "time_of_wetness_h": ("TOW", "{:,.0f}"),
        "mean_encapsulant_rh": ("RHenc", "{:.1f}"),
        "lifetime_energy_mwh": ("Life", "{:,.0f}"),
        "year25_capacity_pct": ("Cap", "{:.1f}"),
        "lcoe_inr_kwh": ("LCOE", "{:.2f}"),
    }
    for key, t in tags.items():
        k = res[key].kpis
        for f, (n, fmt) in fields.items():
            m(f"{n}{t}", fmt.format(k[f]).replace(",", "{,}"))
        for loss, v in res[key].losses.items():
            m(f"Loss{_macro_name(loss.split('(')[0])}{t}", f"{v:.2f}")

    L, F, S = (res[k].kpis for k in ("land", "fpv_fresh", "fpv_saline"))
    SM = res["fpv_saline_mitigated"].kpis
    m("GainYieldF", f"{100 * (F['energy_mwh'] / L['energy_mwh'] - 1):.1f}")
    m("GainYieldS", f"{100 * (S['energy_mwh'] / L['energy_mwh'] - 1):.1f}")
    m("GainLifeF", f"{100 * (F['lifetime_energy_mwh'] / L['lifetime_energy_mwh'] - 1):.1f}")
    m("GainLifeS", f"{100 * (S['lifetime_energy_mwh'] / L['lifetime_energy_mwh'] - 1):.1f}")
    m("GainLifeSM", f"{100 * (SM['lifetime_energy_mwh'] / S['lifetime_energy_mwh'] - 1):.1f}")
    m("dTdayF", f"{L['temp_module_daytime_mean'] - F['temp_module_daytime_mean']:.1f}")
    m("dTmaxF", f"{L['temp_module_max'] - F['temp_module_max']:.1f}")
    m("WaterSaved", f"{F['water_saved_m3_yr']:,.0f}".replace(",", "{,}"))
    m("GHI", f"{weather['ghi'].sum() / 1000:,.0f}".replace(",", "{,}"))
    m("Tair", f"{weather['temp_air'].mean():.1f}")
    m("RHair", f"{weather['rh'].mean():.1f}")
    m("Rain", f"{weather['precip'].sum():,.0f}".replace(",", "{,}"))

    # sensitivity
    piv = grid.pivot(index="dewpoint_offset", columns="salinity", values="lifetime_energy_mwh")
    dpiv = grid.pivot(index="dewpoint_offset", columns="salinity", values="deg_total_pct_yr")
    m("SensLifeMin", f"{grid['lifetime_energy_mwh'].min():,.0f}".replace(",", "{,}"))
    m("SensLifeMax", f"{grid['lifetime_energy_mwh'].max():,.0f}".replace(",", "{,}"))
    m("SensDegMin", f"{grid['deg_total_pct_yr'].min():.2f}")
    m("SensDegMax", f"{grid['deg_total_pct_yr'].max():.2f}")
    m("SensSaltSpan", f"{(piv.max(axis=1) - piv.min(axis=1)).mean():,.0f}".replace(",", "{,}"))
    m("SensMoistSpan", f"{(piv.max(axis=0) - piv.min(axis=0)).mean():,.0f}".replace(",", "{,}"))
    m("SensDegPerK", f"{np.polyfit(dpiv.index, dpiv[1.0], 1)[0]:.3f}")
    m("SensTOWZero", f"{grid.loc[grid.dewpoint_offset == 0, 'time_of_wetness_h'].iloc[0]:,.0f}".replace(",", "{,}"))
    m("SensTOWMax", f"{grid['time_of_wetness_h'].max():,.0f}".replace(",", "{,}"))
    m("SensYieldLoPct", f"{100 * (1 - grid.loc[grid.salinity == 2.0, 'specific_yield_kwh_kwp'].mean() / grid.loc[grid.salinity == 0.25, 'specific_yield_kwh_kwp'].mean()):.1f}")
    # break-even: lifetime energy of saline FPV equals land
    sal1 = grid[grid.dewpoint_offset == 1.5].set_index("salinity")["lifetime_energy_mwh"]
    if L["lifetime_energy_mwh"] > sal1.max():
        m("BreakEvenSalinity", f"$<${sal1.index.min():g}")
    else:
        be = np.interp(L["lifetime_energy_mwh"], sal1.values[::-1], sal1.index.values[::-1])
        m("BreakEvenSalinity", f"{be:.2f}")

    # ensemble
    piv_e = {c: ens.pivot(index="seed", columns="scenario", values=c)
             for c in ("specific_yield_kwh_kwp", "lifetime_energy_mwh", "deg_total_pct_yr", "temp_module_daytime_mean")}
    m("NSeeds", str(N_SEEDS))
    for t, k in (("F", "fpv_fresh"), ("S", "fpv_saline")):
        dy = 100 * (piv_e["specific_yield_kwh_kwp"][k] / piv_e["specific_yield_kwh_kwp"]["land"] - 1)
        dl = 100 * (piv_e["lifetime_energy_mwh"][k] / piv_e["lifetime_energy_mwh"]["land"] - 1)
        dd = piv_e["deg_total_pct_yr"][k] - piv_e["deg_total_pct_yr"]["land"]
        m(f"EnsYield{t}", f"{dy.mean():.2f}")
        m(f"EnsYieldSd{t}", f"{dy.std(ddof=1):.2f}")
        m(f"EnsLife{t}", f"{dl.mean():.2f}")
        m(f"EnsLifeSd{t}", f"{dl.std(ddof=1):.2f}")
        m(f"EnsDeg{t}", f"{dd.mean():+.3f}")
        m(f"EnsDegSd{t}", f"{dd.std(ddof=1):.3f}")
    yl = piv_e["specific_yield_kwh_kwp"]["land"]
    m("EnsYieldLandMin", f"{yl.min():,.0f}".replace(",", "{,}"))
    m("EnsYieldLandMax", f"{yl.max():,.0f}".replace(",", "{,}"))
    dfy = piv_e["specific_yield_kwh_kwp"]["fpv_fresh"] - yl
    m("EnsFreshWins", str(int((dfy > 0).sum())))

    (GEN / "numbers.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    GEN.mkdir(parents=True, exist_ok=True)
    style()

    weather = synthetic_weather(seed=42)
    base = default_scenarios()
    scen = base + [with_mitigation(s) for s in base]
    res = {s.key: run_scenario(weather, s) for s in scen}
    grid = humidity_salinity_grid(weather, base[2])

    rows = []
    for seed in range(1, N_SEEDS + 1):
        w = synthetic_weather(seed=seed)
        for s in base:
            k = run_scenario(w, s).kpis
            rows.append({"seed": seed, "scenario": s.key, **{c: k[c] for c in (
                "specific_yield_kwh_kwp", "lifetime_energy_mwh", "deg_total_pct_yr", "temp_module_daytime_mean")}})
    ens = pd.DataFrame(rows)
    ens.to_csv(GEN / "ensemble.csv", index=False, float_format="%.4f")

    fig_climate(weather)
    fig_temperature(res)
    fig_losses(res)
    fig_soiling(res)
    fig_monthly_pr(res)
    fig_degradation(res)
    fig_lifetime(res)
    fig_sensitivity(grid)
    fig_ensemble(ens)
    write_numbers(res, grid, ens, weather)
    print("assets written to", FIG, "and", GEN)


if __name__ == "__main__":
    main()
