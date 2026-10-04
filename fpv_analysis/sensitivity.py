"""Sensitivity of a floating plant to humidity and salinity."""

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from .config import Scenario, Site
from .simulation import run_scenario


def humidity_salinity_grid(
    weather: pd.DataFrame,
    scenario: Scenario,
    dewpoint_offsets=(0.0, 0.5, 1.0, 1.5, 2.0, 2.5),
    salinity=(0.25, 0.5, 1.0, 1.5, 2.0),
    site: Site = Site(),
) -> pd.DataFrame:
    """Sweep extra moisture over the water and salt load (as a multiple of the scenario's)."""
    rows = []
    for dtd in dewpoint_offsets:
        for s in salinity:
            sc = replace(
                scenario,
                microclimate=replace(scenario.microclimate, dewpoint_offset=dtd),
                soiling=replace(scenario.soiling, salt_rate=scenario.soiling.salt_rate * s),
                degradation=replace(
                    scenario.degradation,
                    chloride_deposition=scenario.degradation.chloride_deposition * s,
                ),
            )
            k = run_scenario(weather, sc, site).kpis
            rows.append(
                {
                    "dewpoint_offset": dtd,
                    "salinity": s,
                    "specific_yield_kwh_kwp": k["specific_yield_kwh_kwp"],
                    "deg_total_pct_yr": k["deg_total_pct_yr"],
                    "lifetime_energy_mwh": k["lifetime_energy_mwh"],
                    "lcoe_inr_kwh": k["lcoe_inr_kwh"],
                    "time_of_wetness_h": k["time_of_wetness_h"],
                }
            )
    return pd.DataFrame(rows)
