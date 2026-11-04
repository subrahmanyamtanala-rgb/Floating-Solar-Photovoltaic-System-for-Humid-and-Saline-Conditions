"""SIMPAT-specific analyses: code-to-code verification, Sobol indices, computational cost.

Run from the repository root (after paper/make_paper_assets.py):

    python paper_simpat/make_simpat_assets.py

Outputs go to paper_simpat/generated (LaTeX macros, CSV) and paper_simpat/figures.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "paper"))

from fpv_analysis import default_scenarios, run_scenario, solar, synthetic_weather, uncertainty  # noqa: E402
from fpv_analysis.config import Site, ThermalParams  # noqa: E402
from fpv_analysis.electrical import pvwatts_dc, pvwatts_inverter  # noqa: E402
from fpv_analysis.thermal import faiman  # noqa: E402
import make_paper_assets as mpa  # noqa: E402  (shared figure style and palette)

GEN = ROOT / "paper_simpat" / "generated"
FIG = ROOT / "paper_simpat" / "figures"
SOBOL_N = 512  # base sample size; total runs = N (D + 2)
SOBOL_SEED = 2025


def _fmt(v, nd=2):
    return mpa._fmt(v, nd)


# --------------------------------------------------------------------------- verification
def verification():
    """Compare each established sub-model with the pvlib reference implementation."""
    import pvlib

    site = Site()
    w = synthetic_weather(site, seed=42)
    mid = w.index + pd.Timedelta(minutes=30)
    ours = solar.solar_position(mid, site.latitude, site.longitude, site.tz_hours)
    ref = pvlib.solarposition.get_solarposition(mid.tz_localize("Asia/Kolkata"), site.latitude, site.longitude)
    up = (ours["zenith"].to_numpy() < 85) & (ref["zenith"].to_numpy() < 85)
    rows = []

    def add(name, a, b, unit, mask=None, rel=False):
        a = np.asarray(a, float)
        b = np.asarray(b, float)
        m = np.isfinite(a) & np.isfinite(b) if mask is None else (mask & np.isfinite(a) & np.isfinite(b))
        d = a[m] - b[m]
        if rel:
            d = 100 * d / np.maximum(np.abs(b[m]), 1e-9)
        rows.append({"submodel": name, "unit": "%" if rel else unit, "n": int(m.sum()),
                     "mae": float(np.mean(np.abs(d))), "max": float(np.max(np.abs(d))), "bias": float(np.mean(d))})

    add("Solar zenith (Spencer vs. SPA)", ours["zenith"], ref["zenith"], "deg", up)
    daz = (ours["azimuth"].to_numpy() - ref["azimuth"].to_numpy() + 180) % 360 - 180
    add("Solar azimuth (Spencer vs. SPA)", daz, np.zeros_like(daz), "deg", up)
    doy = mid.dayofyear.to_numpy()
    e0_ref = pvlib.irradiance.get_extra_radiation(doy, solar_constant=solar.SOLAR_CONSTANT, method="spencer")
    add("Extraterrestrial irradiance", ours["dni_extra"], e0_ref, "", rel=True)

    # Use one common sun position for the remaining irradiance sub-models
    zen, azi, e0 = (ours[c].to_numpy() for c in ("zenith", "azimuth", "dni_extra"))
    ghi = w["ghi"].to_numpy()
    dni, dhi = solar.erbs(ghi, zen, e0)
    erbs_ref = pvlib.irradiance.erbs(ghi, zen, doy)  # pvlib computes k_t with its own solar constant (1366.1)
    mask_day = (zen < 85) & (ghi > 20)
    dni_c, dhi_c = solar.erbs(ghi, zen, e0 * 1366.1 / solar.SOLAR_CONSTANT)
    add("Erbs DHI (common solar constant)", dhi_c, erbs_ref["dhi"], "W/m2", mask_day)
    add("Erbs DNI (common solar constant)", dni_c, erbs_ref["dni"], "W/m2", mask_day)
    add("Erbs DHI (1361 vs. 1366.1 W/m2)", dhi, erbs_ref["dhi"], "W/m2", mask_day)
    tilt, az = 12.0, 180.0
    poa = solar.poa_hay_davies(ghi, dni, dhi, e0, zen, azi, tilt, az, 0.07)
    sky_ref = pvlib.irradiance.haydavies(tilt, az, dhi, dni, e0, zen, azi)
    add("Hay-Davies sky diffuse", poa["poa_sky"], sky_ref, "W/m2", mask_day)
    aoi_ref = pvlib.irradiance.aoi(tilt, az, zen, azi)
    add("Angle of incidence", poa["aoi"], aoi_ref, "deg", mask_day)
    add("ASHRAE IAM", solar.iam_ashrae(poa["aoi"].to_numpy()), pvlib.iam.ashrae(aoi_ref, b=0.05), "-", mask_day & (aoi_ref < 80))
    gnd_ref = pvlib.irradiance.get_ground_diffuse(tilt, ghi, albedo=0.07)
    add("Ground-reflected", poa["poa_ground"], gnd_ref, "W/m2", mask_day)
    am = solar.relative_airmass(zen)
    am_ref = pvlib.atmosphere.get_relative_airmass(zen, model="kastenyoung1989")
    add("Air mass (Kasten-Young)", am, am_ref, "", mask_day, rel=True)
    pw = solar.precipitable_water(w["temp_air"].to_numpy(), w["rh"].to_numpy())
    pw_ref = pvlib.atmosphere.gueymard94_pw(w["temp_air"].to_numpy(), w["rh"].to_numpy())
    add("Precipitable water (Gueymard)", pw, pw_ref, "", rel=True)
    sp = solar.spectral_modifier_monosi(am, pw)
    sp_ref = pvlib.spectrum.spectral_factor_firstsolar(pw_ref, am_ref, module_type="monosi")
    add("Spectral factor (First Solar)", sp, sp_ref, "-", mask_day)
    g = (poa["poa_beam"] + poa["poa_sky"] + poa["poa_ground"]).to_numpy()
    th = ThermalParams(u0=35.0, u1=8.0, night_sky_loss=0.0)
    tm = faiman(g, w["temp_air"].to_numpy(), w["wind_speed"].to_numpy(), th)
    tm_ref = pvlib.temperature.faiman(g, w["temp_air"].to_numpy(), w["wind_speed"].to_numpy(), u0=35.0, u1=8.0)
    add("Faiman module temperature", tm, tm_ref, "K", mask_day)
    pdc = pvwatts_dc(g, tm, 1000.0, -0.0035)
    pdc_ref = pvlib.pvsystem.pvwatts_dc(g, tm, 1000.0, -0.0035)
    add("PVWatts DC power", pdc, pdc_ref, "kW", mask_day)
    pac0 = 1000.0 / 1.2
    pac = pvwatts_inverter(pdc, pac0, 0.98)
    pac_ref = pvlib.inverter.pvwatts(pdc, pac0 / 0.98, eta_inv_nom=0.98)
    add("PVWatts inverter", pac, np.clip(pac_ref, 0, None), "kW", mask_day)
    ver = pd.DataFrame(rows)

    # End-to-end: annual POA with our sun position vs the SPA sun position (all else equal)
    zr, ar = ref["zenith"].to_numpy(), ref["azimuth"].to_numpy()
    dni_r, dhi_r = solar.erbs(ghi, zr, e0)
    poa_r = solar.poa_hay_davies(ghi, dni_r, dhi_r, e0, zr, ar, tilt, az, 0.07)
    g_r = (poa_r["poa_beam"] + poa_r["poa_sky"] + poa_r["poa_ground"]).to_numpy()
    e2e = 100 * (g.sum() / g_r.sum() - 1)
    return ver, e2e, pvlib.__version__


# --------------------------------------------------------------------------- Sobol
def sobol(weather, outputs):
    from SALib.analyze import sobol as sobol_analyze
    from SALib.sample import sobol as sobol_sample

    params = uncertainty.PARAMS
    problem = {
        "num_vars": len(params),
        "names": [p.name for p in params],
        "bounds": [[np.log(p.low), np.log(p.high)] if p.log else [p.low, p.high] for p in params],
    }
    X = sobol_sample.sample(problem, SOBOL_N, calc_second_order=False, seed=SOBOL_SEED)
    samples = [{p.name: (float(np.exp(x[i])) if p.log else float(x[i])) for i, p in enumerate(params)} for x in X]
    import multiprocessing as mp

    with mp.get_context("fork").Pool(os.cpu_count() or 1, initializer=uncertainty._init_worker,
                                     initargs=(weather,)) as pool:
        res = pool.map(uncertainty._evaluate_sample, samples, chunksize=64)
    out = pd.DataFrame(res)
    tables = {}
    for col in outputs:
        si = sobol_analyze.analyze(problem, out[col].to_numpy(), calc_second_order=False, seed=SOBOL_SEED,
                                   print_to_console=False)
        tables[col] = pd.DataFrame({"param": problem["names"], "S1": si["S1"], "S1_conf": si["S1_conf"],
                                    "ST": si["ST"], "ST_conf": si["ST_conf"]}).sort_values("ST", ascending=False)
    return tables, len(X)


def fig_sobol(tables, names):
    mpa.style()
    fig, axes = plt.subplots(1, 2, figsize=(mpa.DCOL, 2.5), sharex=True)
    for ax, (col, title), tag in zip(axes, names, "ab"):
        t = tables[col].head(8)[::-1]
        y = np.arange(len(t))
        ax.barh(y + 0.18, t["ST"], height=0.34, xerr=t["ST_conf"], color=mpa.SERIES[0], label="Total-order $S_T$",
                error_kw=dict(lw=0.6, capsize=1.5))
        ax.barh(y - 0.18, t["S1"].clip(lower=0), height=0.34, xerr=t["S1_conf"], color=mpa.SERIES[1],
                label="First-order $S_1$", error_kw=dict(lw=0.6, capsize=1.5))
        ax.set_yticks(y, [uncertainty.PARAM_BY_NAME[n].label.split(" (")[0] for n in t["param"]], fontsize=6.5)
        ax.set_xlabel("Sobol index")
        ax.grid(axis="y", visible=False)
        ax.set_title(f"({tag}) {title}", loc="left", fontsize=8)
    axes[0].legend(loc="lower right", fontsize=6.5)
    fig.tight_layout(pad=0.3, w_pad=1.0)
    fig.savefig(FIG / "sobol.pdf", bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


# --------------------------------------------------------------------------- cost
def runtime(weather):
    s = default_scenarios()[2]
    run_scenario(weather, s)
    times = []
    for _ in range(20):
        t0 = time.perf_counter()
        run_scenario(weather, s)
        times.append(time.perf_counter() - t0)
    return float(np.median(times))


def main():
    GEN.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    weather = synthetic_weather(seed=42)
    lines = ["% Auto-generated by paper_simpat/make_simpat_assets.py - do not edit by hand."]

    def m(name, value):
        lines.append(f"\\newcommand{{\\{name}}}{{{value}}}")

    # verification
    ver, e2e, pvver = verification()
    ver.to_csv(GEN / "verification.csv", index=False, float_format="%.6g")
    body = []
    for r in ver.itertuples():
        def g(v):
            if v == 0:
                return "0"
            if abs(v) < 1e-3:
                mant, ex = f"{v:.1e}".split("e")
                return f"${mant}\\times10^{{{int(ex)}}}$"
            return f"{v:.3g}"
        unit = {"%": "\\%", "W/m2": "W/m$^2$", "-": "--", "": "--"}.get(r.unit, r.unit)
        name = r.submodel.replace("W/m2", "W/m$^2$")
        body.append(f"{name} & {unit} & {r.n:,} & {g(r.mae)} & {g(r.max)} \\\\".replace(",", "{,}", 1))
    (GEN / "table_verification.tex").write_text("\\newcommand{\\TabVerification}{%\n" + "\n".join(body) + "}\n",
                                                encoding="utf-8")
    vz = ver.set_index("submodel")
    m("PvlibVersion", pvver)
    m("VerZenMAE", f"{vz.loc['Solar zenith (Spencer vs. SPA)', 'mae']:.2f}")
    m("VerZenMax", f"{vz.loc['Solar zenith (Spencer vs. SPA)', 'max']:.2f}")
    m("VerAzMAE", f"{vz.loc['Solar azimuth (Spencer vs. SPA)', 'mae']:.2f}")
    m("VerPOAEtoE", _fmt(e2e, 2))
    exact = ver[ver["max"] < 1e-9]
    m("VerNExact", str(len(exact)))
    m("VerNTotal", str(len(ver)))
    m("VerExactMax", f"{exact['max'].max():.0e}".replace("e-", "\\times10^{-") + "}")
    m("VerErbsMax", f"{vz.loc['Erbs DHI (1361 vs. 1366.1 W/m2)', 'max']:.1f}")

    # Sobol
    outputs = ["fpv_fresh:d_lifetime_energy_mwh_pct", "fpv_saline:d_lifetime_energy_mwh_pct"]
    t0 = time.time()
    cache = [GEN / f"sobol_{c.split(':')[0]}.csv" for c in outputs]
    if "--reuse-sobol" in sys.argv and all(c.exists() for c in cache):
        tables = {c: pd.read_csv(f) for c, f in zip(outputs, cache)}
        nruns = SOBOL_N * (len(uncertainty.PARAMS) + 2)
        sob_wall = float((GEN / "sobol_wall.txt").read_text())
    else:
        tables, nruns = sobol(weather, outputs)
        sob_wall = time.time() - t0
        (GEN / "sobol_wall.txt").write_text(f"{sob_wall:.1f}")
    for col, t in tables.items():
        t.to_csv(GEN / f"sobol_{col.split(':')[0]}.csv", index=False, float_format="%.4g")
    fig_sobol(tables, [(outputs[0], "FPV fresh $-$ land, 25-yr energy"), (outputs[1], "FPV saline $-$ land, 25-yr energy")])
    m("SobolN", f"{SOBOL_N}")
    m("SobolRuns", f"{nruns:,}".replace(",", "{,}"))
    m("SobolEvals", f"{4 * nruns:,}".replace(",", "{,}"))
    for tag, col in (("F", outputs[0]), ("S", outputs[1])):
        t = tables[col].reset_index(drop=True)
        for i in range(3):
            m(f"Sob{tag}Name{'ABC'[i]}", uncertainty.PARAM_BY_NAME[t.param[i]].label.split(" (")[0])
            m(f"Sob{tag}ST{'ABC'[i]}", f"{t.ST[i]:.2f}")
        m(f"Sob{tag}SumS", f"{t.S1.clip(lower=0).sum():.2f}")
        m(f"Sob{tag}SumST", f"{t.ST.sum():.2f}")
        m(f"Sob{tag}NInfl", str(int((t.ST - t.ST_conf > 0.05).sum())))
    rows = []
    tf = tables[outputs[0]].set_index("param")
    ts = tables[outputs[1]].set_index("param")
    order = (tf["ST"] + ts["ST"]).sort_values(ascending=False).index[:10]
    for p in order:
        rows.append(f"{uncertainty.PARAM_BY_NAME[p].label} & {tf.loc[p, 'S1']:.2f} & {tf.loc[p, 'ST']:.2f}$\\pm${tf.loc[p, 'ST_conf']:.2f} "
                    f"& {ts.loc[p, 'S1']:.2f} & {ts.loc[p, 'ST']:.2f}$\\pm${ts.loc[p, 'ST_conf']:.2f} \\\\")
    (GEN / "table_sobol.tex").write_text("\\newcommand{\\TabSobol}{%\n" + "\n".join(rows) + "}\n", encoding="utf-8")

    # cost
    rt = runtime(weather)
    m("RunTimeMs", f"{1000 * rt:.0f}")
    m("SobolWallMin", f"{sob_wall / 60:.1f}")
    m("NCores", str(os.cpu_count() or 1))
    (GEN / "numbers_simpat.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(ver.round(5).to_string())
    print("e2e POA %:", e2e)
    for col, t in tables.items():
        print(col)
        print(t.head(8).round(3).to_string())
    print("runtime s:", rt, "sobol wall min:", sob_wall / 60)


if __name__ == "__main__":
    main()
