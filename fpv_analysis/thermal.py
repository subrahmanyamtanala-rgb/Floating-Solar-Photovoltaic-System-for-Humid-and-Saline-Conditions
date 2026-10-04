"""Module temperature and surface-moisture models."""

from __future__ import annotations

import numpy as np

from .climate import magnus_es
from .config import ThermalParams


def faiman(poa: np.ndarray, temp_air: np.ndarray, wind_speed: np.ndarray, p: ThermalParams) -> np.ndarray:
    """Faiman (2008) module temperature, degC.

    At night the module radiates to the sky and runs a few kelvin below
    ambient, which is what drives dew formation on the glass.
    """
    u = p.u0 + p.u1 * np.asarray(wind_speed)
    heat = np.where(np.asarray(poa) < 50.0, np.asarray(poa) - p.night_sky_loss, poa)
    return np.asarray(temp_air) + heat / u


def surface_rh(temp_module: np.ndarray, temp_dew: np.ndarray) -> np.ndarray:
    """Relative humidity of the air layer in contact with the module, %.

    Uses the ambient vapour pressure and the module temperature: a hot module
    is "dry", a module colder than the dew point is wet (100 %).
    """
    return np.clip(100.0 * magnus_es(temp_dew) / magnus_es(temp_module), 0.0, 100.0)


def condensation(
    temp_module: np.ndarray, temp_dew: np.ndarray, form_margin: float = 1.0, dry_margin: float = 4.0
) -> np.ndarray:
    """True where dew is present on the glass.

    Dew forms once the module is within ``form_margin`` K of the dew point and
    persists, after sunrise, until the module is ``dry_margin`` K above it.
    """
    depression = np.asarray(temp_module) - np.asarray(temp_dew)
    wet = np.zeros(len(depression), dtype=bool)
    state = False
    for i, d in enumerate(depression):
        if d < form_margin:
            state = True
        elif d > dry_margin:
            state = False
        wet[i] = state
    return wet
