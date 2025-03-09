"""Demo of prisma object creation and deserialization."""

from prisma import Prisma
from prisma.models import (
    DHW,
    HVAC,
    ConditioningSystems,
    ConstructionAssembly,
    ConstructionMaterial,
    Day,
    Envelope,
    EnvelopeAssembly,
    Equipment,
    GlazingConstructionSimple,
    Infiltration,
    Lighting,
    Occupancy,
    Operations,
    SpaceUse,
    ThermalSystem,
    Thermostat,
    Ventilation,
    WaterUse,
    Week,
    Year,
)
from prisma.types import (
    ConstructionAssemblyInclude,
    ConstructionAssemblyLayerInclude,
    EnvelopeAssemblyInclude,
)

from epinterface.sbem.components.envelope import (
    ConstructionAssemblyComponent,
    EnvelopeAssemblyComponent,
    ZoneEnvelopeComponent,
)
from epinterface.sbem.components.operations import ZoneOperationsComponent
from epinterface.sbem.components.schedules import YearComponent
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
from epinterface.sbem.prisma.client import (
    SPACE_USE_INCLUDE,
    YEAR_INCLUDE,
    delete_all,
    prisma_settings,
)


def test_schedules(db: Prisma):  # noqa: D103
    with db.tx() as tx:
        day = await Day.prisma(tx).create(
            data={
                "Name": "Office Day asdfd",
                "Type": "Fraction",
                "Hour_00": 0.0,
                "Hour_01": 0.0,
                "Hour_02": 0.0,
                "Hour_03": 0.0,
                "Hour_04": 0.0,
                "Hour_05": 0.0,
                "Hour_06": 0.0,
                "Hour_07": 0.0,
                "Hour_08": 0.0,
                "Hour_09": 0.0,
                "Hour_10": 0.0,
                "Hour_11": 0.0,
                "Hour_12": 0.0,
                "Hour_13": 0.0,
                "Hour_14": 0.0,
                "Hour_15": 0.0,
                "Hour_16": 0.0,
                "Hour_17": 0.0,
                "Hour_18": 0.0,
                "Hour_19": 0.0,
                "Hour_20": 0.0,
                "Hour_21": 0.0,
                "Hour_22": 0.0,
                "Hour_23": 0.0,
            }
        )
        week = await Week.prisma(tx).create(
            data={
                "Name": "Office Week asdf",
                "Monday": {
                    "connect": {
                        "id": day.id,
                    }
                },
                "Tuesday": {
                    "connect": {
                        "id": day.id,
                    }
                },
                "Wednesday": {
                    "connect": {
                        "id": day.id,
                    }
                },
                "Thursday": {
                    "connect": {
                        "id": day.id,
                    }
                },
                "Friday": {
                    "connect": {
                        "id": day.id,
                    }
                },
                "Saturday": {
                    "connect": {
                        "id": day.id,
                    }
                },
                "Sunday": {
                    "connect": {
                        "id": day.id,
                    }
                },
            }
        )
        year = await Year.prisma(tx).create(
            data={
                "Name": "Office Year asdf",
                "Type": "Fraction",
                "Weeks": {
                    "create": [
                        {
                            "StartMonth": 1,
                            "StartDay": 1,
                            "EndMonth": 12,
                            "EndDay": 31,
                            "Week": {
                                "connect": {
                                    "id": week.id,
                                }
                            },
                        }
                    ]
                },
            },
            include=YEAR_INCLUDE,
        )

    year = YearComponent.model_validate(year, from_attributes=True)


