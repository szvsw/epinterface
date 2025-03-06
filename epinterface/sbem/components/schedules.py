"""This module contains the definitions for the schedules."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from epinterface.sbem.common import NamedObject

ScheduleTypeLimit = Literal["Fraction", "Temperature"]


class DayComponent(NamedObject):
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


class WeekComponent(NamedObject):
    """A week with a list of days."""

    Monday: DayComponent
    Tuesday: DayComponent
    Wednesday: DayComponent
    Thursday: DayComponent
    Friday: DayComponent
    Saturday: DayComponent
    Sunday: DayComponent


class RepeatedWeekComponent(BaseModel):
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


class YearComponent(NamedObject):
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
    def check_leaf_days_have_consistent_type(self):
        """Check that the leaf days have a consistent type."""
        # TODO: Implement
        return self
