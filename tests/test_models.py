from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from fpv_analysis import default_scenarios, run_scenario, synthetic_weather, with_mitigation
from fpv_analysis import solar
from fpv_analysis.climate import dew_point, rh_from_dewpoint
from fpv_analysis.config import SoilingParams, ThermalParams
from fpv_analysis.degradation import arrhenius, encapsulant_rh, lifetime_energy
from fpv_analysis.electrical import pvwatts_dc, pvwatts_inverter
from fpv_analysis.soiling import soiling_ratio
from fpv_analysis.thermal import condensation, faiman, surface_rh


@pytest.fixture(scope="module")
def weather():
    return synthetic_weather(seed=1)


@pytest.fixture(scope="module")
def results(weather):
    return {s.key: run_scenario(weather, s) for s in default_scenarios()}


def test_solar_noon_zenith_equinox():
    # around the March equinox the noon zenith angle equals the latitude
    t = pd.DatetimeIndex(["2023-03-21 12:00"])
    best = min(
        solar.solar_position(t + pd.Timedelta(minutes=m), 17.69, 83.22, 5.5)["zenith"].iloc[0]
        for m in range(-60, 1)
    )
    assert best == pytest.approx(17.69, abs=1.0)


def test_erbs_conserves_ghi():
    ghi = np.array([800.0, 300.0])
    zen = np.array([30.0, 60.0])
    e0 = np.array([1361.0, 1361.0])
    dni, dhi = solar.erbs(ghi, zen, e0)
    np.testing.assert_allclose(dhi + dni * np.cos(np.radians(zen)), ghi, rtol=1e-9)


def test_spectral_factor_near_one_at_reference():
    m = solar.spectral_modifier_monosi(np.array([1.5]), np.array([1.42]))
    assert m[0] == pytest.approx(1.0, abs=0.01)


def test_humidity_gives_spectral_gain_for_csi():
    dry, humid = solar.spectral_modifier_monosi(np.array([1.5, 1.5]), np.array([0.5, 4.5]))
    assert humid > dry


def test_dew_point_roundtrip():
    t, rh = 30.0, 75.0
    assert rh_from_dewpoint(t, dew_point(t, rh)) == pytest.approx(rh, rel=1e-6)


def test_faiman_more_cooling_with_higher_u():
    land = faiman(np.array([1000.0]), np.array([30.0]), np.array([2.0]), ThermalParams())
    fpv = faiman(np.array([1000.0]), np.array([30.0]), np.array([2.0]), ThermalParams(u0=35.0, u1=8.0))
    assert fpv[0] < land[0]


def test_surface_rh_and_condensation():
    assert surface_rh(np.array([20.0]), np.array([20.0]))[0] == pytest.approx(100.0)
    assert surface_rh(np.array([50.0]), np.array([20.0]))[0] < 30.0
    wet = condensation(np.array([22.0, 20.5, 22.0, 25.0]), np.full(4, 20.0))
    assert wet.tolist() == [False, True, True, False]  # hysteresis keeps it wet at +2 K


def test_pvwatts_stc_and_clipping():
    assert pvwatts_dc(np.array([1000.0]), np.array([25.0]), 1000.0, -0.0035)[0] == pytest.approx(1000.0)
    pac = pvwatts_inverter(np.array([0.0, 500.0, 2000.0]), 833.0)
    assert pac[0] == 0.0 and 0.95 * 500 < pac[1] < 500 and pac[2] == pytest.approx(833.0)


def test_soiling_rain_and_cleaning(weather):
    no_clean = soiling_ratio(weather, SoilingParams(cleaning_interval_days=0, rain_threshold=1e9), 15.0)
    cleaned = soiling_ratio(weather, SoilingParams(), 15.0)
    assert no_clean["soiling_ratio"].iloc[-1] == pytest.approx(SoilingParams().min_ratio)
    assert cleaned["soiling_ratio"].mean() > no_clean["soiling_ratio"].mean()


def test_peck_increases_with_temperature_and_humidity():
    assert arrhenius(np.array([60.0]), 0.79, 25.0)[0] > arrhenius(np.array([40.0]), 0.79, 25.0)[0] > 1.0
    lagged = encapsulant_rh(np.r_[np.full(100, 40.0), np.full(100, 90.0)], 48.0)
    assert 40.0 < lagged[150] < 90.0


