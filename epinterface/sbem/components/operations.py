"""Operations components for the SBEM library."""

from archetypal.idfclass import IDF
from archetypal.schedule import Schedule, ScheduleTypeLimits
from shapely.geometry import Polygon

from epinterface.interface import WaterUseEquipment
from epinterface.sbem.common import MetadataMixin, NamedObject
from epinterface.sbem.components.space_use import ZoneSpaceUseComponent
from epinterface.sbem.components.systems import DHWComponent, ZoneHVACComponent


class ZoneOperationsComponent(
    NamedObject,
    MetadataMixin,
    extra="forbid",
):
    """Zone use consolidation across space use, HVAC, DHW."""

    SpaceUse: ZoneSpaceUseComponent
    HVAC: ZoneHVACComponent
    DHW: DHWComponent

    def add_water_use_to_idf_zone(self, idf: IDF, target_zone_name: str) -> IDF:
        """Handle adding water use to the zone based on both DHW and Operations.SpaceUse.WaterUse.

        We choose to execute this from the zone component interface because it requires context from both
        zone.Operations.SpaceUse.WaterUse and zone.Operations.

        This will be responsible for:
            1. Extracting the total area of the zone by finding the matching surfaces.
            2. Computing the total number of people in the zone based on the occupancy density and the total area.
            3. Computing the total flow rate of water use/s in the zone based on the flow rate per person/day and the total number of people.
            4. Adding the water use equipment to the zone.


        # TODO: major problem - this assumes the zone has already been correctly sized!
        # this method should only actually be called AFTER
        # the building has been properly rescaled, which currently is executed at the very end.
        # that hook should probably be moved up.

        Args:
            idf (IDF): The IDF object to add the operations to.
            target_zone_name (str): The name of the zone to add the operations to.

        Returns:
            idf (IDF): The updated IDF object.
        """
        # TODO: should IsOn definitely live in DHW? should dhw be nullable?
        # should it live in spaceuse.wateruse for consistency?
        if not self.DHW.IsOn:
            return idf

        # Acquire the relevant data fields
        flow_rate_per_person_per_day = (
            self.SpaceUse.WaterUse.FlowRatePerPerson
        )  # m3/person/day
        occupant_density = self.SpaceUse.Occupancy.PeopleDensity  # ppl/m2
        water_supply_temperature = self.DHW.WaterSupplyTemperature  # degC
        water_temperature_inlet = self.DHW.WaterTemperatureInlet  # degC
        water_use_frac_sched = self.SpaceUse.WaterUse.Schedule
        water_use_name = f"{target_zone_name}_{self.SpaceUse.WaterUse.safe_name}_{self.DHW.safe_name}_WATER"

        # determine zone area to then compute total people
        # we will do this by finding all matching surfaces and computing their areas.
        zone = next(
            (x for x in idf.idfobjects["ZONE"] if x.Name == target_zone_name), None
        )
        if zone is None:
            raise ValueError(f"NO_ZONE:{target_zone_name}")
        area = 0
        area_ct = 0
        for srf in idf.idfobjects["BUILDINGSURFACE:DETAILED"]:
            # TODO: ensure that this still works for basements and attics.
            if srf.Zone_Name == zone.Name and srf.Surface_Type.lower() == "floor":
                poly = Polygon(srf.coords)
                area += poly.area
                area_ct += 1
        if area_ct > 1:
            raise ValueError(f"TOO_MANY_FLOORS:{zone.Name}")
        if area == 0 or area_ct == 0:
            raise ValueError(f"NO_AREA:{zone.Name}")
        total_ppl = occupant_density * area

        # Compute final flow rates.
        total_flow_rate_per_day = flow_rate_per_person_per_day * total_ppl  # m3/day
        total_flow_rate_per_s = total_flow_rate_per_day / (3600 * 24)  # m3/s
        # TODO: Update this rather than being constant rate

        lim = "Temperature"
        if not idf.getobject("SCHEDULETYPELIMITS", lim):
            lim = ScheduleTypeLimits(
                Name="Temperature",
                LowerLimit=-60,
                UpperLimit=200,
            )
            lim.to_epbunch(idf)

        # TODO: should we be using time-varying temperatures?
        target_temperature_schedule = Schedule.constant_schedule(
            value=water_supply_temperature,  # pyright: ignore [reportArgumentType]
            Name=f"{water_use_name}_TargetWaterTemperatureSch",
            Type="Temperature",
        )
        inlet_temperature_schedule = Schedule.constant_schedule(
            value=water_temperature_inlet,  # pyright: ignore [reportArgumentType]
            Name=f"{water_use_name}_InletWaterTemperatureSch",
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

        if water_use_frac_sched.schedule_type_limits != "Fraction":
            msg = f"WATER_USE_FRACTION_SCHEDULE_TYPE_NOT_FRACTION:{water_use_name}"
            raise ValueError(msg)

        idf, water_use_frac_sch_name = water_use_frac_sched.add_year_to_idf(
            idf, name_prefix=water_use_name
        )

        hot_water = WaterUseEquipment(
            Name=water_use_name,
            EndUse_Subcategory="Domestic Hot Water",
            Peak_Flow_Rate=total_flow_rate_per_s,  # TODO: Update this to actual peak rate?
            Flow_Rate_Fraction_Schedule_Name=water_use_frac_sch_name,
            Zone_Name=target_zone_name,
            Target_Temperature_Schedule_Name=target_temperature_yr_schedule.Name,
            Hot_Water_Supply_Temperature_Schedule_Name=target_temperature_schedule.Name,
            Cold_Water_Supply_Temperature_Schedule_Name=inlet_temperature_schedule.Name,
            Sensible_Fraction_Schedule_Name=None,
            Latent_Fraction_Schedule_Name=None,
        )
        idf = hot_water.add(idf)
        return idf
