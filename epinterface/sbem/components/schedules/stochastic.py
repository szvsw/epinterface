"""This module contains the definitions for the schedule generators."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field


# TESTING COMMIT
class ScheduleOutput(ABC):
    """Base class for schedule outputs."""

    @abstractmethod
    def construct_idf_object(self):
        """Construct the IDF object for the schedule."""
        pass


class FractionalScheduleOutput(ScheduleOutput, BaseModel):
    """Base class for fractional schedule outputs."""

    peak_value: float = Field(
        ...,
        description="The peak value of the schedule, in the units of the peak_units field.",
        ge=0,
    )
    normalized_timeseries: Sequence[float] = Field(
        ..., description="The normalized timeseries of the schedule."
    )


class TemperatureScheduleOutput(ScheduleOutput, BaseModel):
    """Base class for temperature schedule outputs."""

    timeseries: Sequence[float] = Field(
        ..., description="The timeseries of the temperature schedule."
    )


class StochasticEquipmentScheduleOutput(FractionalScheduleOutput):
    """Output for the equipment schedule.

    Inherits from FractionalScheduleOutput, so it will contain a normalized timeseries and a peak value.
    """

    dishwasher_cycles_per_week: int = Field(
        ..., ge=0, description="The number of dishwasher cycles per week."
    )
    laundry_cycles_per_week: int = Field(
        ..., ge=0, description="The number of laundry cycles per week."
    )
    peak_units: Literal["W/m2"] = "W/m2"


class StochasticLightingScheduleOutput(FractionalScheduleOutput):
    """Output for the lighting schedule.

    Inherits from FractionalScheduleOutput, so it will contain a normalized timeseries and a peak value.
    """

    peak_units: Literal["W/m2"] = "W/m2"


class StochasticOccupancyScheduleOutput(FractionalScheduleOutput):
    """Output for the occupancy schedule.

    Inherits from FractionalScheduleOutput, so it will contain a normalized timeseries and a peak value.
    """

    peak_units: Literal["people"] = "people"


class StochasticWaterUseScheduleOutput(FractionalScheduleOutput):
    """Output for the water use schedule.

    Inherits from FractionalScheduleOutput, so it will contain a normalized timeseries and a peak value.
    """

    peak_units: Literal["m3/s"] = "m3/s"


class StochasticHeatingSetpointScheduleOutput(TemperatureScheduleOutput):
    """Output for the heating setpoint schedule.

    Inherits from TemperatureScheduleOutput, so it will contain a timeseries of temperatures.
    """

    timeseries_units: Literal["°C"] = "°C"


class StochasticCoolingSetpointScheduleOutput(TemperatureScheduleOutput):
    """Output for the cooling setpoint schedule.

    Inherits from TemperatureScheduleOutput, so it will contain a timeseries of temperatures.
    """

    timeseries_units: Literal["°C"] = "°C"


ScheduleOutputType = (
    StochasticEquipmentScheduleOutput
    | StochasticLightingScheduleOutput
    | StochasticOccupancyScheduleOutput
    | StochasticWaterUseScheduleOutput
    | StochasticHeatingSetpointScheduleOutput
    | StochasticCoolingSetpointScheduleOutput
)


class ScheduleContext(BaseModel):
    """Context for the schedule generation."""

    equipment: StochasticEquipmentScheduleOutput | None = None
    lighting: StochasticLightingScheduleOutput | None = None
    occupancy: StochasticOccupancyScheduleOutput | None = None
    water_use: StochasticWaterUseScheduleOutput | None = None
    heating_setpoint: StochasticHeatingSetpointScheduleOutput | None = None
    cooling_setpoint: StochasticCoolingSetpointScheduleOutput | None = None

    @property
    def safe_occupancy(self) -> StochasticOccupancyScheduleOutput:
        """Get the occupancy schedule, raising an error if it is not set."""
        if self.occupancy is None:
            msg = "Occupancy schedule is not set"
            raise ValueError(msg)
        return self.occupancy

    @property
    def safe_equipment(self) -> StochasticEquipmentScheduleOutput:
        """Get the equipment schedule, raising an error if it is not set."""
        if self.equipment is None:
            msg = "Equipment schedule is not set"
            raise ValueError(msg)
        return self.equipment

    @property
    def safe_lighting(self) -> StochasticLightingScheduleOutput:
        """Get the lighting schedule, raising an error if it is not set."""
        if self.lighting is None:
            msg = "Lighting schedule is not set"
            raise ValueError(msg)
        return self.lighting

    @property
    def safe_water_use(self) -> StochasticWaterUseScheduleOutput:
        """Get the water use schedule, raising an error if it is not set."""
        if self.water_use is None:
            msg = "Water use schedule is not set"
            raise ValueError(msg)
        return self.water_use

    @property
    def safe_heating_setpoint(self) -> StochasticHeatingSetpointScheduleOutput:
        """Get the heating setpoint schedule, raising an error if it is not set."""
        if self.heating_setpoint is None:
            msg = "Heating setpoint schedule is not set"
            raise ValueError(msg)
        return self.heating_setpoint

    @property
    def safe_cooling_setpoint(self) -> StochasticCoolingSetpointScheduleOutput:
        """Get the cooling setpoint schedule, raising an error if it is not set."""
        if self.cooling_setpoint is None:
            msg = "Cooling setpoint schedule is not set"
            raise ValueError(msg)
        return self.cooling_setpoint


def get_generator(generator: np.random.Generator | int) -> np.random.Generator:
    """Get a random generator from an integer or a generator."""
    if isinstance(generator, int):
        return np.random.default_rng(generator)
    return generator


class ScheduleGenerator(ABC, BaseModel):
    """Base class for all schedule generators."""

    @abstractmethod
    def generate_schedule(
        self, generator: np.random.Generator | int, context: ScheduleContext
    ) -> ScheduleOutputType:
        """Generate a schedule."""
        pass


class StochasticEquipmentScheduleGenerator(ScheduleGenerator):
    """Generator for the dishwasher schedule."""

    # TODO: Other parameters for the equipment schedule generator go here...
    dishwasher_frequency_min: float
    dishwasher_frequency_max: float

    laundry_frequency_min: float
    laundry_frequency_max: float

    def generate_schedule(
        self, generator: np.random.Generator | int, context: ScheduleContext
    ) -> StochasticEquipmentScheduleOutput:
        """Generate a dishwasher schedule."""
        generator = get_generator(generator)

        raise NotImplementedError("DishwasherScheduleGenerator is not implemented")


class StochasticLightingScheduleGenerator(ScheduleGenerator):
    """Generator for the lighting schedule."""

    # TODO: Other parameters for the lighting schedule generator go here...
    working_hours_start: int = Field(
        ..., ge=0, le=24, description="The start of the working hours."
    )
    working_hours_end: int = Field(
        ..., ge=0, le=24, description="The end of the working hours."
    )

    def generate_schedule(
        self,
        generator: np.random.Generator | int,
        context: ScheduleContext,
    ) -> StochasticLightingScheduleOutput:
        """Generate a lighting schedule."""
        generator = get_generator(generator)
        raise NotImplementedError("LightingScheduleGenerator is not implemented")


class StochasticWaterUseScheduleGenerator(ScheduleGenerator):
    """Generator for the domestic hot water schedule."""

    # TODO: Other parameters for the domestic hot water schedule generator go here...

    def generate_schedule(
        self,
        generator: np.random.Generator | int,
        context: ScheduleContext,
    ) -> StochasticWaterUseScheduleOutput:
        """Generate a domestic hot water schedule."""
        generator = get_generator(generator)
        equipment = context.safe_equipment
        _laundry_cycles_per_week = equipment.laundry_cycles_per_week
        _dishwasher_cycles_per_week = equipment.dishwasher_cycles_per_week
        raise NotImplementedError(
            "DomesticHotWaterScheduleGenerator is not implemented"
        )


class StochasticOccupancyScheduleGenerator(ScheduleGenerator):
    """Generator for the occupancy schedule."""

    # TODO: Other parameters for the occupancy schedule generator go here...
    home_hours_start: int = Field(
        ..., ge=0, le=24, description="The start of the home hours."
    )
    home_hours_end: int = Field(
        ..., ge=0, le=24, description="The end of the home hours."
    )
    people_min: int = Field(..., ge=0, description="The minimum number of people.")
    people_max: int = Field(..., ge=0, description="The maximum number of people.")

    def generate_schedule(
        self,
        generator: np.random.Generator | int,
        context: ScheduleContext,
    ) -> StochasticOccupancyScheduleOutput:
        """Generate an occupancy schedule."""
        generator = get_generator(generator)
        raise NotImplementedError("OccupancyScheduleGenerator is not implemented")


class StochasticHeatingSetpointScheduleGenerator(ScheduleGenerator):
    """Generator for the heating setpoint schedule."""

    # TODO: Other parameters for the heating setpoint schedule generator go here...
    heating_setpoint_min: float = Field(
        ..., ge=0, description="The minimum heating setpoint."
    )
    heating_setpoint_max: float = Field(
        ..., ge=0, description="The maximum heating setpoint."
    )

    def generate_schedule(
        self,
        generator: np.random.Generator | int,
        context: ScheduleContext,
    ) -> StochasticHeatingSetpointScheduleOutput:
        """Generate a heating setpoint schedule."""
        generator = get_generator(generator)
        raise NotImplementedError("HeatingSetpointScheduleGenerator is not implemented")


class StochasticCoolingSetpointScheduleGenerator(ScheduleGenerator):
    """Generator for the cooling setpoint schedule."""

    # TODO: Other parameters for the cooling setpoint schedule generator go here...
    cooling_setpoint_min: float = Field(
        ..., ge=0, description="The minimum cooling setpoint."
    )
    cooling_setpoint_max: float = Field(
        ..., ge=0, description="The maximum cooling setpoint."
    )

    def generate_schedule(
        self,
        generator: np.random.Generator | int,
        context: ScheduleContext,
    ) -> StochasticCoolingSetpointScheduleOutput:
        """Generate a cooling setpoint schedule."""
        generator = get_generator(generator)
        raise NotImplementedError("CoolingSetpointScheduleGenerator is not implemented")


class StochasticScheduleGenerator(BaseModel):
    """Generator for stochastic schedules."""

    equipment: StochasticEquipmentScheduleGenerator
    lighting: StochasticLightingScheduleGenerator
    occupancy: StochasticOccupancyScheduleGenerator
    water_use: StochasticWaterUseScheduleGenerator
    heating_setpoint: StochasticHeatingSetpointScheduleGenerator
    cooling_setpoint: StochasticCoolingSetpointScheduleGenerator

    def generate_schedules(self, generator: np.random.Generator | int):
        """Generate all the schedules."""
        generator = get_generator(generator)
        context = ScheduleContext(
            equipment=None,
            lighting=None,
            occupancy=None,
            water_use=None,
            heating_setpoint=None,
            cooling_setpoint=None,
        )
        context.equipment = self.equipment.generate_schedule(generator, context)
        context.lighting = self.lighting.generate_schedule(generator, context)
        context.occupancy = self.occupancy.generate_schedule(generator, context)
        context.water_use = self.water_use.generate_schedule(generator, context)
        context.heating_setpoint = self.heating_setpoint.generate_schedule(
            generator, context
        )
        context.cooling_setpoint = self.cooling_setpoint.generate_schedule(
            generator, context
        )
        return context


if __name__ == "__main__":
    import yaml

    generator = StochasticScheduleGenerator(
        equipment=StochasticEquipmentScheduleGenerator(
            dishwasher_frequency_min=1,
            dishwasher_frequency_max=2,
            laundry_frequency_min=1,
            laundry_frequency_max=2,
        ),
        lighting=StochasticLightingScheduleGenerator(
            working_hours_start=1,
            working_hours_end=2,
        ),
        occupancy=StochasticOccupancyScheduleGenerator(
            home_hours_start=1,
            home_hours_end=2,
            people_min=1,
            people_max=2,
        ),
        water_use=StochasticWaterUseScheduleGenerator(),
        heating_setpoint=StochasticHeatingSetpointScheduleGenerator(
            heating_setpoint_min=1,
            heating_setpoint_max=2,
        ),
        cooling_setpoint=StochasticCoolingSetpointScheduleGenerator(
            cooling_setpoint_min=1,
            cooling_setpoint_max=2,
        ),
    )
    schedules = generator.generate_schedules(12345)
    print(yaml.dump(schedules.model_dump(mode="json"), indent=2, sort_keys=False))
