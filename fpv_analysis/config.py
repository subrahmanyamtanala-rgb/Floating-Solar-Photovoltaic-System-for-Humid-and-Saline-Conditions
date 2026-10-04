"""Scenario and parameter definitions.

All parameters are plain dataclasses so that a scenario can be copied and
modified with :func:`dataclasses.replace` for sensitivity studies.  Default
values describe a 1 MWp plant near Visakhapatnam (Andhra Pradesh, India), a
hot, humid, coastal site with salt-laden air.  Values that come from the
literature are noted next to the field; values that are engineering
assumptions are marked as such and should be replaced with measured data
whenever it is available.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class Site:
    name: str = "Visakhapatnam, Andhra Pradesh, India"
    latitude: float = 17.69  # deg N
    longitude: float = 83.22  # deg E
    tz_hours: float = 5.5  # IST (UTC+05:30)
    year: int = 2023


@dataclass(frozen=True)
class Microclimate:
    """How the air directly above the array differs from the site weather.

    ``air_coupling`` pulls the air temperature towards the water temperature
    (0 = no water influence, 1 = air equals water temperature).
    ``dewpoint_offset`` raises the dew point to represent extra moisture from
    evaporation.  ``wind_factor`` scales wind speed (open water has lower
    surface roughness than land).
    """

    air_coupling: float = 0.0
    dewpoint_offset: float = 0.0  # degC
    wind_factor: float = 1.0
    albedo: float = 0.20  # ground: ~0.2 for dry soil/grass; water: 0.06-0.08


@dataclass(frozen=True)
class ThermalParams:
    """Faiman module temperature model: Tm = Ta + G / (u0 + u1 * ws)."""

    u0: float = 25.0  # W/m2K   (open-rack default, Faiman 2008 / pvlib)
    u1: float = 6.84  # W/m3sK
    night_sky_loss: float = 40.0  # W/m2 net long-wave loss to the night sky


@dataclass(frozen=True)
class SoilingParams:
    """Dust + salt deposition with rain, dew and manual cleaning."""

    dust_rate: float = 0.15  # g/m2/day dust deposition (assumption)
    salt_rate: float = 0.015  # g/m2/day sea-salt deposition (assumption)
    k_dust: float = 0.035  # transmittance loss per g/m2 of dust
    k_salt: float = 0.060  # transmittance loss per g/m2 of salt crust
    min_ratio: float = 0.70  # floor of the soiling ratio
    rain_threshold: float = 2.0  # mm/day needed to clean
    rain_clean_dust: float = 0.80  # fraction of dust removed by rain (at 20 deg tilt)
    rain_clean_salt: float = 0.95  # salt is water soluble
    deliquescence_rh: float = 75.0  # NaCl deliquescence relative humidity, %
    cementation: float = 0.5  # rain-cleaning penalty on dust once salt has deliquesced
    cleaning_interval_days: int = 15  # manual cleaning interval (0 = never)
    cleaning_efficiency: float = 0.95


@dataclass(frozen=True)
class DegradationParams:
    """Annual power-degradation model (see :mod:`fpv_analysis.degradation`)."""

    base_rate: float = 0.30  # %/yr intrinsic (UV, thermal cycling, LeTID)
    # Temperature-humidity (hydrolysis / delamination) - Peck model
    th_ref_rate: float = 0.10  # %/yr at reference conditions
    peck_ea: float = 0.79  # eV (Peck 1986)
    peck_n: float = 3.0  # humidity exponent (Peck 1986)
    ref_temp: float = 25.0  # degC
    ref_rh: float = 60.0  # %
    moisture_tau_h: float = 48.0  # encapsulant moisture time constant, hours
    # Potential-induced degradation
    pid_ref_rate: float = 0.06  # %/yr at reference conditions
    pid_ea: float = 0.90  # eV (Hacke et al.)
    pid_rh50: float = 70.0  # RH at which the glass surface becomes conductive
    pid_salt_shift: float = 15.0  # RH50 reduction for a full salt film, % RH
    # Reduction factors for module-level mitigations.  These are MODEL ASSUMPTIONS:
    # passing IEC TS 62804-1 (PID) or IEC 61701 (salt mist) qualification does not by
    # itself establish a numerical reduction of field degradation.
    pid_mitigation: float = 0.0  # 0 = standard; e.g. 0.9 for PID-resistant cell/encapsulant
    # Salt-mist / chloride corrosion of cells, ribbons, junction boxes
    corrosion_ref_rate: float = 0.10  # %/yr at TOW_ref and Cl_ref
    tow_ref_h: float = 2500.0  # time of wetness reference, h/yr (ISO 9223 class T4)
    chloride_deposition: float = 30.0  # mg Cl/m2/day at the site
    chloride_ref: float = 60.0  # mg/m2/day (ISO 9223 S1/S2 boundary)
    salt_mist_mitigation: float = 0.0  # 0 = standard; e.g. 0.5 for salt-mist-hardened modules
    encapsulant_moisture_factor: float = 1.0  # <1 for low-permeability (glass-glass, POE) packages


@dataclass(frozen=True)
class SystemDesign:
    dc_kwp: float = 1000.0
    dc_ac_ratio: float = 1.20
    tilt: float = 15.0  # deg
    azimuth: float = 180.0  # deg, south facing
    gamma_pdc: float = -0.0035  # 1/K Pmax temperature coefficient (mono PERC)
    inverter_eff_nom: float = 0.98
    wiring_loss: float = 0.015
    mismatch_loss: float = 0.010
    motion_loss: float = 0.0  # wave-induced orientation mismatch (FPV only)
    lid_loss: float = 0.010  # first-year light induced degradation
    availability: float = 0.99
    dew_optical_loss: float = 0.04  # transmittance loss while condensate is present


@dataclass(frozen=True)
class Economics:
    """Illustrative Indian-market values in INR; replace with project quotes."""

    capex_per_wp: float = 35.0  # INR/Wp (incl. land lease)
    opex_per_kwp_yr: float = 450.0  # INR/kWp/yr (incl. cleaning)
    opex_escalation: float = 0.05
    discount_rate: float = 0.09
    lifetime_years: int = 25
    covered_area_m2_per_kwp: float = 10.0  # FPV footprint on the water
    evaporation_mm_yr: float = 1800.0  # pan evaporation, used for FPV freshwater only
    evaporation_reduction: float = 0.0  # fraction of evaporation avoided under the array


@dataclass(frozen=True)
class Scenario:
    key: str
    label: str
    system: SystemDesign = field(default_factory=SystemDesign)
    microclimate: Microclimate = field(default_factory=Microclimate)
    thermal: ThermalParams = field(default_factory=ThermalParams)
    soiling: SoilingParams = field(default_factory=SoilingParams)
    degradation: DegradationParams = field(default_factory=DegradationParams)
    economics: Economics = field(default_factory=Economics)


def default_scenarios() -> list[Scenario]:
    """The three systems compared in the study."""

    land = Scenario(
        key="land",
        label="Land-mounted PV (coastal)",
    )

    fpv_fresh = Scenario(
        key="fpv_fresh",
        label="Floating PV (freshwater reservoir)",
        system=SystemDesign(
            tilt=12.0,
            wiring_loss=0.020,
            motion_loss=0.007,
            availability=0.985,
        ),
        microclimate=Microclimate(
            air_coupling=0.25, dewpoint_offset=1.0, wind_factor=1.15, albedo=0.07
        ),
        # Within the 31-57 W/m2K heat-loss range reported for FPV by
        # Liu et al. (2018) and Dörenkämper et al. (2021).
        thermal=ThermalParams(u0=35.0, u1=8.0),
        soiling=SoilingParams(dust_rate=0.04, salt_rate=0.010),
        degradation=DegradationParams(chloride_deposition=8.0),
        economics=Economics(
            capex_per_wp=45.0, opex_per_kwp_yr=550.0, evaporation_reduction=0.65
        ),
    )

    fpv_saline = Scenario(
        key="fpv_saline",
        label="Floating PV (saline / near-shore)",
        system=SystemDesign(
            tilt=12.0,
            wiring_loss=0.020,
            motion_loss=0.010,
            availability=0.980,
        ),
        microclimate=Microclimate(
            air_coupling=0.30, dewpoint_offset=1.5, wind_factor=1.25, albedo=0.07
        ),
        thermal=ThermalParams(u0=35.0, u1=8.0),
        soiling=SoilingParams(dust_rate=0.03, salt_rate=0.060),
        degradation=DegradationParams(chloride_deposition=180.0),
        economics=Economics(capex_per_wp=52.0, opex_per_kwp_yr=750.0),
    )

    return [land, fpv_fresh, fpv_saline]


# Cost adders (INR/Wp, INR/kWp/yr) for the mitigation options - illustrative assumptions.
COST_PID = 0.5
COST_SALT_MIST = 1.0
COST_GLASS_GLASS = 2.0
COST_EXTRA_CLEANING = 100.0


def with_mitigation(
    scenario: Scenario,
    pid: bool = True,
    salt_mist: bool = True,
    glass_glass: bool = False,
    cleaning_interval_days: int | None = None,
    mu_pid: float = 0.9,
    mu_salt: float = 0.5,
    moisture_factor: float = 0.8,
    suffix: str = "_mitigated",
) -> Scenario:
    """Same plant with module-level and O&M mitigations.

    * ``pid``: PID-resistant module technology (qualified with IEC TS 62804-1),
      represented by the assumed reduction factor ``mu_pid``.
    * ``salt_mist``: salt-mist-hardened module (qualified with IEC 61701),
      represented by the assumed reduction factor ``mu_salt`` on corrosion.
    * ``glass_glass``: low-permeability glass-glass package, represented by an
      assumed reduction of encapsulant moisture (``moisture_factor``).
    * ``cleaning_interval_days``: a shorter manual-cleaning interval.
    """

    deg, soil, econ = scenario.degradation, scenario.soiling, scenario.economics
    capex, opex = econ.capex_per_wp, econ.opex_per_kwp_yr
    parts = []
    if pid:
        deg = replace(deg, pid_mitigation=mu_pid)
        capex += COST_PID
        parts.append("PID-resistant")
    if salt_mist:
        deg = replace(deg, salt_mist_mitigation=mu_salt)
        capex += COST_SALT_MIST
        parts.append("salt-mist-hardened")
    if glass_glass:
        deg = replace(deg, encapsulant_moisture_factor=moisture_factor)
        capex += COST_GLASS_GLASS
        parts.append("glass-glass")
    if cleaning_interval_days is not None:
        soil = replace(soil, cleaning_interval_days=cleaning_interval_days)
        opex += COST_EXTRA_CLEANING * max(0.0, 15.0 / cleaning_interval_days - 1.0)
        parts.append(f"{cleaning_interval_days}-day cleaning")
    return replace(
        scenario,
        key=scenario.key + suffix,
        label=scenario.label + " + " + ", ".join(parts),
        degradation=deg,
        soiling=soil,
        economics=replace(econ, capex_per_wp=capex, opex_per_kwp_yr=opex),
    )
