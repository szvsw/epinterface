"""This module contains the definitions for the schedules."""

from typing import Any, Literal

from archetypal.idfclass.idf import IDF
from pydantic import BaseModel, Field, field_validator, model_validator

from epinterface.interface import ScheduleDayHourly, ScheduleWeekDaily, ScheduleYear
from epinterface.sbem.common import NamedObject

# TODO: handle schedule type limits in a consistent way once?
ScheduleTypeLimit = Literal["Fraction", "Temperature"]


class DayComponent(NamedObject, extra="forbid"):
    """A day of the week with a schedule type limit and a list of values."""

    Type: ScheduleTypeLimit
    Hour_00: float
    Hour_01: float
    Hour_02: float
    Hour_03: float
    Hour_04: float
    Hour_05: float
    Hour_06: float
    Hour_07: float
    Hour_08: float
    Hour_09: float
    Hour_10: float
    Hour_11: float
    Hour_12: float
    Hour_13: float
    Hour_14: float
    Hour_15: float
    Hour_16: float
    Hour_17: float
    Hour_18: float
    Hour_19: float
    Hour_20: float
    Hour_21: float
    Hour_22: float
    Hour_23: float

    @property
    def Values(self) -> list[float]:
        """Get the values of the day as a list."""
        return [
            self.Hour_00,
            self.Hour_01,
            self.Hour_02,
            self.Hour_03,
            self.Hour_04,
            self.Hour_05,
            self.Hour_06,
            self.Hour_07,
            self.Hour_08,
            self.Hour_09,
            self.Hour_10,
            self.Hour_11,
            self.Hour_12,
            self.Hour_13,
            self.Hour_14,
            self.Hour_15,
            self.Hour_16,
            self.Hour_17,
            self.Hour_18,
            self.Hour_19,
            self.Hour_20,
            self.Hour_21,
            self.Hour_22,
            self.Hour_23,
        ]

    @model_validator(mode="after")
    def validate_values(self):
        """Validate the values of the day are consistent with the schedule type limit."""
        # TODO: Implement with a eye for Archetypal

        # check that the values are consistent with the schedule type limit

        return self

    def add_day_to_idf(self, idf: IDF, name_prefix: str | None) -> tuple[IDF, str]:
        """Add the day to the IDF.

        The name prefix can be used to scope the schedule creation to ensure a unique schedule per object.

        Args:
            idf (IDF): The IDF object to add the day to.
            name_prefix (str | None): The prefix to use for the schedule name.

        Returns:
            idf (IDF): The IDF object with the day added.
            day_name (str): The name of the day schedule.
        """
        day_sched = ScheduleDayHourly(
            Name=self.Name,
            Schedule_Type_Limits_Name=self.Type,
            Hour_1=self.Hour_00,
            Hour_2=self.Hour_01,
            Hour_3=self.Hour_02,
            Hour_4=self.Hour_03,
            Hour_5=self.Hour_04,
            Hour_6=self.Hour_05,
            Hour_7=self.Hour_06,
            Hour_8=self.Hour_07,
            Hour_9=self.Hour_08,
            Hour_10=self.Hour_09,
            Hour_11=self.Hour_10,
            Hour_12=self.Hour_11,
            Hour_13=self.Hour_12,
            Hour_14=self.Hour_13,
            Hour_15=self.Hour_14,
            Hour_16=self.Hour_15,
            Hour_17=self.Hour_16,
            Hour_18=self.Hour_17,
            Hour_19=self.Hour_18,
            Hour_20=self.Hour_19,
            Hour_21=self.Hour_20,
            Hour_22=self.Hour_21,
            Hour_23=self.Hour_22,
            Hour_24=self.Hour_23,
        )
        if name_prefix is not None:
            day_sched.Name = f"{name_prefix}_DAY_{day_sched.Name}"
        idf = day_sched.add(idf)
        return idf, day_sched.Name


class WeekComponent(NamedObject, extra="forbid"):
    """A week with a list of days."""

    Monday: DayComponent
    Tuesday: DayComponent
    Wednesday: DayComponent
    Thursday: DayComponent
    Friday: DayComponent
    Saturday: DayComponent
    Sunday: DayComponent

    @model_validator(mode="after")
    def validate_type_limits_are_consistent(self):
        """Validate that the type limits are consistent."""
        lim = self.Monday.Type
        for day in self.Days:
            if day.Type != lim:
                msg = "Type limits are not consistent"
                raise ValueError(msg)
        return self

    @property
    def Days(self) -> list[DayComponent]:
        """Get the days of the week as a list."""
        return [
            self.Monday,
            self.Tuesday,
            self.Wednesday,
            self.Thursday,
            self.Friday,
            self.Saturday,
            self.Sunday,
        ]

    def add_week_to_idf(self, idf: IDF, name_prefix: str | None) -> tuple[IDF, str]:
        """Add the week to the IDF.

        The name prefix can be used to scope the schedule creation to ensure a unique schedule per object.

        Args:
            idf (IDF): The IDF object to add the week to.
            name_prefix (str | None): The prefix to use for the schedule name.

        Returns:
            idf (IDF): The IDF object with the week added.
            week_name (str): The name of the week schedule.
        """
        idf, monday_name = self.Monday.add_day_to_idf(idf, name_prefix)
        idf, tuesday_name = self.Tuesday.add_day_to_idf(idf, name_prefix)
        idf, wednesday_name = self.Wednesday.add_day_to_idf(idf, name_prefix)
        idf, thursday_name = self.Thursday.add_day_to_idf(idf, name_prefix)
        idf, friday_name = self.Friday.add_day_to_idf(idf, name_prefix)
        idf, saturday_name = self.Saturday.add_day_to_idf(idf, name_prefix)
        idf, sunday_name = self.Sunday.add_day_to_idf(idf, name_prefix)
        week_sched = ScheduleWeekDaily(
            Name=self.Name,
            Monday_ScheduleDay_Name=monday_name,
            Tuesday_ScheduleDay_Name=tuesday_name,
            Wednesday_ScheduleDay_Name=wednesday_name,
            Thursday_ScheduleDay_Name=thursday_name,
            Friday_ScheduleDay_Name=friday_name,
            Saturday_ScheduleDay_Name=saturday_name,
            Sunday_ScheduleDay_Name=sunday_name,
        )
        if name_prefix is not None:
            week_sched.Name = f"{name_prefix}_WEEK_{week_sched.Name}"
        idf = week_sched.add(idf)
        return idf, week_sched.Name

    @property
    def Type(self) -> ScheduleTypeLimit:
        """Get the type limit of the week."""
        return self.Monday.Type


