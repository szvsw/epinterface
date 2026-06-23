"""Zone and floor annual energy summaries from EnergyPlus SQL output.

Energy-accounting caveats (important for interpreting the columns below):

- ``sim_lighting_site_kwh`` and ``sim_equipment_site_kwh`` are electric *site*
  energy (the electricity consumed by lights and plug loads).
- ``sim_heating_delivered_kwh`` and ``sim_cooling_delivered_kwh`` are *delivered*
  ideal-load thermal energy, i.e. the heating/cooling the ideal-loads air system
  added to / removed from the zone air. They are NOT fuel/utility energy: no COP
  or fuel mapping has been applied.
- ``sim_total_included_kwh`` is the sum of the four columns above. It mixes site
  electricity with delivered thermal energy, so it is neither true site energy,
  utility energy, nor source energy. It is "the simulated zone energy that is
  currently included" and should be labelled as such in any downstream report.
- Domestic hot water (DHW) is NOT included in zone or floor results yet.

The metadata columns (``floor_index``, ``role``, ``category``, ``ep_storey_index``,
``floor_area_m2``) are owned by the assignment summary; see
``merge_assignment_and_energy`` for how duplicate metadata is avoided on join.
"""

from __future__ import annotations

from collections.abc import Hashable, Sequence
from typing import Any

import pandas as pd
from archetypal.idfclass import IDF
from archetypal.idfclass.sql import Sql

from epinterface.geometry import ShoeboxGeometry, get_zone_floor_area
from epinterface.sbem.zone_assignment import (
    ZoneAssignmentResolver,
)

J_TO_KWH = 1.0 / 3_600_000.0

# (EnergyPlus output variable name, result column name). Column names encode the
# energy-accounting meaning: "site" = electric site energy, "delivered" = ideal
# load thermal energy (no COP/fuel applied). See the module docstring.
_ZONE_ENERGY_VARS: tuple[tuple[str, str], ...] = (
    ("Zone Lights Electricity Energy", "sim_lighting_site_kwh"),
    ("Zone Electric Equipment Electricity Energy", "sim_equipment_site_kwh"),
    ("Zone Ideal Loads Zone Total Heating Energy", "sim_heating_delivered_kwh"),
    ("Zone Ideal Loads Zone Total Cooling Energy", "sim_cooling_delivered_kwh"),
)

TOTAL_ENERGY_COLUMN = "sim_total_included_kwh"

# Metadata columns produced by both the assignment summary and the energy
# summary; dropped from the energy frame before joining so the merge does not
# create ``*_x`` / ``*_y`` duplicates.
_ENERGY_METADATA_COLUMNS: frozenset[str] = frozenset({
    "floor_area_m2",
    "ep_storey_index",
    "floor_index",
    "role",
    "category",
})


def _normalized_zone_name(name: str) -> str:
    return name.replace("_", " ").upper()


def _zone_name_lookup(zone_names: list[str]) -> dict[str, str]:
    return {_normalized_zone_name(zone_name): zone_name for zone_name in zone_names}


def _match_zone_name(key_value: str, zone_lookup: dict[str, str]) -> str | None:
    """Map SQL KeyValue strings to generated EnergyPlus zone names."""
    key_value = key_value.strip()
    if key_value in zone_lookup.values():
        return key_value
    normalized = _normalized_zone_name(key_value)
    if normalized in zone_lookup:
        return zone_lookup[normalized]
    suffix = " IDEAL LOADS AIR SYSTEM"
    if normalized.endswith(suffix):
        candidate = normalized[: -len(suffix)]
        return zone_lookup.get(candidate)
    return None


def _key_value_from_column(
    column: Any,
    column_names: Sequence[Hashable | None],
) -> str:
    """Extract the SQL KeyValue portion from a timeseries column label."""
    if isinstance(column, tuple):
        values = list(column)
        if not values:
            return ""
        column_names_list = list(column_names)
        if "KeyValue" in column_names_list:
            key_value_index = column_names_list.index("KeyValue")
            if key_value_index < len(values):
                return str(values[key_value_index])
        return str(values[1] if len(values) > 1 else values[0])
    return str(column)


