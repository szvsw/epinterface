"""A module for parsing SBEM template data and generating EnergyPlus objects."""

import logging
from datetime import timedelta
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
from epinterface.sbem.prisma.client import (
    CONDITIONING_SYSTEMS_INCLUDE,
    CONSTRUCTION_ASSEMBLY_INCLUDE,
    DHW_INCLUDE,
    ENVELOPE_ASSEMBLY_INCLUDE,
    ENVELOPE_INCLUDE,
    EQUIPMENT_INCLUDE,
    HVAC_INCLUDE,
    LIGHTING_INCLUDE,
    OCCUPANCY_INCLUDE,
    SPACE_USE_INCLUDE,
    THERMAL_SYSTEM_INCLUDE,
    THERMOSTAT_INCLUDE,
    VENTILATION_INCLUDE,
    WATER_USE_INCLUDE,
    YEAR_INCLUDE,
    delete_all,
)

logger = logging.getLogger(__name__)


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


# TODO: consider adding validations for every single component using deep fetchers
# within the transaction so that nicer errors are raised when the data is going to be loaded.
# TODO: consider using batch adds rather than looping adds.
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
        "Conditioning_constructor",
        "Systems_assembly",
        "DHW_Constructor",
        "Ventilation_constructor",
        "Materials",
        "Window_choices",
        "Construction_components",
        "Envelope_assembly",
    ]
    component_dfs_dict = {
        sheet: xls.parse(sheet, skiprows=1)
        for sheet in sheet_names
        if sheet in xls.sheet_names
    }

    # Drop rows with NaNs because we want to be able to have
    # template rows in the sheet.
    for sheet, df in component_dfs_dict.items():
        if sheet in ["Materials", "Construction_components"]:
            mask = df["Name"].isna()
        else:
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

    # remove any duplicate instances from materials
    component_dfs_dict["Materials"] = component_dfs_dict["Materials"].drop_duplicates(
        subset=["Name"]
    )

    return component_dfs_dict


