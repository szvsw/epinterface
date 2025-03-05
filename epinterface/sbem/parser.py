"""A module for reading the input excel template into the correct class format from sbem library."""

from pathlib import Path
from typing import Any

import pandas as pd
from archetypal.schedule import ScheduleTypeLimits

from epinterface.sbem.interface import (
    ConstructionMaterial,
    GlazingConstructionSimple,
    SBEMConstruction,
    SBEMTemplateBuilderEquipment,
    SBEMTemplateBuilderHeatingCooling,
    SBEMTemplateBuilderLighting,
    SBEMTemplateBuilderOccupancy,
    SBEMTemplateBuilderThermostat,
    SBEMTemplateBuilderVentilation,
    SBEMTemplateLibraryHandler,
    Schedule,
    ScheduleTransferObject,
    ZoneConditioning,
    ZoneDHW,
    ZoneEnvelope,
    ZoneSpaceUse,
)


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


def create_library(base_path: Path) -> SBEMTemplateLibraryHandler:
    """Create the library from the excel file."""
    occupancy_data = load_excel_to_dict(base_path, "Occupancy")
    lighting_data = load_excel_to_dict(base_path, "Lighting")
    equipment_data = load_excel_to_dict(base_path, "Power")
    thermostat_data = load_excel_to_dict(base_path, "Setpoints")
    water_flow_data = load_excel_to_dict(base_path, "Water_flow")
    space_use_data = load_excel_to_dict(base_path, "Space_use_assembly")
    heating_cooling_data = load_excel_to_dict(base_path, "Conditioning_constructor")
    ventilation_data = load_excel_to_dict(base_path, "Ventilation_constructor")
    dhw_data = load_excel_to_dict(base_path, "DHW_Constructor")
    hvac_dhw_data = load_excel_to_dict(base_path, "HVAC_DHW_assembly")
    materials_data = load_excel_to_dict(base_path, "Materials_choices")
    construction_data = load_excel_to_dict(base_path, "Construction_components")
    envelope_data = load_excel_to_dict(base_path, "Envelope_assembly")

    # check the glazing ingestion mechanism
    glazing_construction = envelope_data[envelope_data["Envelope_type"] == "Windows"]

    space_uses = {
        name: ZoneSpaceUse(
            Name=name,
            Occupancy=SBEMTemplateBuilderOccupancy.model_validate(occupancy_data[name]),
            Lighting=SBEMTemplateBuilderLighting.model_validate(lighting_data[name]),
            Equipment=SBEMTemplateBuilderEquipment.model_validate(equipment_data[name]),
            Thermostat=SBEMTemplateBuilderThermostat.model_validate(
                thermostat_data[name]
            ),
        )
        for name in space_use_data
    }

    conditionings = {
        name: ZoneConditioning(
            Name=name,
            HeatingCooling=SBEMTemplateBuilderHeatingCooling.model_validate(
                heating_cooling_data[name]
            ),
            Ventilation=SBEMTemplateBuilderVentilation.model_validate(
                ventilation_data[name]
            ),
        )
        for name in hvac_dhw_data
    }

    # TODO: Discuss
    dhws = {name: ZoneDHW.model_validate(dhw_data[name]) for name in dhw_data}

    constructions = {
        name: SBEMConstruction.model_validate(construction_data[name])
        for name in construction_data
    }

    materials = {
        name: ConstructionMaterial.model_validate(materials_data[name])
        for name in materials_data
    }

    envelopes = {
        name: ZoneEnvelope.model_validate(envelope_data[name]) for name in envelope_data
    }

    glazing_constructions = {
        name: GlazingConstructionSimple.model_validate(glazing_construction[name])
        for name in glazing_construction
    }

    schedules = create_schedules(base_path)

    return SBEMTemplateLibraryHandler(
        SpaceUses=space_uses,
        Envelopes=envelopes,
        GlazingConstructions=glazing_constructions,
        Constructions=constructions,
        OpaqueMaterials=materials,
        Schedules=schedules,
        Conditionings=conditionings,
    )


if __name__ == "__main__":
    base_path = Path("data/Template_data.xlsx")
    library = create_library(base_path)
    print(library)
