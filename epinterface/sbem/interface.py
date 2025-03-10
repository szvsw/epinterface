"""A module for parsing SBEM template data and generating EnergyPlus objects."""

import logging
from pathlib import Path

import pandas as pd
from prisma import Prisma
from prisma.models import (
    ConstructionAssembly,
    Envelope,
    EnvelopeAssembly,
    Equipment,
    GlazingConstructionSimple,
    Infiltration,
    Lighting,
    Occupancy,
    Thermostat,
    WaterUse,
)
from pydantic import Field

from epinterface.sbem.common import MetadataMixin
from epinterface.sbem.components.envelope import (
    ConstructionAssemblyComponent,
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
from epinterface.sbem.prisma.client import (
    delete_all,
)

logger = logging.getLogger(__name__)


# attribution classes


class ComponentLibrary(MetadataMixin, arbitrary_types_allowed=True):
    """SBEM library object to handle the different components."""

    Operations: dict[str, ZoneOperationsComponent] = Field(
        ..., description="Operations component gathers HVAC and DHW and Space Use."
    )
    SpaceUse: dict[str, ZoneSpaceUseComponent] = Field(
        ...,
        description="Space use component gathers occupancy, lighting, equipment, and thermostats.",
    )
    Occupancy: dict[str, OccupancyComponent]
    Lighting: dict[str, LightingComponent]
    Equipment: dict[str, EquipmentComponent]
    Thermostat: dict[str, ThermostatComponent]
    WaterUse: dict[str, WaterUseComponent]

    HVAC: dict[str, ZoneHVACComponent] = Field(
        ..., description="HVAC component gathers conditioningsystems and ventilation."
    )
    ConditioningSystems: dict[str, ConditioningSystemsComponent]
    ThermalSystem: dict[str, ThermalSystemComponent]
    Ventilation: dict[str, VentilationComponent]

    DHW: dict[str, DHWComponent]

    Envelope: dict[str, ZoneEnvelopeComponent] = Field(
        ...,
        description="Envelope component gathers envelope assemblies, infiltration, and window definition.",
    )
    GlazingConstructionSimple: dict[str, GlazingConstructionSimpleComponent]
    Infiltration: dict[str, InfiltrationComponent]
    EnvelopeAssembly: dict[str, EnvelopeAssemblyComponent] = Field(
        ...,
        description="Envelope assembly component gathers roof, facade, slab, partition, external floor, ground slab, ground wall, and internal mass assemblies.",
    )
    ConstructionAssembly: dict[str, ConstructionAssemblyComponent]
    ConstructionMaterial: dict[str, ConstructionMaterialComponent]

    Year: dict[str, YearComponent]
    Week: dict[str, WeekComponent]
    Day: dict[str, DayComponent]


def excel_parser(path: Path) -> dict[str, pd.DataFrame]:
    """Parse an excel file and return dictionary of dataframes."""
    xls = pd.ExcelFile(path)
    sheet_names = [
        "Day_schedules",
        "Week_schedules",
        "Year_schedules",
        "Occupancy",
        "Lighting",
        "Equipment",
        "Thermostat",
        "Water flow",
        "Space use assembly",
        "Conditioning",
        "HVAC",
        "DHW",
        "Ventilation",
        "Materials",
        "Construction",
        "Envelope assembly",
        "Windows",
        "Infiltration",
    ]
    component_dfs_dict = {
        sheet: xls.parse(sheet) for sheet in sheet_names if sheet in xls.sheet_names
    }

    return component_dfs_dict


async def add_excel_to_db(path: Path, erase_db: bool = False, db: Prisma = None):
    """Add an excel file to the database."""
    if erase_db:
        delete_all()

    if db is None:
        db = Prisma()
        await db.connect()

    # handle converting excel to dfs
    component_dfs_dict = excel_parser(path)

    # add Day
    day_map = {}
    for _, row in component_dfs_dict["Day schedules"].iterrows():
        day = await db.day.create(
            data={
                "Name": str(row["Name"]),
                "Type": str(row["Type"]),
                **{
                    f"Hour_{str(i).zfill(2)}": float(row[f"Hour_{str(i).zfill(2)}"])
                    for i in range(24)
                },
            }
        )
        day_map[row["Name"]] = day.id
    # add Week
    week_map = {}
    for _, row in component_dfs_dict["Week schedules"].iterrows():
        week = await db.week.create(
            data={
                "Name": row["Name"],
                "MondayId": day_map[row["Monday"]],
                "TuesdayId": day_map[row["Tuesday"]],
                "WednesdayId": day_map[row["Wednesday"]],
                "ThursdayId": day_map[row["Thursday"]],
                "FridayId": day_map[row["Friday"]],
                "SaturdayId": day_map[row["Saturday"]],
                "SundayId": day_map[row["Sunday"]],
            }
        )
        week_map[row["Name"]] = week.id

    # add year: note that your will need to connnnect to weeks
    year_map = {}
    for _, row in component_dfs_dict["Year schedules"].iterrows():
        year = await db.year.create(
            data={
                "Name": row["Name"],
                "Type": row["Type"],
                "Weeks": {
                    "create": [
                        {
                            "StartDay": week_num * 7 + 1,
                            "EndDay": (week_num + 1) * 7,
                            "WeekId": week_map[row[f"Week_{week_num}"]],
                        }
                        for week_num in range(52)
                    ]
                },
            }
        )
        year_map[row["Name"]] = year.id

        year = YearComponent.model_validate(year, from_attributes=True)

    # add lighting/equipment/occupancy/thermostat/wateruse, connect to schedules

    # TODO: Use this for all of space use:
    # for category in ["Occupancy", "Lighting", "Equipment", "Thermostat", "Water flow"]:
    #     model = category.replace(" ", "")
    #     for _, row in component_dfs_dict[category].iterrows():
    #         await getattr(db, model.lower()).create(
    #             data={
    #                 "Name": row["Name"],
    #                 **({  # Set common schedule linking
    #                     "ScheduleId": year_map[row["Schedule"]]
    #                 } if "Schedule" in row else {})
    #             }
    #         )

    # occupancy
    for _, row in component_dfs_dict["Occupancy"].iterrows():
        occupancy = await Occupancy.prisma().create(
            data={
                "Name": row["Name"],
                "PeopleDensity": row["Occupancy"],
                "IsOn": True,
                "MetabolicRate": row["MetabolicRate"],
                "Schedule": {"connect": {"id": year_map[row["Schedule"]]}},
            }
        )

    for _, row in component_dfs_dict["Lighting"].iterrows():
        lighting = await Lighting.prisma(tx).create(
            data={
                "Name": row["Name"],
                "PowerDensity": row["PowerDensity"],
                "DimmingType": row["DimmingType"],
                "IsOn": True,
                "Schedule": {"connect": {"id": year_map[row["Schedule"]]}},
            }
        )

    for _, row in component_dfs_dict["Equipment"].iterrows():
        equipment = await Equipment.prisma().create(
            data={
                "Name": row["Name"],
                "PowerDensity": row["PowerDensity"],
                "IsOn": True,
                "Schedule": {"connect": {"id": year_map[row["Schedule"]]}},
            }
        )

    for _, row in component_dfs_dict["Thermostat"].iterrows():
        thermostat = await Thermostat.prisma().create(
            data={
                "Name": row["Name"],
                "HeatingSetpoint": row["HeatingSetpoint"],
                "CoolingSetpoint": row["CoolingSetpoint"],
                "IsOn": True,
                "HeatingSchedule": {
                    "connect": {"id": year_map[row["HeatingSchedule"]]}
                },
                "CoolingSchedule": {
                    "connect": {"id": year_map[row["CoolingSchedule"]]}
                },
            }
        )

    for _, row in component_dfs_dict["WaterUse"].iterrows():
        wateruse = await WaterUse.prisma().create(
            data={
                "Name": row["Name"],
                "FlowRatePerPerson": row["FlowRate"],
                "Schedule": {"connect": {"id": year_map[row["Schedule"]]}},
            }
        )

    # space use
    for _, row in component_dfs_dict["Space use assembly"].iterrows():
        await db.spaceuse.create(
            data={
                "Name": row["Name"],
                "OccupancyId": row["Occupancy"],
                "LightingId": row["Lighting"],
                "EquipmentId": row["Equipment"],
                "ThermostatId": row["Thermostat"],
                "WaterUseId": row["WaterUse"],
            }
        )

    # add cooling/heating systems
    for system_type in ["Heating", "Cooling"]:
        for _, row in (
            component_dfs_dict["Conditioning"]
            .query(f'Type == "{system_type}"')
            .iterrows()
        ):
            await db.thermalsystem.create(
                data={
                    "Name": row["Name"],
                    "ConditioningType": system_type,
                    "Fuel": row["Fuel"],
                    "SystemCOP": row["Efficiency"],
                    "DistributionCOP": row["DistributionEfficiency"],
                }
            )

    # add conditioning systems
    conditioning_map = {"Heating": {}, "Cooling": {}}
    for _, row in component_dfs_dict["Conditioning"].iterrows():
        system = await db.thermalsystem.create(
            data={
                "Name": row["Name"],
                "ConditioningType": row["Type"],  # "Heating" or "Cooling"
                "Fuel": row["Fuel"],
                "SystemCOP": row["Efficiency"],
                "DistributionCOP": row["DistributionEfficiency"],
            }
        )
        conditioning_map[row["Type"]][row["Name"]] = system.id

    # add ventilation
    ventilation_map = {}
    for _, row in component_dfs_dict["Ventilation"].iterrows():
        system = await db.ventilation.create(
            data={
                "Name": row["Name"],
                "Rate": row["Rate"],
                "MinFreshAir": row["MinFreshAir"],
                "Type": row["Type"],
                "TechType": row["TechType"],
                "ScheduleId": year_map[row["Schedule"]],
            }
        )
        ventilation_map[row["Name"]] = system.id

    # add hvac
    for _, row in component_dfs_dict["HVAC"].iterrows():
        if row["Name"] in conditioning_map and row["Ventilation"] in ventilation_map:
            await db.hvac.create(
                data={
                    "Name": row["Name"],
                    "ConditioningSystemsId": conditioning_map[row["Name"]],
                    "VentilationId": ventilation_map[row["Ventilation"]],
                }
            )

    # add dhw
    for _, row in component_dfs_dict["DHW"].iterrows():
        await db.dhw.create(
            data={
                "Name": row["Name"],
                "SystemCOP": row["SystemCOP"],
                "WaterTemperatureInlet": row["WaterTemperatureInlet"],
                "WaterSupplyTemperature": row["WaterSupplyTemperature"],
                "FuelType": row["FuelType"],
                "DistributionCOP": row["DistributionEfficiency"],
                "IsOn": True,
            }
        )

    # add operations
    # Get the latest created HVAC, SpaceUse and DHW records
    hvac = await db.hvac.find_first(order={"id": "desc"})
    space_use = await db.spaceuse.find_first(order={"id": "desc"})
    dhw = await db.dhw.find_first(order={"id": "desc"})

    if not hvac or not space_use or not dhw:
        msg = "Missing HVAC, SpaceUse or DHW records."
        logger.error(msg)
        raise ValueError(msg)

    # Create the Operations item
    operations = await db.operations.create(
        data={
            "Name": f"{hvac.Name}_{space_use.Name}_{dhw.Name}",
            "SpaceUseId": space_use.id,
            "HVACId": hvac.id,
            "DHWId": dhw.id,
        }
    )

    # add infiltration
    # get the infilitration and name columns from the envelope df
    infilitration = component_dfs_dict["Envelope"]["Infiltration", "Name"]
    infiltration_map = {}
    for _, row in infilitration.iterrows():
        with db.tx() as tx:
            infiltration = Infiltration.prisma(tx).create(
                data={
                    "Name": row["Name"],
                    "IsOn": True,
                    "ConstantCoefficient": 0.0,
                    "TemperatureCoefficient": 0.0,
                    "WindVelocityCoefficient": 0.0,
                    "WindVelocitySquaredCoefficient": 0.0,
                    "AFNAirMassFlowCoefficientCrack": 0.0,
                    "AirChangesPerHour": row["Infiltration"],
                    "FlowPerExteriorSurfaceArea": 0.0,
                    "CalculationMethod": "Flow/Zone",
                },
            )
            infiltration_map[row["Name"]] = infiltration.id

    # add materials
    for _, row in component_dfs_dict["Materials"].iterrows():
        material = await db.constructionmaterial.create(
            data={
                "Name": row["Name"],
                "Roughness": row["Roughness"],
                "ThermalAbsorptance": row["ThermalAbsorptance"],
                "SolarAbsorptance": row["SolarAbsorptance"],
                "TemperatureCoefficientThermalConductivity": row[
                    "TemperatureCoefficientThermalConductivity"
                ],
                "Type": row["Type"],
                "Density": row["Density"],
                "Conductivity": row["Conductivity"],
                "SpecificHeat": row["SpecificHeat"],
                "VisibleAbsorptance": row["VisibleAbsorptance"],
            }
        )

    # add construction assemblies - connenct to materials
    construction_map = {}
    for _, row in component_dfs_dict["Construction"].iterrows():
        with db.tx() as tx:
            layers = []
            # Iterate over the columns to extract materials and thicknesses
            for i in range(1, len(row) // 2 + 1):
                material_key = f"Material_{i}"
                thickness_key = f"Thickness_{i}"
                if material_key in row and thickness_key in row:
                    layers.append({
                        "create": {
                            "LayerOrder": i,
                            "Thickness": row[thickness_key],
                            "ConstructionMaterial": {
                                "connect": {"id": row[material_key]}
                            },
                        }
                    })

            # Create a ConstructionAssembly entry
            construction_assembly = ConstructionAssembly.prisma(tx).create(
                data={"Name": row["Name"], "Type": row["Type"], "Layers": layers}
            )

            construction_map[row["Name"]] = construction_assembly.id

    # add envelope assemblies - connect to construction assemblies
    # TODO: update with changes to excel
    envelope_assembly_map = {}
    for _, row in component_dfs_dict["Envelope_assembly"].iterrows():
        envelope_assembly = EnvelopeAssembly.prisma(tx).create(
            data={
                "Name": row["Name"],
                "InternalMassExposedAreaPerArea": 0,
                "GroundIsAdiabatic": True,
                "RoofIsAdiabatic": True,
                "FacadeIsAdiabatic": True,
                "SlabIsAdiabatic": True,
                "PartitionIsAdiabatic": True,
                "RoofAssembly": {
                    "connect": {"id": construction_map[row["RoofAssembly"]]}
                },
                "FacadeAssembly": {
                    "connect": {"id": construction_map[row["FacadeAssembly"]]}
                },
                "SlabAssembly": {
                    "connect": {"id": construction_map[row["SlabAssembly"]]}
                },
                "PartitionAssembly": {
                    "connect": {"id": construction_map[row["PartitionAssembly"]]}
                },
                "ExternalFloorAssembly": {
                    "connect": {"id": construction_map[row["ExternalFloorAssembly"]]}
                },
                "GroundSlabAssembly": {
                    "connect": {"id": construction_map[row["GroundSlabAssembly"]]}
                },
                "GroundWallAssembly": {
                    "connect": {"id": construction_map[row["GroundWallAssembly"]]}
                },
                "InternalMassAssembly": {
                    "connect": {"id": construction_map[row["InternalMassAssembly"]]}
                },
            }
        )
        envelope_assembly_map[row["Name"]] = envelope_assembly.id

    # add glazing constructions
    window = component_dfs_dict["Construction"].loc[
        component_dfs_dict["Construction"]["Type"] == "Window"
    ]
    window_map = {}
    for _, row in window.iterrows():
        window = await GlazingConstructionSimple.prisma().create(
            data={
                "Name": row["Name"],
                "UValue": row["UValue"],
                "SHGF": row["SHGC"],
                "TVis": row["TVis"],
                "Type": row["Glazing"],
            }
        )
        window_map[row["Name"]] = window.id

    # add envelope - connect to envelope assemblies, glazing constructions, infiltration
    for _, row in component_dfs_dict["Envelope"].iterrows():
        envelope = Envelope.prisma(tx).create(
            data={
                "Name": row["Name"],
                "Assemblies": {
                    "connect": {
                        "id": envelope_assembly_map[row["Assemblies"]],
                    }
                },
                "Infiltration": {
                    "connect": {
                        "id": infiltration_map[row["Infiltration"]],
                    }
                },
                "Window": {
                    "connect": {
                        "id": window_map[row["Window"]],
                    }
                },
            }
        )


# add model validation to each component


if __name__ == "__main__":
    path_to_excel = Path("path/to/your/lib.xlsx")
    add_excel_to_db(path_to_excel, erase_db=True)
