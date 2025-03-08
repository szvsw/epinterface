"""Partial type generators for deep object fetching."""

from prisma.models import (
    HVAC,
    Equipment,
    Lighting,
    Occupancy,
    Operations,
    RepeatedWeek,
    SpaceUse,
    Thermostat,
    Ventilation,
    WaterUse,
    Week,
    Year,
)

Week.create_partial(
    name="WeekWithDays",
    required={
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    },
)


RepeatedWeek.create_partial(
    name="RepeatedWeekWithWeeks", required={"Week"}, relations={"Week": "WeekWithDays"}
)

Year.create_partial(
    name="YearWithWeeks",
    required={"Weeks"},
    relations={"Weeks": "RepeatedWeekWithWeeks"},
)

Occupancy.create_partial(
    name="OccupancyWithSchedule",
    required={"Schedule"},
    relations={"Schedule": "YearWithWeeks"},
)

Lighting.create_partial(
    name="LightingWithSchedule",
    required={"Schedule"},
    relations={"Schedule": "YearWithWeeks"},
)

Equipment.create_partial(
    name="EquipmentWithSchedule",
    required={"Schedule"},
    relations={"Schedule": "YearWithWeeks"},
)

Thermostat.create_partial(
    name="ThermostatWithSchedule",
    required={"HeatingSchedule", "CoolingSchedule"},
    relations={"HeatingSchedule": "YearWithWeeks", "CoolingSchedule": "YearWithWeeks"},
)

WaterUse.create_partial(
    name="WaterUseWithSchedule",
    required={"Schedule"},
    relations={"Schedule": "YearWithWeeks"},
)

Ventilation.create_partial(
    name="VentilationWithSchedule",
    required={"Schedule"},
    relations={"Schedule": "YearWithWeeks"},
)

HVAC.create_partial(
    name="HVACWithConditioningSystemsAndVentilation",
    required={"ConditioningSystems", "Ventilation"},
    relations={
        "Ventilation": "VentilationWithSchedule",
    },
)


SpaceUse.create_partial(
    name="SpaceUseWithChildren",
    required={"Lighting", "Equipment", "Thermostat", "WaterUse", "Occupancy"},
    relations={
        "Lighting": "LightingWithSchedule",
        "Equipment": "EquipmentWithSchedule",
        "Thermostat": "ThermostatWithSchedule",
        "WaterUse": "WaterUseWithSchedule",
        "Occupancy": "OccupancyWithSchedule",
    },
)


Operations.create_partial(
    name="OperationsWithChildren",
    required={"SpaceUse", "HVAC", "DHW"},
    relations={
        "SpaceUse": "SpaceUseWithChildren",
        "HVAC": "HVACWithConditioningSystemsAndVentilation",
    },
)
