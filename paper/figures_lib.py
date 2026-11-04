"""Publication figures, rendered at exact print size for each target journal.

Each figure is drawn with matplotlib's constrained layout at the physical width at which the
manuscript places it, and saved without bounding-box cropping, so the placement scale is 1 and
the font sizes in the code are the printed sizes. The rules applied to every figure are:

* text >= 7 pt (tick labels, legends, cell annotations); axis labels and panel labels 8 pt;
* vector output only (heatmaps use pcolormesh, not a raster image);
* colour is never the only cue: series also differ by line style, marker or hatch, so the
  figures survive grayscale print and colour-vision deficiency;
* multi-panel figures carry (a), (b), ... panel labels.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from fpv_analysis.plots import GRID, INK, INK_2, MONTHS, NEUTRAL, SEQ_BLUE, SERIES  # noqa: E402

MM = 1 / 25.4
NAMES = {"land": "Land PV", "fpv_fresh": "FPV freshwater", "fpv_saline": "FPV saline"}
LS = ["-", "--", "-."]  # line style per plant (redundant with colour)
MK = ["o", "s", "^"]  # marker per plant
HATCH = ["", "////", "...."]  # bar hatch per plant
MECH_HATCH = ["", "////", "\\\\\\\\", "...."]  # stacked degradation mechanisms


PLAIN = {
    "th_ref": "Peck reference rate", "pid_ref": "PID reference rate", "corr_ref": "Corrosion reference rate",
    "dew_loss": "Dew optical loss", "k_dust": "Dust loss coefficient", "k_salt": "Salt loss coefficient",
    "cementation": "Deliquescence cementation", "u0_land": "Land heat loss U0", "u1_land": "Land heat loss U1",
    "dust_land": "Land dust deposition", "cl_land": "Land chloride deposition", "u0_fpv": "FPV heat loss U0",
    "u1_fpv": "FPV heat loss U1", "wind_fpv": "Over-water wind factor", "motion": "Wave-motion mismatch",
    "alpha_fresh": "Air–water coupling (fresh)", "dtd_fresh": "Dew-point rise (fresh)",
    "alpha_saline": "Air–water coupling (saline)", "dtd_saline": "Dew-point rise (saline)",
    "salt_saline": "Saline salt deposition", "cl_saline": "Saline chloride deposition",
    "mu_pid": "PID mitigation factor", "mu_salt": "Salt-mist mitigation factor", "capex_land": "Land CAPEX",
    "capex_fresh": "FPV fresh CAPEX", "capex_saline": "FPV saline CAPEX", "discount": "Discount rate",
    "escalation": "O&M escalation",
}


def plain_label(name: str) -> str:
    """Plain-text parameter name for 7-pt tick labels (no sub/superscripts)."""
    return PLAIN[name]


@dataclass(frozen=True)
class Target:
    name: str
    out: Path
    col: float  # inches, single-column figure width
    wide: float  # inches, wide figure width


def ieee(out: Path) -> Target:
    return Target("ieee", out, 3.5, 7.16)  # IEEEtran \columnwidth and \textwidth


def elsevier(out: Path) -> Target:
    # Elsevier single-column artwork width (90 mm) and a 126 mm wide figure, which fits the
    # elsarticle preprint 11 pt text block (360 pt = 126.5 mm) at scale 1.
    return Target("elsevier", out, 90 * MM, 126 * MM)


def style():
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["STIXGeneral", "Times New Roman", "DejaVu Serif"],
        "mathtext.fontset": "stix",
        "font.size": 8,
        "axes.labelsize": 8,
        "axes.titlesize": 8,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "legend.fontsize": 7,
        "legend.frameon": False,
        "legend.handlelength": 2.2,
        "axes.edgecolor": INK_2,
        "axes.linewidth": 0.6,
        "axes.labelcolor": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "lines.linewidth": 1.3,
        "lines.markersize": 3.5,
        "hatch.linewidth": 0.5,
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
        "pdf.fonttype": 42,  # embedded TrueType, never Type 3
        "figure.constrained_layout.h_pad": 0.02,
        "figure.constrained_layout.w_pad": 0.02,
    })


def figure(width, height, *args, **kw):
    return plt.subplots(*args, figsize=(width, height), layout="constrained", **kw)


def save(fig, t: Target, name: str):
    t.out.mkdir(parents=True, exist_ok=True)
    fig.savefig(t.out / name, metadata={"CreationDate": None, "ModDate": None})
    plt.close(fig)


def panel(ax, tag, text=""):
    ax.set_title(f"({tag}) {text}".rstrip(), loc="left", fontsize=8)


def legend_above(ax, ncols, **kw):
    return ax.legend(ncols=ncols, loc="lower center", bbox_to_anchor=(0.5, 1.0), borderaxespad=0.2, **kw)


# --------------------------------------------------------------------------- figures
def fig_climate(t, w):
    m = pd.DataFrame({
        "ghi": w["ghi"].resample("MS").sum() / 1000.0 / w["ghi"].resample("MS").sum().index.days_in_month,
        "temp": w["temp_air"].resample("MS").mean(),
        "rh": w["rh"].resample("MS").mean(),
        "rain": w["precip"].resample("MS").sum(),
    })
    fig, axes = figure(t.col, 2.9, 2, 2, sharex=True)
    x = np.arange(12)
    specs = [("ghi", "Daily GHI (kWh/m$^2$)"), ("temp", "Air temperature (°C)"),
             ("rh", "Relative humidity (%)"), ("rain", "Rainfall (mm/month)")]
    for ax, (c, lab), tag in zip(axes.flat, specs, "abcd"):
        if c == "rain":
            ax.bar(x, m[c], color=SERIES[0], width=0.7)
        else:
            ax.plot(x, m[c], color=SERIES[0], marker="o")
        panel(ax, tag, lab)
        ax.set_xticks(x[::2], [MONTHS[i] for i in range(0, 12, 2)])
    save(fig, t, "climate.pdf")


def fig_temperature(t, res):
    fig, ax = figure(t.col, 2.4)
    for i, k in enumerate(NAMES):
        h = res[k].hourly[res[k].hourly.index.month == 5]
        p = h.groupby(h.index.hour)["temp_module"].mean()
        ax.plot(p.index, p.values, color=SERIES[i], linestyle=LS[i], marker=MK[i], markevery=3, label=NAMES[k])
    air = h.groupby(h.index.hour)["temp_air"].mean()
    ax.plot(air.index, air.values, color=NEUTRAL, linestyle=":", linewidth=1.2, label="Ambient air (land)")
    ax.set_xlim(0, 23)
    ax.set_xticks(range(0, 24, 3))
    ax.set_xlabel("Hour of day (IST)")
    ax.set_ylabel("Module temperature (°C)")
    legend_above(ax, 2)
    save(fig, t, "module_temperature.pdf")


def fig_losses(t, res):
    names = list(res["land"].losses.keys())
    short = ["IAM", "Spectral", "Soiling", "Dew", "Temperature", "DC (wiring, mismatch,\nmotion, LID)",
             "Inverter + clipping", "Availability"]
    fig, ax = figure(t.col, 3.1)
    y = np.arange(len(names))
    hgt = 0.26
    for i, k in enumerate(NAMES):
        ax.barh(y + (i - 1) * hgt, [res[k].losses[n] for n in names], height=hgt * 0.92, color=SERIES[i],
                hatch=HATCH[i], edgecolor="white", linewidth=0.3, label=NAMES[k])
    ax.set_yticks(y, short)
    ax.invert_yaxis()
    ax.axvline(0, color=INK_2, linewidth=0.6)
    ax.set_xlabel("Loss (% of preceding stage; negative = gain)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right")
    save(fig, t, "losses.pdf")


def fig_soiling(t, res):
    # Small multiples: the three daily series overlap too much to share one axis.
    fig, axes = figure(t.col, 3.0, 3, 1, sharex=True, sharey=True)
    for i, (ax, k) in enumerate(zip(axes, NAMES)):
        d = res[k].hourly["soiling_ratio"].resample("D").mean()
        ax.plot(d.index, 100 * d.values, color=SERIES[i], linewidth=0.9)
        ax.text(0.01, 0.06, f"({'abc'[i]}) {NAMES[k]}", transform=ax.transAxes, fontsize=8, va="bottom",
                bbox=dict(facecolor="white", edgecolor="none", pad=1.0))
    axes[1].set_ylabel("Soiling ratio (%)")
    axes[-1].xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b"))
    save(fig, t, "soiling.pdf")


def fig_monthly_pr(t, res):
    fig, ax = figure(t.col, 2.2)
    x = np.arange(12)
    for i, k in enumerate(NAMES):
        ax.plot(x, res[k].monthly["performance_ratio"].to_numpy(), color=SERIES[i], linestyle=LS[i],
                marker=MK[i], label=NAMES[k])
    ax.set_xticks(x, [m[:1] for m in MONTHS])
    ax.set_xlabel("Month")
    ax.set_ylabel("Performance ratio")
    legend_above(ax, 3)
    save(fig, t, "monthly_pr.pdf")


def fig_degradation(t, res):
    keys = ["land", "fpv_fresh", "fpv_saline", "land_mitigated", "fpv_fresh_mitigated", "fpv_saline_mitigated"]
    labels = ["Land", "FPV fresh", "FPV saline", "Land (M)", "FPV fresh (M)", "FPV saline (M)"]
    mech = [("deg_base_pct_yr", "Intrinsic"), ("deg_temp_humidity_pct_yr", "Temperature–humidity"),
            ("deg_pid_pct_yr", "PID"), ("deg_corrosion_pct_yr", "Chloride corrosion")]
    fig, ax = figure(t.col, 2.7)
    y = np.arange(len(keys))
    left = np.zeros(len(keys))
    for i, (c, n) in enumerate(mech):
        v = np.array([res[k].kpis[c] for k in keys])
        ax.barh(y, v, left=left, color=SERIES[i], hatch=MECH_HATCH[i], height=0.62, label=n,
                edgecolor="white", linewidth=0.8)
        left += v
    for yi, tot in zip(y, left):
        ax.text(tot + 0.02, yi, f"{tot:.2f}", va="center", fontsize=7)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, left.max() * 1.17)
    ax.set_xlabel("Modelled degradation rate (%/yr)")
    ax.grid(axis="y", visible=False)
    legend_above(ax, 2)
    save(fig, t, "degradation.pdf")


def fig_lifetime(t, res):
    fig, ax = figure(t.col, 2.3)
    yrs = np.arange(1, 26)
    for i, k in enumerate(NAMES):
        ax.plot(yrs, res[k].lifetime_kwh / 1e3, color=SERIES[i], marker=MK[i], markevery=4, label=NAMES[k])
        ax.plot(yrs, res[k + "_mitigated"].lifetime_kwh / 1e3, color=SERIES[i], linestyle=":", linewidth=1.1,
                marker=MK[i], markevery=(2, 4), markerfacecolor="white")
    ax.plot([], [], color=NEUTRAL, linestyle=":", linewidth=1.1, marker="o", markerfacecolor="white",
            label="Mitigated modules (M)")
    ax.set_xlabel("Year of operation")
    ax.set_ylabel("Annual energy (MWh/MWp)")
    ax.set_xlim(1, 25)
    ax.legend(loc="lower left")
    save(fig, t, "lifetime.pdf")


def _heat(ax, fig, piv, cmap, fmt, cbar_label, dark_when):
    vals = piv.values
    ny, nx = vals.shape
    mesh = ax.pcolormesh(np.arange(nx + 1) - 0.5, np.arange(ny + 1) - 0.5, vals, cmap=cmap,
                         edgecolors="white", linewidth=0.6)
    ax.set_xlim(-0.5, nx - 0.5)
    ax.set_ylim(ny - 0.5, -0.5)
    ax.grid(False)
    lo, hi = np.nanmin(vals), np.nanmax(vals)
    for (r, c), v in np.ndenumerate(vals):
        frac = (v - lo) / (hi - lo + 1e-12)
        ax.text(c, r, format(v, fmt), ha="center", va="center", fontsize=7,
                color="white" if dark_when(frac) else INK)
    cb = fig.colorbar(mesh, ax=ax, shrink=0.95, pad=0.02)
    cb.solids.set_rasterized(False)  # keep the colour bar vector
    cb.solids.set_edgecolor("face")  # no cell gridlines inside the colour bar
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=7, width=0.6)
    cb.set_label(cbar_label, fontsize=8)


def fig_sensitivity(t, grid):
    fig, axes = figure(t.wide, 2.6, 1, 2)
    for ax, (col, lab, fmt), tag in zip(
        axes,
        [("deg_total_pct_yr", "Degradation rate (%/yr)", ".2f"),
         ("lifetime_energy_mwh", "25-year energy (MWh/MWp)", ".0f")],
        "ab",
    ):
        piv = grid.pivot(index="dewpoint_offset", columns="salinity", values=col).sort_index(ascending=False)
        if col == "deg_total_pct_yr":
            _heat(ax, fig, piv, SEQ_BLUE, fmt, lab, lambda f: f > 0.45)
        else:
            _heat(ax, fig, piv, SEQ_BLUE.reversed(), fmt, lab, lambda f: f < 0.55)
        ax.set_xticks(range(piv.shape[1]), [f"{c:g}$\\times$" for c in piv.columns])
        ax.set_yticks(range(piv.shape[0]), [f"+{i:g}" for i in piv.index])
        ax.set_xlabel("Salt/chloride deposition (multiple of baseline)")
        ax.set_ylabel("Dew-point rise over water (K)")
        panel(ax, tag)
    save(fig, t, "sensitivity.pdf")


def fig_ensemble(t, ens):
    fig, axes = figure(t.col, 2.2, 1, 2)
    for ax, (col, lab), tag in zip(axes, [("specific_yield_kwh_kwp", "Year-1 yield vs land (%)"),
                                          ("lifetime_energy_mwh", "25-yr energy vs land (%)")], "ab"):
        piv = ens.pivot(index="seed", columns="scenario", values=col)
        for i, k in enumerate(["fpv_fresh", "fpv_saline"]):
            d = 100 * (piv[k] / piv["land"] - 1)
            ax.boxplot(d, positions=[i], widths=0.5, patch_artist=True, showfliers=True,
                       boxprops=dict(facecolor=SERIES[i + 1], edgecolor=INK_2, linewidth=0.6, hatch=HATCH[i + 1]),
                       medianprops=dict(color=INK, linewidth=1.0), whiskerprops=dict(linewidth=0.6),
                       capprops=dict(linewidth=0.6), flierprops=dict(markersize=2.5))
        ax.axhline(0, color=INK_2, linewidth=0.6)
        ax.set_xticks([0, 1], ["FPV\nfresh", "FPV\nsaline"])
        ax.set_ylabel(lab)
        ax.grid(axis="x", visible=False)
        panel(ax, tag)
    save(fig, t, "ensemble.pdf")


def fig_uncertainty(t, mc, rc):
    fig, axes = figure(t.wide, 2.7, 1, 2, gridspec_kw={"width_ratios": [1, 1.3]})
    ax = axes[0]
    cols = [("fpv_fresh:d_lifetime_energy_mwh_pct", "FPV fresh", SERIES[1], HATCH[1]),
            ("fpv_saline:d_lifetime_energy_mwh_pct", "FPV saline", SERIES[2], HATCH[2]),
            ("fpv_saline_mitigated:d_lifetime_energy_mwh_pct", "FPV saline (M)", SERIES[3], "\\\\\\\\")]
    data = [mc[c] for c, *_ in cols]
    parts = ax.violinplot(data, positions=range(3), showextrema=False, widths=0.8)
    for body, (_, _, col, hatch) in zip(parts["bodies"], cols):
        body.set_facecolor(col)
        body.set_edgecolor(INK_2)
        body.set_linewidth(0.6)
        body.set_alpha(0.9)
        body.set_hatch(hatch)
    for i, d in enumerate(data):
        lo, med, hi = np.percentile(d, [2.5, 50, 97.5])
        ax.vlines(i, lo, hi, color=INK, linewidth=0.9)
        ax.plot(i, med, "o", color="white", markeredgecolor=INK, markersize=4)
    ax.axhline(0, color=INK_2, linewidth=0.6)
    ax.set_xticks(range(3), ["FPV\nfresh", "FPV\nsaline", "FPV\nsaline (M)"])
    ax.set_ylabel("25-year energy vs land PV (%)")
    ax.grid(axis="x", visible=False)
    panel(ax, "a")

    ax = axes[1]
    top = rc.head(10)[::-1]
    labels = [plain_label(n) for n in top.index]
    pos = top.values > 0
    ax.barh(np.arange(len(top))[pos], top.values[pos], color=SERIES[0], height=0.6, label="Positive")
    ax.barh(np.arange(len(top))[~pos], top.values[~pos], color=SERIES[1], hatch="////", edgecolor="white",
            linewidth=0.3, height=0.6, label="Negative")
    ax.set_yticks(range(len(top)), labels)
    ax.axvline(0, color=INK_2, linewidth=0.6)
    ax.set_xlabel("Spearman correlation (saline $-$ land)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper left")  # the top rows have no negative bars
    panel(ax, "b")
    save(fig, t, "uncertainty.pdf")


def fig_thresholds(t, salt, hum):
    fig, axes = figure(t.col, 2.3, 1, 2)
    ax = axes[0]
    x = salt["salt_rate"] * 1000
    ax.plot(x, 100 * (salt["specific_yield_kwh_kwp"] / salt.attrs["land_yield"] - 1), color=SERIES[0],
            linestyle="-", marker="o", label="Year 1")
    ax.plot(x, 100 * (salt["lifetime_energy_mwh"] / salt.attrs["land_lifetime"] - 1), color=SERIES[1],
            linestyle="--", marker="s", label="25 years")
    ax.axhline(0, color=INK_2, linewidth=0.6)
    ax.set_xlabel("Salt deposition (mg/m$^2$/d)")
    ax.set_ylabel("Saline FPV vs land (%)")
    ax.legend(loc="lower left")
    panel(ax, "a")
    ax = axes[1]
    ax.plot(hum["dewpoint_offset"], 100 * (hum["lifetime_energy_mwh"] / hum.attrs["land_lifetime"] - 1),
            color=SERIES[1], linestyle="--", marker="s")
    ax.axhline(0, color=INK_2, linewidth=0.6)
    ax.set_xlabel("Dew-point rise $\\Delta T_d$ (K)")
    ax.set_ylabel("Fresh FPV vs land, 25 yr (%)")
    panel(ax, "b")
    save(fig, t, "thresholds.pdf")


def fig_convergence(t, conv, n_mc):
    fig, ax = figure(t.col, 2.4)
    for i, (col, name) in enumerate([("fpv_fresh:d_lifetime_energy_mwh_pct", "FPV fresh"),
                                     ("fpv_saline:d_lifetime_energy_mwh_pct", "FPV saline")]):
        d = conv[conv.output == col]
        c = SERIES[i + 1]
        ax.errorbar(d["n"], d["median"], yerr=1.96 * d["se_median"], color=c, marker=MK[i + 1], capsize=2,
                    linewidth=1.2, elinewidth=0.8, label=f"{name}: median")
        ax.plot(d["n"], d["p2.5"], color=c, linestyle="--", linewidth=0.9, marker=MK[i + 1], markersize=2.5,
                markerfacecolor="white")
        ax.plot(d["n"], d["p97.5"], color=c, linestyle="--", linewidth=0.9, marker=MK[i + 1], markersize=2.5,
                markerfacecolor="white")
    ax.plot([], [], color=NEUTRAL, linestyle="--", linewidth=0.9, label="2.5 and 97.5 percentiles")
    ax.axhline(0, color=INK_2, linewidth=0.6)
    ax.axvline(n_mc, color=NEUTRAL, linewidth=0.8, linestyle=":")
    ax.set_xscale("log")
    ax.minorticks_off()
    ax.set_xticks([250, 500, 1000, 2000, 5000], ["250", "500", "1000", "2000", "5000"])
    ax.set_xlabel("Number of Monte Carlo samples")
    ax.set_ylabel("25-yr energy vs land (%)")
    legend_above(ax, 2)
    save(fig, t, "convergence.pdf")


def fig_sobol(t, tables, names):
    fig, axes = figure(t.wide, 2.9, 1, 2, sharex=True)
    for ax, (col, title), tag in zip(axes, names, "ab"):
        tab = tables[col].head(8)[::-1]
        y = np.arange(len(tab))
        ax.barh(y + 0.18, tab["ST"], height=0.34, xerr=tab["ST_conf"], color=SERIES[0], label="Total-order index",
                error_kw=dict(lw=0.7, capsize=1.5))
        ax.barh(y - 0.18, tab["S1"].clip(lower=0), height=0.34, xerr=tab["S1_conf"], color=SERIES[1],
                hatch="////", edgecolor="white", linewidth=0.3, label="First-order index",
                error_kw=dict(lw=0.7, capsize=1.5))
        ax.set_yticks(y, [plain_label(n) for n in tab["param"]])
        ax.set_xlabel("Sobol index")
        ax.grid(axis="y", visible=False)
        panel(ax, tag, title)
    axes[0].legend(loc="lower right")
    save(fig, t, "sobol.pdf")


def render_all(t: Target, d: dict, n_mc: int):
    """All shared figures for one target."""
    style()
    fig_climate(t, d["weather"])
    fig_temperature(t, d["res"])
    fig_losses(t, d["res"])
    fig_soiling(t, d["res"])
    fig_monthly_pr(t, d["res"])
    fig_degradation(t, d["res"])
    fig_lifetime(t, d["res"])
    fig_sensitivity(t, d["grid"])
    fig_ensemble(t, d["ens"])
    fig_uncertainty(t, d["mc"], d["rc"])
    fig_thresholds(t, d["salt"], d["hum"])
    fig_convergence(t, d["conv"], n_mc)
