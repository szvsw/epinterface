"""Systems components for the SBEM library."""

from typing import Literal

from archetypal.idfclass import IDF
from pydantic import Field, model_validator

from epinterface.interface import (
    AirflowNetworkMultiZoneComponentDetailedOpening,
    AirflowNetworkMultiZoneReferenceCrackConditions,
    AirflowNetworkMultiZoneSurface,
    AirflowNetworkMultiZoneSurfaceCrack,
    AirflowNetworkMultiZoneZone,
    AirflowNetworkSimulationControl,
)
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
    "Steam",
    "ChilledWater",
]
HeatingSystemType = Literal[
    "ElectricResistance", "GasBoiler", "GasFurnace", "ASHP", "GSHP"
]
CoolingSystemType = Literal["DX", "EvapCooling"]
DistributionType = Literal["Hydronic", "Air", "Steam"]


class ThermalSystemComponent(NamedObject, MetadataMixin, extra="forbid"):
    """A thermal system object in the SBEM library."""

    ConditioningType: Literal["Heating", "Cooling", "HeatingAndCooling"]
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
        if (
            self.ConditioningType != "Heating"
            and self.ConditioningType != "HeatingAndCooling"
        ):
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
        if (
            self.ConditioningType != "Cooling"
            and self.ConditioningType != "HeatingAndCooling"
        ):
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
        if self.Heating and "heating" not in self.Heating.ConditioningType.lower():
            msg = "Heating system type is only applicable to heating systems."
            raise ValueError(msg)
        if self.Cooling and "cooling" not in self.Cooling.ConditioningType.lower():
            msg = "Cooling system type is only applicable to cooling systems."
            raise ValueError(msg)

        return self


VentilationProvider = Literal["None", "Natural", "Mechanical", "Both"]

EconomizerMethod = Literal[
    "NoEconomizer", "DifferentialDryBulb", "DifferentialEnthalpy"
]

HRVMethod = Literal["NoHRV", "Sensible", "Enthalpy"]

DCVMethod = Literal["NoDCV", "OccupancySchedule", "CO2Setpoint"]


class VentilationComponent(NamedObject, MetadataMixin, extra="forbid"):
    """A ventilation object in the SBEM library."""

    # TODO: add unit notes in field descriptions
    FreshAirPerFloorArea: float = Field(
        ...,
        title="Fresh air per m2 of the object [m³/s/m²]",
        ge=0,
        le=0.05,
    )
    FreshAirPerPerson: float = Field(
        ...,
        title="Fresh air per person of the object [m³/s/p]",
        ge=0,
        le=0.05,
    )
    Schedule: YearComponent = Field(..., title="Ventilation schedule of the object")
    Provider: VentilationProvider = Field(..., title="Type of the object")
    HRV: HRVMethod = Field(..., title="HRV type of the object")
    Economizer: EconomizerMethod = Field(..., title="Economizer type of the object")
    DCV: DCVMethod = Field(..., title="DCV type of the object")

    @model_validator(mode="after")
    def validate_ventilation_systems(self):
        """Validate that the ventilation systems are correct.

        If the ventilation type is natural, then the zone cannot have variants of mechanical ventilation systems (e.g, HRV, DCV, Economizer).
        """
        if self.Provider == "Natural":
            if self.HRV != "NoHRV":
                msg = "Natural ventilation systems can't have HRV."
                raise ValueError(msg)
            if self.DCV != "NoDCV":
                msg = "Natural ventilation systems can't have DCV."
                raise ValueError(msg)
            if self.Economizer != "NoEconomizer":
                msg = "Natural ventilation systems can't have an Economizer."
                raise ValueError(msg)
        if self.Provider == "None":
            if self.HRV != "NoHRV":
                msg = "None ventilation systems can't have HRV."
                raise ValueError(msg)
            if self.DCV != "NoDCV":
                msg = "None ventilation systems can't have DCV."
                raise ValueError(msg)
            if self.Economizer != "NoEconomizer":
                msg = "None ventilation systems can't have an Economizer."
                raise ValueError(msg)
        return self


# Re-exported for convenience to downstream callers
AFNControlMode = Literal[
    "MultizoneWithDistribution",
    "MultizoneWithoutDistribution",
    "MultizoneWithDistributionOnlyDuringFanOperation",
    "NoMultizoneOrDistribution",
]
WPCType = Literal["Input", "SurfaceAverageCalculation"]
AFNBuildingType = Literal["LowRise", "HighRise"]

# Linkage type tag — used to select which detailed-opening or crack component
# the surface should reference, and what default opening behavior to apply.
LinkageKind = Literal["window", "doorway", "crack"]


