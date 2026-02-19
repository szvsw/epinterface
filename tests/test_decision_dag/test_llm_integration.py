"""Integration test: generate a DecisionDAG via an LLM for a Massachusetts building stock.

Run with:
    uv run --env-file .env python tests/test_decision_dag/test_llm_integration.py
"""

from __future__ import annotations

import asyncio
import json

from epinterface.sbem.decision_dag.agent import build_user_message, generate_dag
from epinterface.sbem.decision_dag.executor import DAGExecutor
from epinterface.sbem.decision_dag.fields import (
    FieldType,
    SupplementaryContext,
    UserFieldDefinition,
    UserFieldSet,
)
from epinterface.sbem.decision_dag.validation import validate_dag_structure

FIELD_SET = UserFieldSet(
    fields=[
        UserFieldDefinition(
            name="income",
            field_type=FieldType.NUMERIC,
            description="Annual household income in USD. Correlates loosely with ability to invest in energy upgrades.",
            data_quality_description="Self-reported on utility assistance applications. About 30% of rows are missing.",
            min_value=0,
            max_value=500_000,
            unit="USD/year",
        ),
        UserFieldDefinition(
            name="year_built",
            field_type=FieldType.NUMERIC,
            description="Year the building was originally constructed.",
            data_quality_description="From assessor records; generally reliable, though some entries are approximate decades (e.g. 1900 for anything pre-1910).",
            min_value=1700,
            max_value=2025,
            unit="year",
        ),
        UserFieldDefinition(
            name="building_typology",
            field_type=FieldType.CATEGORICAL,
            description="Building typology classification from assessor data.",
            data_quality_description="Assessor-derived, reliable.",
            categories=[
                "single_family_detached",
                "single_family_attached",
                "small_multifamily_2_4",
                "medium_multifamily_5_20",
                "large_multifamily_20_plus",
            ],
        ),
        UserFieldDefinition(
            name="weatherization_status",
            field_type=FieldType.CATEGORICAL,
            description="Whether the building has been through a weatherization assistance program.",
            data_quality_description="From state WAP records. Only captures state-funded programs; private weatherization is not tracked. About 60% of rows are missing (unknown status).",
            categories=["weatherized", "not_weatherized", "unknown"],
        ),
        UserFieldDefinition(
            name="last_renovation",
            field_type=FieldType.CATEGORICAL,
            description="Approximate timeframe of last known major renovation or retrofit.",
            data_quality_description="From permit records where available. Very sparse -- roughly 70% missing.",
            categories=[
                "never",
                "before_1980",
                "1980_2000",
                "2000_2010",
                "2010_present",
            ],
        ),
    ],
    context_description=(
        "We are building energy models for a portfolio of ~5,000 residential buildings "
        "in Massachusetts for a utility-funded energy efficiency program. The goal is to "
        "estimate building energy use and identify retrofit opportunities. Data is sparse "
        "and of mixed quality."
    ),
    region_description=(
        "Massachusetts, USA. IECC Climate Zone 5A. Cold winters, warm humid summers. "
        "Heating-dominated climate with ~5,500 HDD65 and ~700 CDD65. "
        "State energy code is based on IECC 2021 for new construction."
    ),
    building_stock_description=(
        "Predominantly older housing stock. Roughly 60% of buildings were built before 1960. "
        "Mix of wood-frame (most common for single-family), triple-decker multi-family "
        "(very common in urban MA), and some masonry construction in older urban cores. "
        "Natural gas heating dominates (~65%), followed by oil (~20%), and electric/heat pump (~15%). "
        "Many older buildings have minimal insulation, especially in walls."
    ),
    supplementary_context=[
        SupplementaryContext(
            title="Heating System Distribution by Building Age",
            content=json.dumps(
                {
                    "pre_1940": {
                        "gas_furnace": 0.45,
                        "oil_boiler": 0.35,
                        "steam": 0.10,
                        "electric_resistance": 0.05,
                        "heat_pump": 0.05,
                    },
                    "1940_1970": {
                        "gas_furnace": 0.55,
                        "oil_boiler": 0.25,
                        "electric_resistance": 0.10,
                        "heat_pump": 0.10,
                    },
                    "1970_2000": {
                        "gas_furnace": 0.60,
                        "oil_boiler": 0.15,
                        "electric_resistance": 0.10,
                        "heat_pump": 0.15,
                    },
                    "post_2000": {
                        "gas_furnace": 0.40,
                        "oil_boiler": 0.05,
                        "electric_resistance": 0.05,
                        "heat_pump": 0.50,
                    },
                },
                indent=2,
            ),
            format_hint="json",
        ),
        SupplementaryContext(
            title="Typical Wall Construction by Era",
            content=(
                "Pre-1940: Double-wythe brick or balloon-frame wood with no insulation, plaster interior. "
                "Infiltration is very high (often 1.0+ ACH).\n"
                "1940-1970: Platform-frame wood, often with minimal batt insulation (R-7 to R-11 cavities), "
                "some with aluminum siding over original clapboard. Infiltration moderate (0.5-0.8 ACH).\n"
                "1970-2000: Wood frame with R-11 to R-19 cavity insulation, vinyl or wood siding, "
                "some continuous insulation in later builds. Infiltration moderate (0.3-0.6 ACH).\n"
                "Post-2000: Wood frame with R-19+ cavity, often R-5 to R-10 continuous exterior insulation, "
                "air sealing. Infiltration low (0.15-0.35 ACH)."
            ),
            format_hint="plaintext",
        ),
        SupplementaryContext(
            title="Massachusetts Weatherization Program Notes",
            content=(
                "The MA WAP program typically performs: air sealing (blower-door guided), "
                "attic insulation to R-38 minimum, wall insulation (dense-pack cellulose) "
                "where feasible, and sometimes basement/crawlspace insulation. "
                "Weatherized homes see roughly a 20-30% reduction in infiltration and "
                "improved wall/attic R-values compared to un-weatherized homes of the same era."
            ),
            format_hint="plaintext",
        ),
    ],
)

