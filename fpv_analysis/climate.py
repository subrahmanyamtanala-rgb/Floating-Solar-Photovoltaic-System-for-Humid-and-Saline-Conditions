"""Hourly weather for a hot, humid, coastal site.

Two sources are supported:

* :func:`synthetic_weather` builds a reproducible typical year from monthly
  climatology (default: Visakhapatnam).  It is meant for method development
  and comparative studies, not for bankable yield estimates.
* :func:`load_weather_csv` reads measured or TMY data (for example exported
  from NASA POWER, PVGIS or a site weather station).

Both return a DataFrame indexed by local time with the columns
``ghi`` (W/m2), ``temp_air`` (degC), ``rh`` (%), ``wind_speed`` (m/s) and
``precip`` (mm/h).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Microclimate, Site
from .solar import clearsky_ghi_haurwitz, solar_position

# Approximate monthly climatology for Visakhapatnam (IMD normals, rounded).
VIZAG_CLIMATE = pd.DataFrame(
    {
        "temp_mean": [24.6, 26.2, 28.4, 30.4, 32.0, 31.2, 29.6, 29.6, 29.2, 28.0, 26.2, 24.6],
        "temp_range": [9.0, 9.0, 8.0, 6.5, 6.5, 7.0, 6.5, 6.5, 6.5, 6.5, 8.0, 9.0],
        "rh_mean": [70, 70, 73, 75, 73, 74, 78, 79, 80, 77, 71, 68],
        "wind_mean": [2.6, 2.8, 3.2, 3.8, 4.2, 4.5, 4.0, 3.7, 3.0, 2.6, 2.6, 2.5],
        "rain_mm": [10, 10, 10, 20, 60, 100, 140, 150, 180, 230, 80, 15],
        "rain_days": [1, 1, 1, 2, 3, 7, 9, 10, 11, 10, 4, 1],
        "clearness": [0.90, 0.91, 0.90, 0.87, 0.83, 0.71, 0.65, 0.67, 0.69, 0.75, 0.84, 0.88],
    },
    index=range(1, 13),
)


def magnus_es(temp_c):
    """Saturation vapour pressure over water in hPa (Magnus-Tetens)."""
    return 6.112 * np.exp(17.62 * np.asarray(temp_c) / (243.12 + np.asarray(temp_c)))


def dew_point(temp_c, rh):
    gamma = np.log(np.clip(rh, 1e-3, 100.0) / 100.0) + 17.62 * temp_c / (243.12 + temp_c)
    return 243.12 * gamma / (17.62 - gamma)


def rh_from_dewpoint(temp_c, td_c):
    return np.clip(100.0 * magnus_es(td_c) / magnus_es(temp_c), 1.0, 100.0)


def _daily_series(climate: pd.DataFrame, days: pd.DatetimeIndex, column: str) -> np.ndarray:
    """Smoothly interpolate a monthly normal to daily values (mid-month anchors)."""
    anchors = pd.to_datetime([f"{days[0].year}-{m:02d}-15" for m in range(1, 13)])
    # wrap around the year so January and December blend into each other
    x = np.concatenate([[anchors[-1].dayofyear - 365], anchors.dayofyear, [anchors[0].dayofyear + 365]])
    y = climate[column].to_numpy(dtype=float)
    y = np.concatenate([[y[-1]], y, [y[0]]])
    return np.interp(days.dayofyear, x, y)


def synthetic_weather(site: Site = Site(), climate: pd.DataFrame = VIZAG_CLIMATE, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    times = pd.date_range(f"{site.year}-01-01 00:00", f"{site.year}-12-31 23:00", freq="h")
    days = pd.date_range(f"{site.year}-01-01", f"{site.year}-12-31", freq="D")
    n_days = len(days)
    month = days.month.to_numpy()

    # --- rain (daily occurrence, exponential amounts) --------------------------
    days_in_month = days.days_in_month.to_numpy()
    p_rain = climate.loc[month, "rain_days"].to_numpy() / days_in_month
    mean_amount = (climate.loc[month, "rain_mm"] / climate.loc[month, "rain_days"]).to_numpy()
    rainy = rng.random(n_days) < p_rain
    rain_daily = np.where(rainy, rng.exponential(mean_amount), 0.0)

    # --- daily clearness index (AR(1) around the monthly mean) -----------------
    kc_mean = _daily_series(climate, days, "clearness")
    noise = np.zeros(n_days)
    for i in range(1, n_days):
        noise[i] = 0.6 * noise[i - 1] + rng.normal(0.0, 0.08)
    kc = kc_mean + noise - np.where(rainy, 0.25, 0.0)
    kc = np.clip(kc, 0.12, 0.98)

    # --- daily temperature, range, dew point, wind -----------------------------
    t_noise = np.zeros(n_days)
    for i in range(1, n_days):
        t_noise[i] = 0.7 * t_noise[i - 1] + rng.normal(0.0, 0.6)
    t_mean = _daily_series(climate, days, "temp_mean") + t_noise - np.where(rainy, 1.5, 0.0)
    t_range = _daily_series(climate, days, "temp_range") * (0.55 + 0.45 * kc / kc_mean)
    rh_mean = _daily_series(climate, days, "rh_mean")
    td = dew_point(_daily_series(climate, days, "temp_mean"), rh_mean) + rng.normal(0.0, 0.8, n_days)
    td = np.where(rainy, td + 0.8, td)
    # mean-preserving log-normal day-to-day variability
    wind_mean = _daily_series(climate, days, "wind_mean") * rng.lognormal(-0.5 * 0.2**2, 0.2, n_days)

    # --- expand to hourly -------------------------------------------------------
    day_idx = (times.normalize() - times[0].normalize()).days.to_numpy()
    hour = times.hour.to_numpy()

    mid = times + pd.Timedelta(minutes=30)  # hourly values represent the hour mean
    sun = solar_position(mid, site.latitude, site.longitude, site.tz_hours)
    ghi_clear = clearsky_ghi_haurwitz(sun["zenith"].to_numpy())
    # broken-cloud variability grows as the day gets cloudier
    hourly_var = kc[day_idx] * (1.0 + rng.normal(0.0, 0.25, len(times)) * (1.0 - kc[day_idx]))
    ghi = ghi_clear * np.clip(hourly_var, 0.05, 1.05)

    # temperature: maximum ~14:00, minimum ~05:00 (two-part cosine)
    phase = np.where(
        (hour >= 5) & (hour < 14),
        np.cos(np.pi * (hour - 14) / 9.0),
        np.cos(np.pi * ((hour - 14) % 24) / 15.0),
    )
    temp_air = t_mean[day_idx] + 0.5 * t_range[day_idx] * phase
    # Holding Td fixed over a day makes the mean of the hourly RH exceed the RH implied by
    # the daily means (RH is convex in T).  Shift Td per month until the monthly mean RH
    # matches the normal.
    month_h = times.month.to_numpy()
    for _ in range(3):
        rh = rh_from_dewpoint(temp_air, np.minimum(td[day_idx], temp_air))
        target = climate.loc[month_h, "rh_mean"].to_numpy(dtype=float)
        bias = pd.Series(rh - target).groupby(month_h).mean()
        slope = 17.62 * 243.12 / (243.12 + td) ** 2 * climate.loc[month, "rh_mean"].to_numpy(dtype=float)
        td = td - bias.loc[month].to_numpy() / slope
    rh = rh_from_dewpoint(temp_air, np.minimum(td[day_idx], temp_air))

    # wind: afternoon sea breeze
    breeze = 1.0 + 0.35 * np.sin(np.pi * (hour - 9) / 12.0) * ((hour >= 9) & (hour <= 21))
    breeze = breeze / breeze[:24].mean()  # keep the daily mean equal to the normal
    wind = np.clip(wind_mean[day_idx] * breeze * rng.lognormal(-0.5 * 0.15**2, 0.15, len(times)), 0.3, None)

    # rain falls in a 3-hour afternoon/evening block
    start = rng.integers(13, 20, n_days)
    precip = np.zeros(len(times))
    in_block = (hour >= start[day_idx]) & (hour < start[day_idx] + 3)
    precip[in_block] = rain_daily[day_idx][in_block] / 3.0

    return pd.DataFrame(
        {"ghi": ghi, "temp_air": temp_air, "rh": rh, "wind_speed": wind, "precip": precip},
        index=times,
    )


def load_weather_csv(path: str) -> pd.DataFrame:
    """Load hourly weather from CSV with a timestamp column and the standard columns."""
    df = pd.read_csv(path, parse_dates=[0], index_col=0)
    required = {"ghi", "temp_air", "rh", "wind_speed"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"weather file is missing columns: {sorted(missing)}")
    if "precip" not in df.columns:
        df["precip"] = 0.0
    return df[["ghi", "temp_air", "rh", "wind_speed", "precip"]].astype(float)


def apply_microclimate(weather: pd.DataFrame, micro: Microclimate) -> pd.DataFrame:
    """Air conditions directly above the array (over water for FPV)."""
    out = weather.copy()
    td = dew_point(weather["temp_air"].to_numpy(), weather["rh"].to_numpy())
    if micro.air_coupling > 0.0:
        # Water temperature follows the 30-day running mean of air temperature
        daily = weather["temp_air"].resample("D").mean()
        water = daily.rolling(30, min_periods=1, center=True).mean() + 0.5
        water_h = water.reindex(weather.index, method="ffill").to_numpy()
        out["temp_water"] = water_h
        out["temp_air"] = weather["temp_air"] + micro.air_coupling * (water_h - weather["temp_air"])
    td = td + micro.dewpoint_offset
    out["rh"] = rh_from_dewpoint(out["temp_air"].to_numpy(), np.minimum(td, out["temp_air"].to_numpy()))
    out["wind_speed"] = weather["wind_speed"] * micro.wind_factor
    out["temp_dew"] = np.minimum(td, out["temp_air"].to_numpy())
    return out
