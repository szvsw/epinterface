"""Space use components for the SBEM library.."""

import logging
from typing import Literal

from archetypal.idfclass import IDF
from archetypal.schedule import Schedule, ScheduleTypeLimits
from pydantic import Field

from epinterface.constants import assumed_constants, physical_constants
from epinterface.interface import ElectricEquipment, Lights, People
from epinterface.sbem.common import BoolStr, MetadataMixin, NamedObject
from epinterface.sbem.exceptions import NotImplementedParameter

logger = logging.getLogger(__name__)


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
    MetabolicRate: float = assumed_constants.MetabolicRate_met

    @property
    def MetabolicRate_met_to_W(self):
        """Get the metabolic rate in Watts."""
        avg_human_weight_kg = assumed_constants.AvgHumanWeight_kg
        conversion_factor = physical_constants.ConversionFactor_W_per_kg
        # mets * kg * W/kg = W
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
            Fraction_Radiant=assumed_constants.FractionRadiantPeople,
            Sensible_Heat_Fraction="autocalculate",
            Activity_Level_Schedule_Name=activity_sch_year.Name,
        )

        idf = people.add(idf)
        return idf


DimmingTypeType = Literal["Off", "Stepped", "Continuous"]


class LightingComponent(NamedObject, MetadataMixin):
    """A lighting object in the SBEM library."""

    LightingPowerDensity: float = Field(
        ...,
        title="Lighting density of the object",
        ge=0,
        validation_alias="LightingDensity [W/m²]",
    )

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
            Return_Air_Fraction=assumed_constants.ReturnAirFractionLights,
            Fraction_Radiant=assumed_constants.FractionRadiantLights,
            Fraction_Visible=assumed_constants.FractionVisibleLights,
            Fraction_Replaceable=assumed_constants.FractionReplaceableLights,
            EndUse_Subcategory=None,
        )
        idf = lights.add(idf)
        return idf


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
            Fraction_Latent=assumed_constants.FractionLatentEquipment,
            Fraction_Radiant=assumed_constants.FractionRadiantEquipment,
            Fraction_Lost=assumed_constants.FractionLostEquipment,
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

        raise NotImplementedError
        idf = idf.newidfobject("HVACTEMPLATE:THERMOSTAT", **self.model_dump())
        return idf


class WaterUseComponent(NamedObject, MetadataMixin):
    """A water use object in the SBEM library."""

    FlowRatePerPerson: float = Field(
        ..., title="Flow rate per person [m3/day/p]", ge=0, le=0.1
    )
    WaterSchedule: str = Field(
        ..., title="Water schedule"
    )  # TODO: Define a schedule preset to import (not from template)

    @property
    def schedule_names(self) -> set[str]:
        """Get the schedule names used in the object.

        Returns:
            set[str]: The schedule names.
        """
        raise NotImplementedError
        return {self.WaterSchedule} if self.IsOn else set()


class ZoneSpaceUseComponent(NamedObject):
    """Space use object."""

    # TODO
    Occupancy: OccupancyComponent
    Lighting: LightingComponent
    Equipment: EquipmentComponent
    Thermostat: ThermostatComponent
    WaterUse: WaterUseComponent

    def add_loads_to_idf_zone(self, idf: IDF, target_zone_name: str) -> IDF:
        """Add the loads to an IDF zone.

        This will add the people, equipment, and lights to the zone.

        Args:
            idf (IDF): The IDF object to add the loads to.
            target_zone_name (str): The name of the zone to add the loads to.

        Returns:
            IDF: The updated IDF object.
        """
        idf = self.Lighting.add_lights_to_idf_zone(idf, target_zone_name)
        idf = self.Occupancy.add_people_to_idf_zone(idf, target_zone_name)
        idf = self.Equipment.add_equipment_to_idf_zone(idf, target_zone_name)
        idf = self.Thermostat.add_thermostat_to_idf_zone(idf, target_zone_name)
        raise NotImplementedError
        return idf
