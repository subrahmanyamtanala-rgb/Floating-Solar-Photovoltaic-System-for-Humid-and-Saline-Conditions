"""Long-term degradation driven by heat, humidity and salt.

The annual power-loss rate is the sum of four mechanisms::

    R = R_base + R_TH + R_PID + R_corr        (%/yr)

* ``R_base``  - intrinsic loss (UV, thermal cycling), site independent.
* ``R_TH``    - hydrolysis / delamination, Peck model
  ``k = exp(-Ea/kB (1/T - 1/Tref)) * (RH_enc/RH_ref)^n`` evaluated with the
  hourly module temperature and the encapsulant moisture level.  Moisture in
  the encapsulant follows the module-surface RH with a first-order lag of
  ``moisture_tau_h`` hours (diffusion through the backsheet).
* ``R_PID``   - potential-induced degradation.  Only while the array is under
  voltage (daytime); Arrhenius in module temperature, multiplied by the
  probability that the glass surface is conductive.  Hygroscopic salt lowers
  the RH at which the surface film forms.
* ``R_corr``  - corrosion of metallisation, ribbons and connectors, scaled by
  the ISO 9223 time of wetness (hours with RH > 80 % or dew on the module)
  and the square root of the chloride deposition rate.

Each reference rate is an engineering calibration so that a standard module
on land in a hot-humid Indian climate degrades by about 1 %/yr, in line with
the All-India surveys (NCPRE/NISE, 2014-2018).  Replace with field data where
available.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import DegradationParams

K_BOLTZMANN_EV = 8.617333e-5


def arrhenius(temp_c: np.ndarray, ea: float, ref_c: float) -> np.ndarray:
    t = np.asarray(temp_c) + 273.15
    return np.exp(-ea / K_BOLTZMANN_EV * (1.0 / t - 1.0 / (ref_c + 273.15)))


def encapsulant_rh(surface_rh: np.ndarray, tau_h: float) -> np.ndarray:
    """First-order lag (exponentially weighted mean) of the surface RH."""
    alpha = 1.0 - np.exp(-1.0 / tau_h)
    out = np.empty(len(surface_rh))
    level = float(np.mean(surface_rh))  # start from equilibrium
    for i, value in enumerate(np.asarray(surface_rh)):
        level += alpha * (value - level)
        out[i] = level
    return out


@dataclass
class DegradationResult:
    base: float
    temp_humidity: float
    pid: float
    corrosion: float
    time_of_wetness_h: float
    mean_encapsulant_rh: float

    @property
    def total(self) -> float:
        return self.base + self.temp_humidity + self.pid + self.corrosion

    def as_dict(self) -> dict:
        return {
            "deg_base_pct_yr": self.base,
            "deg_temp_humidity_pct_yr": self.temp_humidity,
            "deg_pid_pct_yr": self.pid,
            "deg_corrosion_pct_yr": self.corrosion,
            "deg_total_pct_yr": self.total,
            "time_of_wetness_h": self.time_of_wetness_h,
            "mean_encapsulant_rh": self.mean_encapsulant_rh,
        }


def annual_degradation(hourly: pd.DataFrame, p: DegradationParams) -> DegradationResult:
    """Annual degradation from an hourly simulation frame.

    ``hourly`` needs ``temp_module``, ``rh_surface``, ``rh`` (air), ``temp_air``,
    ``poa`` and ``wet`` (dew on the glass) and ``salt_mass`` columns.
    """
    tm = hourly["temp_module"].to_numpy()
    rh_enc = encapsulant_rh(hourly["rh_surface"].to_numpy(), p.moisture_tau_h) * p.encapsulant_moisture_factor

    k_th = arrhenius(tm, p.peck_ea, p.ref_temp) * (rh_enc / p.ref_rh) ** p.peck_n
    r_th = p.th_ref_rate * float(np.mean(k_th))

    energised = hourly["poa"].to_numpy() > 50.0
    salt_cover = np.clip(hourly["salt_mass"].to_numpy() / 0.5, 0.0, 1.0)
    rh50 = p.pid_rh50 - p.pid_salt_shift * salt_cover
    leakage = 1.0 / (1.0 + np.exp(-(hourly["rh"].to_numpy() - rh50) / 5.0))
    k_pid = arrhenius(tm, p.pid_ea, p.ref_temp) * leakage * energised
    r_pid = p.pid_ref_rate * float(np.mean(k_pid)) * 8760.0 / max(energised.sum(), 1) * (1.0 - p.pid_mitigation)

    wet = (hourly["rh"].to_numpy() > 80.0) & (hourly["temp_air"].to_numpy() > 0.0) | hourly["wet"].to_numpy()
    tow = float(wet.sum()) * 8760.0 / len(hourly)
    r_corr = (
        p.corrosion_ref_rate
        * (tow / p.tow_ref_h)
        * np.sqrt(p.chloride_deposition / p.chloride_ref)
        * (1.0 - p.salt_mist_mitigation)
    )

    return DegradationResult(
        base=p.base_rate,
        temp_humidity=r_th,
        pid=r_pid,
        corrosion=float(r_corr),
        time_of_wetness_h=tow,
        mean_encapsulant_rh=float(np.mean(rh_enc)),
    )


def lifetime_energy(first_year_kwh: float, rate_pct: float, years: int) -> np.ndarray:
    """Energy for each year of operation under constant linear-relative degradation."""
    y = np.arange(years)
    return first_year_kwh * (1.0 - rate_pct / 100.0) ** y
