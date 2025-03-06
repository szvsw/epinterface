"""A module for parsing SBEM template data and generating EnergyPlus objects."""

import logging

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
