"""Partial type generators for deep object fetching."""

from prisma.models import (
    HVAC,
    ConstructionAssembly,
    ConstructionAssemblyLayer,
    Envelope,
    EnvelopeAssembly,
    Equipment,
    Lighting,
    Occupancy,
    Operations,
    SpaceUse,
    Thermostat,
    Ventilation,
    WaterUse,
    Week,
    Year,
    Zone,
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


Year.create_partial(
    name="YearWithWeeks",
    required={
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    },
    relations={
        "January": "WeekWithDays",
        "February": "WeekWithDays",
        "March": "WeekWithDays",
        "April": "WeekWithDays",
        "May": "WeekWithDays",
        "June": "WeekWithDays",
        "July": "WeekWithDays",
        "August": "WeekWithDays",
        "September": "WeekWithDays",
        "October": "WeekWithDays",
        "November": "WeekWithDays",
        "December": "WeekWithDays",
    },
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


ConstructionAssemblyLayer.create_partial(
    name="ConstructionAssemblyLayerWithConstructionMaterial",
    required={"ConstructionMaterial"},
)

ConstructionAssembly.create_partial(
    name="ConstructionAssemblyWithLayers",
    required={"Layers"},
    relations={"Layers": "ConstructionAssemblyLayerWithConstructionMaterial"},
)

EnvelopeAssembly.create_partial(
    name="EnvelopeAssemblyWithChildren",
    required={
        "RoofAssembly",
        "FacadeAssembly",
        "SlabAssembly",
        "PartitionAssembly",
        "ExternalFloorAssembly",
        "GroundSlabAssembly",
        "GroundWallAssembly",
    },
    relations={
        "RoofAssembly": "ConstructionAssemblyWithLayers",
        "FacadeAssembly": "ConstructionAssemblyWithLayers",
        "SlabAssembly": "ConstructionAssemblyWithLayers",
        "PartitionAssembly": "ConstructionAssemblyWithLayers",
        "ExternalFloorAssembly": "ConstructionAssemblyWithLayers",
        "GroundSlabAssembly": "ConstructionAssemblyWithLayers",
        "GroundWallAssembly": "ConstructionAssemblyWithLayers",
        "InternalMassAssembly": "ConstructionAssemblyWithLayers",
    },
)

Envelope.create_partial(
    name="EnvelopeWithChildren",
    required={"Assemblies", "Infiltration", "Window"},
    relations={"Assemblies": "EnvelopeAssemblyWithChildren"},
)

Zone.create_partial(
    name="ZoneWithChildren",
    required={"Envelope", "Operations"},
    relations={
        "Envelope": "EnvelopeWithChildren",
        "Operations": "OperationsWithChildren",
    },
)
