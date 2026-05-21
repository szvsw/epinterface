"""This module contains the definitions for the schedule generators."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import numpy as np
from obgeneration.generator.dhw_generator import DHWGenerator
from obgeneration.generator.equipment_generator import EquipmentGenerator
from obgeneration.generator.hvac_generator import HVACGenerator
from obgeneration.generator.lighting_generator import LightingGenerator
from obgeneration.generator.occupancy_generator import (
    HouseholdOccupancyFractions,
    OccupancyGenerator,
)
from obgeneration.model import builders
from obgeneration.model.equipment import Equipment
from obgeneration.model.occupancy import MobilityCluster
from pydantic import BaseModel, ConfigDict, Field, model_validator

from epinterface.interface import ScheduleDayList, ScheduleYearFromDays
from epinterface.weather import WeatherUrl


class ScheduleOutput(ABC):
    """Base class for schedule outputs."""

    @abstractmethod
    def construct_idf_object(self) -> ScheduleYearFromDays:
        """Construct the IDF object for the schedule."""
        pass


class FractionalScheduleOutput(ScheduleOutput, BaseModel):
    """Base class for fractional schedule outputs."""

    name: str = Field(
        ...,
        description="The name of the schedule.",
    )
    peak_value: float = Field(
        ...,
        description="The peak value of the schedule, in the units of the peak_units field.",
        ge=0,
    )
    normalized_timeseries: Sequence[float] = Field(
        ..., description="The normalized timeseries of the schedule."
    )

    def construct_idf_object(self):
        """Construct the IDF object for the schedule."""
        ts_by_day = (
            np.array(self.normalized_timeseries)
            .reshape(-1, 96, 1)
            .repeat(15, axis=-1)
            .reshape(-1, 1440)
        )
        days = [
            ScheduleDayList(
                Name=f"{self.name}Day{i:03d}",
                Schedule_Type_Limits_Name="Fraction",
                Values=tuple(ts_by_day[i]),
                Minutes_per_Item=1,
            )
            for i in range(365)
        ]
        year = ScheduleYearFromDays(
            Name=f"{self.name}Year",
            Schedule_Type_Limits_Name="Fraction",
            day_schedules=days,
            start_day_of_week="Sunday",  # this should be the START DAY OF THE INPUT DAYS
        )
        return year


class TemperatureScheduleOutput(ScheduleOutput, BaseModel):
    """Base class for temperature schedule outputs."""

    timeseries: Sequence[float] = Field(
        ..., description="The timeseries of the temperature schedule."
    )

    def construct_idf_object(self):
        """Construct the IDF object for the schedule."""
        raise NotImplementedError("IDF object construction is not implemented")


class StochasticEquipmentScheduleOutput(FractionalScheduleOutput):
    """Output for the equipment schedule.

    Inherits from FractionalScheduleOutput, so it will contain a normalized timeseries and a peak value.
    """

    peak_units: Literal["W/m2"] = "W/m2"


class StochasticLightingScheduleOutput(FractionalScheduleOutput):
    """Output for the lighting schedule.

    Inherits from FractionalScheduleOutput, so it will contain a normalized timeseries and a peak value.
    """

    dimming_enabled: bool = Field(
        ...,
        description="Whether daylight dimming is enabled for the lighting schedule.",
    )
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

    occupancy: list[list[HouseholdOccupancyFractions]] | None = None
    num_occupants: int | None = None
    equipment: Equipment | None = None
    dishwasher_cycles: list[list[int]] | None = None
    laundry_cycles: list[list[int]] | None = None

    @property
    def safe_occupancy(self) -> list[list[HouseholdOccupancyFractions]]:
        """Get the occupancy states schedule, raising an error if it is not set."""
        if self.occupancy is None:
            msg = "Occupancy states schedule is not set"
            raise ValueError(msg)
        return self.occupancy

    @property
    def safe_num_occupants(self) -> int:
        """Get the number of occupants, raising an error if it is not set."""
        if self.num_occupants is None:
            msg = "Number of occupants is not set"
            raise ValueError(msg)
        return self.num_occupants

    @property
    def safe_equipment(self) -> Equipment:
        """Get the equipment, raising an error if it is not set."""
        if self.equipment is None:
            msg = "Equipment is not set"
            raise ValueError(msg)
        return self.equipment

    @property
    def safe_dishwasher_cycles(self) -> list[list[int]]:
        """Get the dishwasher cycles, raising an error if it is not set."""
        if self.dishwasher_cycles is None:
            msg = "Dishwasher cycles are not set"
            raise ValueError(msg)
        return self.dishwasher_cycles

    @property
    def safe_laundry_cycles(self) -> list[list[int]]:
        """Get the laundry cycles, raising an error if it is not set."""
        if self.laundry_cycles is None:
            msg = "Laundry cycles are not set"
            raise ValueError(msg)
        return self.laundry_cycles


class ScheduleResults(BaseModel):
    """Results of the schedule generation."""

    occupancy: StochasticOccupancyScheduleOutput | None = None
    heating_setpoint: StochasticHeatingSetpointScheduleOutput | None = None
    cooling_setpoint: StochasticCoolingSetpointScheduleOutput | None = None
    lighting: StochasticLightingScheduleOutput | None = None
    equipment: StochasticEquipmentScheduleOutput | None = None
    water_use: StochasticWaterUseScheduleOutput | None = None


class ScheduleGenerationConfig(BaseModel):
    """Shared configuration for all generated schedules."""

    model_config = ConfigDict(frozen=True)
    resolution_minutes: int = Field(
        ...,
        description="Minutes represented by each timestep for all generated schedules.",
        gt=0,
    )


def get_generator(generator: np.random.Generator | int) -> np.random.Generator:
    """Get a random generator from an integer or a generator."""
    if isinstance(generator, int):
        return np.random.default_rng(generator)
    return generator


class ScheduleGenerator(ABC, BaseModel):
    """Base class for all schedule generators."""

    @abstractmethod
    def generate_schedule(
        self,
        generator: np.random.Generator | int,
        context: ScheduleContext,
        config: ScheduleGenerationConfig,
    ) -> ScheduleOutputType:
        """Generate a schedule."""
        pass


OccupancyPatternName = Literal[
    "mostly_home",
    "long_day_away",
    "morning_away",
    "afternoon_away",
    "evening_night_away",
]


class StochasticOccupancyScheduleGenerator(ScheduleGenerator):
    """Generator for the occupancy schedule."""

    weekday_occupancy_patterns: Sequence[OccupancyPatternName] = Field(
        ...,
        description="Per-occupant weekday occupancy patterns.",
    )
    weekend_occupancy_patterns: Sequence[OccupancyPatternName] | None = Field(
        None,
        description="Per-occupant weekend occupancy patterns. If omitted, weekday patterns are reused.",
    )

    @model_validator(mode="after")
    def validate_patterns(self):
        """Validate weekday/weekend occupancy pattern presence and lengths."""
        if len(self.weekday_occupancy_patterns) == 0:
            msg = "At least one weekday pattern is required"
            raise ValueError(msg)

        if self.weekend_occupancy_patterns is not None and len(
            self.weekend_occupancy_patterns
        ) != len(self.weekday_occupancy_patterns):
            msg = (
                f"weekend_occupancy_patterns must have the same length as "
                f"weekday_occupancy_patterns, but got {len(self.weekend_occupancy_patterns)} and "
                f"{len(self.weekday_occupancy_patterns)}, respectively."
            )
            raise ValueError(msg)
        return self

    @property
    def num_occupants(self) -> int:
        """Return the number of occupants represented by the weekday patterns."""
        return len(self.weekday_occupancy_patterns)

    @classmethod
    def from_uniform_patterns(
        cls,
        weekday_pattern: OccupancyPatternName,
        num_occupants: int,
        weekend_pattern: OccupancyPatternName | None = None,
    ) -> "StochasticOccupancyScheduleGenerator":
        """Create a generator by repeating one pattern for each occupant."""
        if num_occupants <= 0:
            msg = f"num_occupants must be positive, but got {num_occupants}."
            raise ValueError(msg)
        return cls(
            weekday_occupancy_patterns=(weekday_pattern,) * num_occupants,
            weekend_occupancy_patterns=(
                None if weekend_pattern is None else (weekend_pattern,) * num_occupants
            ),
        )

    def generate_schedule(
        self,
        generator: np.random.Generator | int,
        context: ScheduleContext,
        config: ScheduleGenerationConfig,
    ) -> StochasticOccupancyScheduleOutput:
        """Generate an occupancy schedule."""
        generator = get_generator(generator)
        occupancy = builders.build_occupancy(
            mobility_clusters=[
                MobilityCluster(pattern) for pattern in self.weekday_occupancy_patterns
            ],
            weekend_clusters=[
                MobilityCluster(pattern) for pattern in self.weekend_occupancy_patterns
            ]
            if self.weekend_occupancy_patterns is not None
            else None,
        )
        occupancy_res = OccupancyGenerator.generate_with_defaults(
            occupancy,
            config.resolution_minutes,
            rng=generator,
        )
        context.occupancy = occupancy_res.occupancy_states
        context.num_occupants = self.num_occupants
        return StochasticOccupancyScheduleOutput(
            name="Occupancy",
            peak_value=occupancy_res.peak_value,
            normalized_timeseries=occupancy_res.schedule,
        )


class StochasticHeatingSetpointScheduleGenerator(ScheduleGenerator):
    """Generator for the heating setpoint schedule."""

    has_heating: bool = Field(..., description="Whether the building has heating.")
    heating_setpoint_active: float = Field(
        ..., ge=0, description="Heating setpoint while active."
    )
    heating_setpoint_sleep: float | None = Field(
        None, ge=0, description="Heating setpoint while asleep."
    )
    heating_setpoint_away: float | None = Field(
        None, ge=0, description="Heating setpoint while away."
    )

    def generate_schedule(
        self,
        generator: np.random.Generator | int,
        context: ScheduleContext,
        config: ScheduleGenerationConfig,
    ) -> StochasticHeatingSetpointScheduleOutput:
        """Generate a heating setpoint schedule."""
        generator = get_generator(generator)
        heating = builders.build_heating(
            self.has_heating,
            self.heating_setpoint_active,
            self.heating_setpoint_sleep,
            self.heating_setpoint_away,
        )
        heating_setpoint_res = HVACGenerator.generate_heating_with_defaults(
            heating, context.safe_occupancy
        )
        if heating_setpoint_res is None:
            msg = "Failed to generate heating setpoint schedule."
            raise RuntimeError(msg)
        return StochasticHeatingSetpointScheduleOutput(
            timeseries=heating_setpoint_res.schedule
        )


class StochasticCoolingSetpointScheduleGenerator(ScheduleGenerator):
    """Generator for the cooling setpoint schedule."""

    has_cooling: bool = Field(..., description="Whether the building has cooling.")
    cooling_setpoint_active: float = Field(
        ..., ge=0, description="Cooling setpoint while active."
    )
    cooling_setpoint_sleep: float | None = Field(
        None, ge=0, description="Cooling setpoint while asleep."
    )
    cooling_setpoint_away: float | None = Field(
        None, ge=0, description="Cooling setpoint while away."
    )

    def generate_schedule(
        self,
        generator: np.random.Generator | int,
        context: ScheduleContext,
        config: ScheduleGenerationConfig,
    ) -> StochasticCoolingSetpointScheduleOutput:
        """Generate a cooling setpoint schedule."""
        generator = get_generator(generator)
        cooling = builders.build_cooling(
            self.has_cooling,
            self.cooling_setpoint_active,
            self.cooling_setpoint_sleep,
            self.cooling_setpoint_away,
        )
        cooling_setpoint_res = HVACGenerator.generate_cooling_with_defaults(
            cooling, context.safe_occupancy
        )
        if cooling_setpoint_res is None:
            msg = "Failed to generate cooling setpoint schedule."
            raise RuntimeError(msg)
        return StochasticCoolingSetpointScheduleOutput(
            timeseries=cooling_setpoint_res.schedule
        )


class StochasticLightingScheduleGenerator(ScheduleGenerator):
    """Generator for the lighting schedule."""

    if_led: bool = Field(
        ...,
        description="Whether the building uses LED lighting. This affects the peak value of the schedule.",
    )
    when_away: bool | None = Field(
        None, description="Whether the lights are on when the building is unoccupied."
    )
    when_bright: bool | None = Field(
        None, description="Whether the lights are on when it is bright outside."
    )

    def generate_schedule(
        self,
        generator: np.random.Generator | int,
        context: ScheduleContext,
        config: ScheduleGenerationConfig,
    ) -> StochasticLightingScheduleOutput:
        """Generate a lighting schedule."""
        generator = get_generator(generator)
        lighting = builders.build_lighting(
            self.if_led,
            self.when_away,
            self.when_bright,
        )
        lighting_res = LightingGenerator.generate_with_defaults(
            lighting, context.safe_occupancy, generator
        )
        return StochasticLightingScheduleOutput(
            name="Lighting",
            dimming_enabled=lighting_res.dimming_enabled,
            peak_value=lighting_res.peak_value,
            normalized_timeseries=lighting_res.schedule,
        )


class StochasticEquipmentScheduleGenerator(ScheduleGenerator):
    """Generator for the dishwasher schedule."""

    has_washer: bool = Field(
        ..., description="Whether the building has a washing machine."
    )
    has_dryer: bool = Field(..., description="Whether the building has a dryer.")
    has_cooking_provider: bool = Field(
        ..., description="Whether the building has a cooking-related appliance."
    )
    has_dishwasher: bool = Field(
        ..., description="Whether the building has a dishwasher."
    )
    num_refrigerators: int = Field(
        ..., ge=0, description="The number of refrigerators in the building."
    )
    washer_efficient: bool | None = Field(
        None, description="Whether the washing machine is energy efficient."
    )
    dryer_efficient: bool | None = Field(
        None, description="Whether the dryer is energy efficient."
    )
    dishwasher_efficient: bool | None = Field(
        None, description="Whether the dishwasher is energy efficient."
    )
    refrigerator_efficient: bool | None = Field(
        None, description="Whether the refrigerators are energy efficient."
    )
    laundry_freq_per_week_min: int = Field(
        ..., ge=0, description="Minimum number of laundry cycles per week."
    )
    laundry_freq_per_week_max: int = Field(
        ..., ge=0, description="Maximum number of laundry cycles per week."
    )
    cooking_freq_per_week_min: int = Field(
        ...,
        ge=0,
        description="Minimum number of cooking-related appliance cycles per week.",
    )
    cooking_freq_per_week_max: int = Field(
        ...,
        ge=0,
        description="Maximum number of cooking-related appliance cycles per week.",
    )
    dishwasher_freq_per_week_min: int = Field(
        ..., ge=0, description="Minimum number of dishwasher cycles per week."
    )
    dishwasher_freq_per_week_max: int = Field(
        ..., ge=0, description="Maximum number of dishwasher cycles per week."
    )

    def generate_schedule(
        self,
        generator: np.random.Generator | int,
        context: ScheduleContext,
        config: ScheduleGenerationConfig,
    ) -> StochasticEquipmentScheduleOutput:
        """Generate a dishwasher schedule."""
        generator = get_generator(generator)

        eqp = builders.build_equipment(
            self.has_washer,
            self.has_dryer,
            self.has_cooking_provider,
            self.has_dishwasher,
            self.num_refrigerators,
            self.washer_efficient,
            self.dryer_efficient,
            self.dishwasher_efficient,
            self.refrigerator_efficient,
            (self.laundry_freq_per_week_min, self.laundry_freq_per_week_max),
            (self.cooking_freq_per_week_min, self.cooking_freq_per_week_max),
            (self.dishwasher_freq_per_week_min, self.dishwasher_freq_per_week_max),
        )
        eqp_res = EquipmentGenerator.generate_with_defaults(
            eqp,
            context.safe_occupancy,
            int(context.safe_num_occupants),
            resolution_mins=config.resolution_minutes,
            rng=generator,
        )
        context.equipment = eqp
        context.laundry_cycles = eqp_res.laundry_cycles
        context.dishwasher_cycles = eqp_res.dishwasher_cycles
        return StochasticEquipmentScheduleOutput(
            name="Equipment",
            peak_value=eqp_res.peak_value,
            normalized_timeseries=eqp_res.schedule,
        )


class StochasticWaterUseScheduleGenerator(ScheduleGenerator):
    """Generator for the domestic hot water schedule."""

    def generate_schedule(
        self,
        generator: np.random.Generator | int,
        context: ScheduleContext,
        config: ScheduleGenerationConfig,
    ) -> StochasticWaterUseScheduleOutput:
        """Generate a domestic hot water schedule."""
        generator = get_generator(generator)
        dhw_res = DHWGenerator.generate_with_defaults(
            int(context.safe_num_occupants),
            context.safe_equipment,
            context.safe_laundry_cycles,
            context.safe_dishwasher_cycles,
            config.resolution_minutes,
        )
        return StochasticWaterUseScheduleOutput(
            name="WaterUse",
            peak_value=dhw_res.peak_value,
            normalized_timeseries=dhw_res.schedule,
        )


class StochasticScheduleGenerator(BaseModel):
    """Generator for stochastic schedules."""

    config: ScheduleGenerationConfig
    equipment: StochasticEquipmentScheduleGenerator
    lighting: StochasticLightingScheduleGenerator
    occupancy: StochasticOccupancyScheduleGenerator
    water_use: StochasticWaterUseScheduleGenerator
    heating_setpoint: StochasticHeatingSetpointScheduleGenerator
    cooling_setpoint: StochasticCoolingSetpointScheduleGenerator

    def generate_schedules(
        self, generator: np.random.Generator | int
    ) -> ScheduleResults:
        """Generate all the schedules."""
        generator = get_generator(generator)
        context = ScheduleContext()
        results = ScheduleResults()
        results.occupancy = self.occupancy.generate_schedule(
            generator, context, self.config
        )
        results.heating_setpoint = self.heating_setpoint.generate_schedule(
            generator, context, self.config
        )
        results.cooling_setpoint = self.cooling_setpoint.generate_schedule(
            generator, context, self.config
        )
        results.lighting = self.lighting.generate_schedule(
            generator, context, self.config
        )
        results.equipment = self.equipment.generate_schedule(
            generator, context, self.config
        )
        results.water_use = self.water_use.generate_schedule(
            generator, context, self.config
        )
        return results


if __name__ == "__main__":
    generator = StochasticScheduleGenerator(
        config=ScheduleGenerationConfig(resolution_minutes=15),
        equipment=StochasticEquipmentScheduleGenerator(
            has_washer=True,
            has_dryer=True,
            has_cooking_provider=True,
            has_dishwasher=True,
            num_refrigerators=1,
            washer_efficient=True,
            dryer_efficient=True,
            dishwasher_efficient=True,
            refrigerator_efficient=True,
            laundry_freq_per_week_min=1,
            laundry_freq_per_week_max=2,
            cooking_freq_per_week_min=7,
            cooking_freq_per_week_max=14,
            dishwasher_freq_per_week_min=1,
            dishwasher_freq_per_week_max=2,
        ),
        lighting=StochasticLightingScheduleGenerator(
            if_led=True,
            when_away=False,
            when_bright=False,
        ),
        occupancy=StochasticOccupancyScheduleGenerator.from_uniform_patterns(
            weekday_pattern="mostly_home",
            weekend_pattern="mostly_home",
            num_occupants=2,
        ),
        water_use=StochasticWaterUseScheduleGenerator(),
        heating_setpoint=StochasticHeatingSetpointScheduleGenerator(
            has_heating=True,
            heating_setpoint_active=21,
            heating_setpoint_sleep=18,
            heating_setpoint_away=16,
        ),
        cooling_setpoint=StochasticCoolingSetpointScheduleGenerator(
            has_cooling=True,
            cooling_setpoint_active=24,
            cooling_setpoint_sleep=26,
            cooling_setpoint_away=28,
        ),
    )
    schedules = generator.generate_schedules(42)

    if schedules.lighting is None:
        msg = "Lighting schedule is not set"
        raise ValueError(msg)
    if schedules.equipment is None:
        msg = "Equipment schedule is not set"
        raise ValueError(msg)

    lighting_year = schedules.lighting.construct_idf_object()
    equipment_year = schedules.equipment.construct_idf_object()
    from epinterface.sbem.flat_model import FlatModel

    flat_model = FlatModel(
        F2FHeight=3.25,
        Width=40,
        Depth=40,
        Rotation=45,
        WWR=0.3,
        NFloors=2,
        FacadeRValue=3.0,
        RoofRValue=3.0,
        SlabRValue=3.0,
        WindowUValue=3.0,
        WindowSHGF=0.7,
        WindowTVis=0.5,
        InfiltrationACH=0.5,
        VentFlowRatePerArea=0.001,
        VentFlowRatePerPerson=0.0085,
        VentProvider="Mechanical",
        VentHRV="NoHRV",
        VentEconomizer="NoEconomizer",
        VentDCV="NoDCV",
        DHWFlowRatePerPerson=0.010,
        DHWFuel="Electricity",
        DHWSystemCOP=1.0,
        DHWDistributionCOP=1.0,
        EquipmentPowerDensity=25,
        LightingPowerDensity=10,
        OccupantDensity=0.001,
        EquipmentBase=0.4,
        EquipmentAMInterp=0.5,
        EquipmentLunchInterp=0.8,
        EquipmentPMInterp=0.5,
        EquipmentWeekendPeakInterp=0.25,
        EquipmentSummerPeakInterp=0.5,
        LightingBase=0.3,
        LightingAMInterp=0.75,
        LightingLunchInterp=0.75,
        LightingPMInterp=0.9,
        LightingWeekendPeakInterp=0.75,
        LightingSummerPeakInterp=0.9,
        OccupancyBase=0.05,
        OccupancyAMInterp=0.25,
        OccupancyLunchInterp=0.9,
        OccupancyPMInterp=0.5,
        OccupancyWeekendPeakInterp=0.15,
        OccupancySummerPeakInterp=0.85,
        # HSPRegularWeekdayWorkhours=21,
        # HSPRegularWeekdayNight=21,
        # HSPSummerWeekdayWorkhours=21,
        # HSPSummerWeekdayNight=21,
        # HSPWeekendWorkhours=21,
        # HSPWeekendNight=21,
        # CSPRegularWeekdayWorkhours=23,
        # CSPRegularWeekdayNight=23,
        # CSPSummerWeekdayWorkhours=23,
        # CSPSummerWeekdayNight=23,
        # CSPWeekendWorkhours=23,
        # CSPWeekendNight=23,
        HeatingSetpointBase=21,
        SetpointDeadband=2,
        HeatingSetpointSetback=2,
        CoolingSetpointSetback=2,
        NightSetback=0.5,
        WeekendSetback=0.5,
        SummerSetback=0.5,
        HeatingFuel="Electricity",
        CoolingFuel="Electricity",
        HeatingSystemCOP=1.0,
        CoolingSystemCOP=1.0,
        HeatingDistributionCOP=1.0,
        CoolingDistributionCOP=1.0,
        EPWURI=WeatherUrl(  # pyright: ignore [reportCallIssue]
            "https://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/USA_United_States_of_America/MA_Massachusetts/USA_MA_Bedford-Hanscom.Field.AP.744900_TMYx.2009-2023.zip"
        ),
    )

    outdir = Path("test-out-lighting")
    outdir.mkdir(parents=True, exist_ok=True)
    # r = flat_model.simulate(eplus_parent_dir=outdir)
    model, cb = flat_model.to_model()

    from archetypal.idfclass.idf import IDF

    def callback(idf: IDF) -> IDF:
        """Callback to add the schedules to the IDF."""
        idf = cb(idf)
        lighting_year.add(idf)
        equipment_year.add(idf)
        for lightsobj in idf.idfobjects["LIGHTS"]:
            lightsobj.Schedule_Name = lighting_year.Name
        for equipmentobj in idf.idfobjects["ELECTRICEQUIPMENT"]:
            equipmentobj.Schedule_Name = equipment_year.Name

        return idf

    r = model.run(eplus_parent_dir=outdir, post_geometry_callback=callback)
    print(r.energy_and_peak.groupby(level=["Measurement", "Aggregation"]).sum())

    # print(yaml.dump(schedules.model_dump(mode="json"), indent=2, sort_keys=False))