def test_lifetime_energy():
    e = lifetime_energy(1000.0, 1.0, 25)
    assert e[0] == 1000.0 and e[-1] == pytest.approx(1000.0 * 0.99**24)


def test_specific_yield_plausible(results):
    for r in results.values():
        assert 1300.0 < r.kpis["specific_yield_kwh_kwp"] < 1800.0
        assert 0.70 < r.kpis["performance_ratio"] < 0.90


def test_fpv_runs_cooler_and_more_humid(results):
    land, fresh = results["land"].kpis, results["fpv_fresh"].kpis
    assert fresh["temp_module_daytime_mean"] < land["temp_module_daytime_mean"] - 1.0
    assert fresh["rh_mean"] > land["rh_mean"]
    assert fresh["energy_mwh"] > land["energy_mwh"]


def test_saline_degrades_fastest(results):
    deg = {k: r.kpis["deg_total_pct_yr"] for k, r in results.items()}
    assert deg["fpv_saline"] > deg["land"] and deg["fpv_saline"] > deg["fpv_fresh"]
    assert results["fpv_saline"].kpis["deg_corrosion_pct_yr"] > results["land"].kpis["deg_corrosion_pct_yr"]


def test_mitigation_reduces_degradation(weather):
    saline = default_scenarios()[2]
    base = run_scenario(weather, saline).kpis
    mit = run_scenario(weather, with_mitigation(saline)).kpis
    assert mit["deg_total_pct_yr"] < base["deg_total_pct_yr"]
    assert mit["lifetime_energy_mwh"] > base["lifetime_energy_mwh"]


def test_more_chloride_more_corrosion(weather):
    saline = default_scenarios()[2]
    hi = replace(saline, degradation=replace(saline.degradation, chloride_deposition=400.0))
    assert run_scenario(weather, hi).kpis["deg_corrosion_pct_yr"] > run_scenario(weather, saline).kpis["deg_corrosion_pct_yr"]


def test_cli_writes_outputs(tmp_path):
    from fpv_analysis.cli import main

    assert main(["--out", str(tmp_path), "--no-sensitivity"]) == 0
    assert (tmp_path / "REPORT.md").exists()
    assert (tmp_path / "summary.csv").exists()
    assert len(list((tmp_path / "figures").glob("*.png"))) == 9


def test_mitigation_levers_are_separate(weather):
    saline = default_scenarios()[2]
    pid_only = with_mitigation(saline, pid=True, salt_mist=False)
    salt_only = with_mitigation(saline, pid=False, salt_mist=True)
    base = run_scenario(weather, saline).kpis
    kp, ks = run_scenario(weather, pid_only).kpis, run_scenario(weather, salt_only).kpis
    assert kp["deg_pid_pct_yr"] < base["deg_pid_pct_yr"] and kp["deg_corrosion_pct_yr"] == base["deg_corrosion_pct_yr"]
    assert ks["deg_corrosion_pct_yr"] < base["deg_corrosion_pct_yr"] and ks["deg_pid_pct_yr"] == base["deg_pid_pct_yr"]


def test_uncertainty_baseline_matches_deterministic(weather):
    from fpv_analysis import uncertainty

    out = uncertainty.evaluate(weather, {})
    for s in default_scenarios():
        assert out[f"{s.key}:lifetime_energy_mwh"] == pytest.approx(run_scenario(weather, s).kpis["lifetime_energy_mwh"])


def test_monte_carlo_is_reproducible(weather):
    from fpv_analysis import uncertainty

    a = uncertainty.monte_carlo(weather, n=3, seed=7)
    b = uncertainty.monte_carlo(weather, n=3, seed=7)
    pd.testing.assert_frame_equal(a, b)


def test_weather_generator_reproduces_normals():
    from fpv_analysis import studies

    chk = studies.weather_check(range(1, 6)).set_index("variable")
    assert abs(chk.loc["temp_mean", "mbe"]) < 0.5
    assert abs(chk.loc["rh_mean", "mbe"]) < 0.5
    assert abs(chk.loc["wind_mean", "mbe"]) < 0.1


def test_humidity_threshold_exists(weather):
    from fpv_analysis import studies

    hum = studies.humidity_sweep(weather)
    thr = studies.thresholds(studies.chloride_sweep(weather), studies.salt_sweep(weather), hum)
    assert 0.5 < thr["dtd_star"] < 6.0
