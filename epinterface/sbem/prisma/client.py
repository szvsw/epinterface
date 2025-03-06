"""Prisma client for SBEM."""

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

db = Prisma(auto_register=True)


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
