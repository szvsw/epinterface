"""Flat model used for calibration."""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from epinterface.sbem.builder import ModelRunResults
    from epinterface.sbem.building_flat_model import BuildingFlatModel

import pandas as pd
from archetypal import IDF
from pydantic import BaseModel, Field

from epinterface.analysis.overheating import OverheatingAnalysisConfig
from epinterface.geometry import ShoeboxGeometry, ZoningType
from epinterface.sbem.builder import (
    AtticAssumptions,
    BasementAssumptions,
    Model,
    SimulationPathConfig,
)
from epinterface.sbem.components.envelope import (
    ConstructionAssemblyComponent,
    ConstructionLayerComponent,
    EnvelopeAssemblyComponent,
    GlazingConstructionSimpleComponent,
    InfiltrationComponent,
    ZoneEnvelopeComponent,
)
from epinterface.sbem.components.materials import ConstructionMaterialComponent
from epinterface.sbem.components.operations import ZoneOperationsComponent
from epinterface.sbem.components.schedules import (
    DayComponent,
    WeekComponent,
    YearComponent,
    YearScheduleCategory,
)
from epinterface.sbem.components.space_use import (
    EquipmentComponent,
    LightingComponent,
    OccupancyComponent,
    ThermostatComponent,
    WaterUseComponent,
    ZoneSpaceUseComponent,
)
from epinterface.sbem.components.systems import (
    ConditioningSystemsComponent,
    DHWComponent,
    ThermalSystemComponent,
    VentilationComponent,
    ZoneHVACComponent,
)
from epinterface.sbem.components.zones import ZoneComponent
from epinterface.sbem.zone_assignment import (
    ParsedZoneKey,
    ZoneAssignmentTable,
    parse_zone_key,
)
from epinterface.sbem.zone_params import ZoneParams
from epinterface.weather import WeatherUrl

xps_board = ConstructionMaterialComponent(
    Name="XPSBoard",
    Conductivity=0.037,
    Density=40,
    SpecificHeat=1200,
    ThermalAbsorptance=0.9,
    SolarAbsorptance=0.6,
    VisibleAbsorptance=0.6,
    TemperatureCoefficientThermalConductivity=0.0,
    Roughness="MediumRough",
    Type="Insulation",
)

concrete_mc_light = ConstructionMaterialComponent(
    Name="ConcreteMC_Light",
    Conductivity=1.65,
    Density=2100,
    SpecificHeat=1040,
    ThermalAbsorptance=0.9,
    SolarAbsorptance=0.6,
    VisibleAbsorptance=0.6,
    TemperatureCoefficientThermalConductivity=0.0,
    Roughness="MediumRough",
    Type="Concrete",
)

concrete_rc_dense = ConstructionMaterialComponent(
    Name="ConcreteRC_Dense",
    Conductivity=1.75,
    Density=2400,
    SpecificHeat=840,
    ThermalAbsorptance=0.9,
    SolarAbsorptance=0.6,
    VisibleAbsorptance=0.6,
    TemperatureCoefficientThermalConductivity=0.0,
    Roughness="MediumRough",
    Type="Concrete",
)

gypsum_board = ConstructionMaterialComponent(
    Name="GypsumBoard",
    Conductivity=0.16,
    Density=950,
    SpecificHeat=840,
    ThermalAbsorptance=0.9,
    SolarAbsorptance=0.6,
    VisibleAbsorptance=0.6,
    TemperatureCoefficientThermalConductivity=0.0,
    Roughness="MediumRough",
    Type="Finishes",
)

gypsum_plaster = ConstructionMaterialComponent(
    Name="GypsumPlaster",
    Conductivity=0.42,
    Density=900,
    SpecificHeat=840,
    ThermalAbsorptance=0.9,
    SolarAbsorptance=0.6,
    VisibleAbsorptance=0.6,
    TemperatureCoefficientThermalConductivity=0.0,
    Roughness="MediumRough",
    Type="Finishes",
)

softwood_general = ConstructionMaterialComponent(
    Name="SoftwoodGeneral",
    Conductivity=0.13,
    Density=496,
    SpecificHeat=1630,
    ThermalAbsorptance=0.9,
    SolarAbsorptance=0.6,
    VisibleAbsorptance=0.6,
    TemperatureCoefficientThermalConductivity=0.0,
    Roughness="MediumRough",
    Type="Timber",
)

clay_brick = ConstructionMaterialComponent(
    Name="ClayBrick",
    Conductivity=0.41,
    Density=1000,
    SpecificHeat=920,
    ThermalAbsorptance=0.9,
    SolarAbsorptance=0.6,
    VisibleAbsorptance=0.6,
    TemperatureCoefficientThermalConductivity=0.0,
    Roughness="MediumRough",
    Type="Masonry",
)

concrete_block_h = ConstructionMaterialComponent(
    Name="ConcreteBlockH",
    Conductivity=1.25,
    Density=880,
    SpecificHeat=840,
    ThermalAbsorptance=0.9,
    SolarAbsorptance=0.6,
    VisibleAbsorptance=0.6,
    TemperatureCoefficientThermalConductivity=0.0,
    Roughness="MediumRough",
    Type="Concrete",
)

fiberglass_batts = ConstructionMaterialComponent(
    Name="FiberglassBatt",
    Conductivity=0.043,
    Density=12,
    SpecificHeat=840,
    ThermalAbsorptance=0.9,
    SolarAbsorptance=0.6,
    VisibleAbsorptance=0.6,
    TemperatureCoefficientThermalConductivity=0.0,
    Roughness="MediumRough",
    Type="Insulation",
)

cement_mortar = ConstructionMaterialComponent(
    Name="CementMortar",
    Conductivity=0.8,
    Density=1900,
    SpecificHeat=840,
    ThermalAbsorptance=0.9,
    SolarAbsorptance=0.6,
    VisibleAbsorptance=0.6,
    TemperatureCoefficientThermalConductivity=0.0,
    Roughness="MediumRough",
    Type="Other",
)

ceramic_tile = ConstructionMaterialComponent(
    Name="CeramicTile",
    Conductivity=0.8,
    Density=2243,
    SpecificHeat=840,
    ThermalAbsorptance=0.9,
    SolarAbsorptance=0.6,
    VisibleAbsorptance=0.6,
    TemperatureCoefficientThermalConductivity=0.0,
    Roughness="MediumRough",
    Type="Finishes",
)

urethane_carpet = ConstructionMaterialComponent(
    Name="UrethaneCarpet",
    Conductivity=0.045,
    Density=110,
    SpecificHeat=840,
    ThermalAbsorptance=0.9,
    SolarAbsorptance=0.6,
    VisibleAbsorptance=0.6,
    TemperatureCoefficientThermalConductivity=0.0,
    Roughness="MediumRough",
    Type="Finishes",
)


class ParametericYear(BaseModel):
    """A model for a year schedule that is parameterized by the base, and the interpolation factors."""

    Base: float = Field(default=..., ge=0, le=1)
    """Overnight Baseload"""

    AMInterp: float = Field(default=..., ge=0, le=1)
    """AM Hours: 6pm, 7pm, 8pm, Base + AMInterp * (1-Base)"""

    LunchInterp: float = Field(default=..., ge=0, le=1)
    """Lunch Hours: 12pm, 1pm Base + LunchInterp * (1-Base)"""

    PMInterp: float = Field(default=..., ge=0, le=1)
    """PM Hours: 6pm,7pm,8pm Base + PMInterp * (1-Base)"""

    WeekendPeakInterp: float = Field(default=..., ge=0, le=1)
    """Weekend Peak = Base + WeekendPeakInterp * (1-Base)"""

    SummerPeakInterp: float = Field(default=..., ge=0, le=1)
    """Summer Peak = Base + SummerPeakInterp * (1-Base)"""

    def to_schedule(self, name: str, category: YearScheduleCategory):
        """Convert the parameters to a schedule."""
        peak = 1
        am_inter = self.Base + self.AMInterp * (peak - self.Base)
        lunch_inter = self.Base + self.LunchInterp * (peak - self.Base)
        pm_inter = self.Base + self.PMInterp * (peak - self.Base)

        we_peak = self.Base + self.WeekendPeakInterp * (peak - self.Base)
        we_am_inter_val = self.Base + self.AMInterp * (we_peak - self.Base)
        we_lunch_inter_val = self.Base + self.LunchInterp * (we_peak - self.Base)
        we_pm_inter_val = self.Base + self.PMInterp * (we_peak - self.Base)

        summer_peak = self.Base + self.SummerPeakInterp * (peak - self.Base)
        summer_am_inter = self.Base + self.AMInterp * (summer_peak - self.Base)
        summer_lunch_inter = self.Base + self.LunchInterp * (summer_peak - self.Base)
        summer_pm_inter = self.Base + self.PMInterp * (summer_peak - self.Base)

        summer_we_peak = self.Base + self.SummerPeakInterp * (we_peak - self.Base)
        summer_we_am_inter = self.Base + self.AMInterp * (summer_we_peak - self.Base)
        summer_we_lunch_inter = self.Base + self.LunchInterp * (
            summer_we_peak - self.Base
        )
        summer_we_pm_inter = self.Base + self.PMInterp * (summer_we_peak - self.Base)

        weekday = DayComponent(
            Name=f"{name}_ParametericWeekday",
            Type="Fraction",
            Hour_00=self.Base,
            Hour_01=self.Base,
            Hour_02=self.Base,
            Hour_03=self.Base,
            Hour_04=self.Base,
            Hour_05=self.Base,
            Hour_06=am_inter,
            Hour_07=am_inter,
            Hour_08=am_inter,
            Hour_09=peak,
            Hour_10=peak,
            Hour_11=peak,
            Hour_12=lunch_inter,
            Hour_13=lunch_inter,
            Hour_14=peak,
            Hour_15=peak,
            Hour_16=peak,
            Hour_17=peak,
            Hour_18=pm_inter,
            Hour_19=pm_inter,
            Hour_20=pm_inter,
            Hour_21=self.Base,
            Hour_22=self.Base,
            Hour_23=self.Base,
        )

        weekend = DayComponent(
            Name=f"{name}_ParametericWeekend",
            Type="Fraction",
            Hour_00=self.Base,
            Hour_01=self.Base,
            Hour_02=self.Base,
            Hour_03=self.Base,
            Hour_04=self.Base,
            Hour_05=self.Base,
            Hour_06=we_am_inter_val,
            Hour_07=we_am_inter_val,
            Hour_08=we_am_inter_val,
            Hour_09=we_peak,
            Hour_10=we_peak,
            Hour_11=we_peak,
            Hour_12=we_lunch_inter_val,
            Hour_13=we_lunch_inter_val,
            Hour_14=we_peak,
            Hour_15=we_peak,
            Hour_16=we_peak,
            Hour_17=we_peak,
            Hour_18=we_pm_inter_val,
            Hour_19=we_pm_inter_val,
            Hour_20=we_pm_inter_val,
            Hour_21=self.Base,
            Hour_22=self.Base,
            Hour_23=self.Base,
        )

        summer_weekday = DayComponent(
            Name=f"{name}_ParametericSummerWeekday",
            Type="Fraction",
            Hour_00=self.Base,
            Hour_01=self.Base,
            Hour_02=self.Base,
            Hour_03=self.Base,
            Hour_04=self.Base,
            Hour_05=self.Base,
            Hour_06=summer_am_inter,
            Hour_07=summer_am_inter,
            Hour_08=summer_am_inter,
            Hour_09=summer_peak,
            Hour_10=summer_peak,
            Hour_11=summer_peak,
            Hour_12=summer_lunch_inter,
            Hour_13=summer_lunch_inter,
            Hour_14=summer_peak,
            Hour_15=summer_peak,
            Hour_16=summer_peak,
            Hour_17=summer_peak,
            Hour_18=summer_pm_inter,
            Hour_19=summer_pm_inter,
            Hour_20=summer_pm_inter,
            Hour_21=self.Base,
            Hour_22=self.Base,
            Hour_23=self.Base,
        )

        summer_weekend = DayComponent(
            Name=f"{name}_ParametericSummerWeekend",
            Type="Fraction",
            Hour_00=self.Base,
            Hour_01=self.Base,
            Hour_02=self.Base,
            Hour_03=self.Base,
            Hour_04=self.Base,
            Hour_05=self.Base,
            Hour_06=summer_we_am_inter,
            Hour_07=summer_we_am_inter,
            Hour_08=summer_we_am_inter,
            Hour_09=summer_we_peak,
            Hour_10=summer_we_peak,
            Hour_11=summer_we_peak,
            Hour_12=summer_we_lunch_inter,
            Hour_13=summer_we_lunch_inter,
            Hour_14=summer_we_peak,
            Hour_15=summer_we_peak,
            Hour_16=summer_we_peak,
            Hour_17=summer_we_peak,
            Hour_18=summer_we_pm_inter,
            Hour_19=summer_we_pm_inter,
            Hour_20=summer_we_pm_inter,
            Hour_21=self.Base,
            Hour_22=self.Base,
            Hour_23=self.Base,
        )

        regular_week = WeekComponent(
            Name=f"{name}_ParametericRegularWeek",
            Monday=weekday,
            Tuesday=weekday,
            Wednesday=weekday,
            Thursday=weekday,
            Friday=weekday,
            Saturday=weekend,
            Sunday=weekend,
        )

        summer_week = WeekComponent(
            Name=f"{name}_ParametericSummerWeek",
            Monday=summer_weekday,
            Tuesday=summer_weekday,
            Wednesday=summer_weekday,
            Thursday=summer_weekday,
            Friday=summer_weekday,
            Saturday=summer_weekend,
            Sunday=summer_weekend,
        )

        year = YearComponent(
            Name=f"{name}_ParametericYear",
            Type=category,
            January=regular_week,
            February=regular_week,
            March=regular_week,
            April=regular_week,
            May=regular_week,
            June=summer_week,
            July=summer_week,
            August=summer_week,
            September=regular_week,
            October=regular_week,
            November=regular_week,
            December=regular_week,
        )

        return year