class AFNCrackComponent(NamedObject, MetadataMixin, extra="forbid"):
    """An envelope-crack flow component.

    Defines the power-law mass-flow relationship m_dot = C * (dP)^n that EnergyPlus
    applies to surfaces tagged as cracks. One AFNCrackComponent per envelope
    tightness archetype (e.g., one each for pre-1975, 1975-2003, post-2003).
    """

    FlowCoefficient: float = Field(
        ...,
        title="Air Mass Flow Coefficient at Reference Conditions [kg/s @ 1 Pa, per unit area or absolute]",
        gt=0.0,
        description=(
            "Power-law leading coefficient. EnergyPlus expects this in kg/s at 1 Pa; "
            "scaling per unit surface area is handled by the caller before instantiation."
        ),
    )
    FlowExponent: float = Field(
        default=0.65,
        title="Air Mass Flow Exponent",
        ge=0.5,
        le=1.0,
        description="Typical residential value 0.6-0.7.",
    )
    ReferenceCrackConditions: str | None = Field(
        default=None,
        title="Reference Crack Conditions Name",
        description="Name of the AFN:MultiZone:ReferenceCrackConditions object.",
    )

    def add_to_idf(self, idf: IDF) -> IDF:
        """Emit the AFN:MultiZone:Surface:Crack object."""
        crack = AirflowNetworkMultiZoneSurfaceCrack(
            Name=self.Name,
            Air_Mass_Flow_Coefficient_at_Reference_Conditions=self.FlowCoefficient,
            Air_Mass_Flow_Exponent=self.FlowExponent,
            Reference_Crack_Conditions=self.ReferenceCrackConditions,
        )
        return crack.add(idf)


class AFNDetailedOpeningComponent(NamedObject, MetadataMixin, extra="forbid"):
    """A detailed-opening flow component (operable window or interior doorway).

    Currently models a simple closed-vs-fully-open characteristic (2 opening
    factors). The width/height factors at full opening determine the effective
    open area:
        open_area = parent_surface_area * WidthFactor * HeightFactor
    """

    DischargeCoefficient: float = Field(
        default=0.6,
        title="Discharge Coefficient at Opening Factor 1.0",
        gt=0.0,
        le=1.0,
        description="Typical orifice/window 0.6; doorway 0.65.",
    )
    WidthFactor: float = Field(
        default=1.0,
        title="Width Factor at Opening Factor 1.0",
        ge=0.0,
        le=1.0,
    )
    HeightFactor: float = Field(
        default=0.5,
        title="Height Factor at Opening Factor 1.0",
        ge=0.0,
        le=1.0,
        description="Default 0.5 represents a typical double-hung window with half the area opening.",
    )
    StartHeightFactor: float = Field(
        default=0.0,
        title="Start Height Factor at Opening Factor 1.0",
        ge=0.0,
        le=1.0,
    )
    ClosedFlowCoefficient: float = Field(
        default=0.001,
        title="Air Mass Flow Coefficient When Opening is Closed [kg/s-m @ 1 Pa]",
        gt=0.0,
        description="Residual leakage when fully closed.",
    )
    ClosedFlowExponent: float = Field(
        default=0.65,
        title="Air Mass Flow Exponent When Opening Is Closed",
        ge=0.5,
        le=1.0,
    )

    def add_to_idf(self, idf: IDF) -> IDF:
        """Emit the AFN:MultiZone:Component:DetailedOpening object."""
        opening = AirflowNetworkMultiZoneComponentDetailedOpening(
            Name=self.Name,
            Air_Mass_Flow_Coefficient_When_Opening_is_Closed=self.ClosedFlowCoefficient,
            Air_Mass_Flow_Exponent_When_Opening_is_Closed=self.ClosedFlowExponent,
            Type_of_Rectangular_Large_Vertical_Opening="NonPivoted",
            Number_of_Sets_of_Opening_Factor_Data=2,
            Opening_Factor_1=0.0,
            Discharge_Coefficient_for_Opening_Factor_1=0.001,
            Width_Factor_for_Opening_Factor_1=0.0,
            Height_Factor_for_Opening_Factor_1=1.0,
            Start_Height_Factor_for_Opening_Factor_1=0.0,
            Opening_Factor_2=1.0,
            Discharge_Coefficient_for_Opening_Factor_2=self.DischargeCoefficient,
            Width_Factor_for_Opening_Factor_2=self.WidthFactor,
            Height_Factor_for_Opening_Factor_2=self.HeightFactor,
            Start_Height_Factor_for_Opening_Factor_2=self.StartHeightFactor,
        )
        return opening.add(idf)