def add_excel_to_db(path: Path, db: Prisma, erase_db: bool = False):  # noqa: C901
    """Add an excel file to the database."""
    """Add an excel file to the database."""
    if erase_db:
        delete_all(db)

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
                },
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
            year = tx.year.create(
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
                },
                include=YEAR_INCLUDE,
            )
            YearComponent.model_validate(year, from_attributes=True)

        for _, row in component_dfs_dict["Occupancy"].iterrows():
            occupancy = tx.occupancy.create(
                data={
                    "Name": row["Name"],
                    "PeopleDensity": row["Occupant_density"],
                    "IsOn": True,
                    "MetabolicRate": row["MetabolicRate"],
                    "Schedule": {"connect": {"Name": row["Occupant_schedule"]}},
                },
                include=OCCUPANCY_INCLUDE,
            )
            OccupancyComponent.model_validate(occupancy, from_attributes=True)

        for _, row in component_dfs_dict["Lighting"].iterrows():
            lighting = tx.lighting.create(
                data={
                    "Name": row["Name"],
                    "PowerDensity": row["Lighting_power_density"],
                    "DimmingType": row["DimmingType"],
                    "IsOn": True,
                    "Schedule": {"connect": {"Name": row["Lighting_schedule"]}},
                },
                include=LIGHTING_INCLUDE,
            )
            LightingComponent.model_validate(lighting, from_attributes=True)

        for _, row in component_dfs_dict["Power"].iterrows():
            equipment = tx.equipment.create(
                data={
                    "Name": row["Name"],
                    "PowerDensity": row["Equipment_power_density"],
                    "IsOn": True,
                    "Schedule": {"connect": {"Name": row["Equipment_schedule"]}},
                },
                include=EQUIPMENT_INCLUDE,
            )
            EquipmentComponent.model_validate(equipment, from_attributes=True)

        for _, row in component_dfs_dict["Setpoints"].iterrows():
            thermostat = tx.thermostat.create(
                data={
                    "Name": row["Name"],
                    "HeatingSetpoint": row["Heating_setpoint"],
                    "CoolingSetpoint": row["Cooling_setpoint"],
                    "IsOn": True,
                    "HeatingSchedule": {"connect": {"Name": row["Heating_schedule"]}},
                    "CoolingSchedule": {"connect": {"Name": row["Cooling_schedule"]}},
                },
                include=THERMOSTAT_INCLUDE,
            )
            ThermostatComponent.model_validate(thermostat, from_attributes=True)

        for _, row in component_dfs_dict["Water_flow"].iterrows():
            water_use = tx.wateruse.create(
                data={
                    "Name": row["Name"],
                    "FlowRatePerPerson": row["DHW_flow_rate"],
                    "Schedule": {"connect": {"Name": row["Water_schedule"]}},
                },
                include=WATER_USE_INCLUDE,
            )
            WaterUseComponent.model_validate(water_use, from_attributes=True)

        # space use
        for _, row in component_dfs_dict["Space_use_assembly"].iterrows():
            space_use = tx.spaceuse.create(
                data={
                    "Name": row["Name"],
                    "Occupancy": {"connect": {"Name": row["Occupancy"]}},
                    "Lighting": {"connect": {"Name": row["Lighting"]}},
                    "Equipment": {"connect": {"Name": row["Equipment"]}},
                    "Thermostat": {"connect": {"Name": row["Setpoints"]}},
                    "WaterUse": {"connect": {"Name": row["WaterUse"]}},
                },
                include=SPACE_USE_INCLUDE,
            )
            ZoneSpaceUseComponent.model_validate(space_use, from_attributes=True)

        # # add cooling/heating systems
        # # TODO: think about what happens when a heating and cooling system have the same name
        for _, row in component_dfs_dict["Conditioning_constructor"].iterrows():
            thermal_system = tx.thermalsystem.create(
                data={
                    "Name": row["Name"],
                    "ConditioningType": row["Type"],
                    "Fuel": row["Fuel"],
                    "SystemCOP": row["COP_equipment"],
                    "DistributionCOP": row["Distribution_efficiency"],
                },
                include=THERMAL_SYSTEM_INCLUDE,
            )
            ThermalSystemComponent.model_validate(thermal_system, from_attributes=True)

        # add conditioning systems
        for _, row in component_dfs_dict["Systems_assembly"].iterrows():
            conditioning_system = tx.conditioningsystems.create(
                data={
                    "Name": row["Name"],
                    "Heating": {"connect": {"Name": row["Heating"]}},
                    "Cooling": {"connect": {"Name": row["Cooling"]}},
                },
                include=CONDITIONING_SYSTEMS_INCLUDE,
            )
            ConditioningSystemsComponent.model_validate(
                conditioning_system, from_attributes=True
            )

        # add ventilation
        for _, row in component_dfs_dict["Ventilation_constructor"].iterrows():
            ventilation = tx.ventilation.create(
                data={
                    "Name": row["Name"],
                    "Rate": row["Rate"],
                    "MinFreshAir": row["Min_fresh_air"],
                    "Type": row["Ventilation_type"],
                    "TechType": row["Tech_type"],
                    "Schedule": {"connect": {"Name": row["Window_schedule"]}},
                },
                include=VENTILATION_INCLUDE,
            )
            VentilationComponent.model_validate(ventilation, from_attributes=True)
        # add hvac
        for _, row in component_dfs_dict["Systems_assembly"].iterrows():
            hvac = tx.hvac.create(
                data={
                    "Name": row["Name"],
                    "ConditioningSystems": {"connect": {"Name": row["Name"]}},
                    "Ventilation": {"connect": {"Name": row["Ventilation"]}},
                },
                include=HVAC_INCLUDE,
            )
            ZoneHVACComponent.model_validate(hvac, from_attributes=True)

        # add dhw
        for _, row in component_dfs_dict["DHW_Constructor"].iterrows():
            dhw = tx.dhw.create(
                data={
                    "Name": row["Name"],
                    "SystemCOP": row["System_COP"],
                    "WaterTemperatureInlet": row["Water_temperature_inlet"],
                    "WaterSupplyTemperature": row["Water_supply_temperature"],
                    "FuelType": row["DHW_energy_source"],
                    "DistributionCOP": row["Distribution_efficiency"],
                    "IsOn": True,
                },
                include=DHW_INCLUDE,
            )
            DHWComponent.model_validate(dhw, from_attributes=True)

        # add materials
        for _, row in component_dfs_dict["Materials"].iterrows():
            mat = tx.constructionmaterial.create(
                data={
                    "Name": row["Name"],
                    "Roughness": row["Roughness"],
                    "ThermalAbsorptance": row["ThermalAbsorptance"],
                    "SolarAbsorptance": row["SolarAbsorptance"],
                    "TemperatureCoefficientThermalConductivity": row[
                        "TemperatureCoefficientThermalConductivity"
                    ],
                    "Type": row["Type"],
                    "Density": row["Density [kg/m3]"],
                    "Conductivity": row["Conductivity [W/m.K]"],
                    "SpecificHeat": row["SpecificHeat [J/kg.K]"],
                    "VisibleAbsorptance": row["VisibleAbsorptance"],
                }
            )
            ConstructionMaterialComponent.model_validate(mat, from_attributes=True)

        for _, row in component_dfs_dict["Window_choices"].iterrows():
            glazing = tx.glazingconstructionsimple.create(
                data={
                    "Name": row["Name"],
                    "UValue": row["UValue"],
                    "SHGF": row["SHGF"],
                    "TVis": row["TVis"],
                    "Type": row["Type"],
                },
            )
            GlazingConstructionSimpleComponent.model_validate(
                glazing, from_attributes=True
            )

        # add construction assemblies - connect to materials
        for _, row in component_dfs_dict["Construction_components"].iterrows():
            if "window" in row["Type"].lower():
                continue
            layers = []
            # Iterate over the columns to extract materials and thicknesses
            for i in range(1, len(row) // 2 + 1):
                material_key = f"Material_{i}"
                thickness_key = f"Thickness_{i}"

                has_material = material_key in row and pd.notna(row[material_key])
                has_thickness = thickness_key in row and pd.notna(row[thickness_key])
                if has_material and has_thickness:
                    layers.append({
                        "LayerOrder": i - 1,
                        "Thickness": row[thickness_key],
                        "ConstructionMaterial": {
                            "connect": {"Name": row[material_key]}
                        },
                    })
            # Create a ConstructionAssembly entry
            construction_assembly = tx.constructionassembly.create(
                data={
                    "Name": row["Name"],
                    "Type": row["Type"],
                    "Layers": {"create": layers},
                },
                include=CONSTRUCTION_ASSEMBLY_INCLUDE,
            )
            ConstructionAssemblyComponent.model_validate(
                construction_assembly, from_attributes=True
            )

        # add envelope assemblies - connect to construction assemblies
        # TODO: update with changes to excel
        for _, row in component_dfs_dict["Envelope_assembly"].iterrows():
            envelope_assembly = tx.envelopeassembly.create(
                data={
                    "Name": row["Name"],
                    "InternalMassExposedAreaPerArea": row["InternalMassFraction"],
                    "GroundIsAdiabatic": False,
                    "RoofIsAdiabatic": False,
                    "FacadeIsAdiabatic": False,
                    "SlabIsAdiabatic": False,
                    "PartitionIsAdiabatic": False,
                    "RoofAssembly": {"connect": {"Name": row["Roof"]}},
                    "FacadeAssembly": {"connect": {"Name": row["Facade"]}},
                    "SlabAssembly": {
                        "connect": {"Name": row["Slab"]}
                    },  # FLOOR CEILING SYSTEM!!!!
                    "PartitionAssembly": {"connect": {"Name": row["Partition"]}},
                    "ExternalFloorAssembly": {
                        "connect": {"Name": row["ExternalFloor"]}
                    },
                    "GroundSlabAssembly": {
                        "connect": {"Name": row["GroundFloor"]}
                    },  # FOUNDATION!!!!
                    "GroundWallAssembly": {
                        "connect": {"Name": row["GroundWall"]}  # Basement wall
                    },
                    "InternalMassAssembly": {"connect": {"Name": row["InternalMass"]}},
                },
                include=ENVELOPE_ASSEMBLY_INCLUDE,
            )
            EnvelopeAssemblyComponent.model_validate(
                envelope_assembly, from_attributes=True
            )

        # add envelope - connect to envelope assemblies, glazing constructions, infiltration
        for _, row in component_dfs_dict["Envelope_assembly"].iterrows():
            envelope = tx.envelope.create(
                data={
                    "Name": row["Name"],
                    "Assemblies": {"connect": {"Name": row["Name"]}},
                    "Infiltration": {
                        "create": {
                            "Name": row["Name"],
                            "IsOn": True,
                            "ConstantCoefficient": 0.0,
                            "TemperatureCoefficient": 0.0,
                            "WindVelocityCoefficient": 0.0,
                            "WindVelocitySquaredCoefficient": 0.0,
                            "AFNAirMassFlowCoefficientCrack": 0.0,
                            "AirChangesPerHour": row["Infiltration"]
                            if row["Infiltration_unit"] == "AirChanges/Hour"
                            else 0,
                            "FlowPerExteriorSurfaceArea": row["Infiltration"]
                            if row["Infiltration_unit"] == "Flow/ExteriorArea"
                            else 0,
                            "CalculationMethod": row["Infiltration_unit"],
                        }
                    },
                    "Window": {"connect": {"Name": row["Windows"]}},
                },
                include=ENVELOPE_INCLUDE,
            )
            ZoneEnvelopeComponent.model_validate(envelope, from_attributes=True)