def parameteric_weekday_hourly(params: ParametericYear) -> list[float]:
    """24 weekday hour fractions from parametric schedule shape."""
    peak = 1.0
    am_inter = params.Base + params.AMInterp * (peak - params.Base)
    lunch_inter = params.Base + params.LunchInterp * (peak - params.Base)
    pm_inter = params.Base + params.PMInterp * (peak - params.Base)
    return [
        params.Base,
        params.Base,
        params.Base,
        params.Base,
        params.Base,
        params.Base,
        am_inter,
        am_inter,
        am_inter,
        peak,
        peak,
        peak,
        lunch_inter,
        lunch_inter,
        peak,
        peak,
        peak,
        peak,
        pm_inter,
        pm_inter,
        pm_inter,
        params.Base,
        params.Base,
        params.Base,
    ]


def year_schedule_from_weekday_hourly(
    name: str,
    category: YearScheduleCategory,
    hourly: list[float],
) -> YearComponent:
    """Year schedule with the same weekday profile every day (all seasons)."""
    day = DayComponent(
        Name=f"{name}_CustomDay",
        Type="Fraction",
        **{f"Hour_{h:02d}": hourly[h] for h in range(24)},
    )
    week = WeekComponent(
        Name=f"{name}_CustomWeek",
        Monday=day,
        Tuesday=day,
        Wednesday=day,
        Thursday=day,
        Friday=day,
        Saturday=day,
        Sunday=day,
    )
    return YearComponent(
        Name=f"{name}_CustomYear",
        Type=category,
        January=week,
        February=week,
        March=week,
        April=week,
        May=week,
        June=week,
        July=week,
        August=week,
        September=week,
        October=week,
        November=week,
        December=week,
    )


class ParametricSetpoints(BaseModel):
    """A model for a setpoint schedule that is parameterized by the base, and the setbacks."""

    HeatingSetpoint: float = Field(ge=0, le=22)
    DeadBand: float = Field(ge=0, le=10)
    HeatingSetback: float = Field(ge=0, le=10)
    CoolingSetback: float = Field(ge=0, le=10)
    NightSetback: float = Field(ge=0, le=1)
    WeekendSetback: float = Field(ge=0, le=1)
    SummerSetback: float = Field(ge=0, le=1)

    def to_schedules(self, name_suffix: str = ""):
        """Convert the setpoint parameters to a set of schedules."""
        sfx = name_suffix.replace(" ", "_")
        hsp = self.HeatingSetpoint
        csp = hsp + self.DeadBand
        hsp_setback = hsp - self.HeatingSetback
        csp_setback = csp + self.CoolingSetback

        hsp_night = hsp - self.NightSetback * (hsp - hsp_setback)
        csp_night = csp + self.NightSetback * (csp_setback - csp)

        hsp_weekend_base = hsp - self.WeekendSetback * (hsp - hsp_setback)
        csp_weekend_base = csp + self.WeekendSetback * (csp_setback - csp)

        hsp_summer_base = hsp - self.SummerSetback * (hsp - hsp_setback)
        csp_summer_base = csp + self.SummerSetback * (csp_setback - csp)

        hsp_summer_weekend_base = hsp_summer_base - self.WeekendSetback * (
            hsp_summer_base - hsp_setback
        )
        csp_summer_weekend_base = csp_summer_base + self.WeekendSetback * (
            csp_setback - csp_summer_base
        )

        hsp_standard_day = DayComponent(
            Name=f"HSP_Standard_Day{sfx}",
            Type="Temperature",
            Hour_00=hsp_night,
            Hour_01=hsp_night,
            Hour_02=hsp_night,
            Hour_03=hsp_night,
            Hour_04=hsp_night,
            Hour_05=hsp_night,
            Hour_06=hsp_night,
            Hour_07=hsp,
            Hour_08=hsp,
            Hour_09=hsp,
            Hour_10=hsp,
            Hour_11=hsp,
            Hour_12=hsp,
            Hour_13=hsp,
            Hour_14=hsp,
            Hour_15=hsp,
            Hour_16=hsp,
            Hour_17=hsp,
            Hour_18=hsp,
            Hour_19=hsp_night,
            Hour_20=hsp_night,
            Hour_21=hsp_night,
            Hour_22=hsp_night,
            Hour_23=hsp_night,
        )

        hsp_weekend_day = DayComponent(
            Name=f"HSP_Weekend_Day{sfx}",
            Type="Temperature",
            Hour_00=hsp_night,
            Hour_01=hsp_night,
            Hour_02=hsp_night,
            Hour_03=hsp_night,
            Hour_04=hsp_night,
            Hour_05=hsp_night,
            Hour_06=hsp_night,
            Hour_07=hsp_weekend_base,
            Hour_08=hsp_weekend_base,
            Hour_09=hsp_weekend_base,
            Hour_10=hsp_weekend_base,
            Hour_11=hsp_weekend_base,
            Hour_12=hsp_weekend_base,
            Hour_13=hsp_weekend_base,
            Hour_14=hsp_weekend_base,
            Hour_15=hsp_weekend_base,
            Hour_16=hsp_weekend_base,
            Hour_17=hsp_weekend_base,
            Hour_18=hsp_weekend_base,
            Hour_19=hsp_night,
            Hour_20=hsp_night,
            Hour_21=hsp_night,
            Hour_22=hsp_night,
            Hour_23=hsp_night,
        )

        hsp_summer_day = DayComponent(
            Name=f"HSP_Summer_Day{sfx}",
            Type="Temperature",
            Hour_00=hsp_night,
            Hour_01=hsp_night,
            Hour_02=hsp_night,
            Hour_03=hsp_night,
            Hour_04=hsp_night,
            Hour_05=hsp_night,
            Hour_06=hsp_night,
            Hour_07=hsp_summer_base,
            Hour_08=hsp_summer_base,
            Hour_09=hsp_summer_base,
            Hour_10=hsp_summer_base,
            Hour_11=hsp_summer_base,
            Hour_12=hsp_summer_base,
            Hour_13=hsp_summer_base,
            Hour_14=hsp_summer_base,
            Hour_15=hsp_summer_base,
            Hour_16=hsp_summer_base,
            Hour_17=hsp_summer_base,
            Hour_18=hsp_summer_base,
            Hour_19=hsp_night,
            Hour_20=hsp_night,
            Hour_21=hsp_night,
            Hour_22=hsp_night,
            Hour_23=hsp_night,
        )

        hsp_summer_weekend_day = DayComponent(
            Name=f"HSP_Summer_Weekend_Day{sfx}",
            Type="Temperature",
            Hour_00=hsp_night,
            Hour_01=hsp_night,
            Hour_02=hsp_night,
            Hour_03=hsp_night,
            Hour_04=hsp_night,
            Hour_05=hsp_night,
            Hour_06=hsp_night,
            Hour_07=hsp_summer_weekend_base,
            Hour_08=hsp_summer_weekend_base,
            Hour_09=hsp_summer_weekend_base,
            Hour_10=hsp_summer_weekend_base,
            Hour_11=hsp_summer_weekend_base,
            Hour_12=hsp_summer_weekend_base,
            Hour_13=hsp_summer_weekend_base,
            Hour_14=hsp_summer_weekend_base,
            Hour_15=hsp_summer_weekend_base,
            Hour_16=hsp_summer_weekend_base,
            Hour_17=hsp_summer_weekend_base,
            Hour_18=hsp_summer_weekend_base,
            Hour_19=hsp_night,
            Hour_20=hsp_night,
            Hour_21=hsp_night,
            Hour_22=hsp_night,
            Hour_23=hsp_night,
        )

        csp_standard_day = DayComponent(
            Name=f"CSP_Standard_Day{sfx}",
            Type="Temperature",
            Hour_00=csp_night,
            Hour_01=csp_night,
            Hour_02=csp_night,
            Hour_03=csp_night,
            Hour_04=csp_night,
            Hour_05=csp_night,
            Hour_06=csp_night,
            Hour_07=csp,
            Hour_08=csp,
            Hour_09=csp,
            Hour_10=csp,
            Hour_11=csp,
            Hour_12=csp,
            Hour_13=csp,
            Hour_14=csp,
            Hour_15=csp,
            Hour_16=csp,
            Hour_17=csp,
            Hour_18=csp,
            Hour_19=csp_night,
            Hour_20=csp_night,
            Hour_21=csp_night,
            Hour_22=csp_night,
            Hour_23=csp_night,
        )

        csp_weekend_day = DayComponent(
            Name=f"CSP_Weekend_Day{sfx}",
            Type="Temperature",
            Hour_00=csp_night,
            Hour_01=csp_night,
            Hour_02=csp_night,
            Hour_03=csp_night,
            Hour_04=csp_night,
            Hour_05=csp_night,
            Hour_06=csp_night,
            Hour_07=csp_weekend_base,
            Hour_08=csp_weekend_base,
            Hour_09=csp_weekend_base,
            Hour_10=csp_weekend_base,
            Hour_11=csp_weekend_base,
            Hour_12=csp_weekend_base,
            Hour_13=csp_weekend_base,
            Hour_14=csp_weekend_base,
            Hour_15=csp_weekend_base,
            Hour_16=csp_weekend_base,
            Hour_17=csp_weekend_base,
            Hour_18=csp_weekend_base,
            Hour_19=csp_night,
            Hour_20=csp_night,
            Hour_21=csp_night,
            Hour_22=csp_night,
            Hour_23=csp_night,
        )

        csp_summer_day = DayComponent(
            Name=f"CSP_Summer_Day{sfx}",
            Type="Temperature",
            Hour_00=csp_night,
            Hour_01=csp_night,
            Hour_02=csp_night,
            Hour_03=csp_night,
            Hour_04=csp_night,
            Hour_05=csp_night,
            Hour_06=csp_night,
            Hour_07=csp_summer_base,
            Hour_08=csp_summer_base,
            Hour_09=csp_summer_base,
            Hour_10=csp_summer_base,
            Hour_11=csp_summer_base,
            Hour_12=csp_summer_base,
            Hour_13=csp_summer_base,
            Hour_14=csp_summer_base,
            Hour_15=csp_summer_base,
            Hour_16=csp_summer_base,
            Hour_17=csp_summer_base,
            Hour_18=csp_summer_base,
            Hour_19=csp_night,
            Hour_20=csp_night,
            Hour_21=csp_night,
            Hour_22=csp_night,
            Hour_23=csp_night,
        )

        csp_summer_weekend_day = DayComponent(
            Name=f"CSP_Summer_Weekend_Day{sfx}",
            Type="Temperature",
            Hour_00=csp_night,
            Hour_01=csp_night,
            Hour_02=csp_night,
            Hour_03=csp_night,
            Hour_04=csp_night,
            Hour_05=csp_night,
            Hour_06=csp_night,
            Hour_07=csp_summer_weekend_base,
            Hour_08=csp_summer_weekend_base,
            Hour_09=csp_summer_weekend_base,
            Hour_10=csp_summer_weekend_base,
            Hour_11=csp_summer_weekend_base,
            Hour_12=csp_summer_weekend_base,
            Hour_13=csp_summer_weekend_base,
            Hour_14=csp_summer_weekend_base,
            Hour_15=csp_summer_weekend_base,
            Hour_16=csp_summer_weekend_base,
            Hour_17=csp_summer_weekend_base,
            Hour_18=csp_summer_weekend_base,
            Hour_19=csp_night,
            Hour_20=csp_night,
            Hour_21=csp_night,
            Hour_22=csp_night,
            Hour_23=csp_night,
        )

        hsp_standard_week = WeekComponent(
            Name=f"HSP_Standard_Week{sfx}",
            Monday=hsp_standard_day,
            Tuesday=hsp_standard_day,
            Wednesday=hsp_standard_day,
            Thursday=hsp_standard_day,
            Friday=hsp_standard_day,
            Saturday=hsp_weekend_day,
            Sunday=hsp_weekend_day,
        )

        csp_standard_week = WeekComponent(
            Name=f"CSP_Standard_Week{sfx}",
            Monday=csp_standard_day,
            Tuesday=csp_standard_day,
            Wednesday=csp_standard_day,
            Thursday=csp_standard_day,
            Friday=csp_standard_day,
            Saturday=csp_weekend_day,
            Sunday=csp_weekend_day,
        )

        hsp_summer_week = WeekComponent(
            Name=f"HSP_Summer_Week{sfx}",
            Monday=hsp_summer_day,
            Tuesday=hsp_summer_day,
            Wednesday=hsp_summer_day,
            Thursday=hsp_summer_day,
            Friday=hsp_summer_day,
            Saturday=hsp_summer_weekend_day,
            Sunday=hsp_summer_weekend_day,
        )

        csp_summer_week = WeekComponent(
            Name=f"CSP_Summer_Week{sfx}",
            Monday=csp_summer_day,
            Tuesday=csp_summer_day,
            Wednesday=csp_summer_day,
            Thursday=csp_summer_day,
            Friday=csp_summer_day,
            Saturday=csp_summer_weekend_day,
            Sunday=csp_summer_weekend_day,
        )

        hsp_year = YearComponent(
            Name=f"HSP_Year{sfx}",
            Type="Setpoint",
            January=hsp_standard_week,
            February=hsp_standard_week,
            March=hsp_standard_week,
            April=hsp_standard_week,
            May=hsp_standard_week,
            June=hsp_summer_week,
            July=hsp_summer_week,
            August=hsp_summer_week,
            September=hsp_standard_week,
            October=hsp_standard_week,
            November=hsp_standard_week,
            December=hsp_standard_week,
        )

        csp_year = YearComponent(
            Name=f"CSP_Year{sfx}",
            Type="Setpoint",
            January=csp_standard_week,
            February=csp_standard_week,
            March=csp_standard_week,
            April=csp_standard_week,
            May=csp_standard_week,
            June=csp_summer_week,
            July=csp_summer_week,
            August=csp_summer_week,
            September=csp_standard_week,
            October=csp_standard_week,
            November=csp_standard_week,
            December=csp_standard_week,
        )

        return hsp_year, csp_year


