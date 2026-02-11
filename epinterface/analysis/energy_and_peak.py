"""Postprocess SQL results to standard energy and peak demand metrics (kWh/m², kW/m²)."""

from typing import cast

import numpy as np
import pandas as pd
from archetypal.idfclass.sql import Sql

kWh_per_GJ = 277.778
GJ_per_J = 1e-9

ANNUAL_SUMMARY_REPORT = "AnnualBuildingUtilityPerformanceSummary"
END_USES_TABLE = "End Uses"

DESIRED_METERS = (
    "InteriorEquipment:Electricity",
    "InteriorLights:Electricity",
    "Heating:DistrictHeating",
    "Cooling:DistrictCooling",
    "WaterSystems:DistrictHeating",
)


def standard_results_postprocess(
    sql: Sql,
    *,
    normalizing_floor_area: float,
    heat_cop: float,
    cool_cop: float,
    dhw_cop: float,
    heat_fuel: str | None,
    cool_fuel: str | None,
    dhw_fuel: str,
    all_fuel_names: list[str],
) -> pd.Series:
    """Postprocess the sql file to get the standard results.

    This will return a series with two levels:
    - Aggregation: "Raw", "End Uses", "Utilities"
    - Meter: ["Electricity", "Cooling", "Heating", "Domestic Hot Water"], ["Electricity", "Propane", ...]

    Args:
        sql: The sql file to postprocess.
        normalizing_floor_area: Floor area [m²] used to normalize energy and power (e.g. total conditioned area).
        heat_cop: Effective COP of the heating system (site energy to delivered).
        cool_cop: Effective COP of the cooling system.
        dhw_cop: Effective COP of the DHW system.
        heat_fuel: Fuel type name for heating (e.g. "DistrictHeating"), or None if no heating.
        cool_fuel: Fuel type name for cooling, or None if no cooling.
        dhw_fuel: Fuel type name for domestic hot water.
        all_fuel_names: Sorted list of all fuel type names (union of HVAC and DHW fuel types) for utilities columns.

    Returns:
        series: The postprocessed results (Energy and Peak, with Aggregation and Meter index levels).
    """
    raw_hourly = sql.timeseries_by_name(DESIRED_METERS, "Hourly")
    raw_monthly = sql.timeseries_by_name(DESIRED_METERS, "Monthly")
    raw_df = sql.tabular_data_by_name(ANNUAL_SUMMARY_REPORT, END_USES_TABLE)

    raw_df_relevant = (
        raw_df[
            [
                "Electricity",
                "District Cooling",
                "District Heating",
            ]
        ].droplevel(-1, axis=1)
        * kWh_per_GJ
    ) / normalizing_floor_area
    raw_df_others = raw_df.drop(
        columns=["Electricity", "District Cooling", "District Heating", "Water"]
    )
    if not np.allclose(raw_df_others.sum().sum(), 0):
        cols = raw_df_others.sum(axis=0)
        cols = cols[cols > 0].index.tolist()
        rows = raw_df_others.sum(axis=1)
        rows = rows[rows > 0].index.tolist()
        msg = (
            "There are end uses/fuels which are not accounted for in the standard postprocessing: "
            + ", ".join(rows)
            + " and "
            + ", ".join(cols)
        )
        raise ValueError(msg)
    raw_series_hot_water = raw_df_relevant.loc["Water Systems"]
    raw_series = raw_df_relevant.loc["Total End Uses"] - raw_series_hot_water
    raw_series["Domestic Hot Water"] = raw_series_hot_water.sum()

    raw_monthly = (
        (
            raw_monthly.droplevel(["IndexGroup", "KeyValue"], axis=1)
            * GJ_per_J
            * kWh_per_GJ
            / normalizing_floor_area
        )
        .rename(
            columns={
                "InteriorLights:Electricity": "Lighting",
                "InteriorEquipment:Electricity": "Equipment",
                "Heating:DistrictHeating": "Heating",
                "Cooling:DistrictCooling": "Cooling",
                "WaterSystems:DistrictHeating": "Domestic Hot Water",
            }
        )
        .set_index(pd.RangeIndex(1, 13, 1, name="Month"))
    )
    raw_monthly.columns.name = "Meter"

    if not np.allclose(raw_series.sum(), raw_monthly.sum().sum(), atol=0.5):
        msg = "Raw series and raw monthly do not match: "
        msg += f"Raw series: {raw_series.sum()}"
        msg += f"Raw monthly: {raw_monthly.sum().sum()}"
        raise ValueError(msg)

    raw_hourly = (
        (raw_hourly.droplevel(["IndexGroup", "KeyValue"], axis=1))
        * GJ_per_J
        * kWh_per_GJ
        / normalizing_floor_area
    ).rename(
        columns={
            "InteriorLights:Electricity": "Lighting",
            "InteriorEquipment:Electricity": "Equipment",
            "Heating:DistrictHeating": "Heating",
            "Cooling:DistrictCooling": "Cooling",
            "WaterSystems:DistrictHeating": "Domestic Hot Water",
        }
    )
    raw_hourly.columns.name = "Meter"
    raw_hourly_max: pd.Series = raw_hourly.max(axis=0)
    raw_monthly_hourly_max = raw_hourly.resample("MS").max()

    heat_use = (
        raw_monthly["Heating"] / heat_cop
        if "Heating" in raw_monthly
        else (raw_monthly["Lighting"] * 0).rename("Heating")
    )
    cool_use = (
        raw_monthly["Cooling"] / cool_cop
        if "Cooling" in raw_monthly
        else (raw_monthly["Lighting"] * 0).rename("Cooling")
    )
    dhw_use = (
        raw_monthly["Domestic Hot Water"] / dhw_cop
        if "Domestic Hot Water" in raw_monthly
        else (raw_monthly["Lighting"] * 0).rename("Domestic Hot Water")
    )
    lighting_use = raw_monthly["Lighting"]
    equipment_use = raw_monthly["Equipment"]
    end_use_df = pd.concat(
        [lighting_use, equipment_use, heat_use, cool_use, dhw_use], axis=1
    )

    utilities_df = pd.DataFrame(
        index=pd.RangeIndex(1, 13, 1, name="Month"),
        columns=all_fuel_names,
        dtype=float,
        data=np.zeros((12, len(all_fuel_names))),
    )
    utilities_df["Electricity"] = lighting_use + equipment_use
    if heat_fuel is not None:
        utilities_df[heat_fuel] += heat_use
    if cool_fuel is not None:
        utilities_df[cool_fuel] += cool_use
    utilities_df[dhw_fuel] += dhw_use

    if not np.allclose(utilities_df.sum().sum(), end_use_df.sum().sum()):
        msg = "Utilities df and end use df do not sum to the same value!"
        raise ValueError(msg)

    energy_dfs = (
        pd.concat(
            [raw_monthly, end_use_df, utilities_df],
            axis=1,
            keys=["Raw", "End Uses", "Utilities"],
            names=["Aggregation", "Meter"],
        )
        .unstack()
        .fillna(0)
    )
    energy_series = cast(pd.Series, energy_dfs).rename("kWh/m2")

    heat_use_hourly = (
        (raw_hourly["Heating"] / heat_cop)
        if "Heating" in raw_hourly
        else (raw_hourly["Lighting"] * 0).rename("Heating")
    )
    cool_use_hourly = (
        (raw_hourly["Cooling"] / cool_cop)
        if "Cooling" in raw_hourly
        else (raw_hourly["Lighting"] * 0).rename("Cooling")
    )
    dhw_use_hourly = (
        (raw_hourly["Domestic Hot Water"] / dhw_cop)
        if "Domestic Hot Water" in raw_hourly
        else (raw_hourly["Lighting"] * 0).rename("Domestic Hot Water")
    )
    lighting_use_hourly = raw_hourly["Lighting"]
    equipment_use_hourly = raw_hourly["Equipment"]

    end_use_df_hourly = pd.concat(
        [
            lighting_use_hourly,
            equipment_use_hourly,
            heat_use_hourly,
            cool_use_hourly,
            dhw_use_hourly,
        ],
        axis=1,
    )
    utilities_df_hourly = pd.DataFrame(
        index=raw_hourly.index,
        columns=all_fuel_names,
        dtype=float,
        data=np.zeros((len(raw_hourly), len(all_fuel_names))),
    )
    utilities_df_hourly["Electricity"] = lighting_use_hourly + equipment_use_hourly
    if heat_fuel is not None:
        utilities_df_hourly[heat_fuel] += heat_use_hourly
    if cool_fuel is not None:
        utilities_df_hourly[cool_fuel] += cool_use_hourly
    utilities_df_hourly[dhw_fuel] += dhw_use_hourly

    if not np.allclose(utilities_df_hourly.sum().sum(), end_use_df_hourly.sum().sum()):
        msg = "Utilities df and end use df do not sum to the same value!"
        raise ValueError(msg)

    utility_max = utilities_df_hourly.max()
    utility_monthly_hourly_max = utilities_df_hourly.resample("MS").max()
    utility_max.index.name = "Meter"
    max_data = pd.concat(
        [utility_max, raw_hourly_max],
        axis=0,
        keys=["Utilities", "Raw"],
        names=["Aggregation", "Meter"],
    ).fillna(0)
    max_data = cast(pd.Series, max_data).rename("kW/m2")

    utility_monthly_hourly_max.index = pd.RangeIndex(1, 13, 1, name="Month")
    raw_monthly_hourly_max.index = pd.RangeIndex(1, 13, 1, name="Month")
    max_data_monthly = pd.concat(
        [utility_monthly_hourly_max, raw_monthly_hourly_max],
        axis=1,
        keys=["Utilities", "Raw"],
        names=["Aggregation"],
    ).fillna(0)

    peaks_series = cast(pd.Series, max_data_monthly.unstack()).fillna(0).rename("kW/m2")
    all_data = pd.concat(
        [energy_series, peaks_series],
        keys=["Energy", "Peak"],
        names=["Measurement"],
    )

    return all_data
