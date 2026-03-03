"""Mapping helpers from ClimateStudio structures to SBEM primitives."""

from __future__ import annotations

from typing import Any

from epinterface.sbem.components.schedules import YearScheduleCategory

ROUGHNESS_MAP: dict[int, str] = {
    1: "VeryRough",
    2: "Rough",
    3: "MediumRough",
    4: "MediumSmooth",
}


def map_roughness(value: Any) -> str:
    """Map ClimateStudio numeric roughness to a string value for the schema."""
    if value is None:
        return "MediumRough"
    try:
        key = int(value)
    except (TypeError, ValueError):
        return str(value)
    return ROUGHNESS_MAP.get(key, "MediumRough")


def map_year_schedule_category(
    category: str, name: str | None = None
) -> YearScheduleCategory:
    """Map ClimateStudio schedule category/name to a YearScheduleCategory."""
    cat = (category or "").lower()
    name_l = (name or "").lower()

    if "occup" in cat or "occup" in name_l:
        return "Occupancy"
    if "light" in cat or "light" in name_l:
        return "Lighting"
    if "equip" in cat or "equip" in name_l:
        return "Equipment"
    if "water" in cat or "dhw" in cat or "water" in name_l:
        return "WaterUse"
    if "control" in cat or "setpoint" in cat or "setpoint" in name_l:
        return "Setpoint"
    if "window" in cat or "window" in name_l:
        return "Window"

    # default to equipment if unsure, as it is relatively benign
    return "Equipment"


WindowType = str  # "Single" | "Double" | "Triple"


def map_glazing_type(cs_type: str | None, layer_count: int | None = None) -> str:
    """Map ClimateStudio glazing Type to Single/Double/Triple. Infers from layer count when Type is Other or invalid."""
    t = (cs_type or "").strip().lower()
    if t == "single":
        return "Single"
    if t == "double":
        return "Double"
    if t == "triple":
        return "Triple"
    if layer_count is not None:
        if layer_count <= 1:
            return "Single"
        if layer_count == 2:
            return "Double"
        return "Triple"
    return "Double"


def convert_fresh_air_rate(value: float | int | None) -> float:
    """Convert ClimateStudio fresh air rates to m3/s-like units.

    ClimateStudio values are typically given as l/s; divide by 1000 to get m3/s.
    """
    if value is None:
        return 0.0
    return float(value) / 1000.0
