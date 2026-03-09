"""Ingest a ClimateStudio template JSON into the SBEM Prisma schema."""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

from prisma import Prisma
from prisma.types import EnvelopeAssemblyCreateInput, EnvelopeCreateInput

from epinterface.interface import PROTECTED_SCHEDULE_NAMES
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
from epinterface.sbem.ingestion.climatestudio.mapper import (
    convert_fresh_air_rate,
    map_glazing_type,
    map_roughness,
    map_year_schedule_category,
)
from epinterface.sbem.ingestion.climatestudio.parser import (
    get_library,
    get_settings,
    get_zones,
    load_climatestudio_template,
)
from epinterface.sbem.prisma.client import (
    CONDITIONING_SYSTEMS_INCLUDE,
    CONSTRUCTION_ASSEMBLY_INCLUDE,
    DHW_INCLUDE,
    ENVELOPE_ASSEMBLY_INCLUDE,
    ENVELOPE_INCLUDE,
    EQUIPMENT_INCLUDE,
    HVAC_INCLUDE,
    INFILTRATION_INCLUDE,
    LIGHTING_INCLUDE,
    OCCUPANCY_INCLUDE,
    OPERATIONS_INCLUDE,
    SPACE_USE_INCLUDE,
    THERMAL_SYSTEM_INCLUDE,
    THERMOSTAT_INCLUDE,
    VENTILATION_INCLUDE,
    WATER_USE_INCLUDE,
    WEEK_INCLUDE,
    YEAR_INCLUDE,
    delete_all,
)

logger = logging.getLogger(__name__)


def _schedule_db_name(name: str, category: str | None = None) -> str:
    """Map ClimateStudio schedule name to db name; for protected names, prefix and append category."""
    if name not in PROTECTED_SCHEDULE_NAMES:
        return name
    suffix = f"_{category}" if category else ""
    return f"CS_{name}{suffix}"


def _create_days_weeks_years(library: dict[str, Any], tx: Prisma) -> dict[str, str]:
    """Create Day, Week, and Year schedule records from the template library. Returns name->db_name mapping."""
    year_schedules = library.get("YearSchedules365") or []
    if not isinstance(year_schedules, list):
        msg = "YearSchedules365 must be a list"
        raise TypeError(msg)

    schedule_name_mapping: dict[str, str] = {}
    for sched in year_schedules:
        if not isinstance(sched, dict):
            continue
        name = str(sched.get("Name") or "")
        if not name:
            continue

        category = str(sched.get("Category") or "General")
        year_type = map_year_schedule_category(category, name)

        sched_type = str(sched.get("Type") or "AnyNumber")
        day_schedules = sched.get("DaySchedules") or []
        if not day_schedules:
            logger.warning("year schedule %s has no day schedules", name)
            continue

        first_day = day_schedules[0]
        values = first_day.get("Values") or [0.0] * 24
        if len(values) != 24:
            logger.warning(
                "year schedule %s first day has %s values, expected 24",
                name,
                len(values),
            )
            continue

        db_name = _schedule_db_name(name, category)
        schedule_name_mapping[name] = db_name
        print("Adding year schedule", db_name)
        day_name = f"{db_name}_Day"
        day = tx.day.create(
            data={
                "Name": day_name,
                "Type": sched_type,
                "Hour_00": float(values[0]),
                "Hour_01": float(values[1]),
                "Hour_02": float(values[2]),
                "Hour_03": float(values[3]),
                "Hour_04": float(values[4]),
                "Hour_05": float(values[5]),
                "Hour_06": float(values[6]),
                "Hour_07": float(values[7]),
                "Hour_08": float(values[8]),
                "Hour_09": float(values[9]),
                "Hour_10": float(values[10]),
                "Hour_11": float(values[11]),
                "Hour_12": float(values[12]),
                "Hour_13": float(values[13]),
                "Hour_14": float(values[14]),
                "Hour_15": float(values[15]),
                "Hour_16": float(values[16]),
                "Hour_17": float(values[17]),
                "Hour_18": float(values[18]),
                "Hour_19": float(values[19]),
                "Hour_20": float(values[20]),
                "Hour_21": float(values[21]),
                "Hour_22": float(values[22]),
                "Hour_23": float(values[23]),
            },
        )
        DayComponent.model_validate(day, from_attributes=True)

        week_name = f"{db_name}_Week"
        week = tx.week.create(
            data={
                "Name": week_name,
                "Monday": {"connect": {"Name": day_name}},
                "Tuesday": {"connect": {"Name": day_name}},
                "Wednesday": {"connect": {"Name": day_name}},
                "Thursday": {"connect": {"Name": day_name}},
                "Friday": {"connect": {"Name": day_name}},
                "Saturday": {"connect": {"Name": day_name}},
                "Sunday": {"connect": {"Name": day_name}},
            },
            include=WEEK_INCLUDE,
        )
        WeekComponent.model_validate(week, from_attributes=True)

        year = tx.year.create(
            data={
                "Name": db_name,
                "Type": year_type,
                "January": {"connect": {"Name": week_name}},
                "February": {"connect": {"Name": week_name}},
                "March": {"connect": {"Name": week_name}},
                "April": {"connect": {"Name": week_name}},
                "May": {"connect": {"Name": week_name}},
                "June": {"connect": {"Name": week_name}},
                "July": {"connect": {"Name": week_name}},
                "August": {"connect": {"Name": week_name}},
                "September": {"connect": {"Name": week_name}},
                "October": {"connect": {"Name": week_name}},
                "November": {"connect": {"Name": week_name}},
                "December": {"connect": {"Name": week_name}},
            },
            include=YEAR_INCLUDE,
        )
        YearComponent.model_validate(year, from_attributes=True)

    return schedule_name_mapping


