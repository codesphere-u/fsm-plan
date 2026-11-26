"""CLI entrypoint for fsm-plan."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .planner import CitySanitationSpec, audit_biosolids_reuse_safety, plan_city_fsm


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fsm-plan",
        description="Size municipal Fecal Sludge Management emptying fleets, drying beds, and WHO reuse safety.",
    )
    parser.add_argument("--city", default="MBARARA-CITY", help="Municipality name.")
    parser.add_argument("--population", type=int, default=220000, help="Non-sewered urban population.")
    parser.add_argument("--inaccessible-pct", type=float, default=35.0, help="Percent alleys needing Gulper teams.")
    parser.add_argument("--storage-months", type=float, default=6.0, help="Biosolids storage months before reuse.")
    parser.add_argument("--composted", action="store_true", help="Thermophilic co-composting (>=55C) applied.")
    args = parser.parse_args(argv)

    plan = plan_city_fsm(
        CitySanitationSpec(
            municipality=args.city,
            non_sewered_population=args.population,
            pct_inaccessible_to_trucks=args.inaccessible_pct,
        )
    )
    safety = audit_biosolids_reuse_safety(
        storage_months=args.storage_months,
        thermophilic_composted=args.composted,
    )
    print(json.dumps({"city_fsm_plan": asdict(plan), "biosolids_safety": asdict(safety)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