def _annual_kwh_from_hourly(
    sql: Sql,
    variable_name: str,
    idf: IDF,
) -> dict[str, float]:
    """Sum hourly zone energy values from Joules to annual kWh."""
    zone_names = [zone.Name for zone in idf.idfobjects["ZONE"]]
    zone_lookup = _zone_name_lookup(zone_names)
    try:
        hourly = sql.timeseries_by_name([variable_name], "Hourly")
    except Exception:
        return {}
    if hourly.empty:
        return {}

    totals: dict[str, float] = {}
    column_names = (
        list(hourly.columns.names) if isinstance(hourly.columns, pd.MultiIndex) else []
    )
    for column in hourly.columns:
        key_value = _key_value_from_column(column, column_names)
        zone_name = _match_zone_name(key_value, zone_lookup)
        if zone_name is None:
            continue
        totals[zone_name] = totals.get(zone_name, 0.0) + float(hourly[column].sum())

    return {zone_name: joules * J_TO_KWH for zone_name, joules in totals.items()}


def _context_from_model(
    model: Any | None,
) -> tuple[
    ZoneAssignmentResolver | None,
    ShoeboxGeometry | None,
    float | None,
    bool,
    float | None,
    bool,
]:
    """Duck-type either a builder Model or BuildingFlatModel into resolver context."""
    if model is None:
        return None, None, None, False, None, False

    if hasattr(model, "zone_assignments") and hasattr(model, "geometry"):
        return (
            model.zone_assignments,
            model.geometry,
            model.Attic.UseFraction,
            model.Attic.Conditioned,
            model.Basement.UseFraction,
            model.Basement.Conditioned,
        )

    if hasattr(model, "assignment_resolver") and hasattr(model, "to_model"):
        builder_model, _ = model.to_model()
        return (
            model.assignment_resolver(),
            builder_model.geometry,
            model.attic.UseFraction,
            model.attic.Conditioned,
            model.basement.UseFraction,
            model.basement.Conditioned,
        )

    return None, None, None, False, None, False


def zone_energy_summary(
    sql: Sql,
    idf: IDF,
    *,
    model: Any | None = None,
    resolver: ZoneAssignmentResolver | None = None,
    geometry: ShoeboxGeometry | None = None,
) -> pd.DataFrame:
    """Return annual simulated energy by zone with raw kWh and kWh/m2 columns."""
    (
        model_resolver,
        model_geometry,
        attic_use_fraction,
        attic_conditioned,
        basement_use_fraction,
        basement_conditioned,
    ) = _context_from_model(model)
    resolver = resolver or model_resolver
    geometry = geometry or model_geometry

    zone_names = [zone.Name for zone in idf.idfobjects["ZONE"]]
    area_by_zone = {
        zone_name: float(get_zone_floor_area(idf, zone_name))
        for zone_name in zone_names
    }
    col_data = {
        column_name: _annual_kwh_from_hourly(sql, variable_name, idf)
        for variable_name, column_name in _ZONE_ENERGY_VARS
    }

    metadata_by_zone: dict[str, dict[str, Any]] = {}
    if resolver is not None and geometry is not None:
        for resolved in resolver.resolved_zone_table(
            idf,
            geometry,
            attic_use_fraction=attic_use_fraction,
            attic_conditioned=attic_conditioned,
            basement_use_fraction=basement_use_fraction,
            basement_conditioned=basement_conditioned,
        ):
            metadata_by_zone[resolved.ep_zone_name] = {
                "ep_storey_index": resolved.ep_storey_index,
                "floor_index": resolved.floor_index,
                "role": resolved.role.value,
                "category": resolved.category,
            }

    rows: list[dict[str, Any]] = []
    for zone_name in zone_names:
        area = area_by_zone[zone_name]
        row: dict[str, Any] = {
            "ep_zone_name": zone_name,
            "floor_area_m2": area,
            **metadata_by_zone.get(zone_name, {}),
        }
        raw_values: list[float] = []
        for _, column_name in _ZONE_ENERGY_VARS:
            value = col_data[column_name].get(zone_name)
            row[column_name] = value
            row[f"{column_name}_per_m2"] = None if value is None else value / area
            if value is not None:
                raw_values.append(value)
        total = sum(raw_values) if raw_values else None
        row[TOTAL_ENERGY_COLUMN] = total
        row[f"{TOTAL_ENERGY_COLUMN}_per_m2"] = None if total is None else total / area
        rows.append(row)
    return pd.DataFrame(rows)