def _create_materials(library: dict[str, Any], tx: Prisma) -> None:
    """Create ConstructionMaterial records from OpaqueMaterials."""
    mats = library.get("OpaqueMaterials") or []
    if not isinstance(mats, list):
        msg = "OpaqueMaterials must be a list"
        raise TypeError(msg)

    for mat in mats:
        if not isinstance(mat, dict):
            continue
        name = mat.get("Name")
        if not name:
            continue
        print("Adding material", name)
        created = tx.constructionmaterial.create(
            data={
                "Name": str(name),
                "Conductivity": float(mat.get("Conductivity", 0.0)),
                "Density": float(mat.get("Density", 0.0)),
                "Roughness": map_roughness(mat.get("Roughness")),
                "SpecificHeat": float(mat.get("SpecificHeat", 0.0)),
                "ThermalAbsorptance": float(mat.get("ThermalAbsorptance", 0.9)),
                "SolarAbsorptance": float(mat.get("SolarAbsorptance", 0.7)),
                "VisibleAbsorptance": float(mat.get("VisibleAbsorptance", 0.7)),
                "TemperatureCoefficientThermalConductivity": float(
                    mat.get("TemperatureCoefficientThermalConductivity", 0.0)
                ),
                "Type": str(mat.get("Type") or "Other"),
            },
        )
        ConstructionMaterialComponent.model_validate(created, from_attributes=True)


