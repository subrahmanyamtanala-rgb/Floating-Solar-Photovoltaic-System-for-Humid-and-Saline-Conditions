"""Levelised cost of energy and water co-benefit."""

from __future__ import annotations

import numpy as np

from .config import Economics


def lcoe(annual_kwh: np.ndarray, dc_kwp: float, econ: Economics) -> float:
    """LCOE in INR/kWh from yearly energy (year 1 first)."""
    years = np.arange(1, len(annual_kwh) + 1)
    disc = (1.0 + econ.discount_rate) ** years
    capex = econ.capex_per_wp * dc_kwp * 1000.0
    opex = econ.opex_per_kwp_yr * dc_kwp * (1.0 + econ.opex_escalation) ** (years - 1)
    return float((capex + np.sum(opex / disc)) / np.sum(np.asarray(annual_kwh) / disc))


def water_saved_m3(dc_kwp: float, econ: Economics) -> float:
    """Reservoir evaporation avoided per year by shading the water surface, m3."""
    area = econ.covered_area_m2_per_kwp * dc_kwp
    return area * econ.evaporation_mm_yr / 1000.0 * econ.evaporation_reduction
