"""Per-zone annual energy from EnergyPlus SQL (post-simulation)."""

from __future__ import annotations

import pandas as pd
from archetypal.idfclass import IDF
from archetypal.idfclass.sql import Sql

from epinterface.geometry import get_zone_floor_area

J_to_kWh = 1.0 / 3_600_000.0
GJ_to_kWh = 277.778

_ZONE_ENERGY_VARS: tuple[tuple[str, str], ...] = (
    ("Zone Lights Electricity Energy", "sim_lighting_kwh_per_m2"),
    ("Zone Electric Equipment Electricity Energy", "sim_equipment_kwh_per_m2"),
    ("Zone Ideal Loads Zone Total Heating Energy", "sim_heating_kwh_per_m2"),
    ("Zone Ideal Loads Zone Total Cooling Energy", "sim_cooling_kwh_per_m2"),
)


def _norm_zone_key(name: str) -> str:
    return name.replace("_", " ").upper()


def _zone_name_lookup(zone_names: list[str]) -> dict[str, str]:
    return {_norm_zone_key(zn): zn for zn in zone_names}


def _match_zone_name(key_value: str, zone_lookup: dict[str, str]) -> str | None:
    """Map SQL KeyValue (zone or ideal-loads system name) to EP zone name."""
    kv = key_value.strip()
    if kv in zone_lookup.values():
        return kv
    nkv = _norm_zone_key(kv)
    if nkv in zone_lookup:
        return zone_lookup[nkv]
    suffix = " IDEAL LOADS AIR SYSTEM"
    if nkv.endswith(suffix):
        candidate = nkv[: -len(suffix)]
        if candidate in zone_lookup:
            return zone_lookup[candidate]
    return None


def _annual_kwh_per_m2_from_hourly(
    sql: Sql, variable_name: str, idf: IDF
) -> dict[str, float]:
    """Sum hourly zone energy [J] and normalize by zone floor area."""
    zone_names = [z.Name for z in idf.idfobjects["ZONE"]]
    zone_lookup = _zone_name_lookup(zone_names)
    try:
        hourly = sql.timeseries_by_name([variable_name], "Hourly")
    except Exception:
        return {}
    if hourly.empty:
        return {}

    totals: dict[str, float] = {}
    if isinstance(hourly.columns, pd.MultiIndex):
        for col in hourly.columns:
            key_value = str(col[1]) if len(col) > 1 else str(col[0])
            zn = _match_zone_name(key_value, zone_lookup)
            if zn is None:
                continue
            totals[zn] = totals.get(zn, 0.0) + float(hourly[col].sum())
    else:
        annual_j = hourly.sum()
        for key, joules in annual_j.items():
            zn = _match_zone_name(str(key), zone_lookup)
            if zn is None:
                continue
            totals[zn] = totals.get(zn, 0.0) + float(joules)

    return {
        zn: joules * J_to_kWh / float(get_zone_floor_area(idf, zn))
        for zn, joules in totals.items()
        if float(get_zone_floor_area(idf, zn)) > 0
    }


def _lighting_kwh_per_m2_from_tabular(sql: Sql, idf: IDF) -> dict[str, float]:
    """Lighting consumption from LightingSummary when hourly vars are absent."""
    zone_lookup = _zone_name_lookup([z.Name for z in idf.idfobjects["ZONE"]])
    try:
        tbl = sql.tabular_data_by_name(
            "LightingSummary", "Interior Lighting", "Entire Facility"
        )
    except Exception:
        return {}
    zone_col = ("Zone Name", "")
    cons_col = ("Consumption", "GJ")
    area_col = ("Space Area", "m2")
    if cons_col not in tbl.columns or zone_col not in tbl.columns:
        return {}
    out: dict[str, float] = {}
    for _, row in tbl.iterrows():
        zn = row.loc[zone_col]
        if not isinstance(zn, str) or not zn.strip():
            continue
        cons_val = row.loc[cons_col]
        if pd.isna(cons_val):
            continue
        gj = float(cons_val)
        if area_col in tbl.columns:
            area_val = row.loc[area_col]
            area = 0.0 if pd.isna(area_val) else float(area_val)
        else:
            area = 0.0
        if area <= 0:
            continue
        zn_idf = zone_lookup.get(_norm_zone_key(zn.strip()))
        if zn_idf is None:
            continue
        out[zn_idf] = gj * GJ_to_kWh / area
    return out


def zone_energy_summary(sql: Sql, idf: IDF) -> pd.DataFrame:
    """Annual simulated site energy per zone, normalized to kWh/m2."""
    zone_names = [z.Name for z in idf.idfobjects["ZONE"]]
    rows: list[dict[str, float | str | None]] = []
    col_data: dict[str, dict[str, float]] = {}

    lighting = _annual_kwh_per_m2_from_hourly(
        sql, "Zone Lights Electricity Energy", idf
    )
    if not lighting:
        lighting = _lighting_kwh_per_m2_from_tabular(sql, idf)
    col_data["sim_lighting_kwh_per_m2"] = lighting

    for var_name, col_name in _ZONE_ENERGY_VARS[1:]:
        col_data[col_name] = _annual_kwh_per_m2_from_hourly(sql, var_name, idf)

    for zn in zone_names:
        row: dict[str, float | str | None] = {"ep_zone_name": zn}
        for col_name in [c for _, c in _ZONE_ENERGY_VARS]:
            row[col_name] = col_data.get(col_name, {}).get(zn)
        sim_total = sum(
            float(v)
            for k, v in row.items()
            if k.startswith("sim_") and isinstance(v, int | float)
        )
        row["sim_total_kwh_per_m2"] = sim_total if sim_total else None
        rows.append(row)
    return pd.DataFrame(rows)


def merge_assignment_and_energy(
    assignment: pd.DataFrame,
    energy: pd.DataFrame,
) -> pd.DataFrame:
    """Join resolved assignment summary with simulated zone energy."""
    return assignment.merge(energy, on="ep_zone_name", how="left")