def _create_glazing_constructions(library: dict[str, Any], tx: Prisma) -> None:
    """Create GlazingConstructionSimple records from GlazingConstructionsSimple and GlazingConstructions."""
    created_names: set[str] = set()

    # GlazingConstructionsSimple has Type already as Single/Double/Triple
    simple_glazings = library.get("GlazingConstructionsSimple") or []
    if isinstance(simple_glazings, list):
        for glz in simple_glazings:
            if not isinstance(glz, dict):
                continue
            name = glz.get("Name")
            if not name:
                continue
            print("Adding glazing construction simple", name)
            glz_type = map_glazing_type(glz.get("Type"), layer_count=None)
            created = tx.glazingconstructionsimple.create(
                data={
                    "Name": str(name),
                    "SHGF": float(glz.get("SHGF", 0.0)),
                    "UValue": float(glz.get("UValue", 0.0)),
                    "TVis": float(glz.get("TVis", 0.0)),
                    "Type": glz_type,
                },
            )
            GlazingConstructionSimpleComponent.model_validate(
                created, from_attributes=True
            )
            created_names.add(str(name))

    # GlazingConstructions: infer Type from layer count when Other or invalid
    glazings = library.get("GlazingConstructions") or []
    if not isinstance(glazings, list):
        return

    for glz in glazings:
        if not isinstance(glz, dict):
            continue
        name = glz.get("Name")
        if not name or str(name) in created_names:
            continue
        print("Adding glazing construction", name)
        layers = glz.get("Layers") or []
        layer_count = len(layers) if isinstance(layers, list) else 1
        glz_type = map_glazing_type(glz.get("Type"), layer_count=layer_count)
        created = tx.glazingconstructionsimple.create(
            data={
                "Name": str(name),
                "SHGF": float(glz.get("SHGF", 0.0)),
                "UValue": float(glz.get("UValue", 0.0)),
                "TVis": float(glz.get("TVis", 0.0)),
                "Type": glz_type,
            },
        )
        GlazingConstructionSimpleComponent.model_validate(created, from_attributes=True)


def _create_construction_assemblies(library: dict[str, Any], tx: Prisma) -> None:
    """Create ConstructionAssembly and associated layers from OpaqueConstructions."""
    constructions = library.get("OpaqueConstructions") or []
    if not isinstance(constructions, list):
        return

    for cons in constructions:
        if not isinstance(cons, dict):
            continue
        name = cons.get("Name")
        if not name:
            continue
        print("Adding construction assembly", name)
        layers_data = []
        layers = cons.get("Layers") or []
        for idx, layer in enumerate(layers):
            if not isinstance(layer, dict):
                continue
            material = layer.get("Material") or {}
            mat_name = material.get("Name")
            thickness = layer.get("Thickness")
            if mat_name is None or thickness is None:
                continue
            # ensure material exists (in case not in OpaqueMaterials list)
            if not tx.constructionmaterial.find_unique(where={"Name": str(mat_name)}):
                created_mat = tx.constructionmaterial.create(
                    data={
                        "Name": str(mat_name),
                        "Conductivity": float(material.get("Conductivity", 0.0)),
                        "Density": float(material.get("Density", 0.0)),
                        "Roughness": map_roughness(material.get("Roughness")),
                        "SpecificHeat": float(material.get("SpecificHeat", 0.0)),
                        "ThermalAbsorptance": float(
                            material.get("ThermalAbsorptance", 0.9)
                        ),
                        "SolarAbsorptance": float(
                            material.get("SolarAbsorptance", 0.7)
                        ),
                        "VisibleAbsorptance": float(
                            material.get("VisibleAbsorptance", 0.7)
                        ),
                        "TemperatureCoefficientThermalConductivity": float(
                            material.get(
                                "TemperatureCoefficientThermalConductivity", 0.0
                            )
                        ),
                        "Type": str(material.get("Type") or "Other"),
                    },
                )
                ConstructionMaterialComponent.model_validate(
                    created_mat, from_attributes=True
                )

            layers_data.append({
                "LayerOrder": idx,
                "Thickness": float(thickness),
                "ConstructionMaterial": {"connect": {"Name": str(mat_name)}},
            })
        cons_type = str(cons.get("Type") or "Facade")
        # rename the construction types to match the sbem schema
        naming_mapping = {
            "Roof": "FlatRoof",
            "GroundFloor": "GroundSlab",
        }
        if cons_type in naming_mapping:
            cons_type = naming_mapping[cons_type]
        assembly = tx.constructionassembly.create(
            data={
                "Name": str(name),
                "Type": cons_type,
                "Layers": {"create": layers_data},
            },
            include=CONSTRUCTION_ASSEMBLY_INCLUDE,
        )
        ConstructionAssemblyComponent.model_validate(assembly, from_attributes=True)


