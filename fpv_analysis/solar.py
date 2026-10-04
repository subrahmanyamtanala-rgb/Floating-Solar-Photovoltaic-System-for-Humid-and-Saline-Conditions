"""Solar geometry, irradiance decomposition, transposition and spectral effects."""

from __future__ import annotations

import numpy as np
import pandas as pd

SOLAR_CONSTANT = 1361.0  # W/m2


def _day_angle(doy: np.ndarray) -> np.ndarray:
    return 2.0 * np.pi * (doy - 1) / 365.0


def declination(doy: np.ndarray) -> np.ndarray:
    """Solar declination in radians (Spencer, 1971)."""
    b = _day_angle(doy)
    return (
        0.006918
        - 0.399912 * np.cos(b)
        + 0.070257 * np.sin(b)
        - 0.006758 * np.cos(2 * b)
        + 0.000907 * np.sin(2 * b)
        - 0.002697 * np.cos(3 * b)
        + 0.00148 * np.sin(3 * b)
    )


def equation_of_time(doy: np.ndarray) -> np.ndarray:
    """Equation of time in minutes (Spencer, 1971)."""
    b = _day_angle(doy)
    return 229.18 * (
        0.000075
        + 0.001868 * np.cos(b)
        - 0.032077 * np.sin(b)
        - 0.014615 * np.cos(2 * b)
        - 0.040849 * np.sin(2 * b)
    )


def extraterrestrial(doy: np.ndarray) -> np.ndarray:
    """Extraterrestrial normal irradiance, W/m2."""
    b = _day_angle(doy)
    return SOLAR_CONSTANT * (
        1.00011
        + 0.034221 * np.cos(b)
        + 0.00128 * np.sin(b)
        + 0.000719 * np.cos(2 * b)
        + 0.000077 * np.sin(2 * b)
    )


def solar_position(times: pd.DatetimeIndex, lat: float, lon: float, tz_hours: float) -> pd.DataFrame:
    """Zenith and azimuth (deg, azimuth clockwise from north) for local times."""
    doy = times.dayofyear.to_numpy()
    hour = times.hour.to_numpy() + times.minute.to_numpy() / 60.0
    solar_time = hour + (4.0 * (lon - 15.0 * tz_hours) + equation_of_time(doy)) / 60.0
    omega = np.radians(15.0 * (solar_time - 12.0))
    dec = declination(doy)
    phi = np.radians(lat)

    cosz = np.sin(phi) * np.sin(dec) + np.cos(phi) * np.cos(dec) * np.cos(omega)
    zenith = np.degrees(np.arccos(np.clip(cosz, -1.0, 1.0)))
    azimuth = np.degrees(
        np.arctan2(np.sin(omega), np.cos(omega) * np.sin(phi) - np.tan(dec) * np.cos(phi))
    ) + 180.0
    return pd.DataFrame(
        {"zenith": zenith, "azimuth": azimuth, "dni_extra": extraterrestrial(doy)},
        index=times,
    )


def clearsky_ghi_haurwitz(zenith: np.ndarray) -> np.ndarray:
    """Haurwitz (1945) clear-sky global horizontal irradiance, W/m2."""
    cosz = np.cos(np.radians(zenith))
    ghi = np.zeros_like(cosz)
    up = cosz > 0.01
    ghi[up] = 1098.0 * cosz[up] * np.exp(-0.059 / cosz[up])
    return ghi