def test_construction_assembly(db: Prisma):  # noqa: D103
    with db.tx() as tx:
        material = await ConstructionMaterial.prisma(tx).create(
            data={
                "Name": "Office Material",
                "Roughness": "Rough",
                "ThermalAbsorptance": 0.0,
                "SolarAbsorptance": 0.0,
                "TemperatureCoefficientThermalConductivity": 0.0,
                "Type": "Concrete",
                "Density": 1.0,
                "Conductivity": 0.0,
                "SpecificHeat": 0.0,
                "VisibleAbsorptance": 0.0,
            }
        )
        construction_assembly = await ConstructionAssembly.prisma(tx).create(
            data={
                "Name": "Office Construction Assembly",
                "Type": "Facade",
                "Layers": {
                    "create": [
                        {
                            "LayerOrder": 1,
                            "Thickness": 100,
                            "ConstructionMaterial": {
                                "connect": {
                                    "id": material.id,
                                }
                            },
                        },
                        {
                            "LayerOrder": 0,
                            "Thickness": 2,
                            "ConstructionMaterial": {
                                "connect": {
                                    "id": material.id,
                                }
                            },
                        },
                    ]
                },
            },
            include={
                "Layers": {
                    "include": {
                        "ConstructionMaterial": True,
                    }
                },
            },
        )
        layer_include_material: ConstructionAssemblyLayerInclude = {
            "ConstructionMaterial": True,
        }
        construction_assembly_include_layers: ConstructionAssemblyInclude = {
            "Layers": {"include": layer_include_material},
        }

        envelope_assembly_includes_construction_assemblies: EnvelopeAssemblyInclude = {
            "RoofAssembly": {"include": construction_assembly_include_layers},
            "FacadeAssembly": {"include": construction_assembly_include_layers},
            "SlabAssembly": {"include": construction_assembly_include_layers},
            "PartitionAssembly": {"include": construction_assembly_include_layers},
            "ExternalFloorAssembly": {"include": construction_assembly_include_layers},
            "GroundSlabAssembly": {"include": construction_assembly_include_layers},
            "GroundWallAssembly": {"include": construction_assembly_include_layers},
            "InternalMassAssembly": {"include": construction_assembly_include_layers},
        }

        envelope_assembly = await EnvelopeAssembly.prisma(tx).create(
            data={
                "Name": "Office Envelope Assembly",
                "InternalMassExposedAreaPerArea": 0.1,
                "GroundIsAdiabatic": True,
                "RoofIsAdiabatic": True,
                "FacadeIsAdiabatic": True,
                "SlabIsAdiabatic": True,
                "PartitionIsAdiabatic": True,
                "RoofAssembly": {
                    "connect": {
                        "id": construction_assembly.id,
                    }
                },
                "FacadeAssembly": {
                    "connect": {
                        "id": construction_assembly.id,
                    }
                },
                "SlabAssembly": {
                    "connect": {
                        "id": construction_assembly.id,
                    }
                },
                "PartitionAssembly": {
                    "connect": {
                        "id": construction_assembly.id,
                    }
                },
                "ExternalFloorAssembly": {
                    "connect": {
                        "id": construction_assembly.id,
                    }
                },
                "GroundSlabAssembly": {
                    "connect": {
                        "id": construction_assembly.id,
                    }
                },
                "GroundWallAssembly": {
                    "connect": {
                        "id": construction_assembly.id,
                    }
                },
                "InternalMassAssembly": {
                    "connect": {
                        "id": construction_assembly.id,
                    }
                },
            },
            include=envelope_assembly_includes_construction_assemblies,
        )

        window = await GlazingConstructionSimple.prisma(tx).create(
            data={
                "Name": "Office Window",
                "UValue": 0.0,
                "SHGF": 0.0,
                "TVis": 0.0,
                "Type": "Single",
            }
        )
        infiltration = await Infiltration.prisma(tx).create(
            data={
                "Name": "Office Infiltration",
                "IsOn": True,
                "ConstantCoefficient": 0.0,
                "TemperatureCoefficient": 0.0,
                "WindVelocityCoefficient": 0.0,
                "WindVelocitySquaredCoefficient": 0.0,
                "AFNAirMassFlowCoefficientCrack": 0.0,
                "AirChangesPerHour": 0.0,
                "FlowPerExteriorSurfaceArea": 0.0,
                "CalculationMethod": "Flow/Zone",
            }
        )

        envelope = await Envelope.prisma(tx).create(
            data={
                "Name": "Office Envelope",
                "Assemblies": {
                    "connect": {
                        "id": envelope_assembly.id,
                    }
                },
                "Infiltration": {
                    "connect": {
                        "id": infiltration.id,
                    }
                },
                "Window": {
                    "connect": {
                        "id": window.id,
                    }
                },
            },
            include={
                "Assemblies": {
                    "include": envelope_assembly_includes_construction_assemblies,
                },
                "Infiltration": True,
                "Window": True,
            },
        )

    envelope = ZoneEnvelopeComponent.model_validate(envelope, from_attributes=True)
    envelope_assembly = EnvelopeAssemblyComponent.model_validate(
        envelope_assembly, from_attributes=True
    )
    construction_assembly = ConstructionAssemblyComponent.model_validate(
        construction_assembly, from_attributes=True
    )


