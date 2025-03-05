"""A module for parsing SBEM template data and generating EnergyPlus objects."""

import logging
import re
from typing import Annotated, Any, Literal, TypeVar, cast

import numpy as np
from archetypal.idfclass import IDF
from archetypal.schedule import Schedule, ScheduleTypeLimits
from constants.assumed_constants import assumed_constants
from constants.physical_constants import physical_constants
from pydantic import (
    AliasChoices,
    BaseModel,
    BeforeValidator,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from epinterface.interface import (
    Construction,
    ElectricEquipment,
    InfDesignFlowRateCalculationMethodType,
    Lights,
    Material,
    People,
    SimpleGlazingMaterial,
    WaterUseEquipment,
    ZoneInfiltrationDesignFlowRate,
)

logger = logging.getLogger(__name__)


# exception classes
class SBEMTemplateBuilderException(Exception):
    """A base exception for the SBEM template library."""

    def __init__(self, message: str):
        """Initialize the exception with a message."""
        self.message = message
        super().__init__(self.message)


class DuplicatesFound(SBEMTemplateBuilderException):
    """An error raised when duplicates are found in a SBEM template library."""

    def __init__(self, duplicate_field: str):
        """Initialize the exception with a message.

        Args:
            duplicate_field (str): The field with duplicates
        """
        self.duplicate_field = duplicate_field
        self.message = f"Duplicate objects found in library: {duplicate_field}"
        super().__init__(self.message)


class ValueNotFound(SBEMTemplateBuilderException):
    """An error raised when a value is not found in a SBEM template library."""

    def __init__(self, obj_type: str, value: str):
        """Initialize the exception with a message.

        Args:
            obj_type (str): The type of object that was not found.
            value (str): The value that was not found.
        """
        self.obj_type = obj_type
        self.value = value
        self.message = f"Value not found in library: {obj_type}:{value}"
        super().__init__(self.message)


class NotImplementedParameter(SBEMTemplateBuilderException):
    """An error raised when a template parameter is not implemented."""

    def __init__(self, parameter_name: str, obj_name: str, obj_type: str):
        """Initialize the exception with a message.

        Args:
            parameter_name (str): The name of the parameter.
            obj_name (str): The name of the object.
            obj_type (str): The type of the object.
        """
        self.parameter_name = parameter_name
        self.obj_name = obj_name
        self.obj_type = obj_type
        self.message = f"Parameter {parameter_name} not implemented for {obj_type.upper()}:{obj_name}"
        super().__init__(self.message)


class ScheduleParseError(SBEMTemplateBuilderException):
    """An error raised when a schedule cannot be parsed."""

    def __init__(self, schedule_name: str):
        """Initialize the exception with a message.

        Args:
            schedule_name (str): The name of the schedule.
        """
        self.schedule_name = schedule_name
        super().__init__(f"Failed to parse schedule {schedule_name}")


# TODO: remove this function if climate_studio.builder remains - slightly rewritten from the original
def nan_to_none_or_str(v: Any) -> str | None | Any:
    """Converts NaN to None and leaves strings as is.

    Args:
        v (Any): Value to convert

    Returns:
        v (None | str | Any): Converted value
    """
    if isinstance(v, str):
        return v
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    return v


def str_to_bool(v: str | bool) -> bool:
    """Converts a string to a boolean if necessary.

    Args:
        v (str | bool): Value to convert

    Returns:
        bool: Converted value
    """
    if isinstance(v, bool):
        return v
    return v.lower() == "true"


def str_to_float_list(v: str | list) -> list[float]:
    """Converts a string to a list of floats.

    Args:
        v (str | list): String to convert

    Returns:
        list[float]: List of floats
    """
    if isinstance(v, list):
        return [float(x) for x in v]
    if v == "[]":
        return []
    if not re.match(r"^\[.*\]$", v):
        raise ValueError(f"STRING:NOT_LIST:{v}")
    v = v[1:-1]
    if not re.match(r"^[\-0-9\., ]*$", v):
        raise ValueError(f"STRING:NOT_LIST:{v}")
    return [float(x) for x in v.replace(" ", "").split(",")]


# construction helper function
def str_to_opaque_layer_list(v: str | list):
    """Converts a string to a list of opaque construction layers."""
    if isinstance(v, list):
        return v
    if v == "[]":
        return []
    list_content = v[1:-1].split(", ")
    names = list_content[::2]
    thicknesses = list(map(float, list_content[1::2]))
    return [
        ConstructionLayerComponent(Name=name, Thickness=thickness)
        for name, thickness in zip(names, thicknesses, strict=False)
    ]


# attribution classes
class NamedObject(BaseModel):
    """A Named object (with a name field)."""

    Name: str = Field(..., title="Name of the object used in referencing.")


NanStr = Annotated[str | None, BeforeValidator(nan_to_none_or_str)]
BoolStr = Annotated[bool, BeforeValidator(str_to_bool)]
FloatListStr = Annotated[list[float], BeforeValidator(str_to_float_list)]


# TODO: Make this at the library level not the row level?
class MetadataMixin(BaseModel):
    """Metadata for a SBEM template table object."""

    Category: NanStr = Field(..., title="Category of the object")
    Comment: NanStr = Field(..., title="Comment on the object")
    DataSource: NanStr = Field(..., title="Data source of the object")
    Version: NanStr | None = Field(default=None, title="Version of the object")


# TODO: Add this to the template format? Leaving here for flexibility for now
class EnvironmentalMixin(BaseModel):
    """Environmental data for a SBEM template table object."""

    Cost: float = Field(
        ...,
        title="Cost [$/unit]",
        # a superscript 3 looks like this:
        validation_alias=AliasChoices(
            "Cost [$/m³]",
            "Cost [$/m3]",
            "Cost [$/m²]",
            "Cost [$/m2]",
            "Cost [$/m]",
            "Cost [$/kg]",
            "Cost [$/mÂ²]",
            "Cost [$/mÃ]",
        ),
        ge=0,
    )
    Life: float = Field(
        ...,
        title="Life [years]",
        validation_alias="Life [yr]",
        ge=0,
    )
    EmbodiedCarbon: float = Field(
        ...,
        title="Embodied carbon [kgCO2e/unit]",
        # a superscript 3 looks like this:
        validation_alias=AliasChoices(
            "Embodied carbon [kgCO2e/m³]",
            "Embodied carbon [kgCO2e/m3]",
            "Embodied carbon [kgCO2e/m²]",
            "Embodied carbon [kgCO2e/m2]",
            "Embodied carbon [kgCO2e/m]",
            "Embodied carbon [kgCO2e/kg]",
        ),
        ge=0,
    )


class StandardMaterializedMetadata(EnvironmentalMixin, MetadataMixin):
    """Standard metadata for a SBEM data."""

    pass


# SPACE USE CLASSES
# schedules
class ScheduleTransferObject(BaseModel):
    """Schedule transfer object for help with de/serialization."""

    Name: str
    Type: dict
    Values: list[float]


# TODO: add schedule interface class


# occupancy
class OccupancyComponent(NamedObject, MetadataMixin):
    """An occupancy object in the SBEM library."""

    OccupancyDensity: float = Field(
        ...,
        title="Occupancy density of the object",
        ge=0,
        validation_alias="OccupancyDensity [m²/person]",
    )
    OccupancySchedule: str = Field(..., title="Occupancy schedule of the object")
    PeopleIsOn: BoolStr = Field(..., title="People are on")
    MetabolicRate = physical_constants["MetabolicRate"]

    @property
    def MetabolicRate_met_to_W(self):
        """Get the metabolic rate in Watts."""
        avg_human_weight_kg = physical_constants["avg_human_weight_kg"]
        conversion_factor = physical_constants["conversion_factor"]  # W/kg
        return self.MetabolicRate * avg_human_weight_kg * conversion_factor

    def add_people_to_idf_zone(
        self, idf: IDF, target_zone_or_zone_list_name: str
    ) -> IDF:
        """Add people to an IDF zone.

        Args:
            idf (IDF): The IDF object to add the people to.
            target_zone_or_zone_list_name (str): The name of the zone or zone list to add the people to.

        Returns:
            IDF: The updated IDF object.
        """
        if not self.PeopleIsOn:
            return idf

        activity_sch_name = (
            f"{target_zone_or_zone_list_name}_{self.Name}_Activity_Schedule"
        )
        lim = "AnyNumber"
        if not idf.getobject("SCHEDULETYPELIMITS", lim):
            lim = ScheduleTypeLimits(
                Name="AnyNumber",
                LowerLimit=None,
                UpperLimit=None,
            )
            lim.to_epbunch(idf)
        activity_sch = Schedule.from_values(
            Values=[self.MetabolicRate_met_to_W] * 8760,
            Name=activity_sch_name,
            Type=lim,  # pyright: ignore [reportArgumentType]
        )
        activity_sch_year, *_ = activity_sch.to_year_week_day()
        activity_sch_year.to_epbunch(idf)

        logger.warning(
            f"Adding people to zone with schedule {self.OccupancySchedule}.  Make sure this schedule exists."
        )
        logger.warning(
            f"Ignoring AirspeedSchedule for zone(s) {target_zone_or_zone_list_name}."
        )
        people = People(
            Name=f"{target_zone_or_zone_list_name}_{self.Name.join('_')}_People",
            Zone_or_ZoneList_Name=target_zone_or_zone_list_name,
            Number_of_People_Schedule_Name=self.OccupancySchedule,
            Number_of_People_Calculation_Method="People/Area",
            Number_of_People=None,
            Floor_Area_per_Person=None,
            People_per_Floor_Area=self.OccupancyDensity,
            Fraction_Radiant=assumed_constants["Fraction_Radiant"],
            Sensible_Heat_Fraction="autocalculate",
            Activity_Level_Schedule_Name=activity_sch_year.Name,
        )

        idf = people.add(idf)
        return idf


# lighting


class LightingComponent(NamedObject, MetadataMixin):
    """A lighting object in the SBEM library."""

    LightingPowerDensity: float = Field(
        ...,
        title="Lighting density of the object",
        ge=0,
        validation_alias="LightingDensity [W/m²]",
    )
    DimmingTypeType = Literal["Off", "Stepped", "Continuous"]

    DimmingType: DimmingTypeType = Field(
        ...,
        title="Dimming type",
    )
    LightingSchedule: str = Field(..., title="Lighting schedule of the object")
    LightsIsOn: BoolStr = Field(..., title="Lights are on")

    def add_lights_to_idf_zone(
        self, idf: IDF, target_zone_or_zone_list_name: str
    ) -> IDF:
        """Add lights to an IDF zone.

        Note that this makes some assumptions about the fraction visible/radiant/replaceable.

        Args:
            idf (IDF): The IDF object to add the lights to.
            target_zone_or_zone_list_name (str): The name of the zone or zone list to add the lights to.

        Returns:
            IDF: The updated IDF object.
        """
        if not self.LightsIsOn:
            return idf

        if self.DimmingType != "Off":
            raise NotImplementedParameter("DimmingType:On", self.Name, "Lights")

        logger.warning(
            f"Adding lights to zone with schedule {self.LightingSchedule}.  Make sure this schedule exists."
        )

        logger.warning(
            f"Ignoring IlluminanceTarget for zone(s) {target_zone_or_zone_list_name}."
        )
        lights = Lights(
            Name=f"{target_zone_or_zone_list_name}_{self.Name.join('_')}_Lights",
            Zone_or_ZoneList_Name=target_zone_or_zone_list_name,
            Schedule_Name=self.LightingSchedule,
            Design_Level_Calculation_Method="Watts/Area",
            Watts_per_Zone_Floor_Area=self.LightingPowerDensity,
            Watts_per_Person=None,
            Lighting_Level=None,
            Return_Air_Fraction=0,
            Fraction_Radiant=0.42,
            Fraction_Visible=0.18,
            Fraction_Replaceable=1,
            EndUse_Subcategory=None,
        )
        idf = lights.add(idf)
        return idf


# equipment


class EquipmentComponent(NamedObject, MetadataMixin):
    """An equipment object in the SBEM library."""

    EquipmentDensity: float = Field(..., title="Equipment density of the object")
    EquipmentSchedule: str = Field(..., title="Equipment schedule of the object")
    EquipmentIsOn: BoolStr = Field(..., title="Equipment is on")

    def add_equipment_to_idf_zone(
        self, idf: IDF, target_zone_or_zone_list_name: str
    ) -> IDF:
        """Add equipment to an IDF zone.

        Args:
            idf (IDF): The IDF object to add the equipment to.
            target_zone_or_zone_list_name (str): The name of the zone or zone list to add the equipment to.

        Returns:
            IDF: The updated IDF object.
        """
        if not self.EquipmentIsOn:
            return idf

        logger.warning(
            f"Adding equipment to zone with schedule {self.EquipmentSchedule}.  Make sure this schedule exists."
        )

        equipment = ElectricEquipment(
            Name=f"{target_zone_or_zone_list_name}_{self.Name.join('_')}_Equipment",
            Zone_or_ZoneList_Name=target_zone_or_zone_list_name,
            Schedule_Name=self.EquipmentSchedule,
            Design_Level_Calculation_Method="Watts/Area",
            Watts_per_Zone_Floor_Area=self.EquipmentDensity,
            Watts_per_Person=None,
            Fraction_Latent=assumed_constants["Fraction_Latent_Equipment"],
            Fraction_Radiant=assumed_constants["Fraction_Radiant_Equipment"],
            Fraction_Lost=assumed_constants["Fraction_Lost_Equipment"],
            EndUse_Subcategory=None,
        )
        idf = equipment.add(idf)
        return idf


# TODO: Potentially duplicative with HVACTempelateThermostat in epinterface > interface
class ThermostatComponent(NamedObject, MetadataMixin):
    """A thermostat object in the SBEM library."""

    ThermostatIsOn: BoolStr = Field(..., title="Thermostat is on")
    HeatingSetpoint: float = Field(
        ...,
        title="Heating setpoint of the object",
        validation_alias="HeatingSetpoint [°C]",
    )
    HeatingSchedule: str = Field(..., title="Heating schedule of the object")
    CoolingSetpoint: float = Field(
        ...,
        title="Cooling setpoint of the object",
        validation_alias="CoolingSetpoint [°C]",
    )
    CoolingSchedule: str = Field(..., title="Cooling schedule of the object")

    def add_thermostat_to_idf_zone(
        self, idf: IDF, target_zone_or_zone_list_name: str
    ) -> IDF:
        """Add thermostat settings to an IDF zone.

        Args:
            idf (IDF): The IDF object to add the thermostat settings to.
            target_zone_or_zone_list_name (str): The name of the zone or zone list to add the thermostat settings to.

        Returns:
            IDF: The updated IDF object.
        """
        if not self.ThermostatIsOn:
            return idf

        logger.warning(
            f"Adding thermostat to zone with heating schedule {self.HeatingSchedule} and cooling schedule {self.CoolingSchedule}.  Make sure these schedules exist."
        )

        idf = idf.newidfobject("HVACTEMPLATE:THERMOSTAT", **self.model_dump())
        return idf


class ScheduleException(SBEMTemplateBuilderException):
    """An error raised when a schedule cannot be parsed."""

    def __init__(self, schedule_name: str):
        """Initialize the exception with a message.

        Args:
            schedule_name (str): The day schedule

        """
        self.schedule_name = schedule_name
        self.message = f"Failed to parse schedule {schedule_name}"
        super().__init__(self.message)


# TODO: Add validation when schedules are added to the objects - update this method once schedule methodoligies are confirmed
def SBEMScheduleValidator(NamedObject, extra="forbid"):
    """Schedule validation based on presets."""

    @model_validator
    def schedule_checker(self, schedule_day, schedule_week, schedule_year):
        """Validates that the schedules follow the required schema."""
        if not schedule_day:
            raise ScheduleException
        if not schedule_week:
            raise ScheduleException
        if not schedule_year:
            raise ScheduleException
        return schedule_day, schedule_week, schedule_year

    def schedule_cross_val(self, schedule_day, schedule_week, schedule_year):
        """Confirm that a named schedule in the schedule year exists in the schedule week and schedule day."""
        if schedule_year.Name not in schedule_week.ScheduleNames:
            raise ScheduleException
        if schedule_week.Name not in schedule_day.ScheduleNames:
            raise ScheduleException
        return schedule_day, schedule_week, schedule_year


class ZoneSpaceUseComponent(NamedObject):
    """Space use object."""

    # TODO
    Occupancy: OccupancyComponent
    Lighting: LightingComponent
    Equipment: EquipmentComponent
    Thermostat: ThermostatComponent

    def add_loads_to_idf_zone(self, idf: IDF, target_zone_name: str) -> IDF:
        """Add the loads to an IDF zone.

        This will add the people, equipment, and lights to the zone.

        Args:
            idf (IDF): The IDF object to add the loads to.
            target_zone_name (str): The name of the zone to add the loads to.

        Returns:
            IDF: The updated IDF object.
        """
        idf = self.add_lights_to_idf_zone(idf, target_zone_name)
        idf = self.add_people_to_idf_zone(idf, target_zone_name)
        idf = self.add_equipment_to_idf_zone(idf, target_zone_name)
        idf = self.add_thermostat_to_idf_zone(idf, target_zone_name)
        idf = self.add_water_flow_to_idf_zone(idf, target_zone_name)
        return idf


# HVAC
FuelType = Literal[
    "Electricity",
    "NaturalGas",
    "Propane",
    "FuelOil",
    "WoodPellets",
    "Coal",
    "Gasoline",
    "Diesel",
    "CustomFuel",
]


# heating/cooling
class ConditioningSystemsComponent(NamedObject, MetadataMixin):
    """An HVAC object in the SBEM library."""

    HeatingSystemType = Literal[
        "ElectricResistance", "GasBoiler", "GasFurnace", "ASHP", "GSHP", "Custom"
    ]
    CoolingSystemType = Literal["DX", "EvapCooling", "Custom"]
    HeatingType: HeatingSystemType = Field(..., title="Heating system of the object")
    HeatingFuel: FuelType = Field(..., title="Fuel of the object")
    CoolingType: CoolingSystemType = Field(..., title="Cooling system of the object")
    CoolingFuel: FuelType = Field(..., title="Fuel of the object")
    HeatingSystemCOP: float = Field(
        ..., title="System COP of the object"
    )  # TODO: Add distribution + effective COPs (property that's computed)?

    # ADD THE DUCT METHODS


# ventilation
class VentilationComponent(NamedObject, MetadataMixin):
    """A ventilation object in the SBEM library."""

    VentilationRate: float = Field(..., title="Ventilation rate of the object")
    MinFreshAir: float = Field(
        ...,
        title="Minimum fresh air of the object",
        validation_alias="MinFreshAir [m³/s]",
    )
    VentilationSchedule: str = Field(..., title="Ventilation schedule of the object")
    VentilationType = Literal["Natural", "Mechanical", "Hybrid"]
    VentilationTechType = Literal["ERV", "HRV", "DCV", "None", "Custom"]
    Type: VentilationType = Field(..., title="Type of the object")
    TechType: VentilationTechType = Field(..., title="Technology type of the object")
    VentilationSchedule: str = Field(
        ..., title="Ventilation schedule of the object"
    )  # TODO: Discuss this, could use it for natural ventilation


class ZoneHVACComponent(
    NamedObject,
    MetadataMixin,
    extra="forbid",
):
    """Conditioning object in the SBEM library."""

    HeatingCooling: ConditioningSystemsComponent
    Ventilation: VentilationComponent
    # TODO: change the structure like ZoneSpaceUse
    """Zone conditioning object."""

    def add_conditioning_to_idf_zone(self, idf: IDF, target_zone_name: str) -> IDF:
        """Add conditioning to an IDF zone.

        This constructs HVAC template objects which get assigned to the zone.

        NB: currently, many of the climate studio parameters are ignored -
        particularly the ones related to humidity control.

        Args:
            idf (IDF): The IDF object to add the conditioning to.
            target_zone_name (str): The name of the zone to add the conditioning to.

        Returns:
            IDF: The updated IDF object.
        """
        # TODO: add the idf conversion functions

        return idf


# hot water
class DHWComponent(NamedObject, MetadataMixin, extra="ignore", populate_by_name=True):
    """Domestic Hot Water object."""

    DHWFuelType = Literal["Electricity", "NaturalGas", "Propane", "FuelOil"]

    DomHotWaterCOP: float = Field(
        ...,
        title="Domestic hot water coefficient of performance",
        ge=0,
    )
    WaterTemperatureInlet: float = Field(
        ...,
        title="Water temperature inlet [°C]",
        ge=0,
        le=100,
    )  # TODO:remove this or just set as constant. Leaving for flexibility here

    DistributionCOP: float = Field(
        ...,
        title="Distribution coefficient of performance",
        ge=0,
        le=1,
    )

    WaterSupplyTemperature: float = Field(
        ...,
        title="Water supply temperature [°C]",
        ge=0,
        le=100,
    )
    WaterSchedule: str = Field(
        ..., title="Water schedule"
    )  # TODO: Define a schedule preset to import (not from template)
    FlowRatePerPerson: float = Field(
        ..., title="Flow rate per person [m3/day/p]", ge=0, le=0.1
    )
    IsOn: BoolStr = Field(..., title="Is on")
    HotWaterFuelType: FuelType = Field(..., title="Hot water fuel type")

    @model_validator(mode="before")
    def validate_supply_greater_than_inlet(cls, values: dict[str, Any]):
        """Validate that the supply temperature is greater than the inlet temperature."""
        if values["WaterSupplyTemperature"] <= values["WaterTemperatureInlet"]:
            msg = "Water supply temperature must be greater than the inlet temperature."
            raise ValueError(msg)
        return values

    @property
    def schedule_names(self) -> set[str]:
        """Get the schedule names used in the object.

        Returns:
            set[str]: The schedule names.
        """
        return {self.WaterSchedule} if self.IsOn else set()

    def add_water_to_idf_zone(
        self, idf: IDF, target_zone_name: str, total_ppl: float
    ) -> IDF:
        """Add the hot water to an IDF zone.

        Args:
            idf (IDF): The IDF object to add the hot water to.
            target_zone_name (str): The name of the zone to add the hot water to.
            total_ppl (float): The total number of people in the zone.

        Returns:
            IDF: The updated IDF object.
        """
        if not self.IsOn:
            return idf

        total_flow_rate = self.FlowRatePerPerson * total_ppl  # m3/day
        total_flow_rate_per_s = total_flow_rate / (3600 * 24)  # m3/s
        # TODO: Update this rather than being constant rate

        lim = "Temperature"
        if not idf.getobject("SCHEDULETYPELIMITS", lim):
            lim = ScheduleTypeLimits(
                Name="Temperature",
                LowerLimit=-60,
                UpperLimit=200,
            )
            lim.to_epbunch(idf)

        target_temperature_schedule = Schedule.constant_schedule(
            value=self.WaterSupplyTemperature,  # pyright: ignore [reportArgumentType]
            Name=f"{target_zone_name}_{self.Name}_TargetWaterTemperatureSch",
            Type="Temperature",
        )
        inlet_temperature_schedule = Schedule.constant_schedule(
            value=self.WaterTemperatureInlet,  # pyright: ignore [reportArgumentType]
            Name=f"{target_zone_name}_{self.Name}_InletWaterTemperatureSch",
            Type="Temperature",
        )

        target_temperature_yr_schedule, *_ = (
            target_temperature_schedule.to_year_week_day()
        )
        inlet_temperature_yr_schedule, *_ = (
            inlet_temperature_schedule.to_year_week_day()
        )

        target_temperature_yr_schedule.to_epbunch(idf)
        inlet_temperature_yr_schedule.to_epbunch(idf)

        hot_water = WaterUseEquipment(
            Name=f"{target_zone_name}_{self.Name}_HotWater",
            EndUse_Subcategory="Domestic Hot Water",
            Peak_Flow_Rate=total_flow_rate_per_s,  # TODO: Update this to actual peak rate?
            Flow_Rate_Fraction_Schedule_Name=self.WaterSchedule,
            Zone_Name=target_zone_name,
            Target_Temperature_Schedule_Name=target_temperature_yr_schedule.Name,
            Hot_Water_Supply_Temperature_Schedule_Name=target_temperature_schedule.Name,
            Cold_Water_Supply_Temperature_Schedule_Name=inlet_temperature_schedule.Name,
            Sensible_Fraction_Schedule_Name=None,
            Latent_Fraction_Schedule_Name=None,
        )
        idf = hot_water.add(idf)
        return idf


class ZoneOperationsComponent(
    NamedObject, MetadataMixin, extra="forbid", populate_by_name=True
):
    """Zone use consolidation across space use, HVAC, DHW."""

    SpaceUse: ZoneSpaceUseComponent
    HVAC: ZoneHVACComponent
    DHW: DHWComponent

    def add_space_use_to_idf_zone(self, idf: IDF, target_zone_name: str) -> IDF:
        """Add the loads to an IDF zone.

        This will add the people, equipment, and lights to the zone.

        nb: remember to add the schedules.

        Args:
            idf (IDF): The IDF object to add the loads to.
            target_zone_name (str): The name of the zone to add the loads to.

        Returns:
            IDF: The updated IDF object.
        """
        idf = self.SpaceUse.add_loads_to_idf_zone(idf, target_zone_name)
        return idf

    def add_conditioning_to_idf_zone(self, idf: IDF, target_zone_name: str) -> IDF:
        """Add the conditioning to an IDF zone.

        Args:
            idf (IDF): The IDF object to add the conditioning to.
            target_zone_name (str): The name of the zone to add the conditioning to.

        Returns:
            IDF: The updated IDF object.
        """
        idf = self.HVAC.add_conditioning_to_idf_zone(idf, target_zone_name)
        return idf

    def add_hot_water_to_idf_zone(
        self, idf: IDF, target_zone_name: str, zone_area: float
    ) -> IDF:
        """Add the hot water to an IDF zone.

        Args:
            idf (IDF): The IDF object to add the hot water to.
            target_zone_name (str): The name of the zone to add the hot water to.
            zone_area (float): The area of the zone.

        Returns:
            idf (IDF): The updated IDF object.

        """
        total_people = self.SpaceUse.OccupancyDensity * zone_area
        idf = self.DHW.add_water_to_idf_zone(
            idf, target_zone_name, total_ppl=total_people
        )
        return idf


# CONSTRUCTION CLASSES
ConstructionComponents = Literal[
    "Roof",
    "Facade",
    "Slab",
    "Partition",
    "ExternalFloor",
    "ExteriorFloor",
    "GroundSlab",
    "GroundWall",
    "GroundFloor",
    "InternalMass",
    "InteriorFloor",
]


# TODO: remove? feels redundant
class CommonMaterialPropertiesMixin(BaseModel):
    """Common material properties for glazing and opaque materials."""

    Conductivity: float = Field(
        ...,
        title="Conductivity [W/mK]",
        validation_alias="Conductivity [W/m.K]",
        ge=0,
    )
    Density: float = Field(
        ...,
        title="Density [kg/m3]",
        ge=0,
        validation_alias=AliasChoices(
            "Density [kg/m³]",
            "Density [kg/m3]",
        ),
    )


# TODO: why is this a class? shouldn't thickness just be an attribute in the material consutruction class?
class MaterialWithThickness(BaseModel, populate_by_name=True):
    """Material with a thickness."""

    Thickness: float = Field(
        ...,
        title="Thickness of the material [m]",
        validation_alias="Thickness [m]",
        ge=0,
    )


# Opaque materials
class ConstructionMaterialProperties(
    CommonMaterialPropertiesMixin, populate_by_name=True
):
    """Properties of an opaque material."""

    # add in the commonMaterialsPropertis
    Roughness: str = Field(..., title="Roughness of the opaque material")
    SpecificHeat: float = Field(
        ...,
        title="Specific heat [J/kgK]",
        validation_alias="SpecificHeat [J/kg.K]",
        ge=0,
    )
    ThermalAbsorptance: float = Field(
        ...,
        title="Thermal absorptance",
        ge=0,
        le=1,
        validation_alias="ThermalAbsorptance [0-1]",
    )
    SolarAbsorptance: float = Field(
        ...,
        title="Solar absorptance",
        ge=0,
        le=1,
        validation_alias="SolarAbsorptance [0-1]",
    )

    TemperatureCoefficientThermalConductivity: float = Field(
        ...,
        # a superscript 2 looks like this:
        title="Temperature coefficient of thermal conductivity [W/m.K2²]",
        ge=0,
        validation_alias="TemperatureCoefficientThermalConductivity [W/m-K2]",
    )
    # TODO: material type should be dynamic user entry or enum
    ConstructionMaterialType = Literal[
        "Concrete",
        "Timber",
        "Screed",
        "Masonry",
        "Insulation",
        "Metal",
        "Boards",
        "Other",
        "Plaster",
        "Finishes",
        "Siding",
        "Sealing",
    ]

    Type: ConstructionMaterialType = Field(
        ..., title="Type of the opaque material", validation_alias="Type [enum]"
    )


class ConstructionMaterialComponent(
    ConstructionMaterialProperties,
    StandardMaterializedMetadata,
    NamedObject,
    MetadataMixin,
    extra="forbid",
):
    """Construction material object."""

    pass


class ConstructionLayerComponent(
    MaterialWithThickness, MetadataMixin, NamedObject, extra="forbid"
):
    """Layer of an opaque construction."""

    def dereference_to_material(
        self, material_defs: dict[str, ConstructionMaterialComponent]
    ) -> Material:
        """Converts a referenced material into a direct EP material object.

        Args:
            material_defs (list[OpaqueMaterial]): List of opaque material definitions.

        Returns:
            Material: The material object.
        """
        if self.Name not in material_defs:
            raise ValueNotFound("Material", self.Name)

        mat_def = material_defs[self.Name]

        material = Material(
            Name=f"{self.Name}_{self.Thickness}",
            Thickness=self.Thickness,
            Conductivity=mat_def.Conductivity,
            Density=mat_def.Density,
            Specific_Heat=mat_def.SpecificHeat,
            Thermal_Absorptance=mat_def.ThermalAbsorptance,
            Solar_Absorptance=mat_def.SolarAbsorptance,
            Roughness=mat_def.Roughness,
        )
        return material


# windows definitions
class GlazingConstructionSimpleComponent(
    NamedObject,
    StandardMaterializedMetadata,
    MetadataMixin,
    extra="forbid",
    populate_by_name=True,
):
    """Glazing construction object."""

    WindowType = Literal["Single", "Double", "Triple"]
    SHGF: float = Field(..., title="Solar heat gain factor", ge=0, le=1)
    UValue: float = Field(
        ...,
        title="U-value [W/m²K]",
        validation_alias=AliasChoices(
            "UValue [W/m2-k]",
            "UValue [W/m2K]",
            "UValue [W/m2k]",
        ),
        ge=0,
    )
    TVis: float = Field(..., title="Visible transmittance", ge=0, le=1)
    Type: WindowType = Field(..., title="Type of the glazing construction")

    def add_to_idf(self, idf: IDF) -> IDF:
        """Adds the glazing construction to an IDF object.

        Args:
            idf (IDF): The IDF object to add the construction to.

        Returns:
            IDF: The updated IDF object.
        """
        glazing_mat = SimpleGlazingMaterial(
            Name=self.Name,
            UFactor=self.UValue,
            Solar_Heat_Gain_Coefficient=self.SHGF,
            Visible_Transmittance=self.TVis,
        )

        construction = Construction(
            name=self.Name,
            layers=[glazing_mat],
        )

        idf = construction.add(idf)
        return idf


class WindowDefinition(NamedObject, MetadataMixin, extra="ignore"):
    """Window definition object."""

    Construction: str = Field(..., title="Construction object name")

    @property
    def schedule_names(self) -> set[str]:
        """Get the schedule names used in the object.

        Returns:
            set[str]: The schedule names.
        """
        return set()


class InfiltrationComponent(
    NamedObject, MetadataMixin, extra="forbid", populate_by_name=True
):
    """Zone infiltration object."""

    InfiltrationIsOn: BoolStr = Field(..., title="Infiltration is on")
    InfiltrationConstantCoefficient: float = Field(
        ...,
        title="Infiltration constant coefficient",
    )
    InfiltrationTemperatureCoefficient: float = Field(
        ...,
        title="Infiltration temperature coefficient",
    )
    InfiltrationWindVelocityCoefficient: float = Field(
        ...,
        title="Infiltration wind velocity coefficient",
    )
    InfiltrationWindVelocitySquaredCoefficient: float = Field(
        ...,
        title="Infiltration wind velocity squared coefficient",
    )
    AFN_AirMassFlowCoefficient_Crack: float = Field(
        ...,
        title="AFN air mass flow coefficient crack",
    )

    InfiltrationAch: float = Field(
        ...,
        title="Infiltration air changes per hour",
        ge=0,
        validation_alias="InfiltrationAch [ACH]",
    )
    InfiltrationFlowPerExteriorSurfaceArea: float = Field(
        ...,
        title="Infiltration flow per exterior surface area",
        ge=0,
        validation_alias="InfiltrationFlowPerExteriorSurfaceArea [m3/s/m2]",
    )
    CalculationMethod: InfDesignFlowRateCalculationMethodType = Field(
        ...,
        title="Calculation method",
    )

    def add_infiltration_to_idf_zone(
        self, idf: IDF, target_zone_or_zone_list_name: str
    ):
        """Add infiltration to an IDF zone.

        Args:
            idf (IDF): The IDF object to add the infiltration to.
            target_zone_or_zone_list_name (str): The name of the zone or zone list to add the infiltration to.

        Returns:
            idf (IDF): The updated IDF object.
        """
        if not self.InfiltrationIsOn:
            return idf

        infiltration_schedule_name = (
            f"{target_zone_or_zone_list_name}_{self.Name}_Infiltration_Schedule"
        )
        schedule = Schedule.constant_schedule(
            value=1, Name=infiltration_schedule_name, Type="Fraction"
        )
        inf_schedule, *_ = schedule.to_year_week_day()
        inf_schedule.to_epbunch(idf)
        inf = ZoneInfiltrationDesignFlowRate(
            Name=f"{target_zone_or_zone_list_name}_{self.Name}_Infiltration",
            Zone_or_ZoneList_Name=target_zone_or_zone_list_name,
            Schedule_Name=inf_schedule.Name,
            Design_Flow_Rate_Calculation_Method=self.CalculationMethod,
            Flow_Rate_per_Exterior_Surface_Area=self.InfiltrationFlowPerExteriorSurfaceArea,
            Air_Changes_per_Hour=self.InfiltrationAch,
            Flow_Rate_per_Floor_Area=None,
            Design_Flow_Rate=None,
            Constant_Term_Coefficient=self.InfiltrationConstantCoefficient,
            Temperature_Term_Coefficient=self.InfiltrationTemperatureCoefficient,
            Velocity_Term_Coefficient=self.InfiltrationWindVelocityCoefficient,
            Velocity_Squared_Term_Coefficient=self.InfiltrationWindVelocitySquaredCoefficient,
        )
        idf = inf.add(idf)
        return idf


class ConstructionAssemblyComponent(
    NamedObject, MetadataMixin, extra="forbid", populate_by_name=True
):
    """Opaque construction object."""

    Layers: list[ConstructionLayerComponent] = Field(
        ..., title="Layers of the opaque construction"
    )
    VegetationLayer: NanStr = Field(
        ..., title="Vegetation layer of the opaque construction"
    )
    Type: ConstructionComponents = Field(..., title="Type of the opaque construction")

    def add_to_idf(
        self, idf: IDF, material_defs: dict[str, ConstructionMaterialComponent]
    ) -> IDF:
        """Adds an opaque construction to an IDF object.

        Note that this will add the individual materials as well.

        Args:
            idf (IDF): The IDF object to add the construction to.
            material_defs (list[OpaqueMaterial]): List of opaque material definitions.

        Returns:
            IDF: The updated IDF object.
        """
        layers = [layer.dereference_to_material(material_defs) for layer in self.Layers]

        construction = Construction(
            name=self.Name,
            layers=layers,
        )
        idf = construction.add(idf)
        return idf


class EnvelopeAssemblyComponent(
    NamedObject, MetadataMixin, extra="forbid", populate_by_name=True
):
    """Zone construction object."""

    RoofAssembly: str = Field(..., title="Roof construction object name")
    FacadeAssembly: str = Field(..., title="Facade construction object name")
    SlabAssembly: str = Field(..., title="Slab construction object name")
    PartitionAssembly: str = Field(..., title="Partition construction object name")
    ExternalFloorAssembly: str = Field(
        ..., title="External floor construction object name"
    )
    GroundSlabAssembly: str = Field(..., title="Ground slab construction object name")
    GroundWallAssembly: str = Field(..., title="Ground wall construction object name")
    InternalMassAssembly: str = Field(
        ..., title="Internal mass construction object name"
    )
    InternalMassIsOn: BoolStr = Field(..., title="Internal mass is on")
    InternalMassExposedAreaPerArea: float = Field(
        ...,
        title="Internal mass exposed area per area [m²/m²]",
        validation_alias="InternalMassExposedAreaPerArea [area / floor (m2/m2)]",
    )
    GroundIsAdiabatic: BoolStr = Field(..., title="Ground is adiabatic")
    RoofIsAdiabatic: BoolStr = Field(..., title="Roof is adiabatic")
    FacadeIsAdiabatic: BoolStr = Field(..., title="Facade is adiabatic")
    SlabIsAdiabatic: BoolStr = Field(..., title="Slab is adiabatic")
    PartitionIsAdiabatic: BoolStr = Field(..., title="Partition is adiabatic")


class ZoneEnvelopeComponent(NamedObject, MetadataMixin, extra="forbid"):
    """Zone envelope object."""

    Assemblies: EnvelopeAssemblyComponent
    Infiltration: InfiltrationComponent
    WindowDefinition: WindowDefinition | None
    WWR: float | None = Field(
        default=assumed_constants["WWR"], description="Window to wall ratio", ge=0, le=1
    )
    # Foundation: Foundation | None
    # OtherSettings: OtherSettings | None

    # TODO: add envelope to idf zone
    # (currently in builder)

    @property
    def schedule_names(self) -> set[str]:
        """Get the schedule names used in the object.

        Returns:
            set[str]: The schedule names.
        """
        win_sch = (
            self.WindowDefinition.schedule_names if self.WindowDefinition else set()
        )
        return win_sch


NamedType = TypeVar("NamedType", bound=NamedObject)


class ComponentLibrary(BaseModel, MetadataMixin, arbitrary_types_allowed=True):
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

    HVAC: dict[str, ZoneHVACComponent] = Field(
        ..., description="HVAC component gathers conditioningsystems and ventilation."
    )
    ConditioningSystems: dict[str, ConditioningSystemsComponent]
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

    Schedule: dict[str, Schedule]

    @field_validator("Schedules", mode="before")
    @classmethod
    def validate_schedules(cls, value: dict[str, Any]):
        """Validate the schedules."""
        for key, val in value.items():
            if isinstance(val, dict):
                transfer = ScheduleTransferObject.model_validate(val)
                limit_type = ScheduleTypeLimits.from_dict(transfer.Type)
                value[key] = Schedule.from_values(
                    Name=transfer.Name,
                    Type=limit_type,  # pyright: ignore [reportArgumentType]
                    Values=transfer.Values,
                )
            elif isinstance(val, ScheduleTransferObject):
                limit_type = ScheduleTypeLimits.from_dict(val.Type)
                value[key] = Schedule.from_values(
                    Name=val.Name,
                    Type=limit_type,  # pyright: ignore [reportArgumentType]
                    Values=val.Values,
                )
            elif not isinstance(val, Schedule):
                raise TypeError(f"SCHEDULE_LOAD_ERROR:{type(val)}")
            else:
                continue
        return value

    @field_serializer("Schedules")
    def serialize_schedules(
        self, schedules: dict[str, Schedule]
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


# TODO: update this class
class SurfaceHandler(BaseModel):
    """A handler for filtering and adding surfaces to a model."""

    boundary_condition: str | None
    original_construction_name: str | None
    original_surface_type: str | None
    surface_group: Literal["glazing", "opaque"]

    def assign_srfs(
        self, idf: IDF, lib: ComponentLibrary, construction_name: str
    ) -> IDF:
        """Adds a construction (and its materials) to an IDF and assigns it to matching surfaces.

        Args:
            idf (IDF): The IDF model to add the construction to.
            lib (ClimateStudioLibraryV2): The library of constructions.
            construction_name (str): The name of the construction to add.
        """
        srf_key = (
            "FENESTRATIONSURFACE:DETAILED"
            if self.surface_group == "glazing"
            else "BUILDINGSURFACE:DETAILED"
        )
        if self.boundary_condition is not None and self.surface_group == "glazing":
            raise NotImplementedParameter(
                "BoundaryCondition", self.surface_group, "Glazing"
            )

        srfs = [srf for srf in idf.idfobjects[srf_key] if self.check_srf(srf)]
        construction_lib = (
            lib.OpaqueConstructions
            if self.surface_group != "glazing"
            else lib.GlazingConstructionSimple
        )
        if construction_name not in construction_lib:
            raise KeyError(
                f"MISSING_CONSTRUCTION:{construction_name}:TARGET={self.__repr__()}"
            )
        construction = construction_lib[construction_name]
        idf = (
            construction.add_to_idf(idf)
            if isinstance(construction, GlazingConstructionSimpleComponent)
            else construction.add_to_idf(idf, lib.ConstructionMaterial)
        )
        for srf in srfs:
            srf.Construction_Name = construction.Name
        return idf

    def check_srf(self, srf):
        """Check if the surface matches the filters.

        Args:
            srf (eppy.IDF.BLOCK): The surface to check.

        Returns:
            match (bool): True if the surface matches the filters.
        """
        return (
            self.check_construction_type(srf)
            and self.check_boundary(srf)
            and self.check_construction_name(srf)
        )

    def check_construction_type(self, srf):
        """Check if the surface matches the construction type.

        Args:
            srf (eppy.IDF.BLOCK): The surface to check.

        Returns:
            match (bool): True if the surface matches the construction type.
        """
        if self.surface_group == "glazing":
            # Ignore the construction type check for windows
            return True
        if self.original_surface_type is None:
            # Ignore the construction type check when filter not provided
            return True
        # Check the construction type
        return self.original_surface_type.lower() == srf.Surface_Type.lower()

    def check_boundary(self, srf):
        """Check if the surface matches the boundary condition.

        Args:
            srf (eppy.IDF.BLOCK): The surface to check.

        Returns:
            match (bool): True if the surface matches the boundary condition.
        """
        if self.surface_group == "glazing":
            # Ignore the bc filter check for windows
            return True
        if self.boundary_condition is None:
            # Ignore the bc filter when filter not provided
            return True
        # Check the boundary condition
        return srf.Outside_Boundary_Condition.lower() == self.boundary_condition.lower()

    def check_construction_name(self, srf):
        """Check if the surface matches the original construction name.

        Args:
            srf (eppy.IDF.BLOCK): The surface to check.

        Returns:
            match (bool): True if the surface matches the original construction name.
        """
        if self.original_construction_name is None:
            # Ignore the original construction name check when filter not provided
            return True
        # Check the original construction name
        return srf.Construction_Name.lower() == self.original_construction_name.lower()


# TODO: update this class
class SurfaceHandlers(BaseModel):
    """A collection of surface handlers for different surface types."""

    Roof: SurfaceHandler
    Facade: SurfaceHandler
    Slab: SurfaceHandler
    Ceiling: SurfaceHandler
    Partition: SurfaceHandler
    GroundSlab: SurfaceHandler
    GroundWall: SurfaceHandler
    Window: SurfaceHandler

    @classmethod
    def Default(cls):
        """Get the default surface handlers."""
        roof_handler = SurfaceHandler(
            boundary_condition="outdoors",
            original_construction_name=None,
            original_surface_type="roof",
            surface_group="opaque",
        )
        facade_handler = SurfaceHandler(
            boundary_condition="outdoors",
            original_construction_name=None,
            original_surface_type="wall",
            surface_group="opaque",
        )
        partition_handler = SurfaceHandler(
            boundary_condition="surface",
            original_construction_name=None,
            original_surface_type="wall",
            surface_group="opaque",
        )
        ground_wall_handler = SurfaceHandler(
            boundary_condition="ground",
            original_construction_name=None,
            original_surface_type="wall",
            surface_group="opaque",
        )
        slab_handler = SurfaceHandler(
            boundary_condition="surface",
            original_construction_name=None,
            original_surface_type="floor",
            surface_group="opaque",
        )
        ceiling_handler = SurfaceHandler(
            boundary_condition="surface",
            original_construction_name=None,
            original_surface_type="ceiling",
            surface_group="opaque",
        )
        ground_slab_handler = SurfaceHandler(
            boundary_condition="ground",
            original_construction_name=None,
            original_surface_type="floor",
            surface_group="opaque",
        )
        window_handler = SurfaceHandler(
            boundary_condition=None,
            original_construction_name=None,
            original_surface_type=None,
            surface_group="glazing",
        )

        return cls(
            Roof=roof_handler,
            Facade=facade_handler,
            Slab=slab_handler,
            Ceiling=ceiling_handler,
            Partition=partition_handler,
            GroundSlab=ground_slab_handler,
            GroundWall=ground_wall_handler,
            Window=window_handler,
        )

    def handle_envelope(
        self,
        idf: IDF,
        lib: ComponentLibrary,
        constructions: EnvelopeAssemblyComponent,
        window: WindowDefinition | None,
    ):
        """Assign the envelope to the IDF model.

        Note that this will add a "reversed" construction for the floorsystem slab/ceiling

        Args:
            idf (IDF): The IDF model to add the envelope to.
            lib (ClimateStudioLibraryV2): The library of constructions.
            constructions (ZoneConstruction): The construction names for the envelope.
            window (WindowDefinition | None): The window definition.

        Returns:
            idf (IDF): The updated IDF model.
        """

        # outside walls are the ones with outdoor boundary condition and vertical orientation
        def make_reversed(const: ConstructionAssemblyComponent):
            new_const = const.model_copy(deep=True)
            new_const.Layers = new_const.Layers[::-1]
            new_const.Name = f"{const.Name}_Reversed"
            return new_const

        def reverse_construction(const_name: str, lib: ComponentLibrary):
            const = lib.OpaqueConstructions[const_name]
            new_const = make_reversed(const)
            return new_const

        slab_reversed = reverse_construction(constructions.SlabAssembly, lib)
        lib.OpaqueConstructions[slab_reversed.Name] = slab_reversed

        idf = self.Roof.assign_srfs(
            idf=idf, lib=lib, construction_name=constructions.RoofAssembly
        )
        idf = self.Facade.assign_srfs(
            idf=idf, lib=lib, construction_name=constructions.FacadeAssembly
        )
        idf = self.Partition.assign_srfs(
            idf=idf, lib=lib, construction_name=constructions.PartitionAssembly
        )
        idf = self.Slab.assign_srfs(
            idf=idf, lib=lib, construction_name=slab_reversed.Name
        )
        idf = self.Ceiling.assign_srfs(
            idf=idf, lib=lib, construction_name=constructions.SlabAssembly
        )
        idf = self.GroundSlab.assign_srfs(
            idf=idf, lib=lib, construction_name=constructions.GroundSlabAssembly
        )
        idf = self.GroundWall.assign_srfs(
            idf=idf, lib=lib, construction_name=constructions.GroundWallAssembly
        )
        if window:
            idf = self.Window.assign_srfs(
                idf=idf, lib=lib, construction_name=window.Construction
            )
        return idf