def erbs(ghi: np.ndarray, zenith: np.ndarray, dni_extra: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Split GHI into DNI and DHI with the Erbs et al. (1982) correlation."""
    cosz = np.cos(np.radians(zenith))
    up = cosz > 0.065  # sun more than ~3.7 deg above the horizon
    kt = np.zeros_like(ghi)
    kt[up] = np.clip(ghi[up] / (dni_extra[up] * cosz[up]), 0.0, 1.0)

    df = np.where(
        kt <= 0.22,
        1.0 - 0.09 * kt,
        np.where(
            kt <= 0.80,
            0.9511 - 0.1604 * kt + 4.388 * kt**2 - 16.638 * kt**3 + 12.336 * kt**4,
            0.165,
        ),
    )
    dhi = np.where(up, ghi * df, ghi)
    dni = np.zeros_like(ghi)
    dni[up] = (ghi[up] - dhi[up]) / cosz[up]
    return np.clip(dni, 0.0, None), np.clip(dhi, 0.0, None)


def angle_of_incidence(zenith, azimuth, tilt: float, surface_azimuth: float) -> np.ndarray:
    z, a = np.radians(zenith), np.radians(azimuth)
    b, g = np.radians(tilt), np.radians(surface_azimuth)
    cos_aoi = np.cos(z) * np.cos(b) + np.sin(z) * np.sin(b) * np.cos(a - g)
    return np.degrees(np.arccos(np.clip(cos_aoi, -1.0, 1.0)))


def iam_ashrae(aoi: np.ndarray, b0: float = 0.05) -> np.ndarray:
    """ASHRAE incidence-angle modifier for glass-covered modules."""
    cos_aoi = np.cos(np.radians(aoi))
    iam = np.zeros_like(cos_aoi)
    ok = cos_aoi > 0.0
    iam[ok] = 1.0 - b0 * (1.0 / cos_aoi[ok] - 1.0)
    return np.clip(iam, 0.0, 1.0)


def poa_hay_davies(
    ghi, dni, dhi, dni_extra, zenith, azimuth, tilt: float, surface_azimuth: float, albedo: float
) -> pd.DataFrame:
    """Plane-of-array irradiance with the Hay & Davies (1980) sky model."""
    aoi = angle_of_incidence(zenith, azimuth, tilt, surface_azimuth)
    cos_aoi = np.clip(np.cos(np.radians(aoi)), 0.0, None)
    cosz = np.maximum(np.cos(np.radians(zenith)), 0.087)  # limit Rb near sunrise/sunset
    rb = cos_aoi / cosz
    ai = np.clip(dni / dni_extra, 0.0, 1.0)
    beta = np.radians(tilt)

    beam = dni * cos_aoi
    sky = dhi * (ai * rb + (1.0 - ai) * (1.0 + np.cos(beta)) / 2.0)
    ground = ghi * albedo * (1.0 - np.cos(beta)) / 2.0
    return pd.DataFrame(
        {"poa_beam": beam, "poa_sky": sky, "poa_ground": ground, "aoi": aoi}
    )


def relative_airmass(zenith: np.ndarray) -> np.ndarray:
    """Kasten & Young (1989) relative air mass; NaN when the sun is down."""
    z = np.asarray(zenith, dtype=float)
    am = np.full_like(z, np.nan)
    up = z < 90.0
    am[up] = 1.0 / (np.cos(np.radians(z[up])) + 0.50572 * (96.07995 - z[up]) ** -1.6364)
    return am


def precipitable_water(temp_air: np.ndarray, rh: np.ndarray) -> np.ndarray:
    """Precipitable water in cm from surface T and RH (Gueymard, 1994)."""
    t = np.asarray(temp_air, dtype=float) + 273.15
    theta = t / 273.15
    pw = 0.1 * (0.4976 + 1.5265 * theta + np.exp(13.6897 * theta - 14.9188 * theta**3)) * (
        216.7 * rh / (100.0 * t) * np.exp(22.330 - 49.140 * (100.0 / t) - 10.922 * (100.0 / t) ** 2 - 0.39015 * t / 100.0)
    )
    return np.maximum(pw, 0.1)


# First Solar spectral correction coefficients for monocrystalline silicon
# (Lee & Panchula, 2016), as distributed with pvlib.
_FS_MONOSI = (0.85914, -0.020880, -0.0058853, 0.12029, 0.026814, -0.0017810)


def spectral_modifier_monosi(airmass: np.ndarray, pw_cm: np.ndarray) -> np.ndarray:
    """Spectral mismatch factor of c-Si as a function of air mass and water vapour.

    Humid air absorbs mainly in infrared bands where silicon responds weakly,
    which shifts the spectrum towards the wavelengths c-Si converts best: in
    humid climates the factor is slightly above 1.
    """
    am = np.clip(np.nan_to_num(airmass, nan=10.0), 1.0, 10.0)
    pw = np.clip(pw_cm, 0.1, 8.0)
    c1, c2, c3, c4, c5, c6 = _FS_MONOSI
    m = c1 + c2 * am + c3 * pw + c4 * np.sqrt(am) + c5 * np.sqrt(pw) + c6 * am / np.sqrt(pw)
    return np.clip(m, 0.8, 1.1)