def _create_envelope_assembly_and_infiltration(
    library: dict[str, Any],
    settings: dict[str, Any],
    tx: Prisma,
    template_name: str,
) -> tuple[str, str]:
    """Create EnvelopeAssembly and Infiltration using template_name, returning their names."""
    default_construction = settings.get("DefaultConstructionTemplate") or {}
    constructions = default_construction.get("Constructions") or {}

    roof = constructions.get("RoofConstruction")
    facade = constructions.get("FacadeConstruction")
    slab = constructions.get("SlabConstruction")
    partition = constructions.get("PartitionConstruction")
    external_floor = constructions.get("ExternalFloorConstruction")
    ground_slab = constructions.get("GroundSlabConstruction")
    ground_wall = constructions.get("GroundWallConstruction")
    internal_mass = constructions.get("InternalMassConstruction")
    internal_mass_fraction = float(
        constructions.get("InternalMassExposedAreaPerArea", 0.0)
    )

    env_assembly_name = template_name
    payload: dict[str, Any] = {
        "Name": env_assembly_name,
        "FlatRoofAssembly": {"connect": {"Name": str(roof)}}
        if roof
        else {"connect": {"Name": str(facade)}},
        "FacadeAssembly": {"connect": {"Name": str(facade)}} if facade else None,
        "FloorCeilingAssembly": {"connect": {"Name": str(slab)}} if slab else None,
        "PartitionAssembly": {"connect": {"Name": str(partition)}}
        if partition
        else None,
        "ExternalFloorAssembly": {"connect": {"Name": str(external_floor)}}
        if external_floor
        else None,
        "GroundSlabAssembly": {"connect": {"Name": str(ground_slab)}}
        if ground_slab
        else None,
        "GroundWallAssembly": {"connect": {"Name": str(ground_wall)}}
        if ground_wall
        else None,
        "AtticRoofAssembly": {"connect": {"Name": str(roof)}} if roof else None,
        "AtticFloorAssembly": {"connect": {"Name": str(slab)}} if slab else None,
        "BasementCeilingAssembly": {"connect": {"Name": str(ground_slab)}}
        if ground_slab
        else None,
    }

    if internal_mass and internal_mass_fraction > 0:
        payload["InternalMassAssembly"] = {"connect": {"Name": str(internal_mass)}}
        payload["InternalMassExposedAreaPerArea"] = internal_mass_fraction

    print("Adding envelope assembly", env_assembly_name)
    envelope_assembly = tx.envelopeassembly.create(
        data=cast(EnvelopeAssemblyCreateInput, payload),
        include=ENVELOPE_ASSEMBLY_INCLUDE,
    )
    EnvelopeAssemblyComponent.model_validate(envelope_assembly, from_attributes=True)

    infil = default_construction.get("Infiltration") or {}
    infil_name = f"{template_name}_Infiltration"
    print("Adding infiltration", infil_name)
    infiltration = tx.infiltration.create(
        data={
            "Name": infil_name,
            "IsOn": bool(infil.get("InfiltrationIsOn", True)),
            "ConstantCoefficient": float(
                infil.get("InfiltrationConstantCoefficient", 0.0)
            ),
            "TemperatureCoefficient": float(
                infil.get("InfiltrationTemperatureCoefficient", 0.0)
            ),
            "WindVelocityCoefficient": float(
                infil.get("InfiltrationWindVelocityCoefficient", 0.0)
            ),
            "WindVelocitySquaredCoefficient": float(
                infil.get("InfiltrationWindVelocitySquaredCoefficient", 0.0)
            ),
            "AFNAirMassFlowCoefficientCrack": float(
                infil.get("AFN_AirMassFlowCoefficient_Crack", 0.0)
            ),
            "AirChangesPerHour": float(infil.get("InfiltrationAch", 0.0))
            if infil.get("CalculationMethod") == "AirChanges/Hour"
            else 0.0,
            "FlowPerExteriorSurfaceArea": float(
                infil.get("InfiltrationFlowPerExteriorSurfaceArea", 0.0)
            )
            if infil.get("CalculationMethod") == "Flow/ExteriorArea"
            else 0.0,
            "CalculationMethod": str(
                infil.get("CalculationMethod") or "Flow/ExteriorArea"
            ),
        },
        include=INFILTRATION_INCLUDE,
    )
    InfiltrationComponent.model_validate(infiltration, from_attributes=True)

    return env_assembly_name, infil_name