class RepeatedWeekComponent(BaseModel, extra="forbid"):
    """A week to repeat with a start and end date and a list of days."""

    StartDay: int = Field(..., description="", ge=1, le=31)
    StartMonth: int = Field(..., description="", ge=1, le=12)
    EndDay: int = Field(..., description="", ge=1, le=31)
    EndMonth: int = Field(..., description="", ge=1, le=12)
    Week: WeekComponent

    @model_validator(mode="after")
    def validate_days(self):
        """Validate the start and end days are valid for the chosen months."""
        # check that the mm/dd for start is before the mm/dd for end
        if self.StartMonth > self.EndMonth:
            msg = "Start month must be before end month"
            raise ValueError(msg)
        if self.StartMonth == self.EndMonth and self.StartDay > self.EndDay:
            msg = "Start day must be before end day"
            raise ValueError(msg)

        # check that the start day is valid for the chosen month (e.g. no 31 in february)
        def check_day_valid_for_month(month: int, day: int):
            if month in [1, 3, 5, 7, 8, 10, 12]:
                return day <= 31
            elif month in [4, 6, 9, 11]:
                return day <= 30
            elif month == 2:
                return day <= 29
            else:
                msg = f"Invalid month: {month}"
                raise ValueError(msg)

        start_day_is_valid = check_day_valid_for_month(self.StartMonth, self.StartDay)
        if not start_day_is_valid:
            msg = f"Start day {self.StartDay} is invalid for the chosen month: {self.StartMonth}"
            raise ValueError(msg)

        end_day_is_valid = check_day_valid_for_month(self.EndMonth, self.EndDay)
        if not end_day_is_valid:
            msg = f"End day {self.EndDay} is invalid for the chosen month: {self.EndMonth}"
            raise ValueError(msg)

        return self


class YearComponent(NamedObject, extra="forbid"):
    """A year with a schedule type limit and a list of repeated weeks."""

    Type: ScheduleTypeLimit
    Weeks: list[RepeatedWeekComponent]

    @field_validator("Weeks", mode="after")
    @classmethod
    def validate_weeks(cls, weeks: list[RepeatedWeekComponent]):
        """Validate the weeks are well-ordered and that the start and end days are jan 1 and dec 31."""
        # check that it is well-ordered and that the start and end days are jan 1 and dec 31
        # TODO: Implement
        return weeks

    @model_validator(mode="after")
    def check_weeks_have_consistent_type(self):
        """Check that the weeks have a consistent type."""
        lim = self.Weeks[0].Week.Type
        for week in self.Weeks:
            if week.Week.Type != lim:
                msg = "Type limits are not consistent"
                raise ValueError(msg)

        return self

    def add_year_to_idf(self, idf: IDF, name_prefix: str | None = None):
        """Add the year to the IDF.

        The name prefix can be used to scope the schedule creation to ensure a unique schedule per object.

        Args:
            idf (IDF): The IDF object to add the year to.
            name_prefix (str | None): The prefix to use for the schedule name.

        Returns:
            idf (IDF): The IDF object with the year added.
            year_name (str): The name of the year schedule.
        """
        # because of the weird way eppy requires schedule:year input, we create a pass through dict
        # before validating.
        schedule_year_obj: dict[str, Any] = {
            "Name": self.Name,
            "Schedule_Type_Limits_Name": self.Type,
        }
        for i, week in enumerate(self.Weeks):
            idf, week_name = week.Week.add_week_to_idf(idf, name_prefix)
            schedule_year_obj[f"ScheduleWeek_Name_{i + 1}"] = week_name
            schedule_year_obj[f"Start_Month_{i + 1}"] = week.StartMonth
            schedule_year_obj[f"Start_Day_{i + 1}"] = week.StartDay
            schedule_year_obj[f"End_Month_{i + 1}"] = week.EndMonth
            schedule_year_obj[f"End_Day_{i + 1}"] = week.EndDay

        year_sched = ScheduleYear(**schedule_year_obj)
        if name_prefix is not None:
            year_sched.Name = f"{name_prefix}_YEAR_{year_sched.Name}"
        idf = year_sched.add(idf)
        return idf, year_sched.Name
