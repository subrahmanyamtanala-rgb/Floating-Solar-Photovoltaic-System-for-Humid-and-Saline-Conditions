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
from fpv_analysis import studies, uncertainty  # noqa: E402

FIG = ROOT / "paper" / "figures"
GEN = ROOT / "paper" / "generated"
COL = 3.5  # IEEE single-column width, inches
DCOL = 7.16  # IEEE double-column width, inches
N_SEEDS = 20
N_MC = 1000
MC_SEED = 2024

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
    ax.legend(ncols=2, loc="lower center", bbox_to_anchor=(0.5, 1.0))
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
    ax.set_xlabel("Modelled degradation rate (%/yr)")
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


# --------------------------------------------------------------------------- review additions
def fig_uncertainty(mc, rc):
    fig, axes = plt.subplots(1, 2, figsize=(DCOL, 2.3), gridspec_kw={"width_ratios": [1, 1.25]})
    ax = axes[0]
    cols = [("fpv_fresh:d_lifetime_energy_mwh_pct", "FPV fresh", SERIES[1]),
            ("fpv_saline:d_lifetime_energy_mwh_pct", "FPV saline", SERIES[2]),
            ("fpv_saline_mitigated:d_lifetime_energy_mwh_pct", "FPV saline (M)", SERIES[3])]
    data = [mc[c] for c, _, _ in cols]
    parts = ax.violinplot(data, positions=range(3), showextrema=False, widths=0.8)
    for body, (_, _, col) in zip(parts["bodies"], cols):
        body.set_facecolor(col)
        body.set_edgecolor(INK_2)
        body.set_linewidth(0.5)
        body.set_alpha(0.85)
    for i, d in enumerate(data):
        lo, med, hi = np.percentile(d, [2.5, 50, 97.5])
        ax.vlines(i, lo, hi, color=INK, linewidth=0.8)
        ax.plot(i, med, "o", color="white", markeredgecolor=INK, markersize=3.5)
    ax.axhline(0, color=INK_2, linewidth=0.6)
    ax.set_xticks(range(3), [n for _, n, _ in cols])
    ax.set_ylabel("25-year energy vs land PV (%)")
    ax.grid(axis="x", visible=False)
    ax.set_title("(a)", loc="left", fontsize=8)

    ax = axes[1]
    top = rc.head(10)[::-1]
    labels = [uncertainty.PARAM_BY_NAME[n].label for n in top.index]
    colors = [SERIES[0] if v > 0 else SERIES[1] for v in top.values]
    ax.barh(range(len(top)), top.values, color=colors, height=0.6)
    ax.set_yticks(range(len(top)), labels, fontsize=6.5)
    ax.axvline(0, color=INK_2, linewidth=0.6)
    ax.set_xlabel("Spearman rank correlation with saline−land difference")
    ax.grid(axis="y", visible=False)
    ax.set_title("(b)", loc="left", fontsize=8)
    fig.tight_layout(pad=0.3, w_pad=1.2)
    save(fig, "uncertainty.pdf")


def fig_thresholds(salt, hum):
    fig, axes = plt.subplots(1, 2, figsize=(COL, 1.9))
    ax = axes[0]
    x = salt["salt_rate"] * 1000
    ax.plot(x, 100 * (salt["specific_yield_kwh_kwp"] / salt.attrs["land_yield"] - 1), color=SERIES[0],
            marker="o", markersize=2.5, label="Year-1 yield")
    ax.plot(x, 100 * (salt["lifetime_energy_mwh"] / salt.attrs["land_lifetime"] - 1), color=SERIES[1],
            marker="s", markersize=2.5, label="25-year energy")
    ax.axhline(0, color=INK_2, linewidth=0.6)
    ax.set_xlabel("Salt deposition (mg/m$^2$/day)", fontsize=7)
    ax.set_ylabel("FPV saline vs land (%)", fontsize=7)
    ax.legend(loc="lower left", fontsize=6)
    ax.set_title("(a)", loc="left", fontsize=8)
    ax = axes[1]
    ax.plot(hum["dewpoint_offset"], 100 * (hum["lifetime_energy_mwh"] / hum.attrs["land_lifetime"] - 1),
            color=SERIES[1], marker="s", markersize=2.5)
    ax.axhline(0, color=INK_2, linewidth=0.6)
    ax.set_xlabel("Dew-point rise $\\Delta T_d$ (K)", fontsize=7)
    ax.set_ylabel("FPV fresh 25-yr energy vs land (%)", fontsize=7)
    ax.set_title("(b)", loc="left", fontsize=8)
    fig.tight_layout(pad=0.3, w_pad=0.8)
    save(fig, "thresholds.pdf")


