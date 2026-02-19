"""FlatModel schema introspection and DAG assignment validation.

Provides utilities to generate prompt-friendly descriptions of the
FlatModel schema for LLM consumption, and to validate that DAG
assignments reference valid fields with compatible values.
"""

from __future__ import annotations

import typing
from typing import Any, get_args, get_origin

from pydantic.fields import FieldInfo

from epinterface.sbem.decision_dag.dag import (
    AssignmentNode,
    ComponentRefNode,
    DecisionDAG,
)

_FIELD_GROUPS: dict[str, list[str]] = {
    "Equipment Schedule": [
        "EquipmentBase",
        "EquipmentAMInterp",
        "EquipmentLunchInterp",
        "EquipmentPMInterp",
        "EquipmentWeekendPeakInterp",
        "EquipmentSummerPeakInterp",
    ],
    "Lighting Schedule": [
        "LightingBase",
        "LightingAMInterp",
        "LightingLunchInterp",
        "LightingPMInterp",
        "LightingWeekendPeakInterp",
        "LightingSummerPeakInterp",
    ],
    "Occupancy Schedule": [
        "OccupancyBase",
        "OccupancyAMInterp",
        "OccupancyLunchInterp",
        "OccupancyPMInterp",
        "OccupancyWeekendPeakInterp",
        "OccupancySummerPeakInterp",
    ],
    "Thermostat Setpoints": [
        "HeatingSetpointBase",
        "SetpointDeadband",
        "HeatingSetpointSetback",
        "CoolingSetpointSetback",
        "NightSetback",
        "WeekendSetback",
        "SummerSetback",
    ],
    "HVAC Systems": [
        "HeatingFuel",
        "CoolingFuel",
        "HeatingSystemCOP",
        "CoolingSystemCOP",
        "HeatingDistributionCOP",
        "CoolingDistributionCOP",
    ],
    "Space Use": [
        "EquipmentPowerDensity",
        "LightingPowerDensity",
        "OccupantDensity",
    ],
    "Ventilation": [
        "VentFlowRatePerPerson",
        "VentFlowRatePerArea",
        "VentProvider",
        "VentHRV",
        "VentEconomizer",
        "VentDCV",
    ],
    "Domestic Hot Water": [
        "DHWFlowRatePerPerson",
        "DHWFuel",
        "DHWSystemCOP",
        "DHWDistributionCOP",
    ],
    "Envelope": [
        "InfiltrationACH",
    ],
    "Windows": [
        "WindowUValue",
        "WindowSHGF",
        "WindowTVis",
    ],
    "Facade Construction": [
        "FacadeStructuralSystem",
        "FacadeCavityInsulationRValue",
        "FacadeExteriorInsulationRValue",
        "FacadeInteriorInsulationRValue",
        "FacadeInteriorFinish",
        "FacadeExteriorFinish",
    ],
    "Roof Construction": [
        "RoofStructuralSystem",
        "RoofCavityInsulationRValue",
        "RoofExteriorInsulationRValue",
        "RoofInteriorInsulationRValue",
        "RoofInteriorFinish",
        "RoofExteriorFinish",
    ],
    "Slab Construction": [
        "SlabStructuralSystem",
        "SlabInsulationRValue",
        "SlabInsulationPlacement",
        "SlabInteriorFinish",
        "SlabExteriorFinish",
    ],
    "Geometry": [
        "WWR",
        "F2FHeight",
        "NFloors",
        "Width",
        "Depth",
        "Rotation",
    ],
    "Weather": [
        "EPWURI",
    ],
}

GEOMETRY_AND_WEATHER_FIELDS = {
    "WWR",
    "F2FHeight",
    "NFloors",
    "Width",
    "Depth",
    "Rotation",
    "EPWURI",
}
"""Fields typically provided directly rather than through the DAG."""


