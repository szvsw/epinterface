"""Space use components for the SBEM library.."""

import logging
from typing import Literal

from archetypal.idfclass import IDF
from archetypal.schedule import Schedule, ScheduleTypeLimits
from pydantic import Field

from epinterface.constants import assumed_constants, physical_constants
from epinterface.interface import ElectricEquipment, Lights, People
from epinterface.sbem.common import BoolStr, MetadataMixin, NamedObject
from epinterface.sbem.components.schedules import YearComponent
from epinterface.sbem.exceptions import NotImplementedParameter

logger = logging.getLogger(__name__)


class OccupancyComponent(NamedObject, MetadataMixin, extra="forbid"):
    """An occupancy object in the SBEM library."""

    PeopleDensity: float = Field(
        ...,
        title="Occupancy density of the object [ppl/m2]",
        ge=0,
    )
    Schedule: YearComponent = Field(
        ..., title="Occupancy schedule of the object [frac]"
    )
    IsOn: BoolStr = Field(..., title="People are on")
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
        if not self.IsOn:
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
            f"Adding people to zone with schedule {self.Schedule}.  Make sure this schedule exists."
        )
        logger.warning(
            f"Ignoring AirspeedSchedule for zone(s) {target_zone_or_zone_list_name}."
        )
        raise NotImplementedError
        # TODO: add schedule to idf

        name_prefix = (
            f"{target_zone_or_zone_list_name}_{self.Name.replace(' ', '_')}_PEOPLE"
        )
        idf, year_name = self.Schedule.add_year_to_idf(idf, name_prefix=name_prefix)
        people = People(
            Name=name_prefix,
            Zone_or_ZoneList_Name=target_zone_or_zone_list_name,
            Number_of_People_Schedule_Name=year_name,
            Number_of_People_Calculation_Method="People/Area",
            Number_of_People=None,
            Floor_Area_per_Person=None,
            People_per_Floor_Area=self.PeopleDensity,
            Fraction_Radiant=assumed_constants.FractionRadiantPeople,
            Sensible_Heat_Fraction="autocalculate",
            Activity_Level_Schedule_Name=activity_sch_year.Name,
        )

        idf = people.add(idf)
        return idf


DimmingTypeType = Literal["Off", "Stepped", "Continuous"]


