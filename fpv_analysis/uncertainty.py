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
    basis: str = "Assumption"  # justification of the range (LaTeX, may contain \\cite)

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
    Param("th_ref", "Peck reference rate $R_{TH}^{ref}$ (\\%/yr)", 0.06, 0.14,
          basis="Calibration constant; land total $\\approx$0.9--1\\%/yr~\\cite{dubey2014}; $\\pm$40\\%"),
    Param("pid_ref", "PID reference rate $R_{PID}^{ref}$ (\\%/yr)", 0.03, 0.09,
          basis="Calibration constant; $\\pm$50\\%"),
    Param("corr_ref", "Corrosion reference rate $R_C^{ref}$ (\\%/yr)", 0.05, 0.15,
          basis="Calibration constant; $\\pm$50\\%"),
    Param("dew_loss", "Dew optical loss", 0.0, 0.06,
          basis="Assumption; effect shown negligible (Sec.~\\ref{sec:dew})"),
    Param("k_dust", "Dust loss coefficient $k_d$ (m$^2$/g)", 0.025, 0.045,
          basis="Order of magnitude of dust-soiling studies~\\cite{sarver2013}"),
    Param("k_salt", "Salt loss coefficient $k_s$ (m$^2$/g)", 0.03, 0.09,
          basis="Assumption; no measured salt-crust transmittance"),
    Param("cementation", "Deliquescence cementation factor", 0.25, 0.75,
          basis="Assumption; salt crusts observed on coastal FPV~\\cite{ahmad2026}"),
    # land plant
    Param("u0_land", "Land $U_0$ (W/m$^2$K)", 22.0, 29.0,
          basis="Around open-rack Faiman defaults~\\cite{faiman2008}"),
    Param("u1_land", "Land $U_1$ (W\\,s/m$^3$K)", 4.5, 8.0,
          basis="Around open-rack Faiman defaults~\\cite{faiman2008}"),
    Param("dust_land", "Land dust deposition (multiplier)", 0.5, 2.0, log=True,
          basis="Assumption; no site measurement"),
    Param("cl_land", "Land chloride deposition (multiplier)", 0.5, 2.0, log=True,
          basis="15--60 mg/m$^2$/day, ISO~9223 class S1~\\cite{iso9223}"),
    # floating plants
    # wide enough to include FPV designs with no cooling advantage over open racks
    Param("u0_fpv", "FPV $U_0$ (W/m$^2$K)", 22.0, 45.0,
          basis="Measured FPV values~\\cite{nysted2024,wu2024,dorenkamper2021,lindholm2021}"),
    Param("u1_fpv", "FPV $U_1$ (W\\,s/m$^3$K)", 2.5, 10.0,
          basis="Measured wind terms~\\cite{dorenkamper2024,nysted2024}"),
    Param("wind_fpv", "Over-water wind factor $k_v$", 1.0, 1.35,
          basis="Assumption (lower surface roughness)"),
    Param("motion", "Wave-motion mismatch", 0.003, 0.015,
          basis="Assumption"),
    Param("alpha_fresh", "Air--water coupling $\\alpha$ (fresh)", 0.10, 0.40,
          basis="Assumption"),
    Param("dtd_fresh", "Dew-point rise $\\Delta T_d$ (fresh, K)", 0.5, 1.5,
          basis="Assumption; threshold analysis in Sec.~\\ref{sec:thresholds}"),
    Param("alpha_saline", "Air--water coupling $\\alpha$ (saline)", 0.15, 0.45,
          basis="Assumption"),
    Param("dtd_saline", "Dew-point rise $\\Delta T_d$ (saline, K)", 1.0, 2.0,
          basis="Assumption"),
    Param("salt_saline", "Saline salt deposition (multiplier)", 0.5, 2.0, log=True,
          basis="Assumption; threshold analysis in Sec.~\\ref{sec:thresholds}"),
    Param("cl_saline", "Saline chloride deposition (multiplier)", 0.5, 2.0, log=True,
          basis="90--360 mg/m$^2$/day, ISO~9223 classes S2--S3~\\cite{iso9223}"),
    # mitigation (assumed reduction factors)
    Param("mu_pid", "PID mitigation $\\mu_{PID}$", 0.5, 0.95,
          basis="Assumption (Table~\\ref{tab:mitstd}); not implied by IEC~TS~62804-1"),
    Param("mu_salt", "Salt-mist mitigation $\\mu_C$", 0.2, 0.7,
          basis="Assumption (Table~\\ref{tab:mitstd}); not implied by IEC~61701"),
    # costs and finance
    Param("capex_land", "Land CAPEX (INR/Wp)", 30.0, 40.0,
          basis="Illustrative Indian-market range"),
    Param("capex_fresh", "FPV fresh CAPEX (INR/Wp)", 38.0, 52.0,
          basis="Illustrative Indian-market range"),
    Param("capex_saline", "FPV saline CAPEX (INR/Wp)", 44.0, 60.0,
          basis="Illustrative Indian-market range"),
    Param("discount", "Discount rate", 0.06, 0.12,
          basis="Typical range for utility-scale PV finance"),
    Param("escalation", "O\\&M escalation", 0.02, 0.07,
          basis="Assumption"),
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
        "discount": land.economics.discount_rate,
        "escalation": land.economics.opex_escalation,
    }


