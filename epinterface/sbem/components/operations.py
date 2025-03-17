"""Operations components for the SBEM library."""

from logging import getLogger

import numpy as np
from archetypal.idfclass import IDF
from archetypal.schedule import Schedule, ScheduleTypeLimits

from epinterface.constants import assumed_constants
from epinterface.geometry import get_zone_floor_area, get_zone_glazed_area
from epinterface.interface import (
    HVACTemplateThermostat,
    HVACTemplateZoneIdealLoadsAirSystem,
    WaterUseEquipment,
    ZoneVentilationWindAndStackOpenArea,
)
from epinterface.sbem.common import MetadataMixin, NamedObject
from epinterface.sbem.components.space_use import ZoneSpaceUseComponent
from epinterface.sbem.components.systems import DHWComponent, ZoneHVACComponent

logger = getLogger(__name__)


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

        Note: the water use component's flow rate represents the total amount of water used per person per day;
        in order to calculate a peak flow rate, we will need to ensure that the product of the schedule and the peak
        flow rate would resolve to the same daily average value per person.

        This will be responsible for:
            1. Extracting the total area of the zone by finding the matching surfaces.
            2. Computing the total number of people in the zone based on the occupancy density and the total area.
            3. Computing the average flow rate of water use/s in the zone based on the flow rate per person/day and the total number of people.
            4. Computing the peak flow rate of water use/s in the zone based on the average flow rate and the average fractional value of the schedule.
            5. Adding the water use equipment to the zone.


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
        area = get_zone_floor_area(idf, zone.Name)
        total_ppl = occupant_density * area

        # Compute final flow rates.
        total_flow_per_day = flow_rate_per_person_per_day * total_ppl  # m3/day
        avg_flow_per_s = total_flow_per_day / (3600 * 24)  # m3/s
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
        sch_obj = idf.getobject("SCHEDULE:YEAR", water_use_frac_sch_name)
        arch_sch = Schedule.from_epbunch(sch_obj)
        values = np.array(arch_sch.Values)
        avg_fractional_value = np.sum(values) / 8760
        # total_fractional_value * peak_flow_rate_per_s = avg_float_per_s
        peak_flow_rate_per_s = avg_flow_per_s / avg_fractional_value

        hot_water = WaterUseEquipment(
            Name=water_use_name,
            EndUse_Subcategory="Domestic Hot Water",
            Peak_Flow_Rate=peak_flow_rate_per_s,
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

    def add_thermostat_to_idf_zone(
        self, idf: IDF, target_zone_name: str
    ) -> HVACTemplateThermostat:
        """Add a thermostat to the zone.

        Args:
            idf (IDF): The IDF object to add the thermostat to.
            target_zone_name (str): The name of the zone to add the thermostat to.

        Returns:
            idf (IDF): The updated IDF object.
        """
        thermostat_name = (
            f"{target_zone_name}_{self.HVAC.safe_name}_{self.DHW.safe_name}_THERMOSTAT"
        )
        heating_schedule = self.SpaceUse.Thermostat.HeatingSchedule
        cooling_schedule = self.SpaceUse.Thermostat.CoolingSchedule
        heating_schedule_name = None
        cooling_schedule_name = None
        if heating_schedule is not None:
            idf, heating_schedule_name = heating_schedule.add_year_to_idf(
                idf, name_prefix=thermostat_name
            )
        if cooling_schedule is not None:
            idf, cooling_schedule_name = cooling_schedule.add_year_to_idf(
                idf, name_prefix=thermostat_name
            )

        thermostat = HVACTemplateThermostat(
            Name=thermostat_name,
            Heating_Setpoint_Schedule_Name=heating_schedule_name,
            Constant_Heating_Setpoint=self.SpaceUse.Thermostat.HeatingSetpoint
            if self.SpaceUse.Thermostat.HeatingSchedule is None
            else None,
            Cooling_Setpoint_Schedule_Name=cooling_schedule_name,
            Constant_Cooling_Setpoint=self.SpaceUse.Thermostat.CoolingSetpoint
            if self.SpaceUse.Thermostat.CoolingSchedule is None
            else None,
        )

        idf = thermostat.add(idf)

        return thermostat

    def add_conditioning_to_idf_zone(self, idf: IDF, target_zone_name: str) -> IDF:
        """Add conditioning to an IDF zone."""
        thermostat = self.add_thermostat_to_idf_zone(idf, target_zone_name)
        if self.HVAC.Ventilation.TechType == "DCV":
            # check the design spec outdoor air for the DCV
            raise NotImplementedError("DCV not implemented.")
        if self.HVAC.Ventilation.TechType == "Economizer":
            # check the differential dry bulb vs. differential enthalpy for the economizer
            raise NotImplementedError("Economizer not implemented")
        hvac_template = HVACTemplateZoneIdealLoadsAirSystem(
            Zone_Name=target_zone_name,
            Template_Thermostat_Name=thermostat.Name,
            Maximum_Heating_Air_Flow_Rate="autosize",
            Heating_Limit="NoLimit",
            Maximum_Sensible_Heating_Capacity="autosize",
            Minimum_Cooling_Supply_Air_Temperature=13,
            Maximum_Cooling_Air_Flow_Rate="autosize",
            Maximum_Total_Cooling_Capacity="autosize",
            Cooling_Limit="NoLimit",
            Humidification_Control_Type="None",
            Outdoor_Air_Flow_Rate_per_Person=self.HVAC.Ventilation.FreshAirPerPerson,
            Outdoor_Air_Flow_Rate_per_Zone_Floor_Area=self.HVAC.Ventilation.FreshAirPerFloorArea,
            Outdoor_Air_Flow_Rate_per_Zone=0,
            Demand_Controlled_Ventilation_Type="OccupancySchedule"
            if self.HVAC.Ventilation.TechType == "DCV"
            else "None",
            Outdoor_Air_Economizer_Type="DifferentialDryBulb"
            if self.HVAC.Ventilation.TechType == "Economizer"
            else "NoEconomizer",
            Heat_Recovery_Type="Sensible"
            if self.HVAC.Ventilation.TechType == "HRV"
            else "None",
            Sensible_Heat_Recovery_Effectiveness=assumed_constants.Sensible_Heat_Recovery_Effectiveness,
            Latent_Heat_Recovery_Effectiveness=assumed_constants.Latent_Heat_Recovery_Effectiveness,
            Outdoor_Air_Method="Sum"
            if self.HVAC.Ventilation.Type == "Mechanical"
            or self.HVAC.Ventilation.Type == "Hybrid"
            else "None",
        )
        idf = hvac_template.add(idf)

        if self.HVAC.Ventilation.Type == "Natural":
            # total_window_area = calculate_window_area_for_zone(idf, target_zone_name)
            total_window_area = get_zone_glazed_area(idf, target_zone_name)

            if total_window_area == 0:
                logger.warning(
                    f"No windows found for natural ventilation in zone {target_zone_name}"
                )
                return idf
            vent_wind_stack_name = f"{target_zone_name}_{self.HVAC.safe_name}_{self.DHW.safe_name}_VENTILATION_WIND_AND_STACK_OPEN_AREA"
            idf, vent_wind_stack_name = self.HVAC.Ventilation.Schedule.add_year_to_idf(
                idf, name_prefix=vent_wind_stack_name
            )
            ventilation_wind_and_stack_open_area = ZoneVentilationWindAndStackOpenArea(
                Name=vent_wind_stack_name,
                Zone_or_Space_Name=target_zone_name,
                Minimum_Indoor_Temperature=self.SpaceUse.Thermostat.HeatingSetpoint,
                Maximum_Outdoor_Temperature=self.SpaceUse.Thermostat.CoolingSetpoint,
                Opening_Area=total_window_area,
                Opening_Area_Fraction_Schedule_Name=vent_wind_stack_name,
                Height_Difference=0,
            )
            idf = ventilation_wind_and_stack_open_area.add(idf)

        return idf