def _get_literal_values(annotation: Any) -> list[str] | None:
    """Extract allowed values from a Literal type annotation."""
    origin = get_origin(annotation)
    if origin is typing.Literal:
        return list(get_args(annotation))
    args = get_args(annotation)
    for arg in args:
        if get_origin(arg) is typing.Literal:
            return list(get_args(arg))
    return None


def _describe_field(name: str, info: FieldInfo, annotation: Any) -> str:
    """Produce a one-line description of a single FlatModel field."""
    parts: list[str] = [f"  - {name}"]

    literal_vals = _get_literal_values(annotation)
    if literal_vals is not None:
        parts.append(f"(one of: {literal_vals})")
    else:
        origin = get_origin(annotation)
        if origin is typing.Union:
            type_names = [
                a.__name__ if hasattr(a, "__name__") else str(a)
                for a in get_args(annotation)
            ]
            parts.append(f"({' | '.join(type_names)})")
        elif hasattr(annotation, "__name__"):
            parts.append(f"({annotation.__name__})")
        else:
            parts.append(f"({annotation})")

    constraints: list[str] = []
    for attr in ("ge", "gt", "le", "lt"):
        val = info.metadata and next(
            (getattr(m, attr, None) for m in info.metadata if hasattr(m, attr)),
            None,
        )
        if val is not None:
            constraints.append(f"{attr}={val}")
    if constraints:
        parts.append(f"[{', '.join(constraints)}]")

    if info.default is not None and info.default is not ...:
        parts.append(f"default={info.default}")

    if info.description:
        parts.append(f"-- {info.description}")

    return " ".join(parts)


def get_flat_model_schema_description() -> str:
    """Introspect FlatModel and return a structured, prompt-friendly description.

    Groups fields by category and includes type info, constraints,
    defaults, and descriptions for each field.
    """
    from epinterface.sbem.flat_model import FlatModel

    lines: list[str] = ["# FlatModel Parameters", ""]

    all_fields = FlatModel.model_fields
    type_hints = typing.get_type_hints(FlatModel)
    grouped_names: set[str] = set()

    for group_name, field_names in _FIELD_GROUPS.items():
        lines.append(f"## {group_name}")
        for fname in field_names:
            if fname in all_fields:
                lines.append(
                    _describe_field(fname, all_fields[fname], type_hints.get(fname))
                )
                grouped_names.add(fname)
        lines.append("")

    ungrouped = set(all_fields.keys()) - grouped_names
    if ungrouped:
        lines.append("## Other")
        for fname in sorted(ungrouped):
            lines.append(
                _describe_field(fname, all_fields[fname], type_hints.get(fname))
            )
        lines.append("")

    return "\n".join(lines)


def get_flat_model_field_names() -> set[str]:
    """Return the set of all valid FlatModel field names."""
    from epinterface.sbem.flat_model import FlatModel

    return set(FlatModel.model_fields.keys())


def validate_dag_assignments(dag: DecisionDAG) -> list[str]:
    """Validate that all assignments in the DAG reference valid FlatModel fields.

    Returns a list of error messages (empty if everything is valid).
    Does not check value types/constraints -- that is handled at
    FlatModel construction time.
    """
    valid_fields = get_flat_model_field_names()
    errors: list[str] = []

    for node in dag.nodes:
        if isinstance(node, AssignmentNode):
            for field_name in node.assignments:
                if field_name not in valid_fields:
                    errors.append(
                        f"AssignmentNode '{node.id}': unknown FlatModel field '{field_name}'."
                    )
        elif isinstance(node, ComponentRefNode):
            comp_ids = {c.id for c in dag.components}
            if node.component_id not in comp_ids:
                errors.append(
                    f"ComponentRefNode '{node.id}': references unknown component '{node.component_id}'."
                )

    for comp in dag.components:
        for field_name in comp.assignments:
            if field_name not in valid_fields:
                errors.append(
                    f"IntermediateComponent '{comp.id}': unknown FlatModel field '{field_name}'."
                )

    return errors