def _fmt(v, nd=2):
    return f"{v:,.{nd}f}".replace(",", "{,}").replace("-", "$-$")


def write_review_assets(weather, mc, rc, oat, salt, cl, hum, thr, dew, mit, be, wchk, fin):
    lines = ["% Auto-generated by paper/make_paper_assets.py (review additions) - do not edit by hand.", ""]

    def m(name, value):
        lines.append(f"\\newcommand{{\\{name}}}{{{value}}}")

    m("NMC", f"{N_MC:,}".replace(",", "{,}"))
    m("NParams", str(len(uncertainty.PARAMS)))
    # Monte Carlo summary table rows
    rows = [
        ("Year-1 yield, land (kWh/kWp)", "land:specific_yield_kwh_kwp", 0),
        ("Year-1 yield, FPV fresh (kWh/kWp)", "fpv_fresh:specific_yield_kwh_kwp", 0),
        ("Year-1 yield, FPV saline (kWh/kWp)", "fpv_saline:specific_yield_kwh_kwp", 0),
        ("Degradation, land (\\%/yr)", "land:deg_total_pct_yr", 2),
        ("Degradation, FPV fresh (\\%/yr)", "fpv_fresh:deg_total_pct_yr", 2),
        ("Degradation, FPV saline (\\%/yr)", "fpv_saline:deg_total_pct_yr", 2),
        ("Degradation, FPV saline (M) (\\%/yr)", "fpv_saline_mitigated:deg_total_pct_yr", 2),
        ("$\\Delta$ yield, fresh $-$ land (\\%)", "fpv_fresh:d_specific_yield_kwh_kwp_pct", 2),
        ("$\\Delta$ yield, saline $-$ land (\\%)", "fpv_saline:d_specific_yield_kwh_kwp_pct", 2),
        ("$\\Delta$ 25-yr energy, fresh $-$ land (\\%)", "fpv_fresh:d_lifetime_energy_mwh_pct", 2),
        ("$\\Delta$ 25-yr energy, saline $-$ land (\\%)", "fpv_saline:d_lifetime_energy_mwh_pct", 2),
        ("$\\Delta$ 25-yr energy, saline (M) $-$ land (\\%)", "fpv_saline_mitigated:d_lifetime_energy_mwh_pct", 2),
        ("LCOE, land (INR/kWh)", "land:lcoe_inr_kwh", 2),
        ("LCOE, FPV fresh (INR/kWh)", "fpv_fresh:lcoe_inr_kwh", 2),
        ("LCOE, FPV saline (INR/kWh)", "fpv_saline:lcoe_inr_kwh", 2),
    ]
    body = []
    for lab, col, nd in rows:
        lo, med, hi = np.percentile(mc[col], [2.5, 50, 97.5])
        pp = ""
        if ":d_" in col:
            pp = f"{100 * (mc[col] > 0).mean():.0f}"
        body.append(f"{lab} & {_fmt(med, nd)} & [{_fmt(lo, nd)}, {_fmt(hi, nd)}] & {pp} \\\\")
    (GEN / "table_mc.tex").write_text("\\newcommand{\\TabMC}{%\n" + "\n".join(body) + "}\n", encoding="utf-8")

    for tag, col in (("F", "fpv_fresh"), ("S", "fpv_saline"), ("SM", "fpv_saline_mitigated")):
        for kpi, nm in (("d_specific_yield_kwh_kwp_pct", "Yield"), ("d_lifetime_energy_mwh_pct", "Life")):
            d = mc[f"{col}:{kpi}"]
            lo, med, hi = np.percentile(d, [2.5, 50, 97.5])
            m(f"MC{nm}Med{tag}", _fmt(med, 1))
            m(f"MC{nm}Lo{tag}", _fmt(lo, 1))
            m(f"MC{nm}Hi{tag}", _fmt(hi, 1))
            m(f"MC{nm}Pos{tag}", f"{100 * (d > 0).mean():.0f}")
    for i, (name, val) in enumerate(rc.head(6).items()):
        m(f"RCName{'ABCDEF'[i]}", uncertainty.PARAM_BY_NAME[name].label.split(" (")[0])
        m(f"RCVal{'ABCDEF'[i]}", _fmt(val, 2))
    rcf = uncertainty.rank_correlation(mc, "fpv_fresh:d_lifetime_energy_mwh_pct")
    for i, (name, val) in enumerate(rcf.head(3).items()):
        m(f"RCFName{'ABC'[i]}", uncertainty.PARAM_BY_NAME[name].label.split(" (")[0])
        m(f"RCFVal{'ABC'[i]}", _fmt(val, 2))
    m("PLcoeF", f"{100 * (mc['fpv_fresh:lcoe_inr_kwh'] > mc['land:lcoe_inr_kwh']).mean():.1f}")
    m("PLcoeS", f"{100 * (mc['fpv_saline:lcoe_inr_kwh'] > mc['land:lcoe_inr_kwh']).mean():.1f}")
    # one-at-a-time swings
    o = oat.head(5)
    obody = [f"{r.label} & {uncertainty.PARAM_BY_NAME[r.param].low:g}--{uncertainty.PARAM_BY_NAME[r.param].high:g} "
             f"& {_fmt(r.low, 2)} & {_fmt(r.high, 2)} \\\\" for r in o.itertuples()]
    (GEN / "table_oat.tex").write_text("\\newcommand{\\TabOAT}{%\n" + "\n".join(obody) + "}\n", encoding="utf-8")
    m("OATBase", _fmt(oat["base"].iloc[0], 2))

    # thresholds
    m("ClStarText", "none in 0--400" if np.isnan(thr["chloride_star"]) else _fmt(thr["chloride_star"], 0))
    m("SaltStarYield", _fmt(1000 * thr["salt_star_yield"], 0))
    m("DTdStar", _fmt(thr["dtd_star"], 1))
    cl0 = cl[cl.chloride == 0].iloc[0]
    m("LifeSalineClZeroPct", _fmt(100 * (cl0["lifetime_energy_mwh"] / cl.attrs["land_lifetime"] - 1), 1))
    s0 = salt[salt.salt_rate == 0].iloc[0]
    m("LifeSalineSaltZeroPct", _fmt(100 * (s0["lifetime_energy_mwh"] / salt.attrs["land_lifetime"] - 1), 1))
    m("YieldSalineSaltZeroPct", _fmt(100 * (s0["specific_yield_kwh_kwp"] / salt.attrs["land_yield"] - 1), 1))
    clmax = cl[cl.chloride == cl.chloride.max()].iloc[0]
    m("DegSalineClMax", _fmt(clmax["deg_total_pct_yr"], 2))
    m("DegSalineClZero", _fmt(cl0["deg_total_pct_yr"], 2))
    m("ClMax", f"{cl.chloride.max():g}")
    m("TOWFreshAtStar", _fmt(np.interp(thr["dtd_star"], hum.dewpoint_offset, hum.time_of_wetness_h), 0))

    # dew sensitivity
    m("DewFreshMin", _fmt(dew["fresh_vs_land_pct"].min(), 2))
    m("DewFreshMax", _fmt(dew["fresh_vs_land_pct"].max(), 2))
    m("DewSalineMin", _fmt(dew["saline_vs_land_pct"].min(), 2))
    m("DewSalineMax", _fmt(dew["saline_vs_land_pct"].max(), 2))

    # mitigation table
    mb = [f"{r.option} & {_fmt(r.capex_per_wp, 1)} & {_fmt(r.deg_total_pct_yr, 2)} & {_fmt(r.lifetime_energy_mwh, 0)} "
          f"& {_fmt(r.recovery_pct, 1)} & {_fmt(r.vs_land_pct, 1)} & {_fmt(r.lcoe_inr_kwh, 2)} \\\\"
          for r in mit.itertuples()]
    (GEN / "table_mitigation.tex").write_text("\\newcommand{\\TabMitigation}{%\n" + "\n".join(mb) + "}\n", encoding="utf-8")
    m("MitGGvsLand", _fmt(mit.iloc[4]["vs_land_pct"], 1))
    m("MitAllvsLand", _fmt(mit.iloc[5]["vs_land_pct"], 1))
    m("MitPIDRec", _fmt(mit.iloc[1]["recovery_pct"], 1))
    m("MitSaltRec", _fmt(mit.iloc[2]["recovery_pct"], 1))
    m("MitBothRec", _fmt(mit.iloc[3]["recovery_pct"], 1))
    m("MitBothvsLand", _fmt(mit.iloc[3]["vs_land_pct"], 1))

    # economics
    m("CapexStarF", _fmt(be["fpv_fresh_capex_star"], 1))
    m("CapexStarS", _fmt(be["fpv_saline_capex_star"], 1))
    m("LandPremF", _fmt(be["fpv_fresh_land_premium_star"], 1))
    m("LandPremS", _fmt(be["fpv_saline_land_premium_star"], 1))
    m("WaterStar", _fmt(be["water_value_star"], 0))
    for w, v in be["lcoe_with_water"].items():
        m(f"LCOEWater{['Zero','Ten','Twenty','Forty','Eighty'][list(be['lcoe_with_water']).index(w)]}", _fmt(v, 2))

    # weather check table
    names = {"temp_mean": "Mean air temperature (\\si{\\celsius})", "temp_range": "Diurnal range (K)",
             "rh_mean": "Mean RH (\\%)", "wind_mean": "Mean wind speed (\\si{\\metre\\per\\second})",
             "rain_mm": "Rainfall (mm)$^{\\dagger}$"}
    wb = [f"{names[r.variable]} & {_fmt(r.ref_annual, 1)} & {_fmt(r.sim_annual, 1)} & {_fmt(r.mbe, 2)} "
          f"& {_fmt(r.rmse, 2)} & {r.r:.3f} \\\\" for r in wchk.itertuples()]
    (GEN / "table_weather.tex").write_text("\\newcommand{\\TabWeather}{%\n" + "\n".join(wb) + "}\n", encoding="utf-8")

    # finance sensitivity
    fb = []
    for r in fin.itertuples():
        lab = "Discount rate" if r.param == "discount" else "O\\&M escalation"
        fb.append(f"{lab} {100 * r.value:.0f}\\% & {_fmt(r.land, 2)} & {_fmt(r.fpv_fresh, 2)} & {_fmt(r.fpv_saline, 2)} "
                  f"& {_fmt(r.fresh_minus_land, 2)} & {_fmt(r.saline_minus_land, 2)} \\\\")
    (GEN / "table_finance.tex").write_text("\\newcommand{\\TabFinance}{%\n" + "\n".join(fb) + "}\n", encoding="utf-8")
    m("FinGapFMin", _fmt(fin.fresh_minus_land.min(), 2))
    m("FinGapFMax", _fmt(fin.fresh_minus_land.max(), 2))
    m("FinGapSMin", _fmt(fin.saline_minus_land.min(), 2))
    m("FinGapSMax", _fmt(fin.saline_minus_land.max(), 2))

    # Monte Carlo parameter table (appendix)
    bv = uncertainty.baseline_values()
    pb = []
    for p_ in uncertainty.PARAMS:
        dist = "log-U" if p_.log else "U"
        pb.append(f"{p_.label} & {bv[p_.name]:g} & {dist} & {p_.low:g} & {p_.high:g} & {p_.basis} \\\\")
    (GEN / "table_params.tex").write_text("\\newcommand{\\TabParams}{%\n" + "\n".join(pb) + "}\n", encoding="utf-8")

    (GEN / "numbers_review.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_parameters_json():
    """Machine-readable record of every scenario parameter and the Monte Carlo ranges."""
    import json
    from dataclasses import asdict

    base = default_scenarios()
    data = {
        "weather": {"generator": "fpv_analysis.climate.synthetic_weather", "baseline_seed": 42,
                    "ensemble_seeds": list(range(1, N_SEEDS + 1))},
        "scenarios": {s.key: asdict(s) for s in base + [with_mitigation(s) for s in base]},
        "monte_carlo": {"n": N_MC, "seed": MC_SEED,
                        "parameters": [asdict(p) for p in uncertainty.PARAMS]},
    }
    (GEN / "parameters.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


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

    # ---- peer-review additions
    mc = uncertainty.monte_carlo(weather, n=N_MC, seed=MC_SEED)
    mc.to_csv(GEN / "monte_carlo.csv", index=False, float_format="%.5g")
    rc = uncertainty.rank_correlation(mc, "fpv_saline:d_lifetime_energy_mwh_pct")
    oat = uncertainty.one_at_a_time(weather, "fpv_saline:d_lifetime_energy_mwh_pct")
    salt, cl, hum = studies.salt_sweep(weather), studies.chloride_sweep(weather), studies.humidity_sweep(weather)
    thr = studies.thresholds(cl, salt, hum)
    dew = studies.dew_sensitivity(weather)
    mit = studies.mitigation_matrix(weather)
    be = studies.break_even(weather)
    wchk = studies.weather_check(range(1, N_SEEDS + 1))
    for name, df in (("oat", oat), ("salt_sweep", salt), ("chloride_sweep", cl), ("humidity_sweep", hum),
                     ("dew_sensitivity", dew), ("mitigation", mit), ("weather_check", wchk)):
        df.to_csv(GEN / f"{name}.csv", index=False, float_format="%.5g")
    fig_uncertainty(mc, rc)
    fig_thresholds(salt, hum)
    fin = studies.finance_sensitivity(weather)
    fin.to_csv(GEN / "finance_sensitivity.csv", index=False, float_format="%.5g")
    write_review_assets(weather, mc, rc, oat, salt, cl, hum, thr, dew, mit, be, wchk, fin)
    write_parameters_json()
    print("assets written to", FIG, "and", GEN)


if __name__ == "__main__":
    main()
