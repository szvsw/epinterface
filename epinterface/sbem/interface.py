"""A module for parsing SBEM template data and generating EnergyPlus objects."""

import logging
from pathlib import Path
from typing import Any

import pandas as pd
from prisma import Prisma
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
from epinterface.sbem.prisma.client import delete_all

logger = logging.getLogger(__name__)


# attribution classes

# helper functions


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


def load_excel_to_dict(base_path: Path, sheet_name: str) -> dict[str, Any]:
    """Load the excel file into a dictionary."""
    df = pd.read_excel(base_path, sheet_name=sheet_name, engine="openpyxl")
    df.columns = df.iloc[0]
    df = df[1:]
    data = df.to_dict(orient="records")
    return {d["Name"]: d for d in data}


def excel_parser(path: Path) -> dict[str, pd.DataFrame]:
    """Parse an excel file and return dictionary of dataframes."""
    xls = pd.ExcelFile(path)
    sheet_names = [
        "Day_schedules",
        "Week_schedules",
        "Year_schedules",
        "Occupancy",
        "Lighting",
        "Power",
        "Setpoints",
        "Water_flow",
        "Space_use_assembly",
        # "Conditioning",
        # "HVAC",
        # "DHW",
        # "Ventilation",
        # "Materials",
        # "Construction",
        # "Envelope assembly",
        # "Windows",
        # "Infiltration",
    ]
    component_dfs_dict = {
        sheet: xls.parse(sheet, skiprows=1)
        for sheet in sheet_names
        if sheet in xls.sheet_names
    }

    # Drop rows with NaNs because we want to be able to have
    # template rows in the sheet.
    for sheet, df in component_dfs_dict.items():
        mask = df.isna().any(axis=1)
        old_len = len(df)
        df = df[~mask]
        new_len = len(df)
        if old_len != new_len:
            logger.warning(f"Dropping {old_len - new_len} rows from {sheet}.")
        if new_len == 0:
            msg = f"No data found in {sheet}."
            raise ValueError(msg)
        component_dfs_dict[sheet] = df

    return component_dfs_dict


