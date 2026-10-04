"""Dust and sea-salt soiling under humid conditions.

Daily mass balance for two deposits on the glass:

* dust is only partly removed by rain, and less so on the low tilt typical
  of floating PV;
* sea salt is soluble and washes off easily, but once the air passes the
  NaCl deliquescence humidity (~75 %) the dissolved salt recrystallises as a
  crust that cements dust to the glass and reduces rain cleaning.

The soiling ratio is ``1 - k_dust * m_dust - k_salt * m_salt`` with a floor.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import SoilingParams


def tilt_cleaning_factor(tilt: float) -> float:
    """Relative rain-cleaning effectiveness vs a 20 deg reference tilt."""
    return float(np.clip(np.sin(np.radians(max(tilt, 1.0))) / np.sin(np.radians(20.0)), 0.3, 1.2))


def soiling_ratio(weather: pd.DataFrame, p: SoilingParams, tilt: float) -> pd.DataFrame:
    """Daily soiling ratio and deposit masses, returned at hourly resolution."""
    daily = pd.DataFrame(
        {
            "rain": weather["precip"].resample("D").sum(),
            "rh_max": weather["rh"].resample("D").max(),
            "wind": weather["wind_speed"].resample("D").mean(),
        }
    )
    f_tilt = tilt_cleaning_factor(tilt)
    dust = salt = 0.0
    m_dust, m_salt, ratio = [], [], []
    days_since_clean = 0
    for rain, rh_max, wind in daily.itertuples(index=False):
        # deposition: salt aerosol grows with wind (sea spray), dust is weather independent
        dust += p.dust_rate
        salt += p.salt_rate * (wind / 3.0)
        cemented = rh_max >= p.deliquescence_rh and salt > 0.05
        if rain >= p.rain_threshold:
            dust_eff = p.rain_clean_dust * f_tilt * (1.0 - p.cementation if cemented else 1.0)
            dust *= 1.0 - min(dust_eff, 0.98)
            salt *= 1.0 - min(p.rain_clean_salt * f_tilt, 0.99)
        days_since_clean += 1
        if p.cleaning_interval_days and days_since_clean >= p.cleaning_interval_days:
            dust *= 1.0 - p.cleaning_efficiency
            salt *= 1.0 - p.cleaning_efficiency
            days_since_clean = 0
        m_dust.append(dust)
        m_salt.append(salt)
        ratio.append(max(p.min_ratio, 1.0 - p.k_dust * dust - p.k_salt * salt))

    out = pd.DataFrame({"soiling_ratio": ratio, "dust_mass": m_dust, "salt_mass": m_salt}, index=daily.index)
    return out.reindex(weather.index, method="ffill")