def test_operations(db: Prisma):  # noqa: D103
    with db.tx() as tx:
        day = await Day.prisma(tx).create(
            data={
                "Name": "Office Day",
                "Type": "Fraction",
                "Hour_00": 0.0,
                "Hour_01": 0.0,
                "Hour_02": 0.0,
                "Hour_03": 0.0,
                "Hour_04": 0.0,
                "Hour_05": 0.0,
                "Hour_06": 0.0,
                "Hour_07": 0.0,
                "Hour_08": 0.0,
                "Hour_09": 0.0,
                "Hour_10": 0.0,
                "Hour_11": 0.0,
                "Hour_12": 0.0,
                "Hour_13": 0.0,
                "Hour_14": 0.0,
                "Hour_15": 0.0,
                "Hour_16": 0.0,
                "Hour_17": 0.0,
                "Hour_18": 0.0,
                "Hour_19": 0.0,
                "Hour_20": 0.0,
                "Hour_21": 0.0,
                "Hour_22": 0.0,
                "Hour_23": 0.0,
            }
        )

        schedule = await Year.prisma(tx).create(
            data={
                "Name": "Office Schedule",
                "Type": "Fraction",
                "Weeks": {
                    "create": [
                        {
                            "StartMonth": 1,
                            "StartDay": 1,
                            "EndMonth": 12,
                            "EndDay": 31,
                            "Week": {
                                "create": {
                                    "Name": "Office Week",
                                    "Monday": {"connect": {"id": day.id}},
                                    "Tuesday": {"connect": {"id": day.id}},
                                    "Wednesday": {"connect": {"id": day.id}},
                                    "Thursday": {"connect": {"id": day.id}},
                                    "Friday": {"connect": {"id": day.id}},
                                    "Saturday": {"connect": {"id": day.id}},
                                    "Sunday": {"connect": {"id": day.id}},
                                }
                            },
                        }
                    ]
                },
            }
        )

        occupancy = await Occupancy.prisma(tx).create(
            data={
                "Name": "Office Occupancy",
                "PeopleDensity": 10,
                "IsOn": True,
                "MetabolicRate": 1.2,
                "Schedule": {
                    "connect": {
                        "id": schedule.id,
                    }
                },
            }
        )

        lighting = await Lighting.prisma(tx).create(
            data={
                "Name": "Office Lighting",
                "PowerDensity": 10,
                "DimmingType": "Stepped",
                "IsOn": True,
                "Schedule": {
                    "connect": {
                        "id": schedule.id,
                    }
                },
            }
        )

        thermostat = await Thermostat.prisma(tx).create(
            data={
                "Name": "Office Thermostat",
                "IsOn": True,
                "HeatingSetpoint": 20,
                "CoolingSetpoint": 25,
                "HeatingSchedule": {
                    "connect": {
                        "id": schedule.id,
                    }
                },
                "CoolingSchedule": {
                    "connect": {
                        "id": schedule.id,
                    }
                },
            }
        )

        equipment = await Equipment.prisma(tx).create(
            data={
                "Name": "Office Equipment",
                "PowerDensity": 10,
                "IsOn": True,
                "Schedule": {
                    "connect": {
                        "id": schedule.id,
                    }
                },
            }
        )

        water_use = await WaterUse.prisma(tx).create(
            data={
                "Name": "Office Water Use",
                "FlowRatePerPerson": 0.05,
                "Schedule": {
                    "connect": {
                        "id": schedule.id,
                    }
                },
            }
        )

        space_use = await SpaceUse.prisma(tx).create(
            data={
                "Name": "Office Zone Space Use",
                "Lighting": {
                    "connect": {
                        "id": lighting.id,
                    }
                },
                "Equipment": {
                    "connect": {
                        "id": equipment.id,
                    }
                },
                "Thermostat": {
                    "connect": {
                        "id": thermostat.id,
                    }
                },
                "WaterUse": {
                    "connect": {
                        "id": water_use.id,
                    }
                },
                "Occupancy": {
                    "connect": {
                        "id": occupancy.id,
                    }
                },
            },
            include=SPACE_USE_INCLUDE,
        )

        cooling = await ThermalSystem.prisma(tx).create(
            data={
                "Name": "Office Cooling",
                "ConditioningType": "Cooling",
                "Fuel": "Electricity",
                "SystemCOP": 3.5,
                "DistributionCOP": 0.9,
            }
        )

        heating = await ThermalSystem.prisma(tx).create(
            data={
                "Name": "Office Heating",
                "ConditioningType": "Heating",
                "Fuel": "Electricity",
                "SystemCOP": 3.5,
                "DistributionCOP": 0.9,
            }
        )

        conditioning = await ConditioningSystems.prisma(tx).create(
            data={
                "Name": "Office Conditioning",
                "Cooling": {
                    "connect": {
                        "id": cooling.id,
                    }
                },
                "Heating": {
                    "connect": {
                        "id": heating.id,
                    }
                },
            }
        )

        ventilation = await Ventilation.prisma(tx).create(
            data={
                "Name": "Office Ventilation",
                "Rate": 10,
                "MinFreshAir": 0.5,
                "Type": "Mechanical",
                "TechType": "ERV",
                "Schedule": {
                    "connect": {
                        "id": schedule.id,
                    }
                },
            }
        )

        dhw = await DHW.prisma(tx).create(
            data={
                "Name": "Office DHW",
                "SystemCOP": 3.5,
                "WaterTemperatureInlet": 10,
                "DistributionCOP": 0.9,
                "WaterSupplyTemperature": 50,
                "IsOn": True,
                "FuelType": "Electricity",
            }
        )

        havc = await HVAC.prisma(tx).create(
            data={
                "Name": "Office Zone HVAC",
                "ConditioningSystems": {
                    "connect": {
                        "id": conditioning.id,
                    }
                },
                "Ventilation": {
                    "connect": {
                        "id": ventilation.id,
                    }
                },
            }
        )

        zone_operations = await Operations.prisma(tx).create(
            data={
                "Name": "Office Zone Operations",
                "SpaceUse": {
                    "connect": {
                        "id": space_use.id,
                    }
                },
                "HVAC": {
                    "connect": {
                        "id": havc.id,
                    }
                },
                "DHW": {
                    "connect": {
                        "id": dhw.id,
                    }
                },
            },
            include={
                "SpaceUse": {"include": SPACE_USE_INCLUDE},
                "HVAC": {
                    "include": {
                        "ConditioningSystems": {
                            "include": {
                                "Cooling": True,
                                "Heating": True,
                            }
                        },
                        "Ventilation": {
                            "include": {
                                "Schedule": {"include": YEAR_INCLUDE},
                            }
                        },
                    }
                },
                "DHW": True,
            },
        )

    if zone_operations is None:
        msg = "Zone operations not found"
        raise ValueError(msg)

    operations = ZoneOperationsComponent.model_validate(
        zone_operations, from_attributes=True
    )
    space_use = ZoneSpaceUseComponent.model_validate(
        zone_operations.SpaceUse, from_attributes=True
    )
    thermostat = ThermostatComponent.model_validate(
        zone_operations.SpaceUse.Thermostat, from_attributes=True
    )
    equipment = EquipmentComponent.model_validate(
        zone_operations.SpaceUse.Equipment, from_attributes=True
    )
    lighting = LightingComponent.model_validate(
        zone_operations.SpaceUse.Lighting, from_attributes=True
    )
    water_use = WaterUseComponent.model_validate(
        zone_operations.SpaceUse.WaterUse, from_attributes=True
    )
    occupancy = OccupancyComponent.model_validate(
        zone_operations.SpaceUse.Occupancy, from_attributes=True
    )
    heating = ThermalSystemComponent.model_validate(
        zone_operations.HVAC.ConditioningSystems.Heating, from_attributes=True
    )
    cooling = ThermalSystemComponent.model_validate(
        zone_operations.HVAC.ConditioningSystems.Cooling, from_attributes=True
    )
    conditioning = ConditioningSystemsComponent.model_validate(
        zone_operations.HVAC.ConditioningSystems, from_attributes=True
    )
    ventilation = VentilationComponent.model_validate(
        zone_operations.HVAC.Ventilation, from_attributes=True
    )
    ZoneHVACComponent.model_validate(zone_operations.HVAC, from_attributes=True)
    dhw = DHWComponent.model_validate(zone_operations.DHW, from_attributes=True)

    print(operations.model_dump_json(indent=2))


def main():  # noqa: D103
    db = prisma_settings.db
    db.connect()

    delete_all()
    test_schedules(db)
    test_construction_assembly(db)
    test_operations(db)

    db.disconnect()


if __name__ == "__main__":
    main()