def _resolve_schedule_name(name: str, mapping: dict[str, str]) -> str:
    """Resolve template schedule name to db name using mapping from created schedules."""
    return mapping.get(name, name)


def _create_space_use_components(
    settings: dict[str, Any],
    tx: Prisma,
    schedule_name_mapping: dict[str, str],
    template_name: str,
) -> tuple[str, str, str, str, str, str]:
    """Create Occupancy/Lighting/Equipment/Thermostat/WaterUse/SpaceUse using template_name."""
    space_template = settings.get("DefaultSpaceUseTemplate") or {}
    loads = space_template.get("Loads") or {}
    conditioning = space_template.get("Conditioning") or {}
    hot_water = space_template.get("HotWater") or {}

    occ_sched_name = _resolve_schedule_name(
        str(loads.get("OccupancySchedule") or "occ_custom"), schedule_name_mapping
    )
    lights_sched_name = _resolve_schedule_name(
        str(loads.get("LightsAvailibilitySchedule") or "lights_custom"),
        schedule_name_mapping,
    )
    equip_sched_name = _resolve_schedule_name(
        str(loads.get("EquipmentAvailibilitySchedule") or "equip_custom"),
        schedule_name_mapping,
    )

    heating_sched_name = _resolve_schedule_name(
        str(conditioning.get("HeatingSetpointSchedule") or "AllOn"),
        schedule_name_mapping,
    )
    cooling_sched_name = _resolve_schedule_name(
        str(conditioning.get("CoolingSetpointSchedule") or "AllOn"),
        schedule_name_mapping,
    )

    water_sched_name = _resolve_schedule_name(
        str(hot_water.get("WaterSchedule") or "AllOn"), schedule_name_mapping
    )

    print("Adding occupancy", template_name)
    occupancy = tx.occupancy.create(
        data={
            "Name": template_name,
            "PeopleDensity": float(loads.get("PeopleDensity", 0.0)),
            "IsOn": bool(loads.get("PeopleIsOn", True)),
            "MetabolicRate": float(loads.get("MetabolicRate", 1.2)),
            "Schedule": {"connect": {"Name": occ_sched_name}},
        },
        include=OCCUPANCY_INCLUDE,
    )
    OccupancyComponent.model_validate(occupancy, from_attributes=True)

    print("Adding lighting", template_name)
    lighting = tx.lighting.create(
        data={
            "Name": template_name,
            "PowerDensity": float(loads.get("LightingPowerDensity", 0.0)),
            "DimmingType": str(loads.get("DimmingType") or "Continuous"),
            "IsOn": bool(loads.get("LightsIsOn", True)),
            "Schedule": {"connect": {"Name": lights_sched_name}},
        },
        include=LIGHTING_INCLUDE,
    )
    LightingComponent.model_validate(lighting, from_attributes=True)

    print("Adding equipment", template_name)
    equipment = tx.equipment.create(
        data={
            "Name": template_name,
            "PowerDensity": float(loads.get("EquipmentPowerDensity", 0.0)),
            "IsOn": bool(loads.get("EquipmentIsOn", True)),
            "Schedule": {"connect": {"Name": equip_sched_name}},
        },
        include=EQUIPMENT_INCLUDE,
    )
    EquipmentComponent.model_validate(equipment, from_attributes=True)

    print("Adding thermostat", template_name)
    thermostat = tx.thermostat.create(
        data={
            "Name": template_name,
            "HeatingSetpoint": float(conditioning.get("HeatingSetpoint", 20.0)),
            "CoolingSetpoint": float(conditioning.get("CoolingSetpoint", 26.0)),
            "IsOn": True,
            "HeatingSchedule": {"connect": {"Name": heating_sched_name}},
            "CoolingSchedule": {"connect": {"Name": cooling_sched_name}},
        },
        include=THERMOSTAT_INCLUDE,
    )
    ThermostatComponent.model_validate(thermostat, from_attributes=True)

    print("Adding water use", template_name)
    water_use = tx.wateruse.create(
        data={
            "Name": template_name,
            "FlowRatePerPerson": float(hot_water.get("FlowRatePerPerson", 0.0)),
            "Schedule": {"connect": {"Name": water_sched_name}},
        },
        include=WATER_USE_INCLUDE,
    )
    WaterUseComponent.model_validate(water_use, from_attributes=True)

    print("Adding space use", template_name)
    space_use = tx.spaceuse.create(
        data={
            "Name": template_name,
            "Occupancy": {"connect": {"Name": occupancy.Name}},
            "Lighting": {"connect": {"Name": lighting.Name}},
            "Equipment": {"connect": {"Name": equipment.Name}},
            "Thermostat": {"connect": {"Name": thermostat.Name}},
            "WaterUse": {"connect": {"Name": water_use.Name}},
        },
        include=SPACE_USE_INCLUDE,
    )
    ZoneSpaceUseComponent.model_validate(space_use, from_attributes=True)

    return (
        occupancy.Name,
        lighting.Name,
        equipment.Name,
        thermostat.Name,
        water_use.Name,
        space_use.Name,
    )