class LightingComponent(NamedObject, MetadataMixin, extra="forbid"):
    """A lighting object in the SBEM library."""

    PowerDensity: float = Field(
        ...,
        title="Lighting density of the object [W/m2]",
        ge=0,
    )

    DimmingType: DimmingTypeType = Field(
        ...,
        title="Dimming type",
    )
    Schedule: YearComponent = Field(..., title="Lighting schedule of the object [frac]")
    IsOn: BoolStr = Field(..., title="Lights are on")

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
        if not self.IsOn:
            return idf

        if self.DimmingType != "Off":
            raise NotImplementedParameter("DimmingType:On", self.Name, "Lights")

        logger.warning(
            f"Ignoring IlluminanceTarget for zone(s) {target_zone_or_zone_list_name}."
        )
        name_prefix = (
            f"{target_zone_or_zone_list_name}_{self.Name.replace(' ', '_')}_LIGHTS"
        )
        idf, year_name = self.Schedule.add_year_to_idf(idf, name_prefix=name_prefix)
        lights = Lights(
            Name=name_prefix,
            Zone_or_ZoneList_Name=target_zone_or_zone_list_name,
            Schedule_Name=year_name,
            Design_Level_Calculation_Method="Watts/Area",
            Watts_per_Zone_Floor_Area=self.PowerDensity,
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


class EquipmentComponent(NamedObject, MetadataMixin, extra="forbid"):
    """An equipment object in the SBEM library."""

    PowerDensity: float = Field(..., title="Equipment density of the object [W/m2]")
    Schedule: YearComponent = Field(
        ..., title="Equipment schedule of the object [frac]"
    )
    IsOn: BoolStr = Field(..., title="Equipment is on")

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
        if not self.IsOn:
            return idf

        name_prefix = (
            f"{target_zone_or_zone_list_name}_{self.Name.replace(' ', '_')}_EQUIPMENT"
        )
        idf, year_name = self.Schedule.add_year_to_idf(idf, name_prefix=name_prefix)
        equipment = ElectricEquipment(
            Name=name_prefix,
            Zone_or_ZoneList_Name=target_zone_or_zone_list_name,
            Schedule_Name=year_name,
            Design_Level_Calculation_Method="Watts/Area",
            Watts_per_Zone_Floor_Area=self.PowerDensity,
            Watts_per_Person=None,
            Fraction_Latent=assumed_constants.FractionLatentEquipment,
            Fraction_Radiant=assumed_constants.FractionRadiantEquipment,
            Fraction_Lost=assumed_constants.FractionLostEquipment,
            EndUse_Subcategory=None,
        )
        idf = equipment.add(idf)
        return idf


# TODO: Potentially duplicative with HVACTempelateThermostat in epinterface > interface
class ThermostatComponent(NamedObject, MetadataMixin, extra="forbid"):
    """A thermostat object in the SBEM library."""

    IsOn: BoolStr = Field(..., title="Thermostat is on")
    HeatingSetpoint: float = Field(
        ...,
        title="Heating setpoint of the object",
    )
    HeatingSchedule: YearComponent = Field(..., title="Heating schedule of the object")
    CoolingSetpoint: float = Field(
        ...,
        title="Cooling setpoint of the object",
    )
    CoolingSchedule: YearComponent = Field(..., title="Cooling schedule of the object")

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
        if not self.IsOn:
            return idf

        logger.warning(
            f"Adding thermostat to zone with heating schedule {self.HeatingSchedule} and cooling schedule {self.CoolingSchedule}.  Make sure these schedules exist."
        )

        raise NotImplementedError
        idf = idf.newidfobject("HVACTEMPLATE:THERMOSTAT", **self.model_dump())
        return idf


class WaterUseComponent(NamedObject, MetadataMixin, extra="forbid"):
    """A water use object in the SBEM library."""

    FlowRatePerPerson: float = Field(
        ..., title="Flow rate per person [m3/day/p]", ge=0, le=0.1
    )
    Schedule: YearComponent = Field(..., title="Water schedule")

    @property
    def schedule_names(self) -> set[str]:
        """Get the schedule names used in the object.

        Returns:
            set[str]: The schedule names.
        """
        raise NotImplementedError
        return {self.WaterSchedule} if self.IsOn else set()


class ZoneSpaceUseComponent(NamedObject, MetadataMixin, extra="forbid"):
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
        # idf = self.Occupancy.add_people_to_idf_zone(idf, target_zone_name)
        idf = self.Equipment.add_equipment_to_idf_zone(idf, target_zone_name)
        # idf = self.Thermostat.add_thermostat_to_idf_zone(idf, target_zone_name)
        # raise NotImplementedError
        return idf


if __name__ == "__main__":
    from archetypal.idfclass import IDF

    from epinterface.sbem.components.schedules import (
        DayComponent,
        RepeatedWeekComponent,
        WeekComponent,
        YearComponent,
    )

    day = DayComponent(
        Name="low_day",
        Type="Fraction",
        Hour_00=0,
        Hour_01=0,
        Hour_02=0,
        Hour_03=0,
        Hour_04=0,
        Hour_05=0,
        Hour_06=0,
        Hour_07=0,
        Hour_08=0,
        Hour_09=0,
        Hour_10=0,
        Hour_11=0,
        Hour_12=0,
        Hour_13=0,
        Hour_14=0,
        Hour_15=0,
        Hour_16=0,
        Hour_17=0,
        Hour_18=0,
        Hour_19=0,
        Hour_20=0,
        Hour_21=0,
        Hour_22=0,
        Hour_23=0,
    )
    week = WeekComponent(
        Name="Week",
        Monday=day,
        Tuesday=day,
        Wednesday=day,
        Thursday=day,
        Friday=day,
        Saturday=day,
        Sunday=day,
    )
    repeated_week = RepeatedWeekComponent(
        Week=week,
        StartDay=1,
        StartMonth=1,
        EndDay=31,
        EndMonth=12,
    )
    year = YearComponent(
        Name="Year",
        Weeks=[repeated_week],
        Type="Fraction",
    )

    lighting = LightingComponent(
        Name="some_combo",
        PowerDensity=10,
        Schedule=year,
        IsOn=True,
        DimmingType="Off",
    )
    occupancy = OccupancyComponent(
        Name="some_combo",
        PeopleDensity=1,
        Schedule=year,
        IsOn=True,
    )
    equipment = EquipmentComponent(
        Name="some_combo",
        PowerDensity=10,
        Schedule=year,
        IsOn=True,
    )
    thermostat = ThermostatComponent(
        Name="some_combo",
        IsOn=True,
        HeatingSetpoint=20,
        HeatingSchedule=year,
        CoolingSetpoint=20,
        CoolingSchedule=year,
    )
    water_use = WaterUseComponent(
        Name="WaterUse",
        FlowRatePerPerson=0.01,
        Schedule=year,
    )

    zone_space_use = ZoneSpaceUseComponent(
        Name="ZoneSpaceUse",
        Lighting=lighting,
        Occupancy=occupancy,
        Equipment=equipment,
        Thermostat=thermostat,
        WaterUse=water_use,
    )

    idf = IDF(as_version="22.2.0")
    idf = zone_space_use.add_loads_to_idf_zone(idf, "Zone")
    for obj_type in idf.idfobjects:
        for obj in idf.idfobjects[obj_type]:
            print(obj)
