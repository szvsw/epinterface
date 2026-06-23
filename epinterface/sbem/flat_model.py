"""Flat model used for calibration."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from archetypal import IDF
from pydantic import BaseModel, Field

from epinterface.analysis.overheating import OverheatingAnalysisConfig
from epinterface.geometry import ShoeboxGeometry, ZoningType
from epinterface.sbem.builder import AtticAssumptions, BasementAssumptions, Model
from epinterface.sbem.common import NamedObject
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
    DCVMethod,
    DHWComponent,
    DHWFuelType,
    EconomizerMethod,
    FuelType,
    HRVMethod,
    ThermalSystemComponent,
    VentilationComponent,
    VentilationProvider,
    ZoneHVACComponent,
)
from epinterface.sbem.components.zones import ZoneComponent
from epinterface.sbem.zone_assignment import ZoneTemplate
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


class ParametricSetpoints(BaseModel):
    """A model for a setpoint schedule that is parameterized by the base, and the setbacks."""

    HeatingSetpoint: float = Field(ge=0, le=22)
    DeadBand: float = Field(ge=0, le=10)
    HeatingSetback: float = Field(ge=0, le=10)
    CoolingSetback: float = Field(ge=0, le=10)
    NightSetback: float = Field(ge=0, le=1)
    WeekendSetback: float = Field(ge=0, le=1)
    SummerSetback: float = Field(ge=0, le=1)

    def to_schedules(self):
        """Convert the setpoint parameters to a set of schedules."""
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
            Name="HSP_Standard_Day",
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
            Name="HSP_Weekend_Day",
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
            Name="HSP_Summer_Day",
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
            Name="HSP_Summer_Weekend_Day",
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
            Name="CSP_Standard_Day",
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
            Name="CSP_Weekend_Day",
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
            Name="CSP_Summer_Day",
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
            Name="CSP_Summer_Weekend_Day",
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
            Name="HSP_Standard_Week",
            Monday=hsp_standard_day,
            Tuesday=hsp_standard_day,
            Wednesday=hsp_standard_day,
            Thursday=hsp_standard_day,
            Friday=hsp_standard_day,
            Saturday=hsp_weekend_day,
            Sunday=hsp_weekend_day,
        )

        csp_standard_week = WeekComponent(
            Name="CSP_Standard_Week",
            Monday=csp_standard_day,
            Tuesday=csp_standard_day,
            Wednesday=csp_standard_day,
            Thursday=csp_standard_day,
            Friday=csp_standard_day,
            Saturday=csp_weekend_day,
            Sunday=csp_weekend_day,
        )

        hsp_summer_week = WeekComponent(
            Name="HSP_Summer_Week",
            Monday=hsp_summer_day,
            Tuesday=hsp_summer_day,
            Wednesday=hsp_summer_day,
            Thursday=hsp_summer_day,
            Friday=hsp_summer_day,
            Saturday=hsp_summer_weekend_day,
            Sunday=hsp_summer_weekend_day,
        )

        csp_summer_week = WeekComponent(
            Name="CSP_Summer_Week",
            Monday=csp_summer_day,
            Tuesday=csp_summer_day,
            Wednesday=csp_summer_day,
            Thursday=csp_summer_day,
            Friday=csp_summer_day,
            Saturday=csp_summer_weekend_day,
            Sunday=csp_summer_weekend_day,
        )

        hsp_year = YearComponent(
            Name="HSP_Year",
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
            Name="CSP_Year",
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


class FlatModel(BaseModel):
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

    EquipmentBase: float = Field(ge=0, le=1)
    EquipmentAMInterp: float = Field(ge=0, le=1)
    EquipmentLunchInterp: float = Field(ge=0, le=1)
    EquipmentPMInterp: float = Field(ge=0, le=1)
    EquipmentWeekendPeakInterp: float = Field(ge=0, le=1)
    EquipmentSummerPeakInterp: float = Field(ge=0, le=1)

    LightingBase: float = Field(ge=0, le=1)
    LightingAMInterp: float = Field(ge=0, le=1)
    LightingLunchInterp: float = Field(ge=0, le=1)
    LightingPMInterp: float = Field(ge=0, le=1)
    LightingWeekendPeakInterp: float = Field(ge=0, le=1)
    LightingSummerPeakInterp: float = Field(ge=0, le=1)

    OccupancyBase: float = Field(ge=0, le=1)
    OccupancyAMInterp: float = Field(ge=0, le=1)
    OccupancyLunchInterp: float = Field(ge=0, le=1)
    OccupancyPMInterp: float = Field(ge=0, le=1)
    OccupancyWeekendPeakInterp: float = Field(ge=0, le=1)
    OccupancySummerPeakInterp: float = Field(ge=0, le=1)

    # HSPRegularWeekdayWorkhours: float = Field(ge=0, le=23)
    # HSPRegularWeekdayNight: float = Field(ge=0, le=23)
    # HSPSummerWeekdayWorkhours: float = Field(ge=0, le=23)
    # HSPSummerWeekdayNight: float = Field(ge=0, le=23)
    # HSPWeekendWorkhours: float = Field(ge=0, le=23)
    # HSPWeekendNight: float = Field(ge=0, le=23)

    # CSPRegularWeekdayWorkhours: float = Field(ge=20, le=30)
    # CSPRegularWeekdayNight: float = Field(ge=20, le=30)
    # CSPSummerWeekdayWorkhours: float = Field(ge=20, le=30)
    # CSPSummerWeekdayNight: float = Field(ge=20, le=30)
    # CSPWeekendWorkhours: float = Field(ge=20, le=30)
    # CSPWeekendNight: float = Field(ge=20, le=30)

    HeatingSetpointBase: float = Field(ge=0, le=23)
    SetpointDeadband: float = Field(ge=0, le=10)
    HeatingSetpointSetback: float = Field(ge=0, le=10)
    CoolingSetpointSetback: float = Field(ge=0, le=10)
    NightSetback: float = Field(ge=0, le=1)
    WeekendSetback: float = Field(ge=0, le=1)
    SummerSetback: float = Field(ge=0, le=1)

    HeatingFuel: FuelType
    CoolingFuel: FuelType
    HeatingSystemCOP: float
    CoolingSystemCOP: float
    HeatingDistributionCOP: float
    CoolingDistributionCOP: float

    EquipmentPowerDensity: float = Field(ge=0, le=200)
    LightingPowerDensity: float = Field(ge=0, le=100)
    OccupantDensity: float = Field(ge=0, le=50)

    VentFlowRatePerPerson: float
    VentFlowRatePerArea: float
    VentProvider: VentilationProvider
    VentHRV: HRVMethod
    VentEconomizer: EconomizerMethod
    VentDCV: DCVMethod

    DHWFlowRatePerPerson: float
    DHWFuel: DHWFuelType
    DHWSystemCOP: float
    DHWDistributionCOP: float

    InfiltrationACH: float

    WindowUValue: float
    WindowSHGF: float
    WindowTVis: float

    FacadeRValue: float
    RoofRValue: float
    SlabRValue: float

    WWR: float
    F2FHeight: float
    NFloors: int
    Width: float
    Depth: float
    Rotation: float

    EPWURI: WeatherUrl | Path
    zoning: ZoningType = "core/perim"

    def zone_template(self) -> ZoneTemplate:
        """Return the shell-free zone template fields from this flat model.

        ``FlatModel`` carries shell-only fields (geometry, weather, zoning) that
        are not part of ``ZoneTemplate``. ``ZoneTemplate`` forbids extras, so we
        must project onto its fields explicitly rather than dumping everything.
        """
        return ZoneTemplate.model_validate(
            self.model_dump(include=set(ZoneTemplate.model_fields))
        )

    def to_zone(self) -> ZoneComponent:
        """Convert the flat model to a full zone."""
        return zone_template_to_zone_component(self.zone_template())

    def to_model(self) -> tuple[Model, Callable[[IDF], IDF]]:
        """Returns a tuple of a Model and a post-geometry callback."""
        zone = self.to_zone()
        # TODO: add in a shading mask
        geometry = ShoeboxGeometry(
            x=0,
            y=0,
            w=self.Width,
            d=self.Depth,
            h=self.F2FHeight,
            num_stories=self.NFloors,
            # TODO: should core/perim be dependent on width, depth > 9m?
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
                Zone=zone,
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

    def to_building_model(self):
        """Convert a uniform legacy flat model to the floor-aware building model."""
        from epinterface.sbem.building_flat_model import BuildingFlatModel

        return BuildingFlatModel.from_uniform_flat_model(self, zoning=self.zoning)


def _suffix_named_objects(value: Any, suffix: str, seen: set[int]) -> None:
    """Suffix component object names recursively, skipping shared material definitions."""
    obj_id = id(value)
    if obj_id in seen:
        return
    seen.add(obj_id)

    if isinstance(value, ConstructionMaterialComponent):
        return

    if isinstance(value, NamedObject):
        value.Name = f"{value.Name}_{suffix}"

    if isinstance(value, BaseModel):
        for child in value.__dict__.values():
            _suffix_named_objects(child, suffix, seen)
    elif isinstance(value, dict):
        for child in value.values():
            _suffix_named_objects(child, suffix, seen)
    elif isinstance(value, list | tuple | set):
        for child in value:
            _suffix_named_objects(child, suffix, seen)


def zone_template_to_zone_component(
    params: ZoneTemplate,
    *,
    id_tag: str = "",
) -> ZoneComponent:
    """Convert a resolved zone template into a uniquely named ZoneComponent."""
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

    equipment_schedule = equipment_paramteric.to_schedule(
        name="Equipment", category="Equipment"
    )
    lighting_schedule = lighting_paramteric.to_schedule(
        name="Lighting", category="Lighting"
    )
    occupancy_schedule = occupancy_paramteric.to_schedule(
        name="Occupancy", category="Occupancy"
    )

    setpoint_parametric = ParametricSetpoints(
        HeatingSetpoint=params.HeatingSetpointBase,
        DeadBand=params.SetpointDeadband,
        HeatingSetback=params.HeatingSetpointSetback,
        CoolingSetback=params.CoolingSetpointSetback,
        NightSetback=params.NightSetback,
        WeekendSetback=params.WeekendSetback,
        SummerSetback=params.SummerSetback,
    )

    hsp_year, csp_year = setpoint_parametric.to_schedules()

    thermostat = ThermostatComponent(
        Name="Thermostat",
        IsOn=True,
        HeatingSetpoint=hsp_year.January.Monday.Hour_12,
        CoolingSetpoint=csp_year.January.Monday.Hour_12,
        HeatingSchedule=hsp_year,
        CoolingSchedule=csp_year,
    )

    equipment = EquipmentComponent(
        Name="Equipment",
        PowerDensity=params.EquipmentPowerDensity,
        Schedule=equipment_schedule,
        IsOn=True,
    )

    lighting = LightingComponent(
        Name="Lighting",
        PowerDensity=params.LightingPowerDensity,
        Schedule=lighting_schedule,
        IsOn=True,
        DimmingType="Off",
    )

    occupancy = OccupancyComponent(
        Name="Occupancy",
        PeopleDensity=params.OccupantDensity,
        Schedule=occupancy_schedule,
        IsOn=True,
    )

    water_use = WaterUseComponent(
        Name="WaterUse",
        FlowRatePerPerson=params.DHWFlowRatePerPerson,
        Schedule=occupancy_schedule,
    )

    space_use = ZoneSpaceUseComponent(
        Name="SpaceUse",
        Occupancy=occupancy,
        Lighting=lighting,
        Equipment=equipment,
        Thermostat=thermostat,
        WaterUse=water_use,
    )

    heating_system = ThermalSystemComponent(
        Name="HeatingSystem",
        ConditioningType="Heating",
        Fuel=params.HeatingFuel,
        SystemCOP=params.HeatingSystemCOP,
        DistributionCOP=params.HeatingDistributionCOP,
    )

    cooling_system = ThermalSystemComponent(
        Name="CoolingSystem",
        ConditioningType="Cooling",
        Fuel=params.CoolingFuel,
        SystemCOP=params.CoolingSystemCOP,
        DistributionCOP=params.CoolingDistributionCOP,
    )

    conditioning_system = ConditioningSystemsComponent(
        Name="ConditioningSystem",
        Heating=heating_system,
        Cooling=cooling_system,
    )

    all_off_day = DayComponent(
        Name="AllOffDayComponent",
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
        Name="AllOffWeekComponent",
        Monday=all_off_day,
        Tuesday=all_off_day,
        Wednesday=all_off_day,
        Thursday=all_off_day,
        Friday=all_off_day,
        Saturday=all_off_day,
        Sunday=all_off_day,
    )

    all_off_year = YearComponent(
        Name="AllOffYearComponent",
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
        Name="VentilationSystem",
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
        Name="HVAC",
        ConditioningSystems=conditioning_system,
        Ventilation=ventilation_system,
    )

    dhw = DHWComponent(
        Name="DHW",
        SystemCOP=params.DHWSystemCOP,
        DistributionCOP=params.DHWDistributionCOP,
        # TODO: should these be configurable?
        WaterTemperatureInlet=10,
        WaterSupplyTemperature=55,
        IsOn=True,
        FuelType=params.DHWFuel,
    )

    operations = ZoneOperationsComponent(
        Name="Operations",
        SpaceUse=space_use,
        HVAC=hvac,
        DHW=dhw,
    )

    window_assembly = GlazingConstructionSimpleComponent(
        Name="WindowAssembly",
        UValue=params.WindowUValue,
        SHGF=params.WindowSHGF,
        TVis=params.WindowTVis,
        Type="Single",
    )

    infiltration = InfiltrationComponent(
        Name="Infiltration",
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
        Name="Facade",
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
        Name="Roof",
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
        Name="Partition",
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
        Name="FloorCeiling",
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
        Name="GroundSlabAssembly",
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
        Name="EnvelopeAssemblies",
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
        Name="Envelope",
        AtticInfiltration=infiltration,
        BasementInfiltration=basement_infiltration,
        Window=window_assembly,
        Infiltration=infiltration,
        Assemblies=assemblies,
    )

    zone = ZoneComponent(
        Name="Zone",
        Operations=operations,
        Envelope=envelope,
    )
    if not params.IdealLoadsHeatingOn:
        zone.Operations.HVAC.ConditioningSystems.Heating = None
    if not params.IdealLoadsCoolingOn:
        zone.Operations.HVAC.ConditioningSystems.Cooling = None
    if id_tag:
        _suffix_named_objects(zone, id_tag, set())
    return zone


if __name__ == "__main__":
    flat_model = FlatModel(
        F2FHeight=3.25,
        Width=40,
        Depth=40,
        Rotation=45,
        WWR=0.3,
        NFloors=2,
        FacadeRValue=3.0,
        RoofRValue=3.0,
        SlabRValue=3.0,
        WindowUValue=3.0,
        WindowSHGF=0.7,
        WindowTVis=0.5,
        InfiltrationACH=0.5,
        VentFlowRatePerArea=0.001,
        VentFlowRatePerPerson=0.0085,
        VentProvider="Mechanical",
        VentHRV="NoHRV",
        VentEconomizer="NoEconomizer",
        VentDCV="NoDCV",
        DHWFlowRatePerPerson=0.010,
        DHWFuel="Electricity",
        DHWSystemCOP=1.0,
        DHWDistributionCOP=1.0,
        EquipmentPowerDensity=25,
        LightingPowerDensity=10,
        OccupantDensity=0.01,
        EquipmentBase=0.4,
        EquipmentAMInterp=0.5,
        EquipmentLunchInterp=0.8,
        EquipmentPMInterp=0.5,
        EquipmentWeekendPeakInterp=0.25,
        EquipmentSummerPeakInterp=0.5,
        LightingBase=0.3,
        LightingAMInterp=0.75,
        LightingLunchInterp=0.75,
        LightingPMInterp=0.9,
        LightingWeekendPeakInterp=0.75,
        LightingSummerPeakInterp=0.9,
        OccupancyBase=0.05,
        OccupancyAMInterp=0.25,
        OccupancyLunchInterp=0.9,
        OccupancyPMInterp=0.5,
        OccupancyWeekendPeakInterp=0.15,
        OccupancySummerPeakInterp=0.85,
        # HSPRegularWeekdayWorkhours=21,
        # HSPRegularWeekdayNight=21,
        # HSPSummerWeekdayWorkhours=21,
        # HSPSummerWeekdayNight=21,
        # HSPWeekendWorkhours=21,
        # HSPWeekendNight=21,
        # CSPRegularWeekdayWorkhours=23,
        # CSPRegularWeekdayNight=23,
        # CSPSummerWeekdayWorkhours=23,
        # CSPSummerWeekdayNight=23,
        # CSPWeekendWorkhours=23,
        # CSPWeekendNight=23,
        HeatingSetpointBase=21,
        SetpointDeadband=2,
        HeatingSetpointSetback=2,
        CoolingSetpointSetback=2,
        NightSetback=0.5,
        WeekendSetback=0.5,
        SummerSetback=0.5,
        HeatingFuel="Electricity",
        CoolingFuel="Electricity",
        HeatingSystemCOP=1.0,
        CoolingSystemCOP=1.0,
        HeatingDistributionCOP=1.0,
        CoolingDistributionCOP=1.0,
        EPWURI=WeatherUrl(  # pyright: ignore [reportCallIssue]
            "https://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/USA_United_States_of_America/MA_Massachusetts/USA_MA_Bedford-Hanscom.Field.AP.744900_TMYx.2009-2023.zip"
        ),
    )

    r = flat_model.simulate()

    print(r.energy_and_peak.groupby(level=["Measurement", "Aggregation"]).sum())