def zone_params_to_zone_component(
    params: ZoneParams, *, id_tag: str = ""
) -> ZoneComponent:
    """Build a ZoneComponent from flat scalar zone parameters.

    Args:
        params: Zone calibration scalars.
        id_tag: optional suffix for facade/window/envelope names so multiple zones can differ.
    """
    sfx = ("_" + id_tag.replace(" ", "_")) if id_tag else ""
    # occ_regular_workday = DayComponent(
    #     Name=f"Occupancy_Regular_Workday{sfx}",
    #     Type="Fraction",
    #     Hour_00=params.OccupancyRegularWeekdayNight,
    #     Hour_01=params.OccupancyRegularWeekdayNight,
    #     Hour_02=params.OccupancyRegularWeekdayNight,
    #     Hour_03=params.OccupancyRegularWeekdayNight,
    #     Hour_04=params.OccupancyRegularWeekdayNight,
    #     Hour_05=params.OccupancyRegularWeekdayNight,
    #     Hour_06=params.OccupancyRegularWeekdayEarlyMorning,
    #     Hour_07=params.OccupancyRegularWeekdayEarlyMorning,
    #     Hour_08=params.OccupancyRegularWeekdayEarlyMorning,
    #     Hour_09=params.OccupancyRegularWeekdayMorning,
    #     Hour_10=params.OccupancyRegularWeekdayMorning,
    #     Hour_11=params.OccupancyRegularWeekdayMorning,
    #     Hour_12=params.OccupancyRegularWeekdayLunch,
    #     Hour_13=params.OccupancyRegularWeekdayLunch,
    #     Hour_14=params.OccupancyRegularWeekdayAfternoon,
    #     Hour_15=params.OccupancyRegularWeekdayAfternoon,
    #     Hour_16=params.OccupancyRegularWeekdayAfternoon,
    #     Hour_17=params.OccupancyRegularWeekdayAfternoon,
    #     Hour_18=params.OccupancyRegularWeekdayEvening,
    #     Hour_19=params.OccupancyRegularWeekdayEvening,
    #     Hour_20=params.OccupancyRegularWeekdayEvening,
    #     Hour_21=params.OccupancyRegularWeekdayNight,
    #     Hour_22=params.OccupancyRegularWeekdayNight,
    #     Hour_23=params.OccupancyRegularWeekdayNight,
    # )

    # occ_regular_weekend = DayComponent(
    #     Name=f"Occupancy_Regular_Weekend{sfx}",
    #     Type="Fraction",
    #     Hour_00=params.OccupancyRegularWeekendNight,
    #     Hour_01=params.OccupancyRegularWeekendNight,
    #     Hour_02=params.OccupancyRegularWeekendNight,
    #     Hour_03=params.OccupancyRegularWeekendNight,
    #     Hour_04=params.OccupancyRegularWeekendNight,
    #     Hour_05=params.OccupancyRegularWeekendNight,
    #     Hour_06=params.OccupancyRegularWeekendEarlyMorning,
    #     Hour_07=params.OccupancyRegularWeekendEarlyMorning,
    #     Hour_08=params.OccupancyRegularWeekendEarlyMorning,
    #     Hour_09=params.OccupancyRegularWeekendMorning,
    #     Hour_10=params.OccupancyRegularWeekendMorning,
    #     Hour_11=params.OccupancyRegularWeekendMorning,
    #     Hour_12=params.OccupancyRegularWeekendLunch,
    #     Hour_13=params.OccupancyRegularWeekendLunch,
    #     Hour_14=params.OccupancyRegularWeekendAfternoon,
    #     Hour_15=params.OccupancyRegularWeekendAfternoon,
    #     Hour_16=params.OccupancyRegularWeekendAfternoon,
    #     Hour_17=params.OccupancyRegularWeekendAfternoon,
    #     Hour_18=params.OccupancyRegularWeekendEvening,
    #     Hour_19=params.OccupancyRegularWeekendEvening,
    #     Hour_20=params.OccupancyRegularWeekendEvening,
    #     Hour_21=params.OccupancyRegularWeekendNight,
    #     Hour_22=params.OccupancyRegularWeekendNight,
    #     Hour_23=params.OccupancyRegularWeekendNight,
    # )

    # occ_summer_workday = DayComponent(
    #     Name=f"Occupancy_Summer_Workday{sfx}",
    #     Type="Fraction",
    #     Hour_00=params.OccupancySummerWeekdayNight,
    #     Hour_01=params.OccupancySummerWeekdayNight,
    #     Hour_02=params.OccupancySummerWeekdayNight,
    #     Hour_03=params.OccupancySummerWeekdayNight,
    #     Hour_04=params.OccupancySummerWeekdayNight,
    #     Hour_05=params.OccupancySummerWeekdayNight,
    #     Hour_06=params.OccupancySummerWeekdayEarlyMorning,
    #     Hour_07=params.OccupancySummerWeekdayEarlyMorning,
    #     Hour_08=params.OccupancySummerWeekdayEarlyMorning,
    #     Hour_09=params.OccupancySummerWeekdayMorning,
    #     Hour_10=params.OccupancySummerWeekdayMorning,
    #     Hour_11=params.OccupancySummerWeekdayMorning,
    #     Hour_12=params.OccupancySummerWeekdayLunch,
    #     Hour_13=params.OccupancySummerWeekdayLunch,
    #     Hour_14=params.OccupancySummerWeekdayAfternoon,
    #     Hour_15=params.OccupancySummerWeekdayAfternoon,
    #     Hour_16=params.OccupancySummerWeekdayAfternoon,
    #     Hour_17=params.OccupancySummerWeekdayAfternoon,
    #     Hour_18=params.OccupancySummerWeekdayEvening,
    #     Hour_19=params.OccupancySummerWeekdayEvening,
    #     Hour_20=params.OccupancySummerWeekdayEvening,
    #     Hour_21=params.OccupancySummerWeekdayNight,
    #     Hour_22=params.OccupancySummerWeekdayNight,
    #     Hour_23=params.OccupancySummerWeekdayNight,
    # )

    # occ_summer_weekend = DayComponent(
    #     Name=f"Occupancy_Summer_Weekend{sfx}",
    #     Type="Fraction",
    #     Hour_00=params.OccupancySummerWeekendNight,
    #     Hour_01=params.OccupancySummerWeekendNight,
    #     Hour_02=params.OccupancySummerWeekendNight,
    #     Hour_03=params.OccupancySummerWeekendNight,
    #     Hour_04=params.OccupancySummerWeekendNight,
    #     Hour_05=params.OccupancySummerWeekendNight,
    #     Hour_06=params.OccupancySummerWeekendEarlyMorning,
    #     Hour_07=params.OccupancySummerWeekendEarlyMorning,
    #     Hour_08=params.OccupancySummerWeekendEarlyMorning,
    #     Hour_09=params.OccupancySummerWeekendMorning,
    #     Hour_10=params.OccupancySummerWeekendMorning,
    #     Hour_11=params.OccupancySummerWeekendMorning,
    #     Hour_12=params.OccupancySummerWeekendLunch,
    #     Hour_13=params.OccupancySummerWeekendLunch,
    #     Hour_14=params.OccupancySummerWeekendAfternoon,
    #     Hour_15=params.OccupancySummerWeekendAfternoon,
    #     Hour_16=params.OccupancySummerWeekendAfternoon,
    #     Hour_17=params.OccupancySummerWeekendAfternoon,
    #     Hour_18=params.OccupancySummerWeekendEvening,
    #     Hour_19=params.OccupancySummerWeekendEvening,
    #     Hour_20=params.OccupancySummerWeekendEvening,
    #     Hour_21=params.OccupancySummerWeekendNight,
    #     Hour_22=params.OccupancySummerWeekendNight,
    #     Hour_23=params.OccupancySummerWeekendNight,
    # )

    # occ_regular_week = WeekComponent(
    #     Name=f"Occupancy_Regular_Week{sfx}",
    #     Monday=occ_regular_workday,
    #     Tuesday=occ_regular_workday,
    #     Wednesday=occ_regular_workday,
    #     Thursday=occ_regular_workday,
    #     Friday=occ_regular_workday,
    #     Saturday=occ_regular_weekend,
    #     Sunday=occ_regular_weekend,
    # )

    # occ_summer_week = WeekComponent(
    #     Name=f"Occupancy_Summer_Week{sfx}",
    #     Monday=occ_summer_workday,
    #     Tuesday=occ_summer_workday,
    #     Wednesday=occ_summer_workday,
    #     Thursday=occ_summer_workday,
    #     Friday=occ_summer_workday,
    #     Saturday=occ_summer_weekend,
    #     Sunday=occ_summer_weekend,
    # )

    # occ_year = YearComponent(
    #     Name=f"Occupancy_Schedule{sfx}",
    #     Type="Occupancy",
    #     January=occ_regular_week,
    #     February=occ_regular_week,
    #     March=occ_regular_week,
    #     April=occ_regular_week,
    #     May=occ_regular_week,
    #     June=occ_summer_week,
    #     July=occ_summer_week,
    #     August=occ_summer_week,
    #     September=occ_regular_week,
    #     October=occ_regular_week,
    #     November=occ_regular_week,
    #     December=occ_regular_week,
    # )

    # lighting_regular_workday = DayComponent(
    #     Name=f"Lighting_Regular_Workday{sfx}",
    #     Type="Fraction",
    #     Hour_00=params.LightingRegularWeekdayNight,
    #     Hour_01=params.LightingRegularWeekdayNight,
    #     Hour_02=params.LightingRegularWeekdayNight,
    #     Hour_03=params.LightingRegularWeekdayNight,
    #     Hour_04=params.LightingRegularWeekdayNight,
    #     Hour_05=params.LightingRegularWeekdayNight,
    #     Hour_06=params.LightingRegularWeekdayEarlyMorning,
    #     Hour_07=params.LightingRegularWeekdayEarlyMorning,
    #     Hour_08=params.LightingRegularWeekdayEarlyMorning,
    #     Hour_09=params.LightingRegularWeekdayMorning,
    #     Hour_10=params.LightingRegularWeekdayMorning,
    #     Hour_11=params.LightingRegularWeekdayMorning,
    #     Hour_12=params.LightingRegularWeekdayLunch,
    #     Hour_13=params.LightingRegularWeekdayLunch,
    #     Hour_14=params.LightingRegularWeekdayAfternoon,
    #     Hour_15=params.LightingRegularWeekdayAfternoon,
    #     Hour_16=params.LightingRegularWeekdayAfternoon,
    #     Hour_17=params.LightingRegularWeekdayAfternoon,
    #     Hour_18=params.LightingRegularWeekdayEvening,
    #     Hour_19=params.LightingRegularWeekdayEvening,
    #     Hour_20=params.LightingRegularWeekdayEvening,
    #     Hour_21=params.LightingRegularWeekdayNight,
    #     Hour_22=params.LightingRegularWeekdayNight,
    #     Hour_23=params.LightingRegularWeekdayNight,
    # )

    # lighting_regular_weekend = DayComponent(
    #     Name=f"Lighting_Regular_Weekend{sfx}",
    #     Type="Fraction",
    #     Hour_00=params.LightingRegularWeekendNight,
    #     Hour_01=params.LightingRegularWeekendNight,
    #     Hour_02=params.LightingRegularWeekendNight,
    #     Hour_03=params.LightingRegularWeekendNight,
    #     Hour_04=params.LightingRegularWeekendNight,
    #     Hour_05=params.LightingRegularWeekendNight,
    #     Hour_06=params.LightingRegularWeekendEarlyMorning,
    #     Hour_07=params.LightingRegularWeekendEarlyMorning,
    #     Hour_08=params.LightingRegularWeekendEarlyMorning,
    #     Hour_09=params.LightingRegularWeekendMorning,
    #     Hour_10=params.LightingRegularWeekendMorning,
    #     Hour_11=params.LightingRegularWeekendMorning,
    #     Hour_12=params.LightingRegularWeekendLunch,
    #     Hour_13=params.LightingRegularWeekendLunch,
    #     Hour_14=params.LightingRegularWeekendAfternoon,
    #     Hour_15=params.LightingRegularWeekendAfternoon,
    #     Hour_16=params.LightingRegularWeekendAfternoon,
    #     Hour_17=params.LightingRegularWeekendAfternoon,
    #     Hour_18=params.LightingRegularWeekendEvening,
    #     Hour_19=params.LightingRegularWeekendEvening,
    #     Hour_20=params.LightingRegularWeekendEvening,
    #     Hour_21=params.LightingRegularWeekendNight,
    #     Hour_22=params.LightingRegularWeekendNight,
    #     Hour_23=params.LightingRegularWeekendNight,
    # )

    # lighting_summer_workday = DayComponent(
    #     Name=f"Lighting_Summer_Workday{sfx}",
    #     Type="Fraction",
    #     Hour_00=params.LightingSummerWeekdayNight,
    #     Hour_01=params.LightingSummerWeekdayNight,
    #     Hour_02=params.LightingSummerWeekdayNight,
    #     Hour_03=params.LightingSummerWeekdayNight,
    #     Hour_04=params.LightingSummerWeekdayNight,
    #     Hour_05=params.LightingSummerWeekdayNight,
    #     Hour_06=params.LightingSummerWeekdayEarlyMorning,
    #     Hour_07=params.LightingSummerWeekdayEarlyMorning,
    #     Hour_08=params.LightingSummerWeekdayEarlyMorning,
    #     Hour_09=params.LightingSummerWeekdayMorning,
    #     Hour_10=params.LightingSummerWeekdayMorning,
    #     Hour_11=params.LightingSummerWeekdayMorning,
    #     Hour_12=params.LightingSummerWeekdayLunch,
    #     Hour_13=params.LightingSummerWeekdayLunch,
    #     Hour_14=params.LightingSummerWeekdayAfternoon,
    #     Hour_15=params.LightingSummerWeekdayAfternoon,
    #     Hour_16=params.LightingSummerWeekdayAfternoon,
    #     Hour_17=params.LightingSummerWeekdayAfternoon,
    #     Hour_18=params.LightingSummerWeekdayEvening,
    #     Hour_19=params.LightingSummerWeekdayEvening,
    #     Hour_20=params.LightingSummerWeekdayEvening,
    #     Hour_21=params.LightingSummerWeekdayNight,
    #     Hour_22=params.LightingSummerWeekdayNight,
    #     Hour_23=params.LightingSummerWeekdayNight,
    # )

    # lighting_summer_weekend = DayComponent(
    #     Name=f"Lighting_Summer_Weekend{sfx}",
    #     Type="Fraction",
    #     Hour_00=params.LightingSummerWeekendNight,
    #     Hour_01=params.LightingSummerWeekendNight,
    #     Hour_02=params.LightingSummerWeekendNight,
    #     Hour_03=params.LightingSummerWeekendNight,
    #     Hour_04=params.LightingSummerWeekendNight,
    #     Hour_05=params.LightingSummerWeekendNight,
    #     Hour_06=params.LightingSummerWeekendEarlyMorning,
    #     Hour_07=params.LightingSummerWeekendEarlyMorning,
    #     Hour_08=params.LightingSummerWeekendEarlyMorning,
    #     Hour_09=params.LightingSummerWeekendMorning,
    #     Hour_10=params.LightingSummerWeekendMorning,
    #     Hour_11=params.LightingSummerWeekendMorning,
    #     Hour_12=params.LightingSummerWeekendLunch,
    #     Hour_13=params.LightingSummerWeekendLunch,
    #     Hour_14=params.LightingSummerWeekendAfternoon,
    #     Hour_15=params.LightingSummerWeekendAfternoon,
    #     Hour_16=params.LightingSummerWeekendAfternoon,
    #     Hour_17=params.LightingSummerWeekendAfternoon,
    #     Hour_18=params.LightingSummerWeekendEvening,
    #     Hour_19=params.LightingSummerWeekendEvening,
    #     Hour_20=params.LightingSummerWeekendEvening,
    #     Hour_21=params.LightingSummerWeekendNight,
    #     Hour_22=params.LightingSummerWeekendNight,
    #     Hour_23=params.LightingSummerWeekendNight,
    # )

    # lighting_regular_week = WeekComponent(
    #     Name=f"Lighting_Regular_Week{sfx}",
    #     Monday=lighting_regular_workday,
    #     Tuesday=lighting_regular_workday,
    #     Wednesday=lighting_regular_workday,
    #     Thursday=lighting_regular_workday,
    #     Friday=lighting_regular_workday,
    #     Saturday=lighting_regular_weekend,
    #     Sunday=lighting_regular_weekend,
    # )

    # lighting_summer_week = WeekComponent(
    #     Name=f"Lighting_Summer_Week{sfx}",
    #     Monday=lighting_summer_workday,
    #     Tuesday=lighting_summer_workday,
    #     Wednesday=lighting_summer_workday,
    #     Thursday=lighting_summer_workday,
    #     Friday=lighting_summer_workday,
    #     Saturday=lighting_summer_weekend,
    #     Sunday=lighting_summer_weekend,
    # )

    # lighting_year = YearComponent(
    #     Name=f"Lighting_Schedule{sfx}",
    #     Type="Lighting",
    #     January=lighting_regular_week,
    #     February=lighting_regular_week,
    #     March=lighting_regular_week,
    #     April=lighting_regular_week,
    #     May=lighting_regular_week,
    #     June=lighting_summer_week,
    #     July=lighting_summer_week,
    #     August=lighting_summer_week,
    #     September=lighting_regular_week,
    #     October=lighting_regular_week,
    #     November=lighting_regular_week,
    #     December=lighting_regular_week,
    # )

    # equipment_regular_workday = DayComponent(
    #     Name=f"Equipment_Regular_Workday{sfx}",
    #     Type="Fraction",
    #     Hour_00=params.EquipmentRegularWeekdayNight,
    #     Hour_01=params.EquipmentRegularWeekdayNight,
    #     Hour_02=params.EquipmentRegularWeekdayNight,
    #     Hour_03=params.EquipmentRegularWeekdayNight,
    #     Hour_04=params.EquipmentRegularWeekdayNight,
    #     Hour_05=params.EquipmentRegularWeekdayNight,
    #     Hour_06=params.EquipmentRegularWeekdayEarlyMorning,
    #     Hour_07=params.EquipmentRegularWeekdayEarlyMorning,
    #     Hour_08=params.EquipmentRegularWeekdayEarlyMorning,
    #     Hour_09=params.EquipmentRegularWeekdayMorning,
    #     Hour_10=params.EquipmentRegularWeekdayMorning,
    #     Hour_11=params.EquipmentRegularWeekdayMorning,
    #     Hour_12=params.EquipmentRegularWeekdayLunch,
    #     Hour_13=params.EquipmentRegularWeekdayLunch,
    #     Hour_14=params.EquipmentRegularWeekdayAfternoon,
    #     Hour_15=params.EquipmentRegularWeekdayAfternoon,
    #     Hour_16=params.EquipmentRegularWeekdayAfternoon,
    #     Hour_17=params.EquipmentRegularWeekdayAfternoon,
    #     Hour_18=params.EquipmentRegularWeekdayEvening,
    #     Hour_19=params.EquipmentRegularWeekdayEvening,
    #     Hour_20=params.EquipmentRegularWeekdayEvening,
    #     Hour_21=params.EquipmentRegularWeekdayNight,
    #     Hour_22=params.EquipmentRegularWeekdayNight,
    #     Hour_23=params.EquipmentRegularWeekdayNight,
    # )

    # equipment_regular_weekend = DayComponent(
    #     Name=f"Equipment_Regular_Weekend{sfx}",
    #     Type="Fraction",
    #     Hour_00=params.EquipmentRegularWeekendNight,
    #     Hour_01=params.EquipmentRegularWeekendNight,
    #     Hour_02=params.EquipmentRegularWeekendNight,
    #     Hour_03=params.EquipmentRegularWeekendNight,
    #     Hour_04=params.EquipmentRegularWeekendNight,
    #     Hour_05=params.EquipmentRegularWeekendNight,
    #     Hour_06=params.EquipmentRegularWeekendEarlyMorning,
    #     Hour_07=params.EquipmentRegularWeekendEarlyMorning,
    #     Hour_08=params.EquipmentRegularWeekendEarlyMorning,
    #     Hour_09=params.EquipmentRegularWeekendMorning,
    #     Hour_10=params.EquipmentRegularWeekendMorning,
    #     Hour_11=params.EquipmentRegularWeekendMorning,
    #     Hour_12=params.EquipmentRegularWeekendLunch,
    #     Hour_13=params.EquipmentRegularWeekendLunch,
    #     Hour_14=params.EquipmentRegularWeekendAfternoon,
    #     Hour_15=params.EquipmentRegularWeekendAfternoon,
    #     Hour_16=params.EquipmentRegularWeekendAfternoon,
    #     Hour_17=params.EquipmentRegularWeekendAfternoon,
    #     Hour_18=params.EquipmentRegularWeekendEvening,
    #     Hour_19=params.EquipmentRegularWeekendEvening,
    #     Hour_20=params.EquipmentRegularWeekendEvening,
    #     Hour_21=params.EquipmentRegularWeekendNight,
    #     Hour_22=params.EquipmentRegularWeekendNight,
    #     Hour_23=params.EquipmentRegularWeekendNight,
    # )

    # equipment_summer_workday = DayComponent(
    #     Name=f"Equipment_Summer_Workday{sfx}",
    #     Type="Fraction",
    #     Hour_00=params.EquipmentSummerWeekdayNight,
    #     Hour_01=params.EquipmentSummerWeekdayNight,
    #     Hour_02=params.EquipmentSummerWeekdayNight,
    #     Hour_03=params.EquipmentSummerWeekdayNight,
    #     Hour_04=params.EquipmentSummerWeekdayNight,
    #     Hour_05=params.EquipmentSummerWeekdayNight,
    #     Hour_06=params.EquipmentSummerWeekdayEarlyMorning,
    #     Hour_07=params.EquipmentSummerWeekdayEarlyMorning,
    #     Hour_08=params.EquipmentSummerWeekdayEarlyMorning,
    #     Hour_09=params.EquipmentSummerWeekdayMorning,
    #     Hour_10=params.EquipmentSummerWeekdayMorning,
    #     Hour_11=params.EquipmentSummerWeekdayMorning,
    #     Hour_12=params.EquipmentSummerWeekdayLunch,
    #     Hour_13=params.EquipmentSummerWeekdayLunch,
    #     Hour_14=params.EquipmentSummerWeekdayAfternoon,
    #     Hour_15=params.EquipmentSummerWeekdayAfternoon,
    #     Hour_16=params.EquipmentSummerWeekdayAfternoon,
    #     Hour_17=params.EquipmentSummerWeekdayAfternoon,
    #     Hour_18=params.EquipmentSummerWeekdayEvening,
    #     Hour_19=params.EquipmentSummerWeekdayEvening,
    #     Hour_20=params.EquipmentSummerWeekdayEvening,
    #     Hour_21=params.EquipmentSummerWeekdayNight,
    #     Hour_22=params.EquipmentSummerWeekdayNight,
    #     Hour_23=params.EquipmentSummerWeekdayNight,
    # )

    # equipment_summer_weekend = DayComponent(
    #     Name=f"Equipment_Summer_Weekend{sfx}",
    #     Type="Fraction",
    #     Hour_00=params.EquipmentSummerWeekendNight,
    #     Hour_01=params.EquipmentSummerWeekendNight,
    #     Hour_02=params.EquipmentSummerWeekendNight,
    #     Hour_03=params.EquipmentSummerWeekendNight,
    #     Hour_04=params.EquipmentSummerWeekendNight,
    #     Hour_05=params.EquipmentSummerWeekendNight,
    #     Hour_06=params.EquipmentSummerWeekendEarlyMorning,
    #     Hour_07=params.EquipmentSummerWeekendEarlyMorning,
    #     Hour_08=params.EquipmentSummerWeekendEarlyMorning,
    #     Hour_09=params.EquipmentSummerWeekendMorning,
    #     Hour_10=params.EquipmentSummerWeekendMorning,
    #     Hour_11=params.EquipmentSummerWeekendMorning,
    #     Hour_12=params.EquipmentSummerWeekendLunch,
    #     Hour_13=params.EquipmentSummerWeekendLunch,
    #     Hour_14=params.EquipmentSummerWeekendAfternoon,
    #     Hour_15=params.EquipmentSummerWeekendAfternoon,
    #     Hour_16=params.EquipmentSummerWeekendAfternoon,
    #     Hour_17=params.EquipmentSummerWeekendAfternoon,
    #     Hour_18=params.EquipmentSummerWeekendEvening,
    #     Hour_19=params.EquipmentSummerWeekendEvening,
    #     Hour_20=params.EquipmentSummerWeekendEvening,
    #     Hour_21=params.EquipmentSummerWeekendNight,
    #     Hour_22=params.EquipmentSummerWeekendNight,
    #     Hour_23=params.EquipmentSummerWeekendNight,
    # )

    # equipment_regular_week = WeekComponent(
    #     Name=f"Equipment_Regular_Week{sfx}",
    #     Monday=equipment_regular_workday,
    #     Tuesday=equipment_regular_workday,
    #     Wednesday=equipment_regular_workday,
    #     Thursday=equipment_regular_workday,
    #     Friday=equipment_regular_workday,
    #     Saturday=equipment_regular_weekend,
    #     Sunday=equipment_regular_weekend,
    # )

    # equipment_summer_week = WeekComponent(
    #     Name=f"Equipment_Summer_Week{sfx}",
    #     Monday=equipment_summer_workday,
    #     Tuesday=equipment_summer_workday,
    #     Wednesday=equipment_summer_workday,
    #     Thursday=equipment_summer_workday,
    #     Friday=equipment_summer_workday,
    #     Saturday=equipment_summer_weekend,
    #     Sunday=equipment_summer_weekend,
    # )

    # equipment_year = YearComponent(
    #     Name=f"equipment_Schedule{sfx}",
    #     Type="Equipment",
    #     January=equipment_regular_week,
    #     February=equipment_regular_week,
    #     March=equipment_regular_week,
    #     April=equipment_regular_week,
    #     May=equipment_regular_week,
    #     June=equipment_summer_week,
    #     July=equipment_summer_week,
    #     August=equipment_summer_week,
    #     September=equipment_regular_week,
    #     October=equipment_regular_week,
    #     November=lighting_regular_week,
    #     December=equipment_regular_week,
    # )

    equipment_paramteric = ParametericYear(
        Base=params.EquipmentBase,
        AMInterp=params.EquipmentAMInterp,
        LunchInterp=params.EquipmentLunchInterp,
        PMInterp=params.EquipmentPMInterp,
        WeekendPeakInterp=params.EquipmentWeekendPeakInterp,
        SummerPeakInterp=params.EquipmentSummerPeakInterp,
    )

    lighting_paramteric = ParametericYear(
        Base=params.LightingBase,
        AMInterp=params.LightingAMInterp,
        LunchInterp=params.LightingLunchInterp,
        PMInterp=params.LightingPMInterp,
        WeekendPeakInterp=params.LightingWeekendPeakInterp,
        SummerPeakInterp=params.LightingSummerPeakInterp,
    )

    occupancy_paramteric = ParametericYear(
        Base=params.OccupancyBase,
        AMInterp=params.OccupancyAMInterp,
        LunchInterp=params.OccupancyLunchInterp,
        PMInterp=params.OccupancyPMInterp,
        WeekendPeakInterp=params.OccupancyWeekendPeakInterp,
        SummerPeakInterp=params.OccupancySummerPeakInterp,
    )

    if params.CustomEquipmentWeekdayHourly is not None:
        equipment_schedule = year_schedule_from_weekday_hourly(
            f"Equipment{sfx}",
            "Equipment",
            params.CustomEquipmentWeekdayHourly,
        )
    else:
        equipment_schedule = equipment_paramteric.to_schedule(
            name=f"Equipment{sfx}", category="Equipment"
        )
    if params.CustomLightingWeekdayHourly is not None:
        lighting_schedule = year_schedule_from_weekday_hourly(
            f"Lighting{sfx}",
            "Lighting",
            params.CustomLightingWeekdayHourly,
        )
    else:
        lighting_schedule = lighting_paramteric.to_schedule(
            name=f"Lighting{sfx}", category="Lighting"
        )
    if params.CustomOccupancyWeekdayHourly is not None:
        occupancy_schedule = year_schedule_from_weekday_hourly(
            f"Occupancy{sfx}",
            "Occupancy",
            params.CustomOccupancyWeekdayHourly,
        )
    else:
        occupancy_schedule = occupancy_paramteric.to_schedule(
            name=f"Occupancy{sfx}", category="Occupancy"
        )

    # hsp_regular_workday = DayComponent(
    #     Name=f"HeatingSetpoint_Regular_Workday{sfx}",
    #     Type="Temperature",
    #     Hour_00=params.HSPRegularWeekdayNight,
    #     Hour_01=params.HSPRegularWeekdayNight,
    #     Hour_02=params.HSPRegularWeekdayNight,
    #     Hour_03=params.HSPRegularWeekdayNight,
    #     Hour_04=params.HSPRegularWeekdayNight,
    #     Hour_05=params.HSPRegularWeekdayNight,
    #     Hour_06=params.HSPRegularWeekdayWorkhours,
    #     Hour_07=params.HSPRegularWeekdayWorkhours,
    #     Hour_08=params.HSPRegularWeekdayWorkhours,
    #     Hour_09=params.HSPRegularWeekdayWorkhours,
    #     Hour_10=params.HSPRegularWeekdayWorkhours,
    #     Hour_11=params.HSPRegularWeekdayWorkhours,
    #     Hour_12=params.HSPRegularWeekdayWorkhours,
    #     Hour_13=params.HSPRegularWeekdayWorkhours,
    #     Hour_14=params.HSPRegularWeekdayWorkhours,
    #     Hour_15=params.HSPRegularWeekdayWorkhours,
    #     Hour_16=params.HSPRegularWeekdayWorkhours,
    #     Hour_17=params.HSPRegularWeekdayWorkhours,
    #     Hour_18=params.HSPRegularWeekdayWorkhours,
    #     Hour_19=params.HSPRegularWeekdayNight,
    #     Hour_20=params.HSPRegularWeekdayNight,
    #     Hour_21=params.HSPRegularWeekdayNight,
    #     Hour_22=params.HSPRegularWeekdayNight,
    #     Hour_23=params.HSPRegularWeekdayNight,
    # )

    # hsp_regular_weekend = DayComponent(
    #     Name=f"HeatingSetpoint_Regular_Weekend{sfx}",
    #     Type="Temperature",
    #     Hour_00=params.HSPWeekendNight,
    #     Hour_01=params.HSPWeekendNight,
    #     Hour_02=params.HSPWeekendNight,
    #     Hour_03=params.HSPWeekendNight,
    #     Hour_04=params.HSPWeekendNight,
    #     Hour_05=params.HSPWeekendNight,
    #     Hour_06=params.HSPWeekendWorkhours,
    #     Hour_07=params.HSPWeekendWorkhours,
    #     Hour_08=params.HSPWeekendWorkhours,
    #     Hour_09=params.HSPWeekendWorkhours,
    #     Hour_10=params.HSPWeekendWorkhours,
    #     Hour_11=params.HSPWeekendWorkhours,
    #     Hour_12=params.HSPWeekendWorkhours,
    #     Hour_13=params.HSPWeekendWorkhours,
    #     Hour_14=params.HSPWeekendWorkhours,
    #     Hour_15=params.HSPWeekendWorkhours,
    #     Hour_16=params.HSPWeekendWorkhours,
    #     Hour_17=params.HSPWeekendWorkhours,
    #     Hour_18=params.HSPWeekendWorkhours,
    #     Hour_19=params.HSPWeekendNight,
    #     Hour_20=params.HSPWeekendNight,
    #     Hour_21=params.HSPWeekendNight,
    #     Hour_22=params.HSPWeekendNight,
    #     Hour_23=params.HSPWeekendNight,
    # )

    # hsp_summer_workday = DayComponent(
    #     Name=f"HeatingSetpoint_Summer_Workday{sfx}",
    #     Type="Temperature",
    #     Hour_00=params.HSPSummerWeekdayNight,
    #     Hour_01=params.HSPSummerWeekdayNight,
    #     Hour_02=params.HSPSummerWeekdayNight,
    #     Hour_03=params.HSPSummerWeekdayNight,
    #     Hour_04=params.HSPSummerWeekdayNight,
    #     Hour_05=params.HSPSummerWeekdayNight,
    #     Hour_06=params.HSPSummerWeekdayWorkhours,
    #     Hour_07=params.HSPSummerWeekdayWorkhours,
    #     Hour_08=params.HSPSummerWeekdayWorkhours,
    #     Hour_09=params.HSPSummerWeekdayWorkhours,
    #     Hour_10=params.HSPSummerWeekdayWorkhours,
    #     Hour_11=params.HSPSummerWeekdayWorkhours,
    #     Hour_12=params.HSPSummerWeekdayWorkhours,
    #     Hour_13=params.HSPSummerWeekdayWorkhours,
    #     Hour_14=params.HSPSummerWeekdayWorkhours,
    #     Hour_15=params.HSPSummerWeekdayWorkhours,
    #     Hour_16=params.HSPSummerWeekdayWorkhours,
    #     Hour_17=params.HSPSummerWeekdayWorkhours,
    #     Hour_18=params.HSPSummerWeekdayWorkhours,
    #     Hour_19=params.HSPSummerWeekdayNight,
    #     Hour_20=params.HSPSummerWeekdayNight,
    #     Hour_21=params.HSPSummerWeekdayNight,
    #     Hour_22=params.HSPSummerWeekdayNight,
    #     Hour_23=params.HSPSummerWeekdayNight,
    # )

    # hsp_regular_week = WeekComponent(
    #     Name=f"HeatingSetpoint_Regular_Week{sfx}",
    #     Monday=hsp_regular_workday,
    #     Tuesday=hsp_regular_workday,
    #     Wednesday=hsp_regular_workday,
    #     Thursday=hsp_regular_workday,
    #     Friday=hsp_regular_workday,
    #     Saturday=hsp_regular_weekend,
    #     Sunday=hsp_regular_weekend,
    # )

    # hsp_summer_week = WeekComponent(
    #     Name=f"HeatingSetpoint_Summer_Week{sfx}",
    #     Monday=hsp_summer_workday,
    #     Tuesday=hsp_summer_workday,
    #     Wednesday=hsp_summer_workday,
    #     Thursday=hsp_summer_workday,
    #     Friday=hsp_summer_workday,
    #     Saturday=hsp_regular_weekend,
    #     Sunday=hsp_regular_weekend,
    # )

    # hsp_year = YearComponent(
    #     Name=f"HeatingSetpoint_Schedule{sfx}",
    #     Type="Setpoint",
    #     January=hsp_regular_week,
    #     February=hsp_regular_week,
    #     March=hsp_regular_week,
    #     April=hsp_regular_week,
    #     May=hsp_regular_week,
    #     June=hsp_summer_week,
    #     July=hsp_summer_week,
    #     August=hsp_summer_week,
    #     September=hsp_regular_week,
    #     October=hsp_regular_week,
    #     November=hsp_regular_week,
    #     December=hsp_regular_week,
    # )

    # csp_regular_workday = DayComponent(
    #     Name=f"CoolingSetpoint_Regular_Workday{sfx}",
    #     Type="Temperature",
    #     Hour_00=params.CSPRegularWeekdayNight,
    #     Hour_01=params.CSPRegularWeekdayNight,
    #     Hour_02=params.CSPRegularWeekdayNight,
    #     Hour_03=params.CSPRegularWeekdayNight,
    #     Hour_04=params.CSPRegularWeekdayNight,
    #     Hour_05=params.CSPRegularWeekdayNight,
    #     Hour_06=params.CSPRegularWeekdayWorkhours,
    #     Hour_07=params.CSPRegularWeekdayWorkhours,
    #     Hour_08=params.CSPRegularWeekdayWorkhours,
    #     Hour_09=params.CSPRegularWeekdayWorkhours,
    #     Hour_10=params.CSPRegularWeekdayWorkhours,
    #     Hour_11=params.CSPRegularWeekdayWorkhours,
    #     Hour_12=params.CSPRegularWeekdayWorkhours,
    #     Hour_13=params.CSPRegularWeekdayWorkhours,
    #     Hour_14=params.CSPRegularWeekdayWorkhours,
    #     Hour_15=params.CSPRegularWeekdayWorkhours,
    #     Hour_16=params.CSPRegularWeekdayWorkhours,
    #     Hour_17=params.CSPRegularWeekdayWorkhours,
    #     Hour_18=params.CSPRegularWeekdayWorkhours,
    #     Hour_19=params.CSPRegularWeekdayNight,
    #     Hour_20=params.CSPRegularWeekdayNight,
    #     Hour_21=params.CSPRegularWeekdayNight,
    #     Hour_22=params.CSPRegularWeekdayNight,
    #     Hour_23=params.CSPRegularWeekdayNight,
    # )

    # csp_regular_weekend = DayComponent(
    #     Name=f"CoolingSetpoint_Regular_Weekend{sfx}",
    #     Type="Temperature",
    #     Hour_00=params.CSPWeekendNight,
    #     Hour_01=params.CSPWeekendNight,
    #     Hour_02=params.CSPWeekendNight,
    #     Hour_03=params.CSPWeekendNight,
    #     Hour_04=params.CSPWeekendNight,
    #     Hour_05=params.CSPWeekendNight,
    #     Hour_06=params.CSPWeekendWorkhours,
    #     Hour_07=params.CSPWeekendWorkhours,
    #     Hour_08=params.CSPWeekendWorkhours,
    #     Hour_09=params.CSPWeekendWorkhours,
    #     Hour_10=params.CSPWeekendWorkhours,
    #     Hour_11=params.CSPWeekendWorkhours,
    #     Hour_12=params.CSPWeekendWorkhours,
    #     Hour_13=params.CSPWeekendWorkhours,
    #     Hour_14=params.CSPWeekendWorkhours,
    #     Hour_15=params.CSPWeekendWorkhours,
    #     Hour_16=params.CSPWeekendWorkhours,
    #     Hour_17=params.CSPWeekendWorkhours,
    #     Hour_18=params.CSPWeekendWorkhours,
    #     Hour_19=params.CSPWeekendNight,
    #     Hour_20=params.CSPWeekendNight,
    #     Hour_21=params.CSPWeekendNight,
    #     Hour_22=params.CSPWeekendNight,
    #     Hour_23=params.CSPWeekendNight,
    # )

    # csp_summer_workday = DayComponent(
    #     Name=f"CoolingSetpoint_Summer_Workday{sfx}",
    #     Type="Temperature",
    #     Hour_00=params.CSPSummerWeekdayNight,
    #     Hour_01=params.CSPSummerWeekdayNight,
    #     Hour_02=params.CSPSummerWeekdayNight,
    #     Hour_03=params.CSPSummerWeekdayNight,
    #     Hour_04=params.CSPSummerWeekdayNight,
    #     Hour_05=params.CSPSummerWeekdayNight,
    #     Hour_06=params.CSPSummerWeekdayWorkhours,
    #     Hour_07=params.CSPSummerWeekdayWorkhours,
    #     Hour_08=params.CSPSummerWeekdayWorkhours,
    #     Hour_09=params.CSPSummerWeekdayWorkhours,
    #     Hour_10=params.CSPSummerWeekdayWorkhours,
    #     Hour_11=params.CSPSummerWeekdayWorkhours,
    #     Hour_12=params.CSPSummerWeekdayWorkhours,
    #     Hour_13=params.CSPSummerWeekdayWorkhours,
    #     Hour_14=params.CSPSummerWeekdayWorkhours,
    #     Hour_15=params.CSPSummerWeekdayWorkhours,
    #     Hour_16=params.CSPSummerWeekdayWorkhours,
    #     Hour_17=params.CSPSummerWeekdayWorkhours,
    #     Hour_18=params.CSPSummerWeekdayWorkhours,
    #     Hour_19=params.CSPSummerWeekdayNight,
    #     Hour_20=params.CSPSummerWeekdayNight,
    #     Hour_21=params.CSPSummerWeekdayNight,
    #     Hour_22=params.CSPSummerWeekdayNight,
    #     Hour_23=params.CSPSummerWeekdayNight,
    # )

    # csp_regular_week = WeekComponent(
    #     Name=f"CoolingSetpoint_Regular_Week{sfx}",
    #     Monday=csp_regular_workday,
    #     Tuesday=csp_regular_workday,
    #     Wednesday=csp_regular_workday,
    #     Thursday=csp_regular_workday,
    #     Friday=csp_regular_workday,
    #     Saturday=csp_regular_weekend,
    #     Sunday=csp_regular_weekend,
    # )

    # csp_summer_week = WeekComponent(
    #     Name=f"CoolingSetpoint_Summer_Week{sfx}",
    #     Monday=csp_summer_workday,
    #     Tuesday=csp_summer_workday,
    #     Wednesday=csp_summer_workday,
    #     Thursday=csp_summer_workday,
    #     Friday=csp_summer_workday,
    #     Saturday=csp_regular_weekend,
    #     Sunday=csp_regular_weekend,
    # )

    # csp_year = YearComponent(
    #     Name=f"CoolingSetpoint_Schedule{sfx}",
    #     Type="Setpoint",
    #     January=csp_regular_week,
    #     February=csp_regular_week,
    #     March=csp_regular_week,
    #     April=csp_regular_week,
    #     May=csp_regular_week,
    #     June=csp_summer_week,
    #     July=csp_summer_week,
    #     August=csp_summer_week,
    #     September=csp_regular_week,
    #     October=csp_regular_week,
    #     November=csp_regular_week,
    #     December=csp_regular_week,
    # )

    setpoint_parametric = ParametricSetpoints(
        HeatingSetpoint=params.HeatingSetpointBase,
        DeadBand=params.SetpointDeadband,
        HeatingSetback=params.HeatingSetpointSetback,
        CoolingSetback=params.CoolingSetpointSetback,
        NightSetback=params.NightSetback,
        WeekendSetback=params.WeekendSetback,
        SummerSetback=params.SummerSetback,
    )

    hsp_year, csp_year = setpoint_parametric.to_schedules(name_suffix=sfx)

    thermostat = ThermostatComponent(
        Name=f"Thermostat{sfx}",
        IsOn=True,
        HeatingSetpoint=hsp_year.January.Monday.Hour_12,
        CoolingSetpoint=csp_year.January.Monday.Hour_12,
        HeatingSchedule=hsp_year,
        CoolingSchedule=csp_year,
    )

    equipment = EquipmentComponent(
        Name=f"Equipment{sfx}",
        PowerDensity=params.EquipmentPowerDensity,
        Schedule=equipment_schedule,
        IsOn=True,
    )

    lighting = LightingComponent(
        Name=f"Lighting{sfx}",
        PowerDensity=params.LightingPowerDensity,
        Schedule=lighting_schedule,
        IsOn=True,
        DimmingType="Off",
    )

    occupancy = OccupancyComponent(
        Name=f"Occupancy{sfx}",
        PeopleDensity=params.OccupantDensity,
        Schedule=occupancy_schedule,
        IsOn=True,
    )

    water_use = WaterUseComponent(
        Name=f"WaterUse{sfx}",
        FlowRatePerPerson=params.DHWFlowRatePerPerson,
        Schedule=occupancy_schedule,
    )

    space_use = ZoneSpaceUseComponent(
        Name=f"SpaceUse{sfx}",
        Occupancy=occupancy,
        Lighting=lighting,
        Equipment=equipment,
        Thermostat=thermostat,
        WaterUse=water_use,
    )

    heating_system = (
        ThermalSystemComponent(
            Name=f"HeatingSystem{sfx}",
            ConditioningType="Heating",
            Fuel=params.HeatingFuel,
            SystemCOP=params.HeatingSystemCOP,
            DistributionCOP=params.HeatingDistributionCOP,
        )
        if params.IdealLoadsHeatingOn
        else None
    )

    cooling_system = (
        ThermalSystemComponent(
            Name=f"CoolingSystem{sfx}",
            ConditioningType="Cooling",
            Fuel=params.CoolingFuel,
            SystemCOP=params.CoolingSystemCOP,
            DistributionCOP=params.CoolingDistributionCOP,
        )
        if params.IdealLoadsCoolingOn
        else None
    )

    conditioning_system = ConditioningSystemsComponent(
        Name=f"ConditioningSystem{sfx}",
        Heating=heating_system,
        Cooling=cooling_system,
    )

    all_off_day = DayComponent(
        Name=f"AllOffDayComponent{sfx}",
        Type="Fraction",
        Hour_00=0.0,
        Hour_01=0.0,
        Hour_02=0.0,
        Hour_03=0.0,
        Hour_04=0.0,
        Hour_05=0.0,
        Hour_06=0.0,
        Hour_07=0.0,
        Hour_08=0.0,
        Hour_09=0.0,
        Hour_10=0.0,
        Hour_11=0.0,
        Hour_12=0.0,
        Hour_13=0.0,
        Hour_14=0.0,
        Hour_15=0.0,
        Hour_16=0.0,
        Hour_17=0.0,
        Hour_18=0.0,
        Hour_19=0.0,
        Hour_20=0.0,
        Hour_21=0.0,
        Hour_22=0.0,
        Hour_23=0.0,
    )

    all_off_week = WeekComponent(
        Name=f"AllOffWeekComponent{sfx}",
        Monday=all_off_day,
        Tuesday=all_off_day,
        Wednesday=all_off_day,
        Thursday=all_off_day,
        Friday=all_off_day,
        Saturday=all_off_day,
        Sunday=all_off_day,
    )

    all_off_year = YearComponent(
        Name=f"AllOffYearComponent{sfx}",
        Type="Window",
        January=all_off_week,
        February=all_off_week,
        March=all_off_week,
        April=all_off_week,
        May=all_off_week,
        June=all_off_week,
        July=all_off_week,
        August=all_off_week,
        September=all_off_week,
        October=all_off_week,
        November=all_off_week,
        December=all_off_week,
    )

    ventilation_system = VentilationComponent(
        Name=f"VentilationSystem{sfx}",
        FreshAirPerFloorArea=params.VentFlowRatePerArea,
        FreshAirPerPerson=params.VentFlowRatePerPerson,
        Provider=params.VentProvider,
        # TODO: should hrv sensible/latent efficiency be configurable? (e.g. high/medium/low)
        HRV=params.VentHRV,
        Economizer=params.VentEconomizer,
        DCV=params.VentDCV,
        # TODO: this controls natvnent and should
        # be configurable for residential models
        Schedule=all_off_year,
    )

    hvac = ZoneHVACComponent(
        Name=f"HVAC{sfx}",
        ConditioningSystems=conditioning_system,
        Ventilation=ventilation_system,
    )

    dhw = DHWComponent(
        Name=f"DHW{sfx}",
        SystemCOP=params.DHWSystemCOP,
        DistributionCOP=params.DHWDistributionCOP,
        # TODO: should these be configurable?
        WaterTemperatureInlet=10,
        WaterSupplyTemperature=55,
        IsOn=True,
        FuelType=params.DHWFuel,
    )

    operations = ZoneOperationsComponent(
        Name=f"Operations{sfx}",
        SpaceUse=space_use,
        HVAC=hvac,
        DHW=dhw,
    )

    window_assembly = GlazingConstructionSimpleComponent(
        Name=f"WindowAssembly{sfx}",
        UValue=params.WindowUValue,
        SHGF=params.WindowSHGF,
        TVis=params.WindowTVis,
        Type="Single",
    )

    infiltration = InfiltrationComponent(
        Name=f"Infiltration{sfx}",
        IsOn=True,
        CalculationMethod="AirChanges/Hour",
        AirChangesPerHour=params.InfiltrationACH,
        ConstantCoefficient=0.0,
        TemperatureCoefficient=0.0,
        WindVelocityCoefficient=0.0,
        WindVelocitySquaredCoefficient=0.0,
        AFNAirMassFlowCoefficientCrack=0.0,
        FlowPerExteriorSurfaceArea=0.0,
    )

    # TODO: verify interior/exterior
    # TODO: are we okaky with mass assumptions?
    facade = ConstructionAssemblyComponent(
        Name=f"Facade{sfx}",
        Type="Facade",
        Layers=[
            ConstructionLayerComponent(
                ConstructionMaterial=clay_brick,
                Thickness=0.002,
                LayerOrder=0,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=concrete_block_h,
                Thickness=0.15,
                LayerOrder=1,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=fiberglass_batts,
                Thickness=0.05,
                LayerOrder=2,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=gypsum_board,
                Thickness=0.015,
                LayerOrder=3,
            ),
        ],
    )

    facade_r_value_without_fiberglass = facade.r_value - facade.sorted_layers[2].r_value

    facade_r_value_delta = params.FacadeRValue - facade_r_value_without_fiberglass
    required_fiberglass_thickness = fiberglass_batts.Conductivity * facade_r_value_delta

    if required_fiberglass_thickness < 0.003:
        msg = f"Required Facade Fiberglass thickness is less than 3mm because the desired total facade R-value is {params.FacadeRValue} m²K/W but the concrete and gypsum layers already have a total R-value of {facade_r_value_without_fiberglass} m²K/W."
        raise ValueError(msg)

    facade.sorted_layers[2].Thickness = required_fiberglass_thickness

    roof = ConstructionAssemblyComponent(
        Name=f"Roof{sfx}",
        Type="FlatRoof",
        Layers=[
            ConstructionLayerComponent(
                ConstructionMaterial=xps_board,
                Thickness=0.1,
                LayerOrder=0,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=concrete_mc_light,
                Thickness=0.15,
                LayerOrder=1,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=concrete_rc_dense,
                Thickness=0.2,
                LayerOrder=2,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=gypsum_board,
                Thickness=0.02,
                LayerOrder=3,
            ),
        ],
    )

    roof_r_value_without_xps = roof.r_value - roof.sorted_layers[0].r_value
    roof_r_value_delta = params.RoofRValue - roof_r_value_without_xps
    required_xps_thickness = xps_board.Conductivity * roof_r_value_delta
    if required_xps_thickness < 0.003:
        msg = f"Required Roof XPS thickness is less than 3mm because the desired total roof R-value is {params.RoofRValue} m²K/W but the concrete layers already have a total R-value of {roof_r_value_without_xps} m²K/W."
        raise ValueError(msg)

    roof.sorted_layers[0].Thickness = required_xps_thickness

    partition = ConstructionAssemblyComponent(
        Name=f"Partition{sfx}",
        Type="Partition",
        Layers=[
            ConstructionLayerComponent(
                ConstructionMaterial=gypsum_plaster,
                Thickness=0.02,
                LayerOrder=0,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=softwood_general,
                Thickness=0.02,
                LayerOrder=1,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=gypsum_plaster,
                Thickness=0.02,
                LayerOrder=2,
            ),
        ],
    )

    floor_ceiling = ConstructionAssemblyComponent(
        Name=f"FloorCeiling{sfx}",
        Type="FloorCeiling",
        Layers=[
            ConstructionLayerComponent(
                ConstructionMaterial=urethane_carpet,
                Thickness=0.02,
                LayerOrder=0,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=cement_mortar,
                Thickness=0.02,
                LayerOrder=1,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=concrete_rc_dense,
                Thickness=0.15,
                LayerOrder=2,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=gypsum_board,
                Thickness=0.02,
                LayerOrder=3,
            ),
        ],
    )

    ground_slab_assembly = ConstructionAssemblyComponent(
        Name=f"GroundSlabAssembly{sfx}",
        Type="GroundSlab",
        Layers=[
            ConstructionLayerComponent(
                ConstructionMaterial=xps_board,
                Thickness=0.02,
                LayerOrder=0,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=concrete_rc_dense,
                Thickness=0.15,
                LayerOrder=1,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=concrete_mc_light,
                Thickness=0.04,
                LayerOrder=2,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=cement_mortar,
                Thickness=0.03,
                LayerOrder=3,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=ceramic_tile,
                Thickness=0.02,
                LayerOrder=4,
            ),
        ],
    )

    ground_slab_r_value_without_xps = (
        ground_slab_assembly.r_value - ground_slab_assembly.sorted_layers[0].r_value
    )
    ground_slab_r_value_delta = params.SlabRValue - ground_slab_r_value_without_xps
    required_xps_thickness = xps_board.Conductivity * ground_slab_r_value_delta
    if required_xps_thickness < 0.003:
        msg = f"Required Ground Slab XPS thickness is less than 3mm because the desired total slab R-value is {params.SlabRValue} m²K/W but the concrete layers already have a total R-value of {ground_slab_r_value_without_xps} m²K/W."
        raise ValueError(msg)

    ground_slab_assembly.sorted_layers[0].Thickness = required_xps_thickness

    assemblies = EnvelopeAssemblyComponent(
        Name=f"EnvelopeAssemblies{sfx}",
        FacadeAssembly=facade,
        FlatRoofAssembly=roof,
        AtticRoofAssembly=roof,
        PartitionAssembly=partition,
        FloorCeilingAssembly=floor_ceiling,
        AtticFloorAssembly=floor_ceiling,
        BasementCeilingAssembly=floor_ceiling,
        GroundSlabAssembly=ground_slab_assembly,
        GroundWallAssembly=ground_slab_assembly,
        ExternalFloorAssembly=ground_slab_assembly,
    )

    basement_infiltration = infiltration.model_copy(deep=True)
    envelope = ZoneEnvelopeComponent(
        Name=f"Envelope{sfx}",
        AtticInfiltration=infiltration,
        BasementInfiltration=basement_infiltration,
        Window=window_assembly,
        Infiltration=infiltration,
        Assemblies=assemblies,
    )

    zone = ZoneComponent(
        Name=f"Zone{sfx}",
        Operations=operations,
        Envelope=envelope,
    )

    return zone


