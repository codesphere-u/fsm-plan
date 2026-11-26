"""Eawag-Sandec Fecal Sludge Management (FSM): pit fill, emptying fleet, drying beds & WHO reuse."""

from __future__ import annotations

import math
from dataclasses import dataclass

# Accumulation rates (L / person / year) from Eawag-Sandec / WHO FSM guidelines
_ACCUM_RATE_L_PERSON_YR: dict[str, float] = {
    "dry_pit_nondegradable_wiping": 60.0,
    "dry_pit_degradable_wiping": 40.0,
    "wet_pit_vip": 40.0,
    "pour_flush_septic_tank": 35.0,
    "lined_public_latrine": 80.0,
}


@dataclass(frozen=True)
class PitFillEstimate:
    """Household or communal containment fill-time and emptying cadence."""

    containment_type: str
    effective_volume_m3: float
    users: int
    annual_accumulation_m3: float
    years_to_full: float
    recommended_emptying_interval_years: float


def estimate_pit_fill_years(
    *,
    effective_volume_m3: float,
    users: int,
    containment_type: str = "wet_pit_vip",
    solid_waste_trash_factor: float = 1.15,
) -> PitFillEstimate:
    """Estimate pit-latrine or septic-tank fill time accounting for municipal trash ingress."""
    if effective_volume_m3 <= 0 or users <= 0:
        raise ValueError("effective_volume_m3 and users must be strictly positive")
    key = containment_type.strip().lower()
    if key not in _ACCUM_RATE_L_PERSON_YR:
        raise KeyError(f"Unknown containment_type '{containment_type}'. Options: {sorted(_ACCUM_RATE_L_PERSON_YR)}")
    rate_l = _ACCUM_RATE_L_PERSON_YR[key] * max(1.0, solid_waste_trash_factor)
    annual_m3 = (users * rate_l) / 1000.0
    years_full = effective_volume_m3 / annual_m3
    # Schedule desludging at 85% capacity to prevent rainy-season overflow
    rec_interval = max(0.25, years_full * 0.85)
    return PitFillEstimate(
        containment_type=key,
        effective_volume_m3=round(effective_volume_m3, 2),
        users=users,
        annual_accumulation_m3=round(annual_m3, 3),
        years_to_full=round(years_full, 2),
        recommended_emptying_interval_years=round(rec_interval, 2),
    )


@dataclass(frozen=True)
class DryingBedDesign:
    """Unplanted or planted fecal sludge drying-bed civil sizing (Eawag-Sandec SLR)."""

    daily_sludge_m3: float
    sludge_ts_g_per_l: float
    annual_dry_solids_tonnes: float
    solids_loading_rate_kg_ts_m2_yr: float
    net_drying_bed_area_m2: float
    recommended_bed_count: int
    single_bed_area_m2: float
    expected_dewatered_cake_tonnes_yr: float
    filtrate_leachate_m3_day: float


def size_drying_beds(
    *,
    daily_sludge_m3: float,
    sludge_ts_g_per_l: float = 30.0,  # ~3% TS typical mixed pit + septic sludge
    planted: bool = False,
    climate_rainy_factor: float = 1.0,  # >1.0 extends drying cycle in wet climates
    target_bed_area_m2: float = 40.0,
) -> DryingBedDesign:
    """Size fecal sludge drying beds using Eawag-Sandec Solids Loading Rate (kg TS/m2/yr)."""
    if daily_sludge_m3 <= 0 or sludge_ts_g_per_l <= 0:
        raise ValueError("daily_sludge_m3 and sludge_ts_g_per_l must be positive")
    # Eawag-Sandec design SLR: ~150 kg TS/m2/yr unplanted (100-200), ~200 kg TS/m2/yr planted
    base_slr = 200.0 if planted else 150.0
    eff_slr = base_slr / max(0.7, climate_rainy_factor)

    # 1 m3 * 1 g/L = 1 kg dry solids
    annual_ts_kg = daily_sludge_m3 * sludge_ts_g_per_l * 365.0
    net_area = annual_ts_kg / eff_slr
    bed_count = max(4, math.ceil(net_area / target_bed_area_m2))
    single_area = net_area / bed_count

    # Dewatered biosolids cake reaches ~35% TS (from ~3% TS influent); ~75% volume drains as leachate
    cake_tonnes_yr = (annual_ts_kg / 0.35) / 1000.0
    filtrate_m3_day = daily_sludge_m3 * 0.72

    return DryingBedDesign(
        daily_sludge_m3=round(daily_sludge_m3, 2),
        sludge_ts_g_per_l=round(sludge_ts_g_per_l, 1),
        annual_dry_solids_tonnes=round(annual_ts_kg / 1000.0, 2),
        solids_loading_rate_kg_ts_m2_yr=round(eff_slr, 1),
        net_drying_bed_area_m2=round(net_area, 1),
        recommended_bed_count=bed_count,
        single_bed_area_m2=round(single_area, 1),
        expected_dewatered_cake_tonnes_yr=round(cake_tonnes_yr, 1),
        filtrate_leachate_m3_day=round(filtrate_m3_day, 2),
    )