class AFNComponent(NamedObject, MetadataMixin, extra="forbid"):
    """AirflowNetwork component — top-level multi-zone airflow definition.

    Holds the simulation-control settings, the reference crack conditions, and
    libraries of crack and detailed-opening components keyed by name.

    Three ways IDF objects get emitted:

    1. `add_to_idf(idf)` — emits the simulation control, reference conditions,
       and all reusable flow components (cracks and openings). Call once per IDF.
    2. `add_zone_to_idf(idf, zone_name)` — emits one AFN:MultiZone:Zone object
       declaring the AFN behavior for that zone. Call once per thermal zone.
    3. `add_linkage_to_idf(idf, surface_name, linkage_kind, ...)` — emits one
       AFN:MultiZone:Surface object connecting a heat-transfer or fenestration
       surface to the AFN network. Call once per linkage (window, doorway,
       envelope crack).

    See `afn_setup_spec.md` for the full triple-decker v0 example wiring.
    """

    # Simulation-control settings
    AFNControl: AFNControlMode = Field(
        default="MultizoneWithoutDistribution",
        title="AirflowNetwork Control",
    )
    WindPressureCoefficientType: WPCType = Field(
        default="SurfaceAverageCalculation",
        title="Wind Pressure Coefficient Type",
    )
    BuildingType: AFNBuildingType = Field(default="LowRise", title="Building Type")
    BuildingAspectRatio: float = Field(
        default=0.5,
        title="Ratio of Building Width Along Short Axis to Width Along Long Axis",
        gt=0.0,
        le=1.0,
        description=(
            "For SurfaceAverageCalculation Cp model. Aspect = short axis / long axis. "
            "Triple-decker ~7m x 14m -> 0.5."
        ),
    )
    BuildingLongAxisAzimuth: float = Field(
        default=0.0,
        title="Azimuth Angle of Long Axis of Building [deg]",
        ge=0.0,
        le=180.0,
    )

    # Reusable component libraries
    Cracks: dict[str, AFNCrackComponent] = Field(
        default_factory=dict,
        title="Crack components, keyed by name (must match component Name)",
    )
    Openings: dict[str, AFNDetailedOpeningComponent] = Field(
        default_factory=dict,
        title="Detailed-opening components, keyed by name (must match component Name)",
    )
    WindowOpeningKey: str | None = Field(
        default=None,
        title="Opening component for window linkages",
        description="Key in Openings; defaults to the sole/first opening when unset.",
    )
    EnvelopeCrackKey: str | None = Field(
        default=None,
        title="Crack component for exterior wall linkages",
        description="Key in Cracks; defaults to the sole/first crack when unset.",
    )

    # Reference crack conditions
    ReferenceCrackTemperature: float = Field(
        default=20.0,
        title="Reference Crack Conditions: Reference Temperature [degC]",
    )
    ReferenceCrackPressure: float = Field(
        default=101325.0,
        title="Reference Crack Conditions: Reference Barometric Pressure [Pa]",
    )
    ReferenceCrackHumidityRatio: float = Field(
        default=0.0,
        title="Reference Crack Conditions: Reference Humidity Ratio [kg/kg]",
        ge=0.0,
    )

    @model_validator(mode="after")
    def validate_component_keys(self):
        """Names in the dict keys must match the components' Name fields."""
        for k, v in self.Cracks.items():
            if k != v.Name:
                msg = f"Crack key {k!r} does not match its component Name {v.Name!r}."
                raise ValueError(msg)
        for k, v in self.Openings.items():
            if k != v.Name:
                msg = f"Opening key {k!r} does not match its component Name {v.Name!r}."
                raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_wpc_consistency(self):
        """Building type / aspect ratio only meaningful with SurfaceAverageCalculation."""
        if self.WindPressureCoefficientType == "Input":
            # No further fields validated; user must add their own ExternalNode +
            # WindPressureCoefficientArray + WindPressureCoefficientValues objects.
            pass
        return self

    @property
    def reference_crack_conditions_name(self) -> str:
        """Name used for the AFN:MultiZone:ReferenceCrackConditions object."""
        return f"{self.safe_name}_RefCrackConditions"

    @property
    def window_opening_name(self) -> str | None:
        """Resolved opening component name for window linkages."""
        if self.WindowOpeningKey is not None:
            return self.WindowOpeningKey
        if self.Openings:
            return next(iter(self.Openings.keys()))
        return None

    @property
    def envelope_crack_name(self) -> str | None:
        """Resolved crack component name for exterior wall linkages."""
        if self.EnvelopeCrackKey is not None:
            return self.EnvelopeCrackKey
        if self.Cracks:
            return next(iter(self.Cracks.keys()))
        return None

    def add_to_idf(self, idf: IDF) -> IDF:
        """Add simulation control, reference conditions, and reusable flow components."""
        sim_control = AirflowNetworkSimulationControl(
            Name=f"{self.safe_name}_SimControl",
            AirflowNetwork_Control=self.AFNControl,
            Wind_Pressure_Coefficient_Type=self.WindPressureCoefficientType,
            Building_Type=self.BuildingType,
            Ratio_of_Building_Width_Along_Short_Axis_to_Width_Along_Long_Axis=self.BuildingAspectRatio,
            Azimuth_Angle_of_Long_Axis_of_Building=self.BuildingLongAxisAzimuth,
        )
        idf = sim_control.add(idf)

        ref = AirflowNetworkMultiZoneReferenceCrackConditions(
            Name=self.reference_crack_conditions_name,
            Reference_Temperature=self.ReferenceCrackTemperature,
            Reference_Barometric_Pressure=self.ReferenceCrackPressure,
            Reference_Humidity_Ratio=self.ReferenceCrackHumidityRatio,
        )
        idf = ref.add(idf)

        for crack in self.Cracks.values():
            crack_with_ref = crack.model_copy(
                update={
                    "ReferenceCrackConditions": self.reference_crack_conditions_name
                }
            )
            idf = crack_with_ref.add_to_idf(idf)

        for opening in self.Openings.values():
            idf = opening.add_to_idf(idf)

        return idf

    def add_zone_to_idf(
        self,
        idf: IDF,
        target_zone_name: str,
        venting_availability_schedule_name: str | None = None,
        ventilation_control_mode: Literal[
            "Constant", "Temperature", "Enthalpy", "NoVent"
        ] = "Constant",
    ) -> IDF:
        """Add an AFN:MultiZone:Zone declaration for the given thermal zone."""
        zone = next(
            (z for z in idf.idfobjects["ZONE"] if z.Name == target_zone_name), None
        )
        if zone is None:
            msg = f"NO_ZONE:{target_zone_name}"
            raise ValueError(msg)

        afn_zone = AirflowNetworkMultiZoneZone(
            Zone_Name=target_zone_name,
            Ventilation_Control_Mode=ventilation_control_mode,
            Venting_Availability_Schedule_Name=venting_availability_schedule_name,
        )
        return afn_zone.add(idf)

    def _validate_linkage_component(
        self, linkage_kind: LinkageKind, component_name: str
    ) -> None:
        if linkage_kind == "crack":
            if component_name not in self.Cracks:
                msg = (
                    f"Crack component {component_name!r} not registered. "
                    f"Available: {sorted(self.Cracks.keys())}"
                )
                raise ValueError(msg)
            return
        if linkage_kind in ("window", "doorway"):
            if component_name not in self.Openings:
                msg = (
                    f"Opening component {component_name!r} not registered. "
                    f"Available: {sorted(self.Openings.keys())}"
                )
                raise ValueError(msg)
            return
        msg = f"Unknown linkage kind {linkage_kind!r}."
        raise ValueError(msg)

    @staticmethod
    def _idf_has_surface(idf: IDF, surface_name: str) -> bool:
        for stype in ("BUILDINGSURFACE:DETAILED", "FENESTRATIONSURFACE:DETAILED"):
            if any(s.Name == surface_name for s in idf.idfobjects[stype]):
                return True
        return False

    def add_linkage_to_idf(
        self,
        idf: IDF,
        surface_name: str,
        linkage_kind: LinkageKind,
        component_name: str,
        venting_schedule_name: str | None = None,
        opening_factor: float = 1.0,
        is_interior: bool = False,
    ) -> IDF:
        """Add an AFN:MultiZone:Surface linking a surface to the AFN network."""
        self._validate_linkage_component(linkage_kind, component_name)
        if not self._idf_has_surface(idf, surface_name):
            raise ValueError(f"NO_SURFACE:{surface_name}")

        ext_node_name = None
        if (
            self.WindPressureCoefficientType == "Input"
            and not is_interior
            and linkage_kind != "doorway"
        ):
            ext_node_name = None

        venting_sched = (
            venting_schedule_name if linkage_kind in ("window", "doorway") else None
        )

        afn_surface = AirflowNetworkMultiZoneSurface(
            Surface_Name=surface_name,
            Leakage_Component_Name=component_name,
            External_Node_Name=ext_node_name,
            Window_or_Door_Opening_Factor_or_Crack_Factor=opening_factor,
            Ventilation_Control_Mode="ZoneLevel",
            Venting_Availability_Schedule_Name=venting_sched,
        )
        return afn_surface.add(idf)


class ZoneHVACComponent(
    NamedObject,
    MetadataMixin,
    extra="forbid",
):
    """Conditioning object in the SBEM library."""

    ConditioningSystems: ConditioningSystemsComponent
    Ventilation: VentilationComponent
    AFN: AFNComponent | None = Field(
        default=None,
        title="Airflow network definition for this zone template",
    )


DHWFuelType = Literal["Electricity", "NaturalGas", "Propane", "FuelOil", "Steam"]


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
    )

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

    @property
    def effective_system_cop(self) -> float:
        """Compute the effective system COP based on the system and distribution COPs."""
        return self.SystemCOP * self.DistributionCOP
