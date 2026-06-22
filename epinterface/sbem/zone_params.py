"""Scalar zone inputs shared by FlatModel and per-zone assignment."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from epinterface.sbem.components.systems import (
    DCVMethod,
    DHWFuelType,
    EconomizerMethod,
    FuelType,
    HRVMethod,
    VentilationProvider,
)


class ZoneParams(BaseModel):
    """Building-zone calibration parameters used to construct a ZoneComponent."""

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

    IdealLoadsHeatingOn: bool = True
    IdealLoadsCoolingOn: bool = True

    # optional flat 24h weekday profiles (0-1); when set, used instead of parametric
    CustomLightingWeekdayHourly: list[float] | None = None
    CustomEquipmentWeekdayHourly: list[float] | None = None
    CustomOccupancyWeekdayHourly: list[float] | None = None

    @field_validator(
        "CustomLightingWeekdayHourly",
        "CustomEquipmentWeekdayHourly",
        "CustomOccupancyWeekdayHourly",
    )
    @classmethod
    def _validate_hourly_profile(cls, value: list[float] | None) -> list[float] | None:
        if value is None:
            return None
        if len(value) != 24:
            msg = "hourly profile must have exactly 24 values"
            raise ValueError(msg)
        for hour, fraction in enumerate(value):
            if not 0 <= fraction <= 1:
                msg = f"hour {hour} value {fraction} out of range [0, 1]"
                raise ValueError(msg)
        return value
