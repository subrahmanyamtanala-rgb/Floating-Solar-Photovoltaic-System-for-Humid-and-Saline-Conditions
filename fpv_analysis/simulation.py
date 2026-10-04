"""End-to-end hourly performance simulation of one scenario."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import solar
from .climate import apply_microclimate
from .config import Scenario, Site
from .degradation import DegradationResult, annual_degradation, lifetime_energy
from .economics import lcoe, water_saved_m3
from .electrical import pvwatts_dc, pvwatts_inverter
from .soiling import soiling_ratio
from .thermal import condensation, faiman, surface_rh


@dataclass
class ScenarioResult:
    scenario: Scenario
    hourly: pd.DataFrame
    losses: dict
    degradation: DegradationResult
    kpis: dict
    lifetime_kwh: np.ndarray

    @property
    def monthly(self) -> pd.DataFrame:
        h = self.hourly
        m = pd.DataFrame(
            {
                "energy_kwh": h["p_ac"].resample("MS").sum(),
                "poa_kwh_m2": h["poa"].resample("MS").sum() / 1000.0,
                "temp_module_daytime_mean": h["temp_module"].where(h["poa"] > 50).resample("MS").mean(),
                "soiling_ratio": h["soiling_ratio"].resample("MS").mean(),
            }
        )
        m["performance_ratio"] = m["energy_kwh"] / (self.scenario.system.dc_kwp * m["poa_kwh_m2"])
        return m


def run_scenario(weather: pd.DataFrame, scenario: Scenario, site: Site = Site()) -> ScenarioResult:
    sysd = scenario.system
    w = apply_microclimate(weather, scenario.microclimate)

    mid = w.index + pd.Timedelta(minutes=30)
    sun = solar.solar_position(mid, site.latitude, site.longitude, site.tz_hours)
    zen, azi, e0 = (sun[c].to_numpy() for c in ("zenith", "azimuth", "dni_extra"))
    ghi = w["ghi"].to_numpy()
    dni, dhi = solar.erbs(ghi, zen, e0)
    poa = solar.poa_hay_davies(ghi, dni, dhi, e0, zen, azi, sysd.tilt, sysd.azimuth, scenario.microclimate.albedo)
    poa_global = (poa["poa_beam"] + poa["poa_sky"] + poa["poa_ground"]).to_numpy()

    # optical: incidence angle, spectrum (humidity), soiling (dust + salt), dew
    iam = solar.iam_ashrae(poa["aoi"].to_numpy())
    g_iam = poa["poa_beam"].to_numpy() * iam + poa["poa_sky"].to_numpy() * 0.95 + poa["poa_ground"].to_numpy() * 0.95
    pw = solar.precipitable_water(w["temp_air"].to_numpy(), w["rh"].to_numpy())
    spec = solar.spectral_modifier_monosi(solar.relative_airmass(zen), pw)
    g_spec = g_iam * spec
    soil = soiling_ratio(w, scenario.soiling, sysd.tilt)
    g_soil = g_spec * soil["soiling_ratio"].to_numpy()

    temp_module = faiman(poa_global, w["temp_air"].to_numpy(), w["wind_speed"].to_numpy(), scenario.thermal)
    td = w["temp_dew"].to_numpy()
    wet = condensation(temp_module, td)
    g_eff = g_soil * np.where(wet, 1.0 - sysd.dew_optical_loss, 1.0)

    # electrical
    pdc_ref = pvwatts_dc(g_eff, np.full_like(g_eff, 25.0), sysd.dc_kwp, sysd.gamma_pdc)
    pdc_temp = pvwatts_dc(g_eff, temp_module, sysd.dc_kwp, sysd.gamma_pdc)
    dc_derate = (1 - sysd.wiring_loss) * (1 - sysd.mismatch_loss) * (1 - sysd.motion_loss) * (1 - sysd.lid_loss)
    pdc = pdc_temp * dc_derate
    pac0 = sysd.dc_kwp / sysd.dc_ac_ratio
    pac_inv = pvwatts_inverter(pdc, pac0, sysd.inverter_eff_nom)
    pac = pac_inv * sysd.availability

    hourly = pd.DataFrame(
        {
            "ghi": ghi,
            "poa": poa_global,
            "g_eff": g_eff,
            "temp_air": w["temp_air"].to_numpy(),
            "temp_dew": td,
            "rh": w["rh"].to_numpy(),
            "wind_speed": w["wind_speed"].to_numpy(),
            "precip": w["precip"].to_numpy(),
            "temp_module": temp_module,
            "rh_surface": surface_rh(temp_module, td),
            "wet": wet,
            "precipitable_water_cm": pw,
            "spectral_factor": spec,
            "soiling_ratio": soil["soiling_ratio"].to_numpy(),
            "dust_mass": soil["dust_mass"].to_numpy(),
            "salt_mass": soil["salt_mass"].to_numpy(),
            "p_dc": pdc,
            "p_ac": pac,
        },
        index=w.index,
    )

    def e(x):
        return float(np.sum(x))

    stages = [
        ("Incidence angle (IAM)", e(poa_global), e(g_iam)),
        ("Spectral (humidity)", e(g_iam), e(g_spec)),
        ("Soiling (dust + salt)", e(g_spec), e(g_soil)),
        ("Dew / condensation", e(g_soil), e(g_eff)),
        ("Module temperature", e(pdc_ref), e(pdc_temp)),
        ("DC wiring, mismatch, motion, LID", e(pdc_temp), e(pdc)),
        ("Inverter and clipping", e(pdc), e(pac_inv)),
        ("Availability", e(pac_inv), e(pac)),
    ]
    losses = {name: 100.0 * (1.0 - after / before) for name, before, after in stages}

    deg = annual_degradation(hourly, scenario.degradation)
    econ = scenario.economics
    energy = e(pac)
    life = lifetime_energy(energy, deg.total, econ.lifetime_years)
    poa_kwh = e(poa_global) / 1000.0
    day = poa_global > 50.0

    kpis = {
        "scenario": scenario.key,
        "label": scenario.label,
        "energy_mwh": energy / 1000.0,
        "specific_yield_kwh_kwp": energy / sysd.dc_kwp,
        "performance_ratio": energy / (sysd.dc_kwp * poa_kwh),
        "cuf_dc_pct": 100.0 * energy / (sysd.dc_kwp * 8760.0),
        "ghi_kwh_m2": e(ghi) / 1000.0,
        "poa_kwh_m2": poa_kwh,
        "temp_module_daytime_mean": float(np.mean(temp_module[day])),
        "temp_module_max": float(np.max(temp_module)),
        "temp_module_minus_air_daytime": float(np.mean(temp_module[day] - hourly["temp_air"].to_numpy()[day])),
        "rh_mean": float(hourly["rh"].mean()),
        "dew_hours": int(wet.sum()),
        "soiling_ratio_mean": float(np.mean(soil["soiling_ratio"].to_numpy()[day])),
        **{f"loss_{k}": v for k, v in losses.items()},
        **deg.as_dict(),
        "lifetime_energy_mwh": float(life.sum()) / 1000.0,
        "year25_capacity_pct": 100.0 * (1.0 - deg.total / 100.0) ** (econ.lifetime_years - 1),
        "lcoe_inr_kwh": lcoe(life, sysd.dc_kwp, econ),
        "water_saved_m3_yr": water_saved_m3(sysd.dc_kwp, econ),
    }
    return ScenarioResult(scenario, hourly, losses, deg, kpis, life)


def run_all(weather: pd.DataFrame, scenarios, site: Site = Site()) -> list[ScenarioResult]:
    return [run_scenario(weather, s, site) for s in scenarios]