def build_scenarios(v: dict) -> dict[str, Scenario]:
    """Scenarios for one parameter vector ``v`` (missing keys fall back to the baseline)."""
    v = {**baseline_values(), **v}
    land, fresh, saline = default_scenarios()

    def common(s: Scenario) -> Scenario:
        return replace(
            s,
            economics=replace(s.economics, discount_rate=v["discount"], opex_escalation=v["escalation"]),
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


_WEATHER = None  # set in worker processes


def _init_worker(weather):
    global _WEATHER
    _WEATHER = weather


def _evaluate_sample(v):
    return {**v, **evaluate(_WEATHER, v)}


def draw_samples(n: int, seed: int) -> list[dict]:
    """Parameter vectors in a fixed order, so the first k of n samples equal an n=k run."""
    rng = np.random.default_rng(seed)
    return [{p.name: p.sample(rng) for p in PARAMS} for _ in range(n)]


def monte_carlo(weather: pd.DataFrame, n: int = 1000, seed: int = 2024, workers: int = 1) -> pd.DataFrame:
    samples = draw_samples(n, seed)
    if workers <= 1:
        rows = [{**v, **evaluate(weather, v)} for v in samples]
    else:
        import multiprocessing as mp

        with mp.get_context("fork").Pool(workers, initializer=_init_worker, initargs=(weather,)) as pool:
            rows = pool.map(_evaluate_sample, samples, chunksize=max(1, n // (8 * workers)))
    return pd.DataFrame(rows)


def convergence(mc: pd.DataFrame, columns, sizes=(250, 500, 1000, 2000, 5000), n_boot: int = 500,
                seed: int = 7) -> pd.DataFrame:
    """Median and 95 % interval on nested prefixes of one Monte Carlo run, with bootstrap SEs."""
    rng = np.random.default_rng(seed)
    rows = []
    for n in sizes:
        if n > len(mc):
            continue
        sub = mc.iloc[:n]
        for col in columns:
            x = sub[col].to_numpy()
            q = np.percentile(x, [2.5, 50, 97.5])
            boot = np.percentile(rng.choice(x, size=(n_boot, n), replace=True), [2.5, 50, 97.5], axis=1)
            se = boot.std(axis=1, ddof=1)
            rows.append({"n": n, "output": col, "p2.5": q[0], "median": q[1], "p97.5": q[2],
                         "se_p2.5": se[0], "se_median": se[1], "se_p97.5": se[2], "p_positive": float((x > 0).mean())})
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
