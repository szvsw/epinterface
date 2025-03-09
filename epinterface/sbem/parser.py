"""A module for reading the input excel template into the correct class format from sbem library."""

from pathlib import Path
from typing import Any

import pandas as pd
from archetypal.schedule import Schedule

from epinterface.sbem.components.envelope import (
    ConstructionAssemblyComponent,
    ConstructionLayerComponent,
    EnvelopeAssemblyComponent,
    GlazingConstructionSimpleComponent,
    InfiltrationComponent,
    ZoneEnvelopeComponent,
)
from epinterface.sbem.components.materials import ConstructionMaterialComponent
from epinterface.sbem.components.operations import ZoneOperationsComponent
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
from epinterface.sbem.interface import ComponentLibrary


# helper functions
def load_excel_to_dict(base_path: Path, sheet_name: str) -> dict[str, Any]:
    """Load the excel file into a dictionary."""
    df = pd.read_excel(base_path, sheet_name=sheet_name, engine="openpyxl")
    df.columns = df.iloc[0]
    df = df[1:]
    data = df.to_dict(orient="records")
    return {d["Name"]: d for d in data}


def daily_schedule_handling(daily_schedule_df) -> dict[str, Schedule]:
    """Create the schedules from the excel file."""
    daily_schedules = {}
    for _index, row in daily_schedule_df.iterrows():
        name = row["Name"]
        hours = row[[f"Hour_{i}" for i in range(24)]].tolist()
        daily_schedules[name] = hours
    return daily_schedules


def weekly_schedule_handling(
    weekly_schedule_df, daily_schedule_df
) -> dict[str, Schedule]:
    """Create the schedules from the excel file."""
    weekly_schedules = {}
    for _index, row in weekly_schedule_df.iterrows():
        name = row["Name"]
        days = [
            daily_schedule_df[row[day]]
            for day in [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]
        ]
        weekly_schedules[name] = days
    return weekly_schedules


def yearly_schedule_handling(
    yearly_schedule_df, weekly_schedule_df
) -> dict[str, Schedule]:
    """Create the yearly schedules from the monthly and daily schedule objects."""
    yearly_schedules = {}
    for _index, row in yearly_schedule_df.iterrows():
        start_day = row["Start_Day"]
        week_schedule = weekly_schedule_df[row["Week_Schedule_Name"]]
        schedule = Schedule(Name=row["Name"], start_day=start_day, Values=week_schedule)
        yearly_schedules[schedule.Name] = schedule
    return yearly_schedules


def create_schedules(base_path: Path) -> dict[str, Schedule]:
    """Create the schedules from the excel file."""
    daily_schedules = daily_schedule_handling(
        pd.read_excel(base_path, sheet_name="Daily_Schedules")
    )
    weekly_schedules = weekly_schedule_handling(
        pd.read_excel(base_path, sheet_name="Weekly_Schedules"), daily_schedules
    )
    _yearly_schedules = yearly_schedule_handling(
        pd.read_excel(base_path, sheet_name="Yearly_Schedules"), weekly_schedules
    )
    raise NotImplementedError
    schedules_obj = {}
    # for schedules in yearly_schedules:
    #     schedules_obj[schedules.Name] = schedules
    return schedules_obj


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

    materials_data = load_excel_to_dict(base_path, "Materials_choices")
    construction_data = load_excel_to_dict(base_path, "Construction_components")
    envelope_assembly_data = load_excel_to_dict(base_path, "Envelope_components")
    envelope_data = load_excel_to_dict(base_path, "Envelope_assembly")
    window_data = construction_data[construction_data["Type"] == "Windows"]
    infiltration_data = construction_data[construction_data["Type"] == "Infiltation"]

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

    materials_objs = {
        name: ConstructionMaterialComponent.model_validate(data)
        for name, data in materials_data.items()
    }

    # TODO: Obj creation should reference to materials_objs
    construction_objs = {
        name: ConstructionAssemblyComponent.model_validate(data)
        for name, data in construction_data.items()
    }

    const_layers: dict[str, ConstructionLayerComponent] = {}
    for construction_obj in construction_objs.values():
        for layer in construction_obj.Layers:
            const_layers[layer.Name] = layer

    window_objs = {
        name: GlazingConstructionSimpleComponent.model_validate(data)
        for name, data in window_data.items()
    }
    infiltration_objs = {
        name: InfiltrationComponent.model_validate(data)
        for name, data in infiltration_data.items()
    }

    # TODO: Obj creation should reference to construction_objs
    envelope_assembly_objs = {
        name: EnvelopeAssemblyComponent.model_validate(data)
        for name, data in envelope_assembly_data.items()
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

    envelope_objs = {
        name: ZoneEnvelopeComponent(
            Name=name,
            Assemblies=envelope_assembly_objs[data["Assemblies"]],
            Infiltration=infiltration_objs[data["Infiltration"]],
            Window=window_objs[data["Windows"]],
        )
        for name, data in envelope_data.items()
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
        Envelope=envelope_objs,
        GlazingConstructionSimple=window_objs,
        Infiltration=infiltration_objs,
        EnvelopeAssembly=envelope_assembly_objs,
        ConstructionAssembly=construction_objs,
        ConstructionMaterialLayer=const_layers,
        ConstructionMaterial=materials_objs,
        Schedule={},
    )


if __name__ == "__main__":
    base_path = Path("data/Template_data.xlsx")
    library = create_library(base_path)
    print(library)
