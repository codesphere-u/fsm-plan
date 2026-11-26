"""Tests for fsm-plan."""

from __future__ import annotations

import json

import pytest

from fsm_plan import (
    CitySanitationSpec,
    audit_biosolids_reuse_safety,
    estimate_pit_fill_years,
    plan_city_fsm,
    size_drying_beds,
)
from fsm_plan.cli import main as cli_main


def test_pit_fill_years_and_emptying_interval() -> None:
    est = estimate_pit_fill_years(effective_volume_m3=4.5, users=15, containment_type="wet_pit_vip")
    assert est.years_to_full > 4.0
    assert est.recommended_emptying_interval_years < est.years_to_full


def test_drying_beds_and_city_fleet_sizing() -> None:
    plan = plan_city_fsm(CitySanitationSpec("GULU", non_sewered_population=180000, pct_inaccessible_to_trucks=40.0))
    assert plan.vacuum_trucks_required >= 1
    assert plan.gulper_teams_required >= 5
    assert plan.drying_beds.net_drying_bed_area_m2 > 1000.0
    assert plan.drying_beds.recommended_bed_count >= 25

    wet = size_drying_beds(daily_sludge_m3=50.0, climate_rainy_factor=1.3)
    dry = size_drying_beds(daily_sludge_m3=50.0, climate_rainy_factor=1.0)
    assert wet.net_drying_bed_area_m2 > dry.net_drying_bed_area_m2


def test_helminth_inactivation_who_gate() -> None:
    short = audit_biosolids_reuse_safety(raw_helminth_eggs_per_g_ts=200.0, storage_months=3.0, ambient_temp_c=22.0)
    assert short.safe_for_unrestricted_agriculture is False

    composted = audit_biosolids_reuse_safety(
        raw_helminth_eggs_per_g_ts=200.0,
        storage_months=1.0,
        thermophilic_composted=True,
    )
    assert composted.safe_for_unrestricted_agriculture is True
    assert composted.estimated_helminth_eggs_per_g_ts <= 1.0


def test_cli_runs(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli_main(["--population", "150000", "--composted"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["biosolids_safety"]["safe_for_unrestricted_agriculture"] is True
    assert out["city_fsm_plan"]["vacuum_trucks_required"] >= 1
