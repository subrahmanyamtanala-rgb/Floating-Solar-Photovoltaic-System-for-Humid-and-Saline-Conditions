"""DC and AC power (PVWatts-style models)."""

from __future__ import annotations

import numpy as np


def pvwatts_dc(g_eff: np.ndarray, temp_cell: np.ndarray, pdc0: float, gamma: float) -> np.ndarray:
    """DC power in kW for effective irradiance (W/m2) and cell temperature."""
    return np.clip(pdc0 * g_eff / 1000.0 * (1.0 + gamma * (temp_cell - 25.0)), 0.0, None)


def pvwatts_inverter(pdc: np.ndarray, pac0: float, eta_nom: float = 0.98, eta_ref: float = 0.9637) -> np.ndarray:
    """PVWatts inverter efficiency curve with clipping at the AC rating."""
    pdc0 = pac0 / eta_nom
    zeta = np.clip(pdc / pdc0, 1e-6, None)
    eta = eta_nom / eta_ref * (-0.0162 * zeta - 0.0059 / zeta + 0.9858)
    pac = np.where(pdc > 0.0, pdc * eta, 0.0)
    return np.clip(pac, 0.0, pac0)
