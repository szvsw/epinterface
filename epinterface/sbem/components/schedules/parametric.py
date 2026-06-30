"""This module contains the definitions for the parametric schedules."""

from pydantic import BaseModel, Field

from epinterface.sbem.components.schedules.deterministic import (
    DayComponent,
    WeekComponent,
    YearComponent,
    YearScheduleCategory,
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
