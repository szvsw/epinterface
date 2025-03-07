"""Systems components for the SBEM library."""

from typing import Literal

from archetypal.idfclass import IDF
from archetypal.schedule import Schedule, ScheduleTypeLimits
from pydantic import Field, model_validator

from epinterface.interface import WaterUseEquipment
from epinterface.sbem.common import BoolStr, MetadataMixin, NamedObject
from epinterface.sbem.components.schedules import YearComponent

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
HeatingSystemType = Literal[
    "ElectricResistance", "GasBoiler", "GasFurnace", "ASHP", "GSHP"
]
CoolingSystemType = Literal["DX", "EvapCooling"]
DistributionType = Literal["Hydronic", "Air", "Steam"]


class ThermalSystemComponent(NamedObject, MetadataMixin, extra="forbid"):
    """A thermal system object in the SBEM library."""

    ConditioningType: Literal["Heating", "Cooling"]
    Fuel: FuelType
    SystemCOP: float = Field(
        ...,
        title="System COP",
        ge=0,
    )
    DistributionCOP: float = Field(..., title="Distribution COP", ge=0)

    @property
    def effective_system_cop(self) -> float:
        """Compute the effective system COP based on the system and distribution COPs.

        Returns:
            cop (float): The effective system COP.
        """
        return self.SystemCOP * self.DistributionCOP

    @property
    def HeatingSystemType(self) -> HeatingSystemType:
        """Compute the heating system type based on the system COP.

        Returns:
            heating_system_type (HeatingSystemType): The heating system type.
        """
        if self.ConditioningType != "Heating":
            msg = "Heating system type is only applicable to heating systems."
            raise ValueError(msg)
        # TODO: compute based off of CoP
        msg = "Heating system type is not implemented."
        raise NotImplementedError(msg)
        return "ElectricResistance"

    @property
    def CoolingSystemType(self) -> CoolingSystemType:
        """Compute the cooling system type based on the system COP.

        Returns:
            cooling_system_type (CoolingSystemType): The cooling system type.
        """
        if self.ConditioningType != "Cooling":
            msg = "Cooling system type is only applicable to cooling systems."
            raise ValueError(msg)
        # TODO: compute based off of CoP
        msg = "Cooling system type is not implemented."
        raise NotImplementedError(msg)
        return "DX"

    @property
    def DistributionType(self) -> DistributionType:
        """Compute the distribution type based on the system COP.

        Returns:
            distribution_type (DistributionType): The distribution type.
        """
        # TODO: compute based off of CoP
        msg = "Distribution type is not implemented."
        raise NotImplementedError(msg)
        return "Hydronic"


class ConditioningSystemsComponent(NamedObject, MetadataMixin, extra="forbid"):
    """A conditioning system object in the SBEM library."""

    Heating: ThermalSystemComponent | None
    Cooling: ThermalSystemComponent | None

    @model_validator(mode="after")
    def validate_conditioning_types(self):
        """Validate that the conditioning types are correct.

        Cannot have a heating system assigned to a cooling system and vice versa.
        """
        if self.Heating and self.Heating.ConditioningType != "Heating":
            msg = "Heating system type is only applicable to heating systems."
            raise ValueError(msg)
        if self.Cooling and self.Cooling.ConditioningType != "Cooling":
            msg = "Cooling system type is only applicable to cooling systems."
            raise ValueError(msg)

        return self


VentilationType = Literal["Natural", "Mechanical", "Hybrid"]
VentilationTechType = Literal["ERV", "HRV", "DCV", "None", "Custom"]


class VentilationComponent(NamedObject, MetadataMixin, extra="forbid"):
    """A ventilation object in the SBEM library."""

    # TODO: add unit notes in field descriptions
    Rate: float = Field(..., title="Ventilation rate of the object")
    MinFreshAir: float = Field(
        ...,
        title="Minimum fresh air of the object [m³/s]",
    )
    Schedule: YearComponent = Field(..., title="Ventilation schedule of the object")
    Type: VentilationType = Field(..., title="Type of the object")
    TechType: VentilationTechType = Field(..., title="Technology type of the object")


class ZoneHVACComponent(
    NamedObject,
    MetadataMixin,
    extra="forbid",
):
    """Conditioning object in the SBEM library."""

    ConditioningSystems: ConditioningSystemsComponent
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


DHWFuelType = Literal["Electricity", "NaturalGas", "Propane", "FuelOil"]


class DHWComponent(
    NamedObject,
    MetadataMixin,
    extra="forbid",
):
    """Domestic Hot Water object."""

    SystemCOP: float = Field(
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
    IsOn: BoolStr = Field(..., title="Is on")
    FuelType: DHWFuelType = Field(..., title="Hot water fuel type")

    @model_validator(mode="after")
    def validate_supply_greater_than_inlet(self):
        """Validate that the supply temperature is greater than the inlet temperature."""
        if self.WaterSupplyTemperature <= self.WaterTemperatureInlet:
            msg = "Water supply temperature must be greater than the inlet temperature."
            raise ValueError(msg)
        return self

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
        raise NotImplementedError
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

    @property
    def effective_system_cop(self) -> float:
        """Compute the effective system COP based on the system and distribution COPs.

        Returns:
            cop (float): The effective system COP.
        """
        return self.SystemCOP * self.DistributionCOP
