"""Prisma client for SBEM."""

from dataclasses import dataclass
from functools import cached_property
from typing import Generic, TypeVar

from pydantic import FilePath
from pydantic_settings import BaseSettings

from epinterface.sbem.common import NamedObject
from epinterface.sbem.components.envelope import (
    ConstructionAssemblyComponent,
    EnvelopeAssemblyComponent,
    GlazingConstructionSimpleComponent,
    InfiltrationComponent,
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

try:
    from prisma import Prisma
    from prisma.bases import (
        BaseConditioningSystems,
        BaseConstructionAssembly,
        BaseDHW,
        BaseEnvelope,
        BaseEnvelopeAssembly,
        BaseEquipment,
        BaseGlazingConstructionSimple,
        BaseHVAC,
        BaseInfiltration,
        BaseLighting,
        BaseOccupancy,
        BaseOperations,
        BaseSpaceUse,
        BaseThermalSystem,
        BaseThermostat,
        BaseVentilation,
        BaseWaterUse,
        BaseYear,
    )
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
    from prisma.partials import (
        ConstructionAssemblyWithLayers,
        EnvelopeAssemblyWithChildren,
        EnvelopeWithChildren,
        EquipmentWithSchedule,
        HVACWithConditioningSystemsAndVentilation,
        LightingWithSchedule,
        OccupancyWithSchedule,
        OperationsWithChildren,
        SpaceUseWithChildren,
        ThermostatWithSchedule,
        VentilationWithSchedule,
        WaterUseWithSchedule,
        YearWithWeeks,
    )
    from prisma.types import (
        ConditioningSystemsInclude,
        ConstructionAssemblyInclude,
        ConstructionAssemblyLayerInclude,
        DatasourceOverride,
        DHWInclude,
        EnvelopeAssemblyInclude,
        EnvelopeInclude,
        EquipmentInclude,
        GlazingConstructionSimpleInclude,
        HVACInclude,
        InfiltrationInclude,
        LightingInclude,
        OccupancyInclude,
        OperationsInclude,
        RepeatedWeekInclude,
        SpaceUseInclude,
        ThermalSystemInclude,
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
THERMAL_SYSTEM_INCLUDE: ThermalSystemInclude = {}
DHW_INCLUDE: DHWInclude = {}
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
INFILTRATION_INCLUDE: InfiltrationInclude = {}
GLAZING_CONSTRUCTION_SIMPLE_INCLUDE: GlazingConstructionSimpleInclude = {}

BaseT = TypeVar(
    "BaseT",
    bound=BaseYear
    | BaseOccupancy
    | BaseLighting
    | BaseEquipment
    | BaseWaterUse
    | BaseThermostat
    | BaseVentilation
    | BaseConditioningSystems
    | BaseSpaceUse
    | BaseOperations
    | BaseHVAC
    | BaseThermalSystem
    | BaseDHW
    | BaseConstructionAssembly
    | BaseEnvelopeAssembly
    | BaseEnvelope
    | BaseInfiltration
    | BaseGlazingConstructionSimple,
)
IncludeT = TypeVar(
    "IncludeT",
    YearInclude,
    OccupancyInclude,
    LightingInclude,
    EquipmentInclude,
    WaterUseInclude,
    ThermostatInclude,
    VentilationInclude,
    ConditioningSystemsInclude,
    SpaceUseInclude,
    OperationsInclude,
    HVACInclude,
    ThermalSystemInclude,
    DHWInclude,
    ConstructionAssemblyInclude,
    EnvelopeAssemblyInclude,
    EnvelopeInclude,
    InfiltrationInclude,
    GlazingConstructionSimpleInclude,
)
ValidatorT = TypeVar("ValidatorT", bound=NamedObject, contravariant=True)
YearT = TypeVar("YearT", bound=BaseYear)
OccupancyT = TypeVar("OccupancyT", bound=BaseOccupancy)
LightingT = TypeVar("LightingT", bound=BaseLighting)
EquipmentT = TypeVar("EquipmentT", bound=BaseEquipment)
WaterUseT = TypeVar("WaterUseT", bound=BaseWaterUse)
ThermostatT = TypeVar("ThermostatT", bound=BaseThermostat)
VentilationT = TypeVar("VentilationT", bound=BaseVentilation)
ConditioningSystemsT = TypeVar("ConditioningSystemsT", bound=BaseConditioningSystems)
SpaceUseT = TypeVar("SpaceUseT", bound=BaseSpaceUse)
OperationsT = TypeVar("OperationsT", bound=BaseOperations)
HVACT = TypeVar("HVACT", bound=BaseHVAC)
ThermalSystemT = TypeVar("ThermalSystemT", bound=BaseThermalSystem)
DHWT = TypeVar("DHWT", bound=BaseDHW)
ConstructionAssemblyT = TypeVar("ConstructionAssemblyT", bound=BaseConstructionAssembly)
EnvelopeAssemblyT = TypeVar("EnvelopeAssemblyT", bound=BaseEnvelopeAssembly)
EnvelopeT = TypeVar("EnvelopeT", bound=BaseEnvelope)
InfiltrationT = TypeVar("InfiltrationT", bound=BaseInfiltration)
GlazingConstructionSimpleT = TypeVar(
    "GlazingConstructionSimpleT", bound=BaseGlazingConstructionSimple
)


@dataclass
class Link(Generic[BaseT, IncludeT, ValidatorT]):
    """Link to a deep object."""

    prisma_model: type[BaseT]
    include: IncludeT
    validator: type[ValidatorT]

    async def get_deep_object(self, name: str) -> tuple[BaseT, ValidatorT]:
        """Get a deep object by name."""
        # It would be great if we could disable the type checker for this line,
        # but right now the BaseT / IncludeT are not constrained to only allow certain combinations.

        record = await self.prisma_model.prisma().find_first_or_raise(
            where={"Name": name},
            include=self.include,  # pyright: ignore [reportArgumentType]
        )
        return record, self.validator.model_validate(record, from_attributes=True)


@dataclass
class DeepObjectLinkers(
    Generic[
        YearT,
        OccupancyT,
        LightingT,
        EquipmentT,
        WaterUseT,
        ThermostatT,
        VentilationT,
        ConditioningSystemsT,
        SpaceUseT,
        OperationsT,
        HVACT,
        DHWT,
        ThermalSystemT,
        ConstructionAssemblyT,
        EnvelopeAssemblyT,
        EnvelopeT,
        InfiltrationT,
        GlazingConstructionSimpleT,
    ]
):
    """Deep object linkers."""

    Year: Link[YearT, YearInclude, YearComponent]
    Occupancy: Link[OccupancyT, OccupancyInclude, OccupancyComponent]
    Lighting: Link[LightingT, LightingInclude, LightingComponent]
    Equipment: Link[EquipmentT, EquipmentInclude, EquipmentComponent]
    WaterUse: Link[WaterUseT, WaterUseInclude, WaterUseComponent]
    Thermostat: Link[ThermostatT, ThermostatInclude, ThermostatComponent]
    Ventilation: Link[VentilationT, VentilationInclude, VentilationComponent]
    ConditioningSystems: Link[
        ConditioningSystemsT, ConditioningSystemsInclude, ConditioningSystemsComponent
    ]
    SpaceUse: Link[SpaceUseT, SpaceUseInclude, ZoneSpaceUseComponent]
    Operations: Link[OperationsT, OperationsInclude, ZoneOperationsComponent]
    HVAC: Link[HVACT, HVACInclude, ZoneHVACComponent]
    DHW: Link[DHWT, DHWInclude, DHWComponent]
    ThermalSystem: Link[ThermalSystemT, ThermalSystemInclude, ThermalSystemComponent]
    ConstructionAssembly: Link[
        ConstructionAssemblyT,
        ConstructionAssemblyInclude,
        ConstructionAssemblyComponent,
    ]
    EnvelopeAssembly: Link[
        EnvelopeAssemblyT, EnvelopeAssemblyInclude, EnvelopeAssemblyComponent
    ]
    Envelope: Link[EnvelopeT, EnvelopeInclude, ZoneEnvelopeComponent]
    Infiltration: Link[InfiltrationT, InfiltrationInclude, InfiltrationComponent]
    GlazingConstructionSimple: Link[
        GlazingConstructionSimpleT,
        GlazingConstructionSimpleInclude,
        GlazingConstructionSimpleComponent,
    ]


deep_fetcher = DeepObjectLinkers(
    Year=Link(
        prisma_model=YearWithWeeks,
        include=YEAR_INCLUDE,
        validator=YearComponent,
    ),
    Occupancy=Link(
        prisma_model=OccupancyWithSchedule,
        include=OCCUPANCY_INCLUDE,
        validator=OccupancyComponent,
    ),
    Lighting=Link(
        prisma_model=LightingWithSchedule,
        include=LIGHTING_INCLUDE,
        validator=LightingComponent,
    ),
    Equipment=Link(
        prisma_model=EquipmentWithSchedule,
        include=EQUIPMENT_INCLUDE,
        validator=EquipmentComponent,
    ),
    WaterUse=Link(
        prisma_model=WaterUseWithSchedule,
        include=WATER_USE_INCLUDE,
        validator=WaterUseComponent,
    ),
    Thermostat=Link(
        prisma_model=ThermostatWithSchedule,
        include=THERMOSTAT_INCLUDE,
        validator=ThermostatComponent,
    ),
    Ventilation=Link(
        prisma_model=VentilationWithSchedule,
        include=VENTILATION_INCLUDE,
        validator=VentilationComponent,
    ),
    ConditioningSystems=Link(
        prisma_model=ConditioningSystems,
        include=CONDITIONING_SYSTEMS_INCLUDE,
        validator=ConditioningSystemsComponent,
    ),
    SpaceUse=Link(
        prisma_model=SpaceUseWithChildren,
        include=SPACE_USE_INCLUDE,
        validator=ZoneSpaceUseComponent,
    ),
    Operations=Link(
        prisma_model=OperationsWithChildren,
        include=OPERATIONS_INCLUDE,
        validator=ZoneOperationsComponent,
    ),
    HVAC=Link(
        prisma_model=HVACWithConditioningSystemsAndVentilation,
        include=HVAC_INCLUDE,
        validator=ZoneHVACComponent,
    ),
    DHW=Link(
        prisma_model=DHW,
        include=DHW_INCLUDE,
        validator=DHWComponent,
    ),
    ThermalSystem=Link(
        prisma_model=ThermalSystem,
        include=THERMAL_SYSTEM_INCLUDE,
        validator=ThermalSystemComponent,
    ),
    ConstructionAssembly=Link(
        prisma_model=ConstructionAssemblyWithLayers,
        include=CONSTRUCTION_ASSEMBLY_INCLUDE,
        validator=ConstructionAssemblyComponent,
    ),
    EnvelopeAssembly=Link(
        prisma_model=EnvelopeAssemblyWithChildren,
        include=ENVELOPE_ASSEMBLY_INCLUDE,
        validator=EnvelopeAssemblyComponent,
    ),
    Envelope=Link(
        prisma_model=EnvelopeWithChildren,
        include=ENVELOPE_INCLUDE,
        validator=ZoneEnvelopeComponent,
    ),
    Infiltration=Link(
        prisma_model=Infiltration,
        include=INFILTRATION_INCLUDE,
        validator=InfiltrationComponent,
    ),
    GlazingConstructionSimple=Link(
        prisma_model=GlazingConstructionSimple,
        include=GLAZING_CONSTRUCTION_SIMPLE_INCLUDE,
        validator=GlazingConstructionSimpleComponent,
    ),
)


@dataclass
class PrismaClient:
    """Prisma client for SBEM."""

    db: Prisma


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