def _create_hvac_and_dhw(
    template: dict[str, Any],
    settings: dict[str, Any],
    tx: Prisma,
    schedule_name_mapping: dict[str, str],
    template_name: str,
) -> tuple[str, str, str]:
    """Create ThermalSystem/ConditioningSystems/Ventilation/HVAC/DHW using template_name."""
    hvac_systems = template.get("HVACSystems") or []
    hvac_settings = hvac_systems[0].get("Settings") if hvac_systems else {}

    heating_cop = float(hvac_settings.get("HeatingCOP", 0.0))
    cooling_cop = float(hvac_settings.get("CoolingCOP", 0.0))
    heating_fuel = str(hvac_settings.get("HeatingFuelType") or "NaturalGas")
    cooling_fuel = str(hvac_settings.get("CoolingFuelType") or "Electricity")

    heating_name = f"{template_name}_Heating"
    cooling_name = f"{template_name}_Cooling"

    print("Adding thermal system", heating_name)
    heating_system = tx.thermalsystem.create(
        data={
            "Name": heating_name,
            "ConditioningType": "Heating",
            "Fuel": heating_fuel,
            "SystemCOP": heating_cop,
            "DistributionCOP": 1.0,
        },
        include=THERMAL_SYSTEM_INCLUDE,
    )
    ThermalSystemComponent.model_validate(heating_system, from_attributes=True)

    print("Adding thermal system", cooling_name)
    cooling_system = tx.thermalsystem.create(
        data={
            "Name": cooling_name,
            "ConditioningType": "Cooling",
            "Fuel": cooling_fuel,
            "SystemCOP": cooling_cop,
            "DistributionCOP": 1.0,
        },
        include=THERMAL_SYSTEM_INCLUDE,
    )
    ThermalSystemComponent.model_validate(cooling_system, from_attributes=True)

    conditioning = settings.get("DefaultSpaceUseTemplate", {}).get("Conditioning") or {}
    min_fresh_air_person = convert_fresh_air_rate(conditioning.get("MinFreshAirPerson"))
    min_fresh_air_area = convert_fresh_air_rate(conditioning.get("MinFreshAirArea"))

    vent_sched_name = _resolve_schedule_name(
        str(hvac_settings.get("MechVentAvailSchedule") or "AllOn"),
        schedule_name_mapping,
    )
    heat_recovery_type = str(hvac_settings.get("HeatRecoveryType") or "None")
    economizer_type = str(hvac_settings.get("EconomizerType") or "NoEconomizer")

    hrv = "NoHRV"
    if heat_recovery_type.lower() == "sensible":
        hrv = "Sensible"
    elif heat_recovery_type.lower() == "enthalpy":
        hrv = "Enthalpy"

    econ = "NoEconomizer"
    if economizer_type in {"DifferentialDryBulb", "DifferentialEnthalpy"}:
        econ = economizer_type

    print("Adding ventilation", template_name)
    vent = tx.ventilation.create(
        data={
            "Name": template_name,
            "FreshAirPerPerson": min_fresh_air_person,
            "FreshAirPerFloorArea": min_fresh_air_area,
            "Provider": "Mechanical",
            "HRV": hrv,
            "Economizer": econ,
            "DCV": "NoDCV",
            "Schedule": {"connect": {"Name": vent_sched_name}},
        },
        include=VENTILATION_INCLUDE,
    )
    VentilationComponent.model_validate(vent, from_attributes=True)

    print("Adding conditioning system", template_name)
    cond_systems = tx.conditioningsystems.create(
        data={
            "Name": template_name,
            "Heating": {"connect": {"Name": heating_system.Name}},
            "Cooling": {"connect": {"Name": cooling_system.Name}},
        },
        include=CONDITIONING_SYSTEMS_INCLUDE,
    )
    ConditioningSystemsComponent.model_validate(cond_systems, from_attributes=True)

    print("Adding hvac", template_name)
    hvac = tx.hvac.create(
        data={
            "Name": template_name,
            "ConditioningSystems": {"connect": {"Name": cond_systems.Name}},
            "Ventilation": {"connect": {"Name": vent.Name}},
        },
        include=HVAC_INCLUDE,
    )
    ZoneHVACComponent.model_validate(hvac, from_attributes=True)

    hot_water = settings.get("DefaultSpaceUseTemplate", {}).get("HotWater") or {}
    print("Adding dhw", template_name)
    dhw = tx.dhw.create(
        data={
            "Name": template_name,
            "SystemCOP": float(hot_water.get("DomHotWaterCOP", 1.0)),
            "WaterTemperatureInlet": float(
                hot_water.get("WaterTemperatureInlet", 10.0)
            ),
            "WaterSupplyTemperature": float(
                hot_water.get("WaterSupplyTemperature", 60.0)
            ),
            "FuelType": str(hot_water.get("HotWaterFuelType") or "NaturalGas"),
            "DistributionCOP": 1.0,
            "IsOn": bool(hot_water.get("IsOn", True)),
        },
        include=DHW_INCLUDE,
    )
    DHWComponent.model_validate(dhw, from_attributes=True)

    return hvac.Name, dhw.Name, cond_systems.Name


