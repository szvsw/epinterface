"""Flat model used for calibration."""

from collections.abc import Callable
from pathlib import Path
from typing import Literal

from archetypal import IDF
from pydantic import BaseModel, Field

from epinterface.analysis.overheating import OverheatingAnalysisConfig
from epinterface.geometry import ShoeboxGeometry
from epinterface.sbem.builder import AtticAssumptions, BasementAssumptions, Model
from epinterface.sbem.components.envelope import (
    EnvelopeAssemblyComponent,
    GlazingConstructionSimpleComponent,
    InfiltrationComponent,
    ZoneEnvelopeComponent,
)
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
from epinterface.sbem.flat_constructions.assemblies import (
    build_floor_ceiling_assembly,
    build_partition_assembly,
)
from epinterface.sbem.flat_constructions.base import (
    CavityInsulationMaterialName,
    ContinuousInsulationMaterialName,
)
from epinterface.sbem.flat_constructions.roofs import build_roof_assembly
from epinterface.sbem.flat_constructions.slabs import (
    GroundSlabInteriorFinishName,
    GroundSlabSystemName,
    GroundSlabSystems,
)
from epinterface.sbem.flat_constructions.walls import (
    WallExteriorFinishName,
    WallFramingSystemName,
    WallFramingSystems,
    WallInteriorFinishName,
)
from epinterface.weather import WeatherUrl


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


ZoningMode = Literal["core/perim", "by_storey", "by_building", "auto"]


