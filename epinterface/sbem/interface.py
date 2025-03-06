"""A module for parsing SBEM template data and generating EnergyPlus objects."""

import logging
from typing import Any, cast

import numpy as np
from archetypal.schedule import Schedule as ArchetypalSchedule
from archetypal.schedule import ScheduleTypeLimits
from pydantic import BaseModel, Field, field_serializer, field_validator

from epinterface.sbem.common import MetadataMixin
from epinterface.sbem.components import (
    ConditioningSystemsComponent,
    ConstructionAssemblyComponent,
    ConstructionLayerComponent,
    ConstructionMaterialComponent,
    DHWComponent,
    EnvelopeAssemblyComponent,
    EquipmentComponent,
    GlazingConstructionSimpleComponent,
    InfiltrationComponent,
    LightingComponent,
    OccupancyComponent,
    ThermalSystemComponent,
    ThermostatComponent,
    VentilationComponent,
    WaterUseComponent,
    ZoneEnvelopeComponent,
    ZoneHVACComponent,
    ZoneSpaceUseComponent,
)
from epinterface.sbem.components.operations import ZoneOperationsComponent

logger = logging.getLogger(__name__)


# attribution classes
# schedules
class ScheduleTransferObject(BaseModel):
    """Schedule transfer object for help with de/serialization."""

    Name: str
    Type: dict
    Values: list[float]


# TODO: add schedule interface class


# TODO: Add validation when schedules are added to the objects - update this method once schedule methodoligies are confirmed
# from epinterface.sbem.exceptions import ScheduleException
# class SBEMScheduleValidator(NamedObject, extra="forbid"):
#     """Schedule validation based on presets."""

#     @model_validator
#     def schedule_checker(self, schedule_day, schedule_week, schedule_year):
#         """Validates that the schedules follow the required schema."""
#         if not schedule_day:
#             raise ScheduleException
#         if not schedule_week:
#             raise ScheduleException
#         if not schedule_year:
#             raise ScheduleException
#         return schedule_day, schedule_week, schedule_year

#     def schedule_cross_val(self, schedule_day, schedule_week, schedule_year):
#         """Confirm that a named schedule in the schedule year exists in the schedule week and schedule day."""
#         if schedule_year.Name not in schedule_week.ScheduleNames:
#             raise ScheduleException
#         if schedule_week.Name not in schedule_day.ScheduleNames:
#             raise ScheduleException
#         return schedule_day, schedule_week, schedule_year


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
    ConstructionMaterialLayer: dict[str, ConstructionLayerComponent]
    ConstructionMaterial: dict[str, ConstructionMaterialComponent]

    Schedule: dict[str, ArchetypalSchedule]

    @field_validator("Schedules", mode="before")
    @classmethod
    def validate_schedules(cls, value: dict[str, Any]):
        """Validate the schedules."""
        for key, val in value.items():
            if isinstance(val, dict):
                transfer = ScheduleTransferObject.model_validate(val)
                limit_type = ScheduleTypeLimits.from_dict(transfer.Type)
                value[key] = ArchetypalSchedule.from_values(
                    Name=transfer.Name,
                    Type=limit_type,  # pyright: ignore [reportArgumentType]
                    Values=transfer.Values,
                )
            elif isinstance(val, ScheduleTransferObject):
                limit_type = ScheduleTypeLimits.from_dict(val.Type)
                value[key] = ArchetypalSchedule.from_values(
                    Name=val.Name,
                    Type=limit_type,  # pyright: ignore [reportArgumentType]
                    Values=val.Values,
                )
            elif not isinstance(val, ArchetypalSchedule):
                raise TypeError(f"SCHEDULE_LOAD_ERROR:{type(val)}")
            else:
                continue
        return value

    @field_serializer("Schedules")
    def serialize_schedules(
        self, schedules: dict[str, ArchetypalSchedule]
    ) -> dict[str, "ScheduleTransferObject"]:
        """Serialize the schedules to a dataframe.

        Args:
            schedules (dict[str, Schedule]): The schedules to serialize.

        Returns:
            serialized_schedules (dict[str, list[float]])
        """
        out_result: dict[str, ScheduleTransferObject] = {}
        for name, sch in schedules.items():
            out_result[name] = ScheduleTransferObject(
                Name=sch.Name,
                Type=sch.Type.to_dict(),
                Values=list(cast(np.ndarray, sch.Values)),
            )

        return out_result
