"""Figures for the study (static PNG, matplotlib)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

# Validated categorical palette, used in fixed slot order (never cycled).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
NEUTRAL = "#8a8984"
SEQ_BLUE = LinearSegmentedColormap.from_list(
    "seq_blue", ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
)
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

SHORT = {
    "land": "Land PV",
    "fpv_fresh": "FPV freshwater",
    "fpv_saline": "FPV saline",
}


def _style():
    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "axes.edgecolor": GRID,
            "axes.labelcolor": INK_2,
            "axes.titlecolor": INK,
            "axes.titleweight": "bold",
            "axes.titlesize": 11,
            "axes.titlelocation": "left",
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "xtick.color": INK_2,
            "ytick.color": INK_2,
            "text.color": INK,
            "font.size": 9,
            "legend.frameon": False,
            "lines.linewidth": 2.0,
        }
    )


def _short(result) -> str:
    key = result.scenario.key
    base = key.replace("_mitigated", "")
    name = SHORT.get(base, result.scenario.label)
    return name + (" (mitigated)" if key.endswith("_mitigated") else "")


def _save(fig, out: Path, name: str) -> Path:
    path = out / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def climate(weather: pd.DataFrame, out: Path) -> Path:
    m = pd.DataFrame(
        {
            "ghi": weather["ghi"].resample("MS").sum() / 1000.0 / weather["ghi"].resample("MS").sum().index.days_in_month,
            "temp": weather["temp_air"].resample("MS").mean(),
            "rh": weather["rh"].resample("MS").mean(),
            "rain": weather["precip"].resample("MS").sum(),
        }
    )
    fig, axes = plt.subplots(2, 2, figsize=(9, 5.5), sharex=True)
    specs = [
        ("ghi", "Daily irradiation (GHI)", "kWh/m²/day"),
        ("temp", "Mean air temperature", "°C"),
        ("rh", "Mean relative humidity", "%"),
        ("rain", "Rainfall", "mm/month"),
    ]
    x = np.arange(12)
    for ax, (col, title, unit) in zip(axes.flat, specs):
        if col == "rain":
            ax.bar(x, m[col], color=SERIES[0], width=0.7)
        else:
            ax.plot(x, m[col], color=SERIES[0], marker="o", markersize=4)
        ax.set_title(title)
        ax.set_ylabel(unit)
        ax.set_xticks(x, MONTHS)
    fig.suptitle("Site climate - synthetic typical year", x=0.01, ha="left", fontweight="bold", color=INK)
    fig.tight_layout()
    return _save(fig, out, "fig01_climate.png")


def diurnal_temperature(results, out: Path, month: int = 5) -> Path:
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    air = None
    for i, r in enumerate(results):
        h = r.hourly[r.hourly.index.month == month]
        prof = h.groupby(h.index.hour)["temp_module"].mean()
        ax.plot(prof.index, prof.values, color=SERIES[i], label=_short(r))
        ax.annotate(f"{prof.max():.1f} °C", (prof.idxmax(), prof.max()), textcoords="offset points",
                    xytext=(8, 4) if i < 2 else (-14, -24), color=INK_2, fontsize=8)
        if air is None:
            air = h.groupby(h.index.hour)["temp_air"].mean()
    ax.plot(air.index, air.values, color=NEUTRAL, linestyle="--", linewidth=1.5, label="Air (site)")
    ax.set_xlim(0, 23)
    ax.set_xticks(range(0, 24, 3))
    ax.set_xlabel("Hour of day (IST)")
    ax.set_ylabel("°C")
    ax.set_title(f"Mean module temperature by hour, {MONTHS[month - 1]} (hottest month)")
    ax.legend(loc="upper left")
    return _save(fig, out, "fig02_module_temperature.png")


def monthly_energy(results, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(9, 4.2))
    n = len(results)
    width = 0.8 / n
    x = np.arange(12)
    for i, r in enumerate(results):
        e = r.monthly["energy_kwh"].to_numpy() / 1000.0
        ax.bar(x + (i - (n - 1) / 2) * width, e, width=width * 0.92, color=SERIES[i], label=_short(r))
    ax.set_xticks(x, MONTHS)
    ax.set_ylabel("MWh")
    ax.set_title("Monthly AC energy per 1 MWp")
    ax.legend(ncols=n, loc="upper right")
    ax.grid(axis="x", visible=False)
    return _save(fig, out, "fig03_monthly_energy.png")


def losses(results, out: Path) -> Path:
    names = list(results[0].losses.keys())
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    n = len(results)
    height = 0.8 / n
    y = np.arange(len(names))
    for i, r in enumerate(results):
        v = [r.losses[k] for k in names]
        ax.barh(y + (i - (n - 1) / 2) * height, v, height=height * 0.9, color=SERIES[i], label=_short(r))
    ax.set_yticks(y, names)
    ax.invert_yaxis()
    ax.axvline(0, color=INK_2, linewidth=0.8)
    ax.set_xlabel("Energy loss, % of the preceding stage (negative = gain)")
    ax.set_title("Loss breakdown, year 1")
    ax.legend(loc="lower right")
    ax.grid(axis="y", visible=False)
    return _save(fig, out, "fig04_loss_breakdown.png")


def soiling(results, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(9, 3.8))
    for i, r in enumerate(results):
        d = r.hourly["soiling_ratio"].resample("D").mean()
        ax.plot(d.index, 100 * d.values, color=SERIES[i], linewidth=1.6, label=_short(r))
    ax.set_ylabel("Soiling ratio, %")
    ax.set_title("Daily soiling ratio - dust and salt with rain, dew and fortnightly cleaning")
    ax.legend(ncols=len(results), loc="lower left")
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b"))
    return _save(fig, out, "fig05_soiling.png")


def degradation(results, out: Path) -> Path:
    mech = [
        ("deg_base_pct_yr", "Intrinsic (UV, thermal cycling)"),
        ("deg_temp_humidity_pct_yr", "Temperature-humidity (Peck)"),
        ("deg_pid_pct_yr", "Potential-induced (PID)"),
        ("deg_corrosion_pct_yr", "Salt / chloride corrosion"),
    ]
    labels = [_short(r) for r in results]
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    left = np.zeros(len(results))
    y = np.arange(len(results))
    for i, (col, name) in enumerate(mech):
        v = np.array([r.kpis[col] for r in results])
        ax.barh(y, v, left=left, color=SERIES[i], height=0.6, label=name, edgecolor=SURFACE, linewidth=2)
        left += v
    for yi, total in zip(y, left):
        ax.text(total + 0.02, yi, f"{total:.2f} %/yr", va="center", color=INK, fontsize=8.5)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, left.max() * 1.18)
    ax.set_xlabel("Annual power degradation, %/yr")
    ax.set_title("Degradation rate by mechanism")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncols=2)
    ax.grid(axis="y", visible=False)
    return _save(fig, out, "fig06_degradation.png")


def lifetime(results, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4.2))
    base = [r for r in results if not r.scenario.key.endswith("_mitigated")]
    for i, r in enumerate(base):
        years = np.arange(1, len(r.lifetime_kwh) + 1)
        ax.plot(years, r.lifetime_kwh / 1000.0, color=SERIES[i], label=_short(r))
        mit = next((m for m in results if m.scenario.key == r.scenario.key + "_mitigated"), None)
        if mit is not None:
            ax.plot(years, mit.lifetime_kwh / 1000.0, color=SERIES[i], linestyle=":", linewidth=1.6)
    ax.plot([], [], color=NEUTRAL, linestyle=":", linewidth=1.6, label="Same, with PID-resistant + salt-mist-hardened modules")
    ax.set_xlabel("Year of operation")
    ax.set_ylabel("MWh/yr per MWp")
    ax.set_title("Annual energy over 25 years")
    ax.legend(loc="lower left")
    return _save(fig, out, "fig07_lifetime_energy.png")


def sensitivity(grid: pd.DataFrame, out: Path, value: str, title: str, fmt: str, name: str) -> Path:
    piv = grid.pivot(index="dewpoint_offset", columns="salinity", values=value).sort_index(ascending=False)
    fig, ax = plt.subplots(figsize=(7, 4.6))
    im = ax.imshow(piv.values, cmap=SEQ_BLUE, aspect="auto")
    ax.grid(False)
    ax.set_xticks(range(piv.shape[1]), [f"{c:g}×" for c in piv.columns])
    ax.set_yticks(range(piv.shape[0]), [f"+{i:g} °C" for i in piv.index])
    ax.set_xlabel("Salt and chloride deposition (multiple of the saline baseline)")
    ax.set_ylabel("Dew-point rise over water")
    lo, hi = np.nanmin(piv.values), np.nanmax(piv.values)
    for (r, c), v in np.ndenumerate(piv.values):
        dark = (v - lo) / (hi - lo + 1e-12) > 0.4
        ax.text(c, r, format(v, fmt), ha="center", va="center", fontsize=8.5, color="#ffffff" if dark else INK)
    ax.set_title(title)
    cb = fig.colorbar(im, ax=ax, shrink=0.85)
    cb.outline.set_visible(False)
    return _save(fig, out, name)


def all_figures(weather, results, grid, out: Path) -> list[Path]:
    _style()
    out.mkdir(parents=True, exist_ok=True)
    base = [r for r in results if not r.scenario.key.endswith("_mitigated")]
    return [
        climate(weather, out),
        diurnal_temperature(base, out),
        monthly_energy(base, out),
        losses(base, out),
        soiling(base, out),
        degradation(results, out),
        lifetime(results, out),
        sensitivity(grid, out, "deg_total_pct_yr", "FPV saline: total degradation rate, %/yr", ".2f",
                    "fig08_sensitivity_degradation.png"),
        sensitivity(grid, out, "lifetime_energy_mwh", "FPV saline: 25-year energy, MWh per MWp", ".0f",
                    "fig09_sensitivity_lifetime.png"),
    ]