def _create_operations_and_envelopes(
    template: dict[str, Any],
    env_assembly_name: str,
    infil_name: str,
    space_use_name: str,
    hvac_name: str,
    dhw_name: str,
    tx: Prisma,
    template_name: str,
) -> None:
    """Create Operations, Envelope, and Zone records using template_name."""
    zones = get_zones(template)

    print("Adding operations", template_name)
    operations = tx.operations.create(
        data={
            "Name": template_name,
            "SpaceUse": {"connect": {"Name": space_use_name}},
            "HVAC": {"connect": {"Name": hvac_name}},
            "DHW": {"connect": {"Name": dhw_name}},
        },
        include=OPERATIONS_INCLUDE,
    )
    ZoneOperationsComponent.model_validate(operations, from_attributes=True)

    for z in zones:
        zone_id = str(z.get("Id") or z.get("_Guid") or z.get("Name") or "Zone")
        settings = z.get("Settings") or {}

        win_def = settings.get("WindowDefinition") or {}
        win_construction_name = win_def.get("Construction")

        envelope_name = (
            f"{template_name}_Envelope"
            if len(zones) == 1
            else f"{template_name}_{zone_id}_Envelope"
        )
        envelope_data: EnvelopeCreateInput = {
            "Name": envelope_name,
            "Assemblies": {"connect": {"Name": env_assembly_name}},
            "Infiltration": {"connect": {"Name": infil_name}},
            "AtticInfiltration": {"connect": {"Name": infil_name}},
            "BasementInfiltration": {"connect": {"Name": infil_name}},
        }
        if win_construction_name:
            envelope_data["Window"] = {"connect": {"Name": str(win_construction_name)}}
        envelope = tx.envelope.create(
            data=envelope_data,
            include=ENVELOPE_INCLUDE,
        )
        ZoneEnvelopeComponent.model_validate(envelope, from_attributes=True)

        zone = tx.zone.create(
            data={
                "Name": zone_id,
                "Envelope": {"connect": {"Name": envelope.Name}},
                "Operations": {"connect": {"Name": operations.Name}},
            },
        )
        print("Adding zone", zone.Name)