def add_excel_to_db(path: Path, db: Prisma, erase_db: bool = False):  # noqa: C901
    """Add an excel file to the database."""
    from datetime import timedelta

    """Add an excel file to the database."""
    with db:
        if erase_db:
            delete_all()

        component_dfs_dict = excel_parser(path)
        with db.tx(max_wait=timedelta(seconds=10), timeout=timedelta(minutes=1)) as tx:
            for _, row in component_dfs_dict["Day_schedules"].iterrows():
                tx.day.create(
                    data={
                        "Name": str(row["Day_schedule_name"]),
                        "Type": str(row["Type"]),
                        "Hour_00": float(row["Hour0"]),
                        "Hour_01": float(row["Hour1"]),
                        "Hour_02": float(row["Hour2"]),
                        "Hour_03": float(row["Hour3"]),
                        "Hour_04": float(row["Hour4"]),
                        "Hour_05": float(row["Hour5"]),
                        "Hour_06": float(row["Hour6"]),
                        "Hour_07": float(row["Hour7"]),
                        "Hour_08": float(row["Hour8"]),
                        "Hour_09": float(row["Hour9"]),
                        "Hour_10": float(row["Hour10"]),
                        "Hour_11": float(row["Hour11"]),
                        "Hour_12": float(row["Hour12"]),
                        "Hour_13": float(row["Hour13"]),
                        "Hour_14": float(row["Hour14"]),
                        "Hour_15": float(row["Hour15"]),
                        "Hour_16": float(row["Hour16"]),
                        "Hour_17": float(row["Hour17"]),
                        "Hour_18": float(row["Hour18"]),
                        "Hour_19": float(row["Hour19"]),
                        "Hour_20": float(row["Hour20"]),
                        "Hour_21": float(row["Hour21"]),
                        "Hour_22": float(row["Hour22"]),
                        "Hour_23": float(row["Hour23"]),
                    }
                )

            for _, row in component_dfs_dict["Week_schedules"].iterrows():
                tx.week.create(
                    data={
                        "Name": row["Week_schedules"],
                        "Monday": {"connect": {"Name": row["Mon"]}},
                        "Tuesday": {"connect": {"Name": row["Tue"]}},
                        "Wednesday": {"connect": {"Name": row["Wed"]}},
                        "Thursday": {"connect": {"Name": row["Thur"]}},
                        "Friday": {"connect": {"Name": row["Fri"]}},
                        "Saturday": {"connect": {"Name": row["Sat"]}},
                        "Sunday": {"connect": {"Name": row["Sun"]}},
                    },
                )

            # add year: note that your will need to connnnect to weeks
            for _, row in component_dfs_dict["Year_schedules"].iterrows():
                tx.year.create(
                    data={
                        "Name": row["Year_schedules"],
                        "Type": row["Schedule_type"],
                        "January": {"connect": {"Name": row["Jan"]}},
                        "February": {"connect": {"Name": row["Feb"]}},
                        "March": {"connect": {"Name": row["Mar"]}},
                        "April": {"connect": {"Name": row["Apr"]}},
                        "May": {"connect": {"Name": row["May"]}},
                        "June": {"connect": {"Name": row["Jun"]}},
                        "July": {"connect": {"Name": row["Jul"]}},
                        "August": {"connect": {"Name": row["Aug"]}},
                        "September": {"connect": {"Name": row["Sep"]}},
                        "October": {"connect": {"Name": row["Oct"]}},
                        "November": {"connect": {"Name": row["Nov"]}},
                        "December": {"connect": {"Name": row["Dec"]}},
                    }
                )

            for _, row in component_dfs_dict["Occupancy"].iterrows():
                tx.occupancy.create(
                    data={
                        "Name": row["Name"],
                        "PeopleDensity": row["Occupant_density"],
                        "IsOn": True,
                        "MetabolicRate": row["MetabolicRate"],
                        "Schedule": {"connect": {"Name": row["Occupant_schedule"]}},
                    }
                )

            for _, row in component_dfs_dict["Lighting"].iterrows():
                tx.lighting.create(
                    data={
                        "Name": row["Name"],
                        "PowerDensity": row["Lighting_power_density"],
                        "DimmingType": row["DimmingType"],
                        "IsOn": True,
                        "Schedule": {"connect": {"Name": row["Lighting_schedule"]}},
                    }
                )

            for _, row in component_dfs_dict["Power"].iterrows():
                tx.equipment.create(
                    data={
                        "Name": row["Name"],
                        "PowerDensity": row["Equipment_power_density"],
                        "IsOn": True,
                        "Schedule": {"connect": {"Name": row["Equipment_schedule"]}},
                    }
                )

            for _, row in component_dfs_dict["Setpoints"].iterrows():
                tx.thermostat.create(
                    data={
                        "Name": row["Name"],
                        "HeatingSetpoint": row["Heating_setpoint"],
                        "CoolingSetpoint": row["Cooling_setpoint"],
                        "IsOn": True,
                        "HeatingSchedule": {
                            "connect": {"Name": row["Heating_schedule"]}
                        },
                        "CoolingSchedule": {
                            "connect": {"Name": row["Cooling_schedule"]}
                        },
                    }
                )

            for _, row in component_dfs_dict["Water_flow"].iterrows():
                tx.wateruse.create(
                    data={
                        "Name": row["Name"],
                        "FlowRatePerPerson": row["DHW_flow_rate"],
                        "Schedule": {"connect": {"Name": row["Water_schedule"]}},
                    }
                )
            # space use
            for _, row in component_dfs_dict["Space_use_assembly"].iterrows():
                tx.spaceuse.create(
                    data={
                        "Name": row["Name"],
                        "Occupancy": {"connect": {"Name": row["Occupancy"]}},
                        "Lighting": {"connect": {"Name": row["Lighting"]}},
                        "Equipment": {"connect": {"Name": row["Equipment"]}},
                        "Thermostat": {"connect": {"Name": row["Setpoints"]}},
                        "WaterUse": {"connect": {"Name": row["WaterUse"]}},
                    }
                )
            return

            # # add cooling/heating systems
            # # TODO: think about what happens when a heating and cooling system have the same name
            # for system_type in ["Heating", "Cooling"]:
            #     for _, row in (
            #         component_dfs_dict["Conditioning"]
            #         .query(f'Type == "{system_type}"')
            #         .iterrows()
            #     ):
            #         tx.thermalsystem.create(
            #             data={
            #                 "Name": row["Name"],
            #                 "ConditioningType": system_type,
            #                 "Fuel": row["Fuel"],
            #                 "SystemCOP": row["Efficiency"],
            #                 "DistributionCOP": row["DistributionEfficiency"],
            #             }
            #         )

            # # add conditioning systems
            # for _, row in component_dfs_dict["Conditioning"].iterrows():
            #     system = tx.thermalsystem.create(
            #         data={
            #             "Name": row["Name"],
            #             "ConditioningType": row["Type"],  # "Heating" or "Cooling"
            #             "Fuel": row["Fuel"],
            #             "SystemCOP": row["Efficiency"],
            #             "DistributionCOP": row["DistributionEfficiency"],
            #         }
            #     )

            # # add ventilation
            # for _, row in component_dfs_dict["Ventilation"].iterrows():
            #     system = tx.ventilation.create(
            #         data={
            #             "Name": row["Name"],
            #             "Rate": row["Rate"],
            #             "MinFreshAir": row["MinFreshAir"],
            #             "Type": row["Type"],
            #             "TechType": row["TechType"],
            #             "Schedule": {"connect": {"Name": row["Schedule"]}},
            #         }
            #     )

            # # add hvac
            # for _, row in component_dfs_dict["HVAC"].iterrows():
            #     if (
            #         row["Name"] in conditioning_map
            #         and row["Ventilation"] in ventilation_map
            #     ):
            #         tx.hvac.create(
            #             data={
            #                 "Name": row["Name"],
            #                 "ConditioningSystemsId": conditioning_map[row["Name"]],
            #                 "VentilationId": ventilation_map[row["Ventilation"]],
            #             }
            #         )

            # add dhw
            for _, row in component_dfs_dict["DHW"].iterrows():
                tx.dhw.create(
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

            # # add operations
            # # Get the latest created HVAC, SpaceUse and DHW records
            # hvac = tx.hvac.find_first(order={"id": "desc"})
            # space_use = tx.spaceuse.find_first(order={"id": "desc"})
            # dhw = tx.dhw.find_first(order={"id": "desc"})

            # if not hvac or not space_use or not dhw:
            #     msg = "Missing HVAC, SpaceUse or DHW records."
            #     logger.error(msg)
            #     raise ValueError(msg)

            # # Create the Operations item
            # tx.operations.create(
            #     data={
            #         "Name": f"{hvac.Name}_{space_use.Name}_{dhw.Name}",
            #         "SpaceUseId": space_use.id,
            #         "HVACId": hvac.id,
            #         "DHWId": dhw.id,
            #     }
            # )

            # add infiltration
            # get the infilitration and name columns from the envelope df
            # infilitration = component_dfs_dict["Envelope"]["Infiltration", "Name"]
            # infiltration_map = {}
            # for _, row in infilitration.iterrows():
            #     infiltration = tx.infiltration.create(
            #         data={
            #             "Name": row["Name"],
            #             "IsOn": True,
            #             "ConstantCoefficient": 0.0,
            #             "TemperatureCoefficient": 0.0,
            #             "WindVelocityCoefficient": 0.0,
            #             "WindVelocitySquaredCoefficient": 0.0,
            #             "AFNAirMassFlowCoefficientCrack": 0.0,
            #             "AirChangesPerHour": row["Infiltration"],
            #             "FlowPerExteriorSurfaceArea": 0.0,
            #             "CalculationMethod": "AirChangesPerHour",
            #         },
            #     )
            #     infiltration_map[row["Name"]] = infiltration.id

            # add materials
            for _, row in component_dfs_dict["Materials"].iterrows():
                tx.constructionmaterial.create(
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
            for _, row in component_dfs_dict["Construction"].iterrows():
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
                                    "connect": {"Name": row[material_key]}
                                },
                            }
                        })

                # Create a ConstructionAssembly entry
                tx.constructionassembly.create(
                    data={"Name": row["Name"], "Type": row["Type"], "Layers": layers}
                )

            # add envelope assemblies - connect to construction assemblies
            # TODO: update with changes to excel
            for _, row in component_dfs_dict["Envelope_assembly"].iterrows():
                tx.envelopeassembly.create(
                    data={
                        "Name": row["Name"],
                        "InternalMassExposedAreaPerArea": 0,
                        "GroundIsAdiabatic": True,
                        "RoofIsAdiabatic": True,
                        "FacadeIsAdiabatic": True,
                        "SlabIsAdiabatic": True,
                        "PartitionIsAdiabatic": True,
                        "RoofAssembly": {"connect": {"Name": row["RoofAssembly"]}},
                        "FacadeAssembly": {"connect": {"Name": row["FacadeAssembly"]}},
                        "SlabAssembly": {"connect": {"Name": row["SlabAssembly"]}},
                        "PartitionAssembly": {
                            "connect": {"Name": row["PartitionAssembly"]}
                        },
                        "ExternalFloorAssembly": {
                            "connect": {"Name": row["ExternalFloorAssembly"]}
                        },
                        "GroundSlabAssembly": {
                            "connect": {"Name": row["GroundSlabAssembly"]}
                        },
                        "GroundWallAssembly": {
                            "connect": {"Name": row["GroundWallAssembly"]}
                        },
                        # "InternalMassAssembly": {
                        #     "connect": {"Name": row["InternalMassAssembly"]}
                        # },
                    }
                )

            # add glazing constructions
            window = component_dfs_dict["Construction"].loc[
                component_dfs_dict["Construction"]["Type"] == "Window"
            ]
            for _, row in window.iterrows():
                window = tx.glazingconstructionsimple.create(
                    data={
                        "Name": row["Name"],
                        "UValue": row["UValue"],
                        "SHGF": row["SHGC"],
                        "TVis": row["TVis"],
                        "Type": row["Glazing"],
                    }
                )

            # # add envelope - connect to envelope assemblies, glazing constructions, infiltration
            # for _, row in component_dfs_dict["Envelope"].iterrows():
            #     tx.envelope.create(
            #         data={
            #             "Name": row["Name"],
            #             "Assemblies": {
            #                 "connect": {"Name": row["Assemblies"]}
            #             },
            #             "Infiltration": {"connect": {"Name": row["Infiltration"]}},
            #             "Window": {"connect": {"Name": row["Window"]}},
            #         }
            #     )

        # add model validation to each component


if __name__ == "__main__":
    path_to_excel = Path("tests/data/template_tester_v3.xlsx")
    from epinterface.sbem.prisma.client import PrismaSettings

    logging.basicConfig(level=logging.INFO)

    db_path = Path("test.db")
    settings = PrismaSettings.New(database_path=db_path, if_exists="migrate")
    db = settings.db
    add_excel_to_db(path_to_excel, db, erase_db=True)
