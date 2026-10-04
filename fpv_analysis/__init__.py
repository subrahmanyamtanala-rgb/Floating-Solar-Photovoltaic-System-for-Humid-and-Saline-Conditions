"""Performance analysis of floating solar PV in humid and saline conditions."""

from .config import Scenario, Site, default_scenarios, with_mitigation
from .climate import load_weather_csv, synthetic_weather
from .simulation import ScenarioResult, run_all, run_scenario

__all__ = [
    "Scenario",
    "ScenarioResult",
    "Site",
    "default_scenarios",
    "load_weather_csv",
    "run_all",
    "run_scenario",
    "synthetic_weather",
    "with_mitigation",
]

__version__ = "1.0.0"