def add_climatestudio_to_db(
    path: Path,
    db: Prisma,
    erase_db: bool = False,
    template_name: str = "Default",
) -> None:
    """Add a ClimateStudio template JSON file to the database.

    Args:
        path: path to the ClimateStudio template JSON file.
        db: connected Prisma client.
        erase_db: erase existing data before ingestion.
        template_name: semantic name for this template archetype (e.g. 'Office', 'Residential_pre_1975').
            used as the Name for all semantic components (operations, space use, hvac, dhw, envelope, etc.).
    """
    if erase_db:
        delete_all(db)

    template = load_climatestudio_template(path)
    library = get_library(template)
    settings = get_settings(template)

    with db.tx(max_wait=timedelta(seconds=10), timeout=timedelta(minutes=5)) as tx:
        print("-" * 15, "Adding Day/Week/Year schedules", "-" * 15)
        schedule_name_mapping = _create_days_weeks_years(library, tx)

        print("-" * 15, "Adding Materials", "-" * 15)
        _create_materials(library, tx)

        print("-" * 15, "Adding Glazing Construction Simple", "-" * 15)
        _create_glazing_constructions(library, tx)

        print("-" * 15, "Adding Construction Assemblies", "-" * 15)
        _create_construction_assemblies(library, tx)

        print("-" * 15, "Adding Envelope Assembly and Infiltration", "-" * 15)
        env_name, infil_name = _create_envelope_assembly_and_infiltration(
            library, settings, tx, template_name
        )

        print("-" * 15, "Adding Space Use", "-" * 15)
        (
            _occ_name,
            _light_name,
            _equip_name,
            _therm_name,
            _water_name,
            space_use_name,
        ) = _create_space_use_components(
            settings, tx, schedule_name_mapping, template_name
        )

        print("-" * 15, "Adding HVAC and DHW", "-" * 15)
        hvac_name, dhw_name, _cond_sys_name = _create_hvac_and_dhw(
            template, settings, tx, schedule_name_mapping, template_name
        )

        print("-" * 15, "Adding Operations, Envelopes, and Zones", "-" * 15)
        _create_operations_and_envelopes(
            template,
            env_assembly_name=env_name,
            infil_name=infil_name,
            space_use_name=space_use_name,
            hvac_name=hvac_name,
            dhw_name=dhw_name,
            tx=tx,
            template_name=template_name,
        )

    print("Done adding components to db.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Ingest a ClimateStudio template JSON into the SBEM database."
    )
    parser.add_argument("template", type=Path, help="Path to template.json file")
    parser.add_argument(
        "--name",
        type=str,
        default="Default",
        help="Semantic name for the template archetype (e.g. 'Office', 'Residential_pre_1975').",
    )
    parser.add_argument(
        "--erase-db",
        action="store_true",
        help="Erase existing SBEM data before ingestion.",
    )
    args = parser.parse_args()

    db_client = Prisma()
    db_client.connect()
    try:
        add_climatestudio_to_db(
            args.template,
            db_client,
            erase_db=bool(args.erase_db),
            template_name=args.name,
        )
    finally:
        db_client.disconnect()