class FlatModel(BaseModel):
    """A flattened set of parameters for invoking building energy models more conveniently."""

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
    BasementInfiltrationACH: float

    WindowUValue: float
    WindowSHGF: float
    WindowTVis: float

    FacadeFramingSystem: WallFramingSystemName = "2x4 16OCC Woodframe"
    FacadeCavityInsulationRValue: float = Field(default=0, ge=0)
    FacadeExteriorInsulationRValue: float = Field(default=0, ge=0)
    FacadeInteriorInsulationRValue: float = Field(default=0, ge=0)
    FacadeExteriorInsulationMaterial: ContinuousInsulationMaterialName = "XPSBoard"
    FacadeInteriorInsulationMaterial: ContinuousInsulationMaterialName = "XPSBoard"
    FacadeCavityInsulationMaterial: CavityInsulationMaterialName = "FiberglassBatt"
    FacadeInteriorFinish: WallInteriorFinishName = "drywall"
    FacadeExteriorFinish: WallExteriorFinishName = "wood_siding"

    SubterraneanWallFramingSystem: WallFramingSystemName = "2x4 16OCC Woodframe"
    SubterraneanCavityInsulationRValue: float = Field(default=0, ge=0)
    SubterraneanExteriorInsulationRValue: float = Field(default=0, ge=0)
    SubterraneanInteriorInsulationRValue: float = Field(default=0, ge=0)
    SubterraneanExteriorInsulationMaterial: ContinuousInsulationMaterialName = (
        "XPSBoard"
    )
    SubterraneanInteriorInsulationMaterial: ContinuousInsulationMaterialName = (
        "XPSBoard"
    )
    SubterraneanCavityInsulationMaterial: CavityInsulationMaterialName = (
        "FiberglassBatt"
    )
    SubterraneanInteriorFinish: WallInteriorFinishName = "drywall"
    SubterraneanExteriorFinish: WallExteriorFinishName = "wood_siding"

    # RoofStructuralSystem: RoofStructuralSystemType = "poured_concrete"
    # RoofCavityInsulationRValue: float = Field(default=0, ge=0)
    # RoofExteriorInsulationRValue: float = Field(default=2.5, ge=0)
    # RoofInteriorInsulationRValue: float = Field(default=0, ge=0)
    # RoofExteriorInsulationMaterial: ContinuousInsulationMaterial = "polyiso"
    # RoofInteriorInsulationMaterial: ContinuousInsulationMaterial = "polyiso"
    # RoofCavityInsulationMaterial: CavityInsulationMaterial = "fiberglass"
    # RoofExteriorCavityType: ExteriorCavityType = "none"
    # RoofInteriorFinish: RoofInteriorFinishType = "gypsum_board"
    # RoofExteriorFinish: RoofExteriorFinishType = "epdm_membrane"
    RoofRValue: float = Field(default=3.0, ge=0)

    GroundSlabSystem: GroundSlabSystemName = "BasicConcrete"
    GroundSlabInsulationRValue: float = Field(default=1.5, ge=0)
    GroundSlabInsulationMaterial: ContinuousInsulationMaterialName = "XPSBoard"
    GroundSlabInteriorFinish: GroundSlabInteriorFinishName = "wood_floor"
    GroundSlabStructuralThickness: float = Field(
        default=0.15,
        gt=0,
        le=0.5,
        description="The thickness of the structural material in the ground slab.",
    )

    WWR: float
    F2FHeight: float
    NFloors: int
    Width: float
    Depth: float
    Rotation: float
    ZoningMode: ZoningMode

    EPWURI: WeatherUrl | Path

    def to_zone(self) -> ZoneComponent:
        """Convert the flat model to a full zone."""
        equipment_paramteric = ParametericYear(
            Base=self.EquipmentBase,
            AMInterp=self.EquipmentAMInterp,
            LunchInterp=self.EquipmentLunchInterp,
            PMInterp=self.EquipmentPMInterp,
            WeekendPeakInterp=self.EquipmentWeekendPeakInterp,
            SummerPeakInterp=self.EquipmentSummerPeakInterp,
        )

        lighting_paramteric = ParametericYear(
            Base=self.LightingBase,
            AMInterp=self.LightingAMInterp,
            LunchInterp=self.LightingLunchInterp,
            PMInterp=self.LightingPMInterp,
            WeekendPeakInterp=self.LightingWeekendPeakInterp,
            SummerPeakInterp=self.LightingSummerPeakInterp,
        )

        occupancy_paramteric = ParametericYear(
            Base=self.OccupancyBase,
            AMInterp=self.OccupancyAMInterp,
            LunchInterp=self.OccupancyLunchInterp,
            PMInterp=self.OccupancyPMInterp,
            WeekendPeakInterp=self.OccupancyWeekendPeakInterp,
            SummerPeakInterp=self.OccupancySummerPeakInterp,
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
            HeatingSetpoint=self.HeatingSetpointBase,
            DeadBand=self.SetpointDeadband,
            HeatingSetback=self.HeatingSetpointSetback,
            CoolingSetback=self.CoolingSetpointSetback,
            NightSetback=self.NightSetback,
            WeekendSetback=self.WeekendSetback,
            SummerSetback=self.SummerSetback,
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

        by_building_scaling_factor = (
            1.0 if self.ZoningMode != "by_building" else self.NFloors
        )
        equipment = EquipmentComponent(
            Name="Equipment",
            PowerDensity=self.EquipmentPowerDensity * by_building_scaling_factor,
            Schedule=equipment_schedule,
            IsOn=True,
        )

        lighting = LightingComponent(
            Name="Lighting",
            PowerDensity=self.LightingPowerDensity * by_building_scaling_factor,
            Schedule=lighting_schedule,
            IsOn=True,
            DimmingType="Off",
        )

        occupancy = OccupancyComponent(
            Name="Occupancy",
            PeopleDensity=self.OccupantDensity * by_building_scaling_factor,
            Schedule=occupancy_schedule,
            IsOn=True,
        )

        water_use = WaterUseComponent(
            Name="WaterUse",
            FlowRatePerPerson=self.DHWFlowRatePerPerson,
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
            Fuel=self.HeatingFuel,
            SystemCOP=self.HeatingSystemCOP,
            DistributionCOP=self.HeatingDistributionCOP,
        )

        cooling_system = ThermalSystemComponent(
            Name="CoolingSystem",
            ConditioningType="Cooling",
            Fuel=self.CoolingFuel,
            SystemCOP=self.CoolingSystemCOP,
            DistributionCOP=self.CoolingDistributionCOP,
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
            FreshAirPerFloorArea=self.VentFlowRatePerArea * by_building_scaling_factor,
            FreshAirPerPerson=self.VentFlowRatePerPerson,
            Provider=self.VentProvider,
            # TODO: should hrv sensible/latent efficiency be configurable? (e.g. high/medium/low)
            HRV=self.VentHRV,
            Economizer=self.VentEconomizer,
            DCV=self.VentDCV,
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
            SystemCOP=self.DHWSystemCOP,
            DistributionCOP=self.DHWDistributionCOP,
            # TODO: should these be configurable?
            WaterTemperatureInlet=10,
            WaterSupplyTemperature=55,
            IsOn=True,
            FuelType=self.DHWFuel,
        )

        operations = ZoneOperationsComponent(
            Name="Operations",
            SpaceUse=space_use,
            HVAC=hvac,
            DHW=dhw,
        )

        window_assembly = GlazingConstructionSimpleComponent(
            Name="WindowAssembly",
            UValue=self.WindowUValue,
            SHGF=self.WindowSHGF,
            TVis=self.WindowTVis,
            Type="Single",
        )

        infiltration = InfiltrationComponent(
            Name="Infiltration",
            IsOn=True,
            CalculationMethod="AirChanges/Hour",
            AirChangesPerHour=self.InfiltrationACH,
            ConstantCoefficient=0.0,
            TemperatureCoefficient=0.0,
            WindVelocityCoefficient=0.0,
            WindVelocitySquaredCoefficient=0.0,
            AFNAirMassFlowCoefficientCrack=0.0,
            FlowPerExteriorSurfaceArea=0.0,
        )
        basement_infiltration = InfiltrationComponent(
            Name="BasementInfiltration",
            IsOn=True,
            CalculationMethod="AirChanges/Hour",
            AirChangesPerHour=self.BasementInfiltrationACH,
            ConstantCoefficient=0.0,
            TemperatureCoefficient=0.0,
            WindVelocityCoefficient=0.0,
            WindVelocitySquaredCoefficient=0.0,
            AFNAirMassFlowCoefficientCrack=0.0,
            FlowPerExteriorSurfaceArea=0.0,
        )

        facade = WallFramingSystems[self.FacadeFramingSystem].to_construction_assembly(
            cav_insul_rval=self.FacadeCavityInsulationRValue,
            ext_insul_rval=self.FacadeExteriorInsulationRValue,
            int_insul_rval=self.FacadeInteriorInsulationRValue,
            ext_insul_name=self.FacadeExteriorInsulationMaterial,
            int_insul_name=self.FacadeInteriorInsulationMaterial,
            cav_insul_name=self.FacadeCavityInsulationMaterial,
            ext_finish=self.FacadeExteriorFinish,
            int_finish=self.FacadeInteriorFinish,
        )
        ground_wall = WallFramingSystems[
            self.SubterraneanWallFramingSystem
        ].to_construction_assembly(
            cav_insul_rval=self.SubterraneanCavityInsulationRValue,
            ext_insul_rval=self.SubterraneanExteriorInsulationRValue,
            int_insul_rval=self.SubterraneanInteriorInsulationRValue,
            ext_insul_name=self.SubterraneanExteriorInsulationMaterial,
            int_insul_name=self.SubterraneanInteriorInsulationMaterial,
            cav_insul_name=self.SubterraneanCavityInsulationMaterial,
            ext_finish=self.SubterraneanExteriorFinish,
            int_finish=self.SubterraneanInteriorFinish,
        )
        ground_slab = GroundSlabSystems[self.GroundSlabSystem].to_construction_assembly(
            insul_name=self.GroundSlabInsulationMaterial,
            insul_rval=self.GroundSlabInsulationRValue,
            structural_thickness=self.GroundSlabStructuralThickness,
            interior_finish=self.GroundSlabInteriorFinish,
        )

        roof = build_roof_assembly(r_value=self.RoofRValue)

        partition = build_partition_assembly()

        floor_ceiling = build_floor_ceiling_assembly()

        assemblies = EnvelopeAssemblyComponent(
            Name="EnvelopeAssemblies",
            GroundWallAssembly=ground_wall,
            FacadeAssembly=facade,
            GroundSlabAssembly=ground_slab,
            # TODO: Basement ceiling assembly should be configurable; see mabi retrofits
            BasementCeilingAssembly=floor_ceiling,
            # TODO: attic roof assembly should be configurable; see mabi retrofits
            FlatRoofAssembly=roof,
            AtticRoofAssembly=roof,
            AtticFloorAssembly=floor_ceiling,
            # Unused, no overhangs
            ExternalFloorAssembly=ground_slab,
            # Constant
            PartitionAssembly=partition,
            # Constant
            FloorCeilingAssembly=floor_ceiling,
        )

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

        return zone

    def to_model(self) -> tuple[Model, Callable[[IDF], IDF]]:
        """Returns a tuple of a Model and a post-geometry callback."""
        # TODO: add in a shading mask
        zone = self.to_zone()
        perim_depth = 3
        effective_zoning_mode = (
            self.ZoningMode if self.ZoningMode != "by_building" else "by_storey"
        )
        if effective_zoning_mode == "auto":
            if (self.Width > (2 * perim_depth + 3)) and (
                self.Depth > (2 * perim_depth + 3)
            ):
                # Both the core and perim are large enough to support core/perim zoning
                effective_zoning_mode = "core/perim"
            else:
                effective_zoning_mode = "by_storey"
        effective_f2f_height = (
            self.F2FHeight
            if effective_zoning_mode != "by_building"
            else self.F2FHeight * self.NFloors
        )

        geometry = ShoeboxGeometry(
            x=0,
            y=0,
            w=self.Width,
            d=self.Depth,
            h=effective_f2f_height,
            num_stories=self.NFloors,
            zoning=effective_zoning_mode,
            roof_height=None,
            perim_depth=3,
            wwr=self.WWR,
            basement=False,
            exposed_basement_frac=0,
        )

        def post_geometry_callback(idf: IDF) -> IDF:
            idf.rotate(self.Rotation)
            return idf

        return (
            Model(
                geometry=geometry,
                Zone=zone,
                # TODO: enable attic and basement assumptions
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


if __name__ == "__main__":
    flat_model = FlatModel(
        F2FHeight=3.25,
        Width=40,
        Depth=40,
        Rotation=45,
        WWR=0.3,
        NFloors=2,
        FacadeFramingSystem="2x4 16OCC Woodframe",
        # Facade
        FacadeCavityInsulationRValue=1.2,
        FacadeExteriorInsulationRValue=1.0,
        FacadeInteriorInsulationRValue=0.0,
        FacadeExteriorInsulationMaterial="XPSBoard",
        FacadeInteriorInsulationMaterial="XPSBoard",
        FacadeCavityInsulationMaterial="FiberglassBatt",
        FacadeInteriorFinish="drywall",
        FacadeExteriorFinish="wood_siding",
        # Subterranean
        SubterraneanWallFramingSystem="2x4 16OCC Woodframe",
        SubterraneanCavityInsulationRValue=1.2,
        SubterraneanExteriorInsulationRValue=1.0,
        SubterraneanInteriorInsulationRValue=0.0,
        SubterraneanExteriorInsulationMaterial="XPSBoard",
        SubterraneanInteriorInsulationMaterial="XPSBoard",
        SubterraneanCavityInsulationMaterial="FiberglassBatt",
        SubterraneanInteriorFinish="drywall",
        SubterraneanExteriorFinish="wood_siding",
        # GroundSlab
        GroundSlabSystem="BasicConcrete",
        GroundSlabInsulationRValue=1.5,
        GroundSlabInsulationMaterial="XPSBoard",
        GroundSlabInteriorFinish="wood_floor",
        GroundSlabStructuralThickness=0.15,
        # Roof
        RoofRValue=3.0,
        WindowUValue=3.0,
        WindowSHGF=0.7,
        WindowTVis=0.5,
        InfiltrationACH=0.5,
        BasementInfiltrationACH=0.5,
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