def floor_energy_summary(
    zone_energy: pd.DataFrame,
    *,
    n_floors: int | None = None,
) -> pd.DataFrame:
    """Aggregate zone energy to one row per above-grade floor.

    Raw zone kWh are summed first and only then normalized by the summed floor
    area, so the per-m2 values are area-weighted correctly (rather than averaging
    already-normalized zone values). Only ``category == "main"`` zones are
    included, so basement/attic rows never leak into the floor table.

    Args:
        zone_energy: Per-zone energy table from :func:`zone_energy_summary`.
        n_floors: If provided, assert the result has exactly one row per
            above-grade floor index ``0..n_floors-1``. This enforces the
            "simulation produces n rows where n is the number of floors"
            contract for assignment-backed runs (important for ``core/perim``
            zoning and basement geometries).

    Raises:
        ValueError: If ``n_floors`` is provided and the aggregated floor indices
            do not match ``set(range(n_floors))``.
    """
    if zone_energy.empty or "floor_index" not in zone_energy.columns:
        if n_floors is not None and n_floors > 0:
            msg = (
                "floor_energy_summary produced no rows but expected "
                f"{n_floors} above-grade floor(s)."
            )
            raise ValueError(msg)
        return pd.DataFrame()
    main = zone_energy[zone_energy["category"] == "main"].copy()
    if main.empty:
        if n_floors is not None and n_floors > 0:
            msg = (
                "floor_energy_summary found no 'main' zones but expected "
                f"{n_floors} above-grade floor(s)."
            )
            raise ValueError(msg)
        return pd.DataFrame()

    raw_cols = [column for _, column in _ZONE_ENERGY_VARS] + [TOTAL_ENERGY_COLUMN]
    grouped = (
        main.groupby("floor_index", dropna=False)[["floor_area_m2", *raw_cols]]
        .sum(min_count=1)
        .reset_index()
    )
    for column in raw_cols:
        grouped[f"{column}_per_m2"] = grouped[column] / grouped["floor_area_m2"]
    grouped["floor_index"] = grouped["floor_index"].astype(int)
    grouped = grouped.sort_values("floor_index").reset_index(drop=True)

    if n_floors is not None:
        found = set(grouped["floor_index"].tolist())
        expected = set(range(n_floors))
        if found != expected:
            missing = sorted(expected - found)
            extra = sorted(found - expected)
            msg = (
                "floor_energy_summary expected exactly one row per above-grade "
                f"floor 0..{n_floors - 1}, but got floor indices {sorted(found)}."
            )
            if missing:
                msg += f" Missing floors: {missing}."
            if extra:
                msg += f" Unexpected floors: {extra}."
            raise ValueError(msg)

    return grouped


def merge_assignment_and_energy(
    assignment: pd.DataFrame,
    energy: pd.DataFrame,
) -> pd.DataFrame:
    """Join resolved assignment summary with simulated zone energy.

    The energy frame repeats metadata columns (``floor_index``, ``role``,
    ``category``, ``ep_storey_index``, ``floor_area_m2``) that the assignment
    frame already owns. Those are dropped from the energy frame before the join
    so pandas does not emit ``*_x`` / ``*_y`` suffixed duplicates.
    """
    energy_for_merge = energy.drop(
        columns=[c for c in _ENERGY_METADATA_COLUMNS if c in energy.columns]
    )
    return assignment.merge(energy_for_merge, on="ep_zone_name", how="left")