@dataclass(frozen=True)
class PathogenSafetyAudit:
    """WHO (2006) Guidelines for Safe Use of Excreta helminth & E. coli biosolids check."""

    storage_months: float
    ambient_temp_c: float
    thermophilic_composted: bool
    estimated_helminth_eggs_per_g_ts: float
    safe_for_unrestricted_agriculture: bool
    safe_for_briquette_fuel: bool
    advisory: str


def audit_biosolids_reuse_safety(
    *,
    raw_helminth_eggs_per_g_ts: float = 200.0,
    storage_months: float = 6.0,
    ambient_temp_c: float = 25.0,
    thermophilic_composted: bool = False,
) -> PathogenSafetyAudit:
    """Verify WHO <= 1 viable helminth egg / g TS threshold for agricultural soil conditioner reuse."""
    if raw_helminth_eggs_per_g_ts < 0 or storage_months < 0:
        raise ValueError("Helminth count and storage_months cannot be negative")

    if thermophilic_composted:
        # >=55C co-composting for >=2 weeks achieves >=3-log Ascaris egg inactivation
        residual = raw_helminth_eggs_per_g_ts * 1e-3
    else:
        # Ambient desiccation decay: ~0.20 log10/month at 20C, doubling per +10C
        log_rate_per_month = 0.20 * float(2.0 ** ((ambient_temp_c - 20.0) / 10.0))
        log_reduction = log_rate_per_month * storage_months
        residual = raw_helminth_eggs_per_g_ts * float(10.0 ** (-log_reduction))

    ag_safe = residual <= 1.0
    if ag_safe:
        advisory = (
            f"WHO COMPLIANT ({residual:.2f} eggs/g TS <= 1.0): biosolids safe for unrestricted "
            "agricultural soil-conditioner reuse."
        )
    else:
        advisory = (
            f"UNSAFE FOR DIRECT CROP REUSE ({residual:.1f} viable helminth eggs/g TS > 1.0 WHO limit): "
            "extend ambient storage to >=12 months, co-compost thermophilically (>=55C), "
            "or carbonize into fuel briquettes."
        )

    return PathogenSafetyAudit(
        storage_months=round(storage_months, 1),
        ambient_temp_c=round(ambient_temp_c, 1),
        thermophilic_composted=thermophilic_composted,
        estimated_helminth_eggs_per_g_ts=round(residual, 3),
        safe_for_unrestricted_agriculture=ag_safe,
        safe_for_briquette_fuel=True,
        advisory=advisory,
    )


@dataclass(frozen=True)
class CitySanitationSpec:
    """Municipal non-sewered population and desludging fleet parameters."""

    municipality: str
    non_sewered_population: int
    pct_inaccessible_to_trucks: float = 35.0  # Narrow informal-settlement alleys needing Gulper/pushcarts
    sludge_l_per_person_day: float = 0.15  # ~55 L/person/yr delivered to FSTP
    vacuum_truck_capacity_m3: float = 8.0
    truck_trips_per_day: float = 3.0
    gulper_team_m3_per_day: float = 1.5
    operating_days_year: int = 300


@dataclass(frozen=True)
class CityFsmPlan:
    """City-wide fecal sludge volume, mechanized/manual emptying fleet, and FSTP drying beds."""

    municipality: str
    daily_sludge_generated_m3: float
    truck_serviceable_m3_day: float
    gulper_serviceable_m3_day: float
    vacuum_trucks_required: int
    gulper_teams_required: int
    drying_beds: DryingBedDesign


def plan_city_fsm(spec: CitySanitationSpec) -> CityFsmPlan:
    """Size municipal desludging fleet (vacuum trucks + Gulper teams) and FSTP drying beds."""
    if spec.non_sewered_population <= 0:
        raise ValueError("non_sewered_population must be positive")
    if not (0.0 <= spec.pct_inaccessible_to_trucks <= 100.0):
        raise ValueError("pct_inaccessible_to_trucks must be in [0, 100]")

    annual_m3 = (spec.non_sewered_population * spec.sludge_l_per_person_day * 365.0) / 1000.0
    op_day_m3 = annual_m3 / spec.operating_days_year

    gulper_frac = spec.pct_inaccessible_to_trucks / 100.0
    gulper_m3 = op_day_m3 * gulper_frac
    truck_m3 = op_day_m3 * (1.0 - gulper_frac)

    trucks = math.ceil(truck_m3 / (spec.vacuum_truck_capacity_m3 * spec.truck_trips_per_day)) if truck_m3 > 0 else 0
    gulpers = math.ceil(gulper_m3 / spec.gulper_team_m3_per_day) if gulper_m3 > 0 else 0

    beds = size_drying_beds(daily_sludge_m3=annual_m3 / 365.0)

    return CityFsmPlan(
        municipality=spec.municipality,
        daily_sludge_generated_m3=round(op_day_m3, 2),
        truck_serviceable_m3_day=round(truck_m3, 2),
        gulper_serviceable_m3_day=round(gulper_m3, 2),
        vacuum_trucks_required=trucks,
        gulper_teams_required=gulpers,
        drying_beds=beds,
    )