def _eppy_lights_zone_name(lg: Any) -> str:
    for attr in (
        "Zone_or_ZoneList_Name",
        "Zone_or_ZoneList_or_Space_or_SpaceList_Name",
        "Zone_Name",
    ):
        zn = getattr(lg, attr, None)
        if zn not in (None, ""):
            return str(zn)
    msg = "lights object has no zone reference field"
    raise ValueError(msg)


def _eppy_lights_watts_per_area(lg: Any) -> float:
    v = getattr(lg, "Watts_per_Zone_Floor_Area", None)
    if v not in (None, ""):
        return float(v)
    wpf = getattr(lg, "Watts_per_Floor_Area", None)
    if wpf in (None, ""):
        msg = "lights object has no watts-per-area field"
        raise ValueError(msg)
    return float(wpf)


class FlatModel(ZoneParams):
    """A flattened set of parameters for invoking building energy models more conveniently."""

    # EquipmentSummerWeekdayNight: float = Field(ge=0, le=1)
    # EquipmentSummerWeekdayEarlyMorning: float = Field(ge=0, le=1)
    # EquipmentSummerWeekdayMorning: float = Field(ge=0, le=1)
    # EquipmentSummerWeekdayLunch: float = Field(ge=0, le=1)
    # EquipmentSummerWeekdayAfternoon: float = Field(ge=0, le=1)
    # EquipmentSummerWeekdayEvening: float = Field(ge=0, le=1)

    # EquipmentSummerWeekendNight: float = Field(ge=0, le=1)
    # EquipmentSummerWeekendEarlyMorning: float = Field(ge=0, le=1)
    # EquipmentSummerWeekendMorning: float = Field(ge=0, le=1)
    # EquipmentSummerWeekendLunch: float = Field(ge=0, le=1)
    # EquipmentSummerWeekendAfternoon: float = Field(ge=0, le=1)
    # EquipmentSummerWeekendEvening: float = Field(ge=0, le=1)

    # EquipmentRegularWeekdayNight: float = Field(ge=0, le=1)
    # EquipmentRegularWeekdayEarlyMorning: float = Field(ge=0, le=1)
    # EquipmentRegularWeekdayMorning: float = Field(ge=0, le=1)
    # EquipmentRegularWeekdayLunch: float = Field(ge=0, le=1)
    # EquipmentRegularWeekdayAfternoon: float = Field(ge=0, le=1)
    # EquipmentRegularWeekdayEvening: float = Field(ge=0, le=1)

    # EquipmentRegularWeekendNight: float = Field(ge=0, le=1)
    # EquipmentRegularWeekendEarlyMorning: float = Field(ge=0, le=1)
    # EquipmentRegularWeekendMorning: float = Field(ge=0, le=1)
    # EquipmentRegularWeekendLunch: float = Field(ge=0, le=1)
    # EquipmentRegularWeekendAfternoon: float = Field(ge=0, le=1)
    # EquipmentRegularWeekendEvening: float = Field(ge=0, le=1)

    # LightingSummerWeekdayNight: float = Field(ge=0, le=1)
    # LightingSummerWeekdayEarlyMorning: float = Field(ge=0, le=1)
    # LightingSummerWeekdayMorning: float = Field(ge=0, le=1)
    # LightingSummerWeekdayLunch: float = Field(ge=0, le=1)
    # LightingSummerWeekdayAfternoon: float = Field(ge=0, le=1)
    # LightingSummerWeekdayEvening: float = Field(ge=0, le=1)

    # LightingSummerWeekendNight: float = Field(ge=0, le=1)
    # LightingSummerWeekendEarlyMorning: float = Field(ge=0, le=1)
    # LightingSummerWeekendMorning: float = Field(ge=0, le=1)
    # LightingSummerWeekendLunch: float = Field(ge=0, le=1)
    # LightingSummerWeekendAfternoon: float = Field(ge=0, le=1)
    # LightingSummerWeekendEvening: float = Field(ge=0, le=1)

    # LightingRegularWeekdayNight: float = Field(ge=0, le=1)
    # LightingRegularWeekdayEarlyMorning: float = Field(ge=0, le=1)
    # LightingRegularWeekdayMorning: float = Field(ge=0, le=1)
    # LightingRegularWeekdayLunch: float = Field(ge=0, le=1)
    # LightingRegularWeekdayAfternoon: float = Field(ge=0, le=1)
    # LightingRegularWeekdayEvening: float = Field(ge=0, le=1)

    # LightingRegularWeekendNight: float = Field(ge=0, le=1)
    # LightingRegularWeekendEarlyMorning: float = Field(ge=0, le=1)
    # LightingRegularWeekendMorning: float = Field(ge=0, le=1)
    # LightingRegularWeekendLunch: float = Field(ge=0, le=1)
    # LightingRegularWeekendAfternoon: float = Field(ge=0, le=1)
    # LightingRegularWeekendEvening: float = Field(ge=0, le=1)

    # OccupancySummerWeekdayNight: float = Field(ge=0, le=1)
    # OccupancySummerWeekdayEarlyMorning: float = Field(ge=0, le=1)
    # OccupancySummerWeekdayMorning: float = Field(ge=0, le=1)
    # OccupancySummerWeekdayLunch: float = Field(ge=0, le=1)
    # OccupancySummerWeekdayAfternoon: float = Field(ge=0, le=1)
    # OccupancySummerWeekdayEvening: float = Field(ge=0, le=1)

    # OccupancySummerWeekendNight: float = Field(ge=0, le=1)
    # OccupancySummerWeekendEarlyMorning: float = Field(ge=0, le=1)
    # OccupancySummerWeekendMorning: float = Field(ge=0, le=1)
    # OccupancySummerWeekendLunch: float = Field(ge=0, le=1)
    # OccupancySummerWeekendAfternoon: float = Field(ge=0, le=1)
    # OccupancySummerWeekendEvening: float = Field(ge=0, le=1)

    # OccupancyRegularWeekdayNight: float = Field(ge=0, le=1)
    # OccupancyRegularWeekdayEarlyMorning: float = Field(ge=0, le=1)
    # OccupancyRegularWeekdayMorning: float = Field(ge=0, le=1)
    # OccupancyRegularWeekdayLunch: float = Field(ge=0, le=1)
    # OccupancyRegularWeekdayAfternoon: float = Field(ge=0, le=1)
    # OccupancyRegularWeekdayEvening: float = Field(ge=0, le=1)

    # OccupancyRegularWeekendNight: float = Field(ge=0, le=1)
    # OccupancyRegularWeekendEarlyMorning: float = Field(ge=0, le=1)
    # OccupancyRegularWeekendMorning: float = Field(ge=0, le=1)
    # OccupancyRegularWeekendLunch: float = Field(ge=0, le=1)
    # OccupancyRegularWeekendAfternoon: float = Field(ge=0, le=1)
    # OccupancyRegularWeekendEvening: float = Field(ge=0, le=1)

    EPWURI: WeatherUrl | Path
    zoning: ZoningType = Field(default="core/perim")
    zone_overrides: dict[int, dict[str, dict[str, Any]]] = Field(default_factory=dict)

    def zone_params_defaults(self) -> ZoneParams:
        """Scalars used when building ZoneParams / ZoneComponents."""
        return ZoneParams.model_validate(
            self.model_dump(include=set(ZoneParams.model_fields))
        )

    def zone_assignment_table(self) -> ZoneAssignmentTable:
        """Building defaults plus sparse overrides for per-zone assignment."""
        return ZoneAssignmentTable(
            defaults=self.zone_params_defaults(),
            overrides=self.zone_overrides,
        )

    def to_building(self) -> BuildingFlatModel:
        """Convert to structured building + floor zone assignment model."""
        from epinterface.sbem.building_flat_model import BuildingFlatModel

        return BuildingFlatModel.from_flat_model(self)

    @classmethod
    def from_building(cls, building: BuildingFlatModel) -> FlatModel:
        """Build legacy flat model from building + floor structure."""
        return building.to_flat_model()

    def resolve_params(
        self,
        key: ParsedZoneKey,
        *,
        geometry: ShoeboxGeometry,
        attic_use_fraction: float | None = None,
        attic_conditioned: bool = False,
        basement_use_fraction: float | None = None,
        basement_conditioned: bool = False,
    ) -> ZoneParams:
        """Merge defaults and overrides for one zone key (incl. attic/basement scaling)."""
        return self.zone_assignment_table().resolve(
            key,
            attic_use_fraction=attic_use_fraction,
            attic_conditioned=attic_conditioned,
            basement_use_fraction=basement_use_fraction,
            basement_conditioned=basement_conditioned,
            geometry=geometry,
        )

    def to_zone(self) -> ZoneComponent:
        """Convert the flat model defaults to a single zone component."""
        return zone_params_to_zone_component(self.zone_params_defaults())

    def to_model(self) -> tuple[Model, Callable[[IDF], IDF]]:
        """Returns a tuple of a Model and a post-geometry callback."""
        geometry = ShoeboxGeometry(
            x=0,
            y=0,
            w=self.Width,
            d=self.Depth,
            h=self.F2FHeight,
            num_stories=self.NFloors,
            zoning=self.zoning,
            roof_height=None,
            wwr=self.WWR,
            basement=False,
        )

        def post_geometry_callback(idf: IDF) -> IDF:
            idf.rotate(self.Rotation)
            return idf

        return (
            Model(
                geometry=geometry,
                Zone=None,
                zone_assignments=self.zone_assignment_table(),
                Attic=AtticAssumptions(
                    UseFraction=None,
                    Conditioned=False,
                ),
                Basement=BasementAssumptions(
                    UseFraction=None,
                    Conditioned=False,
                ),
                Weather=self.EPWURI,
            ),
            post_geometry_callback,
        )

    def build_idf(
        self,
        *,
        output_dir: Path | None = None,
        weather_dir: Path | None = None,
    ) -> IDF:
        """Build an IDF without running EnergyPlus."""
        model, cb = self.to_model()
        out = (
            Path(tempfile.mkdtemp(prefix="flat_build_"))
            if output_dir is None
            else Path(output_dir)
        )
        out.mkdir(parents=True, exist_ok=True)
        cfg = (
            SimulationPathConfig(output_dir=out, weather_dir=weather_dir)
            if weather_dir is not None
            else SimulationPathConfig(output_dir=out)
        )
        return model.build(cfg, post_geometry_callback=cb)

    def zone_assignment_summary(self, idf: IDF | None = None) -> pd.DataFrame:
        """Resolved zone params plus optional cross-check against built IDF."""
        model, _ = self.to_model()
        geom = model.geometry
        tbl = self.zone_assignment_table()
        idf_built = idf or self.build_idf()
        lights_by_zone: dict[str, float] = {}
        for lg in idf_built.idfobjects["LIGHTS"]:
            zn = _eppy_lights_zone_name(lg)
            lights_by_zone[zn] = _eppy_lights_watts_per_area(lg)

        facade_by_zone: dict[str, str] = {}
        for srf in idf_built.idfobjects["BUILDINGSURFACE:DETAILED"]:
            if (
                str(srf.Surface_Type).lower() == "wall"
                and str(srf.Outside_Boundary_Condition).lower() == "outdoors"
            ):
                zn = str(srf.Zone_Name)
                facade_by_zone.setdefault(zn, str(srf.Construction_Name))

        rows = []
        for z in idf_built.idfobjects["ZONE"]:
            zn = z.Name
            key = parse_zone_key(zn, geom)
            params = tbl.resolve(
                key,
                attic_use_fraction=model.Attic.UseFraction,
                attic_conditioned=model.Attic.Conditioned,
                basement_use_fraction=model.Basement.UseFraction,
                basement_conditioned=model.Basement.Conditioned,
                geometry=geom,
            )
            rows.append({
                "ep_zone_name": zn,
                "storey_index": key.storey_index,
                "role": key.role.value,
                "category": key.category,
                "LightingPowerDensity": params.LightingPowerDensity,
                "EquipmentPowerDensity": params.EquipmentPowerDensity,
                "FacadeRValue": params.FacadeRValue,
                "idf_lighting_w_per_m2": lights_by_zone.get(zn),
                "idf_facade_construction": facade_by_zone.get(zn),
            })
        return pd.DataFrame(rows)

    def zone_simulation_summary(self, results: ModelRunResults) -> pd.DataFrame:
        """Assignment summary joined with per-zone simulated energy from a model run."""
        from epinterface.analysis.zone_energy import (
            merge_assignment_and_energy,
            zone_energy_summary,
        )

        assign = self.zone_assignment_summary(idf=results.idf)
        energy = zone_energy_summary(results.sql, results.idf)
        return merge_assignment_and_energy(assign, energy)

    @classmethod
    def example_with_zone_overrides(cls) -> FlatModel:
        """Two-storey core/perim shoebox with contrasting zone overrides."""
        from epinterface.sbem.building_flat_model import BuildingFlatModel

        return BuildingFlatModel.example_with_zone_overrides().to_flat_model()

    def simulate(
        self,
        overheating_config: OverheatingAnalysisConfig | None = None,
        eplus_parent_dir: Path | None = None,
    ):
        """Simulate the model and return the IDF, result, and error."""
        model, cb = self.to_model()

        r = model.run(
            post_geometry_callback=cb,
            eplus_parent_dir=eplus_parent_dir,
            overheating_config=overheating_config,
        )

        return r


if __name__ == "__main__":
    run_flat = Path("run_flat")
    run_flat.mkdir(exist_ok=True)
    fm = FlatModel.example_with_zone_overrides()
    print("running energyplus simulation (uses bundled weather zip)...")
    run_results = fm.simulate(eplus_parent_dir=run_flat)
    merged = fm.zone_simulation_summary(run_results)
    cols = [
        "storey_index",
        "role",
        "LightingPowerDensity",
        "sim_lighting_kwh_per_m2",
        "sim_total_kwh_per_m2",
    ]
    print(
        merged[cols]
        .drop_duplicates()
        .sort_values(["storey_index", "role"])
        .to_string(index=False)
    )
    try:
        from epinterface.analysis.zone_assignment_viz import plot_assignment_and_energy

        _assign_fig, energy_fig, _merged = plot_assignment_and_energy(
            fm.zone_assignment_summary(idf=run_results.idf),
            results=run_results,
        )
        out_png = run_flat / "zone_assignment_energy.png"
        cast(Any, energy_fig).savefig(out_png, bbox_inches="tight")
        print(f"wrote {out_png}")
    except ImportError as err:
        print("matplotlib not installed (uv sync --group dev):", err)
