"""Prisma client for SBEM."""

from functools import cached_property

try:
    from prisma import Prisma
    from prisma.models import (
        DHW,
        HVAC,
        ConditioningSystems,
        ConstructionAssembly,
        ConstructionAssemblyLayer,
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
        RepeatedWeek,
        SpaceUse,
        ThermalSystem,
        Thermostat,
        Ventilation,
        WaterUse,
        Week,
        Year,
    )
    from prisma.types import (
        ConditioningSystemsInclude,
        ConstructionAssemblyInclude,
        ConstructionAssemblyLayerInclude,
        DatasourceOverride,
        EnvelopeAssemblyInclude,
        EnvelopeInclude,
        EquipmentInclude,
        HVACInclude,
        LightingInclude,
        OccupancyInclude,
        OperationsInclude,
        RepeatedWeekInclude,
        SpaceUseInclude,
        ThermostatInclude,
        VentilationInclude,
        WaterUseInclude,
        WeekInclude,
        YearInclude,
    )
except (RuntimeError, ImportError) as e:
    msg = "Prisma client has not yet been generated. "
    msg += "Please run `epinterface generate` to generate the client, or if more customization is desired,"
    msg += "run `prisma generate --schema $(epinterface schemapath)` directly."
    raise ImportError(msg) from e
from pydantic import FilePath
from pydantic_settings import BaseSettings


class PrismaSettings(BaseSettings):
    """Settings for the Prisma client."""

    database_path: FilePath | None = None

    @cached_property
    def db(self) -> Prisma:
        """Get the Prisma client."""
        datasource: DatasourceOverride | None = (
            {"url": f"file:{self.database_path}"}
            if self.database_path is not None
            else None
        )
        return Prisma(auto_register=True, datasource=datasource)


prisma_settings = PrismaSettings()

WEEK_INCLUDE: WeekInclude = {
    "Monday": True,
    "Tuesday": True,
    "Wednesday": True,
    "Thursday": True,
    "Friday": True,
    "Saturday": True,
    "Sunday": True,
}
REPEATED_WEEK_INCLUDE: RepeatedWeekInclude = {
    "Week": {"include": WEEK_INCLUDE},
}
YEAR_INCLUDE: YearInclude = {
    "Weeks": {"include": REPEATED_WEEK_INCLUDE},
}
LIGHTING_INCLUDE: LightingInclude = {
    "Schedule": {"include": YEAR_INCLUDE},
}
EQUIPMENT_INCLUDE: EquipmentInclude = {
    "Schedule": {"include": YEAR_INCLUDE},
}
THERMOSTAT_INCLUDE: ThermostatInclude = {
    "HeatingSchedule": {"include": YEAR_INCLUDE},
    "CoolingSchedule": {"include": YEAR_INCLUDE},
}
WATER_USE_INCLUDE: WaterUseInclude = {
    "Schedule": {"include": YEAR_INCLUDE},
}
OCCUPANCY_INCLUDE: OccupancyInclude = {
    "Schedule": {"include": YEAR_INCLUDE},
}
SPACE_USE_INCLUDE: SpaceUseInclude = {
    "Lighting": {"include": LIGHTING_INCLUDE},
    "Equipment": {"include": EQUIPMENT_INCLUDE},
    "Thermostat": {"include": THERMOSTAT_INCLUDE},
    "WaterUse": {"include": WATER_USE_INCLUDE},
    "Occupancy": {"include": OCCUPANCY_INCLUDE},
}
CONDITIONING_SYSTEMS_INCLUDE: ConditioningSystemsInclude = {
    "Heating": True,
    "Cooling": True,
}
VENTILATION_INCLUDE: VentilationInclude = {
    "Schedule": {"include": YEAR_INCLUDE},
}
HVAC_INCLUDE: HVACInclude = {
    "ConditioningSystems": {"include": CONDITIONING_SYSTEMS_INCLUDE},
    "Ventilation": {"include": VENTILATION_INCLUDE},
}
OPERATIONS_INCLUDE: OperationsInclude = {
    "SpaceUse": {"include": SPACE_USE_INCLUDE},
    "HVAC": {"include": HVAC_INCLUDE},
    "DHW": True,
}


LAYER_INCLUDE: ConstructionAssemblyLayerInclude = {
    "ConstructionMaterial": True,
}
CONSTRUCTION_ASSEMBLY_INCLUDE: ConstructionAssemblyInclude = {
    "Layers": {"include": LAYER_INCLUDE},
}
ENVELOPE_ASSEMBLY_INCLUDE: EnvelopeAssemblyInclude = {
    "RoofAssembly": {"include": CONSTRUCTION_ASSEMBLY_INCLUDE},
    "FacadeAssembly": {"include": CONSTRUCTION_ASSEMBLY_INCLUDE},
    "SlabAssembly": {"include": CONSTRUCTION_ASSEMBLY_INCLUDE},
    "PartitionAssembly": {"include": CONSTRUCTION_ASSEMBLY_INCLUDE},
    "ExternalFloorAssembly": {"include": CONSTRUCTION_ASSEMBLY_INCLUDE},
    "GroundSlabAssembly": {"include": CONSTRUCTION_ASSEMBLY_INCLUDE},
    "GroundWallAssembly": {"include": CONSTRUCTION_ASSEMBLY_INCLUDE},
    "InternalMassAssembly": {"include": CONSTRUCTION_ASSEMBLY_INCLUDE},
}
ENVELOPE_INCLUDE: EnvelopeInclude = {
    "Assemblies": {"include": ENVELOPE_ASSEMBLY_INCLUDE},
    "Infiltration": True,
    "Window": True,
}


async def delete_all():
    """Delete all the objects in the database."""
    # delete everything in the db
    await Envelope.prisma().delete_many()
    await EnvelopeAssembly.prisma().delete_many()
    await ConstructionAssemblyLayer.prisma().delete_many()
    await ConstructionAssembly.prisma().delete_many()
    await ConstructionMaterial.prisma().delete_many()
    await Infiltration.prisma().delete_many()
    await GlazingConstructionSimple.prisma().delete_many()
    await Operations.prisma().delete_many()
    await HVAC.prisma().delete_many()
    await ConditioningSystems.prisma().delete_many()
    await SpaceUse.prisma().delete_many()
    await Occupancy.prisma().delete_many()
    await Lighting.prisma().delete_many()
    await Thermostat.prisma().delete_many()
    await Equipment.prisma().delete_many()
    await WaterUse.prisma().delete_many()
    await ThermalSystem.prisma().delete_many()
    await DHW.prisma().delete_many()
    await Ventilation.prisma().delete_many()
    await RepeatedWeek.prisma().delete_many()
    await Year.prisma().delete_many()
    await Week.prisma().delete_many()
    await Day.prisma().delete_many()
