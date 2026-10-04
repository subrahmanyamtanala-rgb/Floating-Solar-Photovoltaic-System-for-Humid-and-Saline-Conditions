"""Targeted studies requested in peer review: thresholds, mitigations, economics, weather check."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from .climate import VIZAG_CLIMATE, synthetic_weather
from .config import Scenario, default_scenarios, with_mitigation
from .economics import lcoe
from .simulation import run_scenario


def _kpis(weather, sc):
    return run_scenario(weather, sc).kpis


def _crossing(x: np.ndarray, y: np.ndarray, target: float) -> float:
    """First x at which y crosses ``target`` (linear interpolation); NaN if it never does."""
    d = np.asarray(y) - target
    for i in range(len(d) - 1):
        if d[i] == 0:
            return float(x[i])
        if d[i] * d[i + 1] < 0:
            return float(x[i] + (x[i + 1] - x[i]) * d[i] / (d[i] - d[i + 1]))
    return float("nan")


# --------------------------------------------------------------------------- thresholds
def chloride_sweep(weather, values=None) -> pd.DataFrame:
    """Saline FPV vs chloride deposition (salt soiling held at baseline)."""
    land, _, saline = default_scenarios()
    values = np.array(values if values is not None else [0, 5, 10, 20, 30, 45, 60, 90, 120, 180, 240, 300, 400])
    rows = []
    for cl in values:
        sc = replace(saline, degradation=replace(saline.degradation, chloride_deposition=float(cl)))
        k = _kpis(weather, sc)
        rows.append({"chloride": cl, **{c: k[c] for c in ("deg_total_pct_yr", "lifetime_energy_mwh", "lcoe_inr_kwh")}})
    df = pd.DataFrame(rows)
    df.attrs["land_lifetime"] = _kpis(weather, land)["lifetime_energy_mwh"]
    return df


def salt_sweep(weather, values=None) -> pd.DataFrame:
    """Saline FPV vs salt soiling deposition (chloride held at baseline)."""
    land, _, saline = default_scenarios()
    values = np.array(values if values is not None else [0.0, 0.005, 0.01, 0.02, 0.03, 0.045, 0.06, 0.08, 0.10, 0.12])
    rows = []
    for r in values:
        sc = replace(saline, soiling=replace(saline.soiling, salt_rate=float(r)))
        k = _kpis(weather, sc)
        rows.append({"salt_rate": r, **{c: k[c] for c in ("specific_yield_kwh_kwp", "loss_Soiling (dust + salt)",
                                                         "deg_total_pct_yr", "lifetime_energy_mwh")}})
    df = pd.DataFrame(rows)
    lk = _kpis(weather, land)
    df.attrs["land_yield"] = lk["specific_yield_kwh_kwp"]
    df.attrs["land_lifetime"] = lk["lifetime_energy_mwh"]
    return df


def humidity_sweep(weather, values=None) -> pd.DataFrame:
    """Freshwater FPV vs dew-point rise over the water."""
    land, fresh, _ = default_scenarios()
    values = np.array(values if values is not None else np.arange(0.0, 6.01, 0.5))
    rows = []
    for d in values:
        sc = replace(fresh, microclimate=replace(fresh.microclimate, dewpoint_offset=float(d)))
        k = _kpis(weather, sc)
        rows.append({"dewpoint_offset": d, **{c: k[c] for c in ("specific_yield_kwh_kwp", "deg_total_pct_yr",
                                                               "lifetime_energy_mwh", "time_of_wetness_h")}})
    df = pd.DataFrame(rows)
    df.attrs["land_lifetime"] = _kpis(weather, land)["lifetime_energy_mwh"]
    return df


def thresholds(cl: pd.DataFrame, salt: pd.DataFrame, hum: pd.DataFrame) -> dict:
    return {
        "chloride_star": _crossing(cl["chloride"].values, cl["lifetime_energy_mwh"].values, cl.attrs["land_lifetime"]),
        "salt_star_yield": _crossing(salt["salt_rate"].values, salt["specific_yield_kwh_kwp"].values,
                                     salt.attrs["land_yield"]),
        "salt_star_life": _crossing(salt["salt_rate"].values, salt["lifetime_energy_mwh"].values,
                                    salt.attrs["land_lifetime"]),
        "dtd_star": _crossing(hum["dewpoint_offset"].values, hum["lifetime_energy_mwh"].values,
                              hum.attrs["land_lifetime"]),
    }


# --------------------------------------------------------------------------- dew loss
def dew_sensitivity(weather, losses=(0.0, 0.02, 0.04, 0.06)) -> pd.DataFrame:
    rows = []
    for dl in losses:
        ks = {s.key: _kpis(weather, replace(s, system=replace(s.system, dew_optical_loss=dl)))
              for s in default_scenarios()}
        rows.append({
            "dew_loss": dl,
            **{f"{k}_yield": v["specific_yield_kwh_kwp"] for k, v in ks.items()},
            "fresh_vs_land_pct": 100 * (ks["fpv_fresh"]["energy_mwh"] / ks["land"]["energy_mwh"] - 1),
            "saline_vs_land_pct": 100 * (ks["fpv_saline"]["energy_mwh"] / ks["land"]["energy_mwh"] - 1),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- mitigation
def mitigation_matrix(weather) -> pd.DataFrame:
    """Mitigation options for the saline plant (and the land reference)."""
    land, _, saline = default_scenarios()
    options = [
        ("Standard module", saline),
        ("PID-resistant", with_mitigation(saline, pid=True, salt_mist=False, suffix="_pid")),
        ("Salt-mist-hardened", with_mitigation(saline, pid=False, salt_mist=True, suffix="_salt")),
        ("PID + salt-mist", with_mitigation(saline, suffix="_both")),
        ("PID + salt-mist + glass-glass", with_mitigation(saline, glass_glass=True, suffix="_gg")),
        ("PID + salt-mist + glass-glass + 7-day cleaning",
         with_mitigation(saline, glass_glass=True, cleaning_interval_days=7, suffix="_all")),
    ]
    base_life = _kpis(weather, saline)["lifetime_energy_mwh"]
    land_k = _kpis(weather, land)
    rows = []
    for name, sc in options:
        k = _kpis(weather, sc)
        rows.append({
            "option": name,
            "deg_total_pct_yr": k["deg_total_pct_yr"],
            "specific_yield_kwh_kwp": k["specific_yield_kwh_kwp"],
            "lifetime_energy_mwh": k["lifetime_energy_mwh"],
            "recovery_pct": 100 * (k["lifetime_energy_mwh"] / base_life - 1),
            "vs_land_pct": 100 * (k["lifetime_energy_mwh"] / land_k["lifetime_energy_mwh"] - 1),
            "capex_per_wp": sc.economics.capex_per_wp,
            "lcoe_inr_kwh": k["lcoe_inr_kwh"],
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- economics
def _pv_terms(r, sc: Scenario):
    e = sc.economics
    years = np.arange(1, e.lifetime_years + 1)
    disc = (1 + e.discount_rate) ** years
    pv_e = float(np.sum(r.lifetime_kwh / disc))
    pv_o = float(np.sum(e.opex_per_kwp_yr * sc.system.dc_kwp * (1 + e.opex_escalation) ** (years - 1) / disc))
    pv_annuity = float(np.sum(1.0 / disc))
    return pv_e, pv_o, pv_annuity


def break_even(weather, water_values=(0, 10, 20, 40, 80)) -> dict:
    land, fresh, saline = default_scenarios()
    res = {s.key: run_scenario(weather, s) for s in (land, fresh, saline)}
    sc = {"land": land, "fpv_fresh": fresh, "fpv_saline": saline}
    l_land = res["land"].kpis["lcoe_inr_kwh"]
    out = {"lcoe_land": l_land}
    pv_e_land, pv_o_land, _ = _pv_terms(res["land"], land)
    for key in ("fpv_fresh", "fpv_saline"):
        pv_e, pv_o, ann = _pv_terms(res[key], sc[key])
        kwp = sc[key].system.dc_kwp
        # CAPEX at which FPV LCOE equals land LCOE
        out[f"{key}_capex_star"] = (l_land * pv_e - pv_o) / (kwp * 1000.0)
        # extra land cost (INR/Wp) at which land LCOE would equal FPV LCOE
        l_fpv = res[key].kpis["lcoe_inr_kwh"]
        out[f"{key}_land_premium_star"] = (l_fpv * pv_e_land - pv_o_land) / (kwp * 1000.0) - land.economics.capex_per_wp
        if key == "fpv_fresh":
            v = res[key].kpis["water_saved_m3_yr"]
            capex = sc[key].economics.capex_per_wp * kwp * 1000.0
            out["water_value_star"] = (capex + pv_o - l_land * pv_e) / (v * ann)
            out["lcoe_with_water"] = {
                w: (capex + pv_o - w * v * ann) / pv_e for w in water_values
            }
    return out


# --------------------------------------------------------------------------- weather check
def weather_check(seeds=range(1, 21)) -> pd.DataFrame:
    """Monthly statistics of the generator against the climatology it is built from."""
    rows = []
    for seed in seeds:
        w = synthetic_weather(seed=seed)
        m = pd.DataFrame({
            "temp_mean": w["temp_air"].resample("MS").mean(),
            "rh_mean": w["rh"].resample("MS").mean(),
            "wind_mean": w["wind_speed"].resample("MS").mean(),
            "rain_mm": w["precip"].resample("MS").sum(),
            "temp_range": (w["temp_air"].resample("D").max() - w["temp_air"].resample("D").min()).resample("MS").mean(),
        })
        m["month"] = range(1, 13)
        m["seed"] = seed
        rows.append(m.reset_index(drop=True))
    sim = pd.concat(rows)
    mean = sim.groupby("month").mean(numeric_only=True)
    out = []
    for col in ("temp_mean", "temp_range", "rh_mean", "wind_mean", "rain_mm"):
        ref = VIZAG_CLIMATE[col].to_numpy(dtype=float)
        s = mean[col].to_numpy()
        out.append({
            "variable": col,
            "mbe": float(np.mean(s - ref)),
            "rmse": float(np.sqrt(np.mean((s - ref) ** 2))),
            "r": float(np.corrcoef(s, ref)[0, 1]),
            "ref_annual": float(ref.sum() if col == "rain_mm" else ref.mean()),
            "sim_annual": float(s.sum() if col == "rain_mm" else s.mean()),
        })
    return pd.DataFrame(out)
