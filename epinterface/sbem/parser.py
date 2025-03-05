"""A module for reading the input excel template into the correct class format from sbem library."""

from pathlib import Path
from typing import Any

import pandas as pd
from archetypal.schedule import Schedule, ScheduleTypeLimits

from epinterface.sbem.components import (
    ConditioningSystemsComponent,
    DHWComponent,
    EquipmentComponent,
    LightingComponent,
    OccupancyComponent,
    ThermalSystemComponent,
    ThermostatComponent,
    VentilationComponent,
    WaterUseComponent,
    ZoneHVACComponent,
    ZoneOperationsComponent,
    ZoneSpaceUseComponent,
)
from epinterface.sbem.interface import ComponentLibrary, ScheduleTransferObject


def load_excel_to_dict(base_path: Path, sheet_name: str) -> dict[str, Any]:
    """Load the excel file into a dictionary."""
    df = pd.read_excel(base_path, sheet_name=sheet_name, engine="openpyxl")
    df.columns = df.iloc[0]
    df = df[1:]
    data = df.to_dict(orient="records")
    return {d["Name"]: d for d in data}


def create_schedules(base_path: Path) -> dict[str, Schedule]:
    """Create the schedules from the excel file."""
    # TODO: UPDATE SCHEDULES
    # day_schedules = load_excel_to_dict(base_path, "Day_schedules")
    # week_schedules = load_excel_to_dict(base_path, "Week_schedules")
    year_schedules = load_excel_to_dict(base_path, "Year_schedules")

    schedules = {}
    for name, data in year_schedules.items():
        transfer = ScheduleTransferObject.model_validate(data)
        limit_type = ScheduleTypeLimits.from_dict(transfer.Type)
        schedules[name] = Schedule.from_values(
            Name=transfer.Name,
            Type=limit_type,  # pyright: ignore [reportArgumentType]
            Values=transfer.Values,
        )
    return schedules


def create_library(base_path: Path) -> ComponentLibrary:
    """Create the library from the excel file."""
    occupancy_data = load_excel_to_dict(base_path, "Occupancy")
    lighting_data = load_excel_to_dict(base_path, "Lighting")
    equipment_data = load_excel_to_dict(base_path, "Power")
    thermostat_data = load_excel_to_dict(base_path, "Setpoints")
    water_use_data = load_excel_to_dict(base_path, "Water_flow")
    space_use_data = load_excel_to_dict(base_path, "Space_use_assembly")

    thermal_system_data = load_excel_to_dict(base_path, "Thermal_systems_constructor")
    conditioning_systems_data = load_excel_to_dict(
        base_path, "Conditioning_constructor"
    )
    ventilation_data = load_excel_to_dict(base_path, "Ventilation_constructor")
    dhw_data = load_excel_to_dict(base_path, "DHW_Constructor")
    hvac_data = load_excel_to_dict(base_path, "HVAC_assembly")
    operations_data = load_excel_to_dict(base_path, "HVAC_dhw_space_use")

    # Convert dicts to objs
    occupancy_objs = {
        name: OccupancyComponent.model_validate(data)
        for name, data in occupancy_data.items()
    }
    lighting_objs = {
        name: LightingComponent.model_validate(data)
        for name, data in lighting_data.items()
    }
    equipment_objs = {
        name: EquipmentComponent.model_validate(data)
        for name, data in equipment_data.items()
    }
    thermostat_objs = {
        name: ThermostatComponent.model_validate(data)
        for name, data in thermostat_data.items()
    }
    water_use_objs = {
        name: WaterUseComponent.model_validate(data)
        for name, data in water_use_data.items()
    }

    dhw_objs = {
        name: DHWComponent.model_validate(data) for name, data in dhw_data.items()
    }
    thermal_system_objs = {
        name: ThermalSystemComponent.model_validate(data)
        for name, data in thermal_system_data.items()
    }
    ventilation_objs = {
        name: VentilationComponent.model_validate(data)
        for name, data in ventilation_data.items()
    }

    space_use_objs = {
        name: ZoneSpaceUseComponent(
            Name=name,
            Occupancy=occupancy_objs[data["Occupancy"]],
            Lighting=lighting_objs[data["Lighting"]],
            Equipment=equipment_objs[data["Equipment"]],
            Thermostat=thermostat_objs[data["Thermostat"]],
            WaterUse=water_use_objs[data["WaterUse"]],
        )
        for name, data in space_use_data.items()
    }

    condition_systems_objs = {
        name: ConditioningSystemsComponent(
            Name=name,
            Heating=thermal_system_objs[data["Heating"]],
            Cooling=thermal_system_objs[data["Cooling"]],
        )
        for name, data in conditioning_systems_data.items()
    }

    hvac_objs = {
        name: ZoneHVACComponent(
            Name=name,
            ConditioningSystems=condition_systems_objs[data["ConditioningSystems"]],
            Ventilation=ventilation_objs[data["Ventilation"]],
        )
        for name, data in hvac_data.items()
    }

    operations_objs = {
        name: ZoneOperationsComponent(
            Name=name,
            SpaceUse=space_use_objs[data["SpaceUse"]],
            HVAC=hvac_objs[data["HVAC"]],
            DHW=dhw_objs[data["DHW"]],
        )
        for name, data in operations_data.items()
    }

    # materials_data = load_excel_to_dict(base_path, "Materials_choices")
    # construction_data = load_excel_to_dict(base_path, "Construction_components")
    # envelope_data = load_excel_to_dict(base_path, "Envelope_assembly")

    # # check the glazing ingestion mechanism
    # glazing_construction = envelope_data[envelope_data["Envelope_type"] == "Windows"]

    # # TODO: Discuss
    # # dhws = {name: DHWComponent.model_validate(dhw_data[name]) for name in dhw_data}

    # constructions = {
    #     name: ConstructionAssemblyComponent.model_validate(construction_data[name])
    #     for name in construction_data
    # }

    # materials = {
    #     name: ConstructionMaterialComponent.model_validate(materials_data[name])
    #     for name in materials_data
    # }

    # envelopes = {
    #     name: ZoneEnvelopeComponent.model_validate(envelope_data[name])
    #     for name in envelope_data
    # }

    # glazing_constructions = {
    #     name: GlazingConstructionSimpleComponent.model_validate(
    #         glazing_construction[name]
    #     )
    #     for name in glazing_construction
    # }

    # schedules = create_schedules(base_path)

    raise NotImplementedError
    return ComponentLibrary(
        Occupancy=occupancy_objs,
        Lighting=lighting_objs,
        Equipment=equipment_objs,
        Thermostat=thermostat_objs,
        WaterUse=water_use_objs,
        SpaceUse=space_use_objs,
        ConditioningSystems=condition_systems_objs,
        ThermalSystem=thermal_system_objs,
        Ventilation=ventilation_objs,
        DHW=dhw_objs,
        HVAC=hvac_objs,
        Operations=operations_objs,
        # Envelope=envelopes,
        # GlazingConstructionSimple=glazing_constructions,
        # ConstructionAssembly=constructions,
        # ConstructionMaterial=materials,
        # Schedule=schedules,
        # HVAC=hvac_objs,
    )


if __name__ == "__main__":
    base_path = Path("data/Template_data.xlsx")
    library = create_library(base_path)
    print(library)