SAMPLE_ROWS = [
    {
        "income": 45000,
        "year_built": 1925,
        "building_typology": "single_family_detached",
        "weatherization_status": "not_weatherized",
        "last_renovation": "never",
    },
    {
        "income": 120000,
        "year_built": 2018,
        "building_typology": "single_family_detached",
        "weatherization_status": "unknown",
        "last_renovation": "2010_present",
    },
    {
        "year_built": 1955,
        "building_typology": "small_multifamily_2_4",
        "weatherization_status": "weatherized",
    },
    {
        "building_typology": "large_multifamily_20_plus",
    },
    {},
]

DIRECT_VALUES = {
    "WWR": 0.15,
    "F2FHeight": 3.0,
    "NFloors": 2,
    "Width": 10.0,
    "Depth": 12.0,
    "Rotation": 0.0,
    "EPWURI": "https://energyplus-weather.s3.amazonaws.com/north_and_central_america_wmo_region_4/USA/MA/USA_MA_Boston-Logan.Intl.AP.725090_TMYx.2007-2021.epw",
}


async def main():
    """Run the full integration test."""
    print("=" * 70)
    print("Decision DAG LLM Integration Test -- Massachusetts Residential Stock")
    print("=" * 70)

    print("\n--- User Message Preview (first 500 chars) ---")
    msg = build_user_message(FIELD_SET)
    import yaml

    with open("tests/test_decision_dag/_last_user_field_set.yaml", "w") as f:
        yaml.dump(FIELD_SET.model_dump(mode="json"), f, indent=2, sort_keys=False)
    with open("tests/test_decision_dag/_last_user_message.txt", "w") as f:
        f.write(msg)
    print(msg[:500] + "...\n")

    print("--- Calling LLM to generate DAG ---")
    dag = await generate_dag(FIELD_SET, model="openai:gpt-5.2-chat-latest")

    print(f"\nDAG description: {dag.description}")
    print(f"Components: {len(dag.components)}")
    print(f"Nodes: {len(dag.nodes)}")
    print(f"Entry nodes: {dag.entry_node_ids}")

    print("\n--- Intermediate Components ---")
    for comp in dag.components:
        print(f"  [{comp.id}] {comp.name}")
        print(f"    {comp.description}")
        print(
            f"    Assigns {len(comp.assignments)} fields: {list(comp.assignments.keys())}"
        )

    print("\n--- Validating DAG ---")
    errors = validate_dag_structure(
        dag, field_set=FIELD_SET, require_full_coverage=True
    )
    if errors:
        print(f"  Validation found {len(errors)} issue(s):")
        for e in errors:
            print(f"    - {e}")
    else:
        print("  DAG passed all structural validation checks.")

    print("\n--- Executing DAG Against Sample Rows ---")
    executor = DAGExecutor(dag)
    for i, row in enumerate(SAMPLE_ROWS):
        print(f"\n  Row {i + 1}: {row or '(empty)'}")
        result = executor.execute(row)
        n_assigned = len(result.assignments)
        n_unresolved = len(result.trace.unresolved_fields)
        print(f"    Visited: {result.trace.visited_node_ids}")
        print(f"    Components applied: {result.trace.applied_component_ids}")
        print(f"    Assigned {n_assigned} fields, {n_unresolved} unresolved")

        highlights = {
            k: result.assignments[k]
            for k in [
                "HeatingFuel",
                "HeatingSystemCOP",
                "InfiltrationACH",
                "FacadeStructuralSystem",
                "FacadeCavityInsulationRValue",
                "WindowUValue",
            ]
            if k in result.assignments
        }
        print(f"    Key values: {highlights}")

    print("\n--- Attempting FlatModel Construction (Row 1) ---")
    try:
        flat_model = executor.execute_to_flat_model(
            SAMPLE_ROWS[0], direct_values=DIRECT_VALUES
        )
        print("  FlatModel created successfully!")
        print(f"  HeatingFuel={flat_model.HeatingFuel}")
        print(f"  InfiltrationACH={flat_model.InfiltrationACH}")
        print(f"  FacadeStructuralSystem={flat_model.FacadeStructuralSystem}")
        print(
            f"  FacadeCavityInsulationRValue={flat_model.FacadeCavityInsulationRValue}"
        )
        print(f"  WindowUValue={flat_model.WindowUValue}")
    except Exception as exc:
        print(f"  FlatModel construction failed: {exc}")

    print("\n--- Serialized DAG (JSON) ---")
    dag_json = dag.model_dump_json(indent=2)
    print(f"  {len(dag_json)} characters")
    print("  (saved to tests/test_decision_dag/_last_dag.json)")
    from pathlib import Path

    Path("tests/test_decision_dag/_last_dag.json").write_text(dag_json)

    print("\n" + "=" * 70)
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
