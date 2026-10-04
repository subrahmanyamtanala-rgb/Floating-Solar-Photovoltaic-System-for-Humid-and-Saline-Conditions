"""Parameter uncertainty: Monte Carlo propagation and one-at-a-time sensitivity.

Weather variability is handled separately (independent synthetic years); this
module propagates uncertainty in the *model parameters* that the study had to
assume.  All scenarios in one sample share the parameters they have in common
(degradation reference rates, soiling coefficients, dew loss), so differences
between scenarios are paired and their spread is not inflated by unrelated
draws.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from .config import Scenario, default_scenarios, with_mitigation
from .simulation import run_scenario


@dataclass(frozen=True)
class Param:
    name: str
    label: str
    low: float
    high: float
    log: bool = False  # sample log-uniformly (for multiplicative factors)

    def sample(self, rng: np.random.Generator) -> float:
        if self.log:
            return float(np.exp(rng.uniform(np.log(self.low), np.log(self.high))))
        return float(rng.uniform(self.low, self.high))

    @property
    def mid(self) -> float:
        return float(np.sqrt(self.low * self.high)) if self.log else 0.5 * (self.low + self.high)


# Ranges are deliberately wide; they bracket the baseline values in config.py.
PARAMS = [
    # shared by all plants
    Param("th_ref", "Peck reference rate $R_{TH}^{ref}$", 0.06, 0.14),
    Param("pid_ref", "PID reference rate $R_{PID}^{ref}$", 0.03, 0.09),
    Param("corr_ref", "Corrosion reference rate $R_C^{ref}$", 0.05, 0.15),
    Param("dew_loss", "Dew optical loss", 0.0, 0.06),
    Param("k_dust", "Dust loss coefficient $k_d$", 0.025, 0.045),
    Param("k_salt", "Salt loss coefficient $k_s$", 0.03, 0.09),
    Param("cementation", "Deliquescence cementation", 0.25, 0.75),
    # land plant
    Param("u0_land", "Land $U_0$", 22.0, 29.0),
    Param("u1_land", "Land $U_1$", 4.5, 8.0),
    Param("dust_land", "Land dust deposition", 0.5, 2.0, log=True),
    Param("cl_land", "Land chloride deposition", 0.5, 2.0, log=True),
    # floating plants
    # wide enough to include FPV designs with no cooling advantage over open racks
    # (U-values of 22-34 W/m2K and wind terms of 2.7-5 W s/m3K have been measured)
    Param("u0_fpv", "FPV $U_0$", 22.0, 45.0),
    Param("u1_fpv", "FPV $U_1$", 2.5, 10.0),
    Param("wind_fpv", "Wind factor $k_v$", 1.0, 1.35),
    Param("motion", "Wave-motion mismatch", 0.003, 0.015),
    Param("alpha_fresh", "Air-water coupling $\\alpha$ (fresh)", 0.10, 0.40),
    Param("dtd_fresh", "Dew-point rise $\\Delta T_d$ (fresh)", 0.5, 1.5),
    Param("alpha_saline", "Air-water coupling $\\alpha$ (saline)", 0.15, 0.45),
    Param("dtd_saline", "Dew-point rise $\\Delta T_d$ (saline)", 1.0, 2.0),
    Param("salt_saline", "Saline salt deposition", 0.5, 2.0, log=True),
    Param("cl_saline", "Saline chloride deposition", 0.5, 2.0, log=True),
    # mitigation (assumed reduction factors)
    Param("mu_pid", "PID mitigation $\\mu_{PID}$", 0.5, 0.95),
    Param("mu_salt", "Salt-mist mitigation $\\mu_C$", 0.2, 0.7),
    # costs
    Param("capex_land", "Land CAPEX (INR/Wp)", 30.0, 40.0),
    Param("capex_fresh", "FPV fresh CAPEX (INR/Wp)", 38.0, 52.0),
    Param("capex_saline", "FPV saline CAPEX (INR/Wp)", 44.0, 60.0),
]
PARAM_BY_NAME = {p.name: p for p in PARAMS}


def baseline_values() -> dict:
    """Parameter values that reproduce the deterministic baseline exactly."""
    land, fresh, saline = default_scenarios()
    return {
        "th_ref": land.degradation.th_ref_rate,
        "pid_ref": land.degradation.pid_ref_rate,
        "corr_ref": land.degradation.corrosion_ref_rate,
        "dew_loss": land.system.dew_optical_loss,
        "k_dust": land.soiling.k_dust,
        "k_salt": land.soiling.k_salt,
        "cementation": land.soiling.cementation,
        "u0_land": land.thermal.u0,
        "u1_land": land.thermal.u1,
        "dust_land": 1.0,
        "cl_land": 1.0,
        "u0_fpv": fresh.thermal.u0,
        "u1_fpv": fresh.thermal.u1,
        "wind_fpv": fresh.microclimate.wind_factor,
        "motion": fresh.system.motion_loss,
        "alpha_fresh": fresh.microclimate.air_coupling,
        "dtd_fresh": fresh.microclimate.dewpoint_offset,
        "alpha_saline": saline.microclimate.air_coupling,
        "dtd_saline": saline.microclimate.dewpoint_offset,
        "salt_saline": 1.0,
        "cl_saline": 1.0,
        "mu_pid": 0.9,
        "mu_salt": 0.5,
        "capex_land": land.economics.capex_per_wp,
        "capex_fresh": fresh.economics.capex_per_wp,
        "capex_saline": saline.economics.capex_per_wp,
    }


def build_scenarios(v: dict) -> dict[str, Scenario]:
    """Scenarios for one parameter vector ``v`` (missing keys fall back to the baseline)."""
    v = {**baseline_values(), **v}
    land, fresh, saline = default_scenarios()

    def common(s: Scenario) -> Scenario:
        return replace(
            s,
            system=replace(s.system, dew_optical_loss=v["dew_loss"]),
            soiling=replace(s.soiling, k_dust=v["k_dust"], k_salt=v["k_salt"], cementation=v["cementation"]),
            degradation=replace(
                s.degradation,
                th_ref_rate=v["th_ref"],
                pid_ref_rate=v["pid_ref"],
                corrosion_ref_rate=v["corr_ref"],
            ),
        )

    def fpv(s: Scenario, alpha: float, dtd: float) -> Scenario:
        s = common(s)
        return replace(
            s,
            thermal=replace(s.thermal, u0=v["u0_fpv"], u1=v["u1_fpv"]),
            microclimate=replace(s.microclimate, air_coupling=alpha, dewpoint_offset=dtd, wind_factor=v["wind_fpv"]
                                 * s.microclimate.wind_factor / fresh.microclimate.wind_factor),
            system=replace(s.system, motion_loss=v["motion"] * s.system.motion_loss / fresh.system.motion_loss),
        )

    land = common(land)
    land = replace(
        land,
        thermal=replace(land.thermal, u0=v["u0_land"], u1=v["u1_land"]),
        soiling=replace(land.soiling, dust_rate=land.soiling.dust_rate * v["dust_land"]),
        degradation=replace(land.degradation, chloride_deposition=land.degradation.chloride_deposition * v["cl_land"]),
        economics=replace(land.economics, capex_per_wp=v["capex_land"]),
    )
    fresh = fpv(fresh, v["alpha_fresh"], v["dtd_fresh"])
    fresh = replace(fresh, economics=replace(fresh.economics, capex_per_wp=v["capex_fresh"]))
    saline = fpv(saline, v["alpha_saline"], v["dtd_saline"])
    saline = replace(
        saline,
        soiling=replace(saline.soiling, salt_rate=saline.soiling.salt_rate * v["salt_saline"]),
        degradation=replace(
            saline.degradation, chloride_deposition=saline.degradation.chloride_deposition * v["cl_saline"]
        ),
        economics=replace(saline.economics, capex_per_wp=v["capex_saline"]),
    )
    saline_mit = with_mitigation(saline, mu_pid=v["mu_pid"], mu_salt=v["mu_salt"])
    return {"land": land, "fpv_fresh": fresh, "fpv_saline": saline, "fpv_saline_mitigated": saline_mit}


KPIS = ["specific_yield_kwh_kwp", "deg_total_pct_yr", "lifetime_energy_mwh", "lcoe_inr_kwh"]


def evaluate(weather: pd.DataFrame, v: dict) -> dict:
    out = {}
    for key, sc in build_scenarios(v).items():
        k = run_scenario(weather, sc).kpis
        for name in KPIS:
            out[f"{key}:{name}"] = k[name]
    for key in ("fpv_fresh", "fpv_saline", "fpv_saline_mitigated"):
        for name in ("specific_yield_kwh_kwp", "lifetime_energy_mwh"):
            out[f"{key}:d_{name}_pct"] = 100.0 * (out[f"{key}:{name}"] / out[f"land:{name}"] - 1.0)
        out[f"{key}:d_deg_total_pct_yr"] = out[f"{key}:deg_total_pct_yr"] - out["land:deg_total_pct_yr"]
    return out


def monte_carlo(weather: pd.DataFrame, n: int = 1000, seed: int = 2024) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        v = {p.name: p.sample(rng) for p in PARAMS}
        rows.append({**v, **evaluate(weather, v)})
    return pd.DataFrame(rows)


def summarize(mc: pd.DataFrame, columns) -> pd.DataFrame:
    q = mc[list(columns)].quantile([0.025, 0.5, 0.975]).T
    q.columns = ["p2.5", "median", "p97.5"]
    q["p_positive"] = (mc[list(columns)] > 0).mean()
    return q


def rank_correlation(mc: pd.DataFrame, output: str) -> pd.Series:
    """Spearman rank correlation of every sampled parameter with ``output``."""
    ranks = mc.rank()
    return pd.Series({p.name: ranks[p.name].corr(ranks[output]) for p in PARAMS}).sort_values(key=np.abs,
                                                                                            ascending=False)


def one_at_a_time(weather: pd.DataFrame, output: str) -> pd.DataFrame:
    """Swing of ``output`` when each parameter moves from its low to its high bound."""
    base = evaluate(weather, {})[output]
    rows = []
    for p in PARAMS:
        lo = evaluate(weather, {p.name: p.low})[output]
        hi = evaluate(weather, {p.name: p.high})[output]
        rows.append({"param": p.name, "label": p.label, "low": lo, "high": hi, "swing": abs(hi - lo)})
    return pd.DataFrame(rows).sort_values("swing", ascending=False).assign(base=base)
