"""A module for parsing climate studio data and generating EnergyPlus objects."""

import logging
import re
from pathlib import Path
from typing import Annotated, Any, Literal, TypeVar, cast

import numpy as np
import pandas as pd
from archetypal.idfclass import IDF
from archetypal.schedule import Schedule, ScheduleTypeLimits
from pydantic import (
    AliasChoices,
    BaseModel,
    BeforeValidator,
    Field,
    field_serializer,
    field_validator,
    validate_call,
)

from epinterface.interface import (
    Construction,
    ElectricEquipment,
    HeatRecoveryTypeType,
    HVACTemplateThermostat,
    HVACTemplateZoneIdealLoadsAirSystem,
    IdealLoadsLimitType,
    InfDesignFlowRateCalculationMethodType,
    Lights,
    Material,
    OutdoorAirEconomizerTypeType,
    People,
    SimpleGlazingMaterial,
    ZoneInfiltrationDesignFlowRate,
    ZoneList,
)

logger = logging.getLogger(__name__)


class ClimateStudioException(Exception):
    """A base exception for the climate studio library."""

    def __init__(self, message: str):
        """Initialize the exception with a message."""
        self.message = message
        super().__init__(self.message)


class ClimateStudioValueNotFound(ClimateStudioException):
    """An error raised when a value is not found in a climate studio library."""

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


class ClimateStudioLibraryDuplicatesFound(ClimateStudioException):
    """An error raised when duplicates are found in a climate studio library."""

    def __init__(self, duplicate_field: str):
        """Initialize the exception with a message.

        Args:
            duplicate_field (str): The field with duplicates
        """
        self.duplicate_field = duplicate_field
        self.message = f"Duplicate objects found in library: {duplicate_field}"
        super().__init__(self.message)


class NotImplementedClimateStudioParameter(ClimateStudioException):
    """An error raised when a climate studio parameter is not implemented."""

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


class ScheduleParseError(ClimateStudioException):
    """An error raised when a schedule cannot be parsed."""

    def __init__(self, schedule_name: str):
        """Initialize the exception with a message.

        Args:
            schedule_name (str): The name of the schedule.
        """
        self.schedule_name = schedule_name
        super().__init__(f"Failed to parse schedule {schedule_name}")


def nan_to_none_or_str(v: Any) -> str | None | Any:
    """Converts NaN to None and leaves strings as is.

    Args:
        v (Any): Value to convert

    Returns:
        v (None | str | Any): Converted value
    """
    if isinstance(v, str):
        return v
    if v is None:
        return None
    if np.isnan(v):
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
    elif v.lower() == "true":
        return True
    elif v.lower() == "false":
        return False
    else:
        return False


def str_to_float_list(v: str | list):
    """Converts a string to a list of floats.

    Args:
        v (str): String to convert

    Returns:
        vals (list[float]): List of floats
    """
    if v == "[]":
        return []
    if isinstance(v, str):
        # re should be used to parse the string -
        # check that it starts with "["  and ends with "]"
        # and the elements are separated by ", "
        # and the elements are all ints or floats

        if not re.match(r"^\[.*\]$", v):
            raise ValueError(f"STRING:NOT_LIST:{v}")
        v = v[1:-1]
        if not re.match(r"^[\-0-9\., ]*$", v):
            raise ValueError(f"STRING:NOT_LIST:{v}")
        v = v.replace(" ", "").split(",")
    return [float(x) for x in v]


NanStr = Annotated[str | None, BeforeValidator(nan_to_none_or_str)]
BoolStr = Annotated[bool, BeforeValidator(str_to_bool)]
FloatListStr = Annotated[list[float], BeforeValidator(str_to_float_list)]


class NamedObject(BaseModel):
    """A Named object (with a name field)."""

    Name: str = Field(..., title="Name of the object used in referencing.")


class EmbodiedCarbonData(BaseModel):
    """Embodied carbon data for a material or construction."""

    EmbodiedEnergy: float = Field(
        ...,
        title="Embodied energy [MJ/unit]",
        validation_alias=AliasChoices(
            "EmbodiedEnergy [MJ/Kg]",
            "EmbodiedEnergy",
            "EmbodiedEnergy [MJ/m²]",
            "EmbodiedEnergy [MJ/mÂ²]",
            "EmbodiedEnergy [MJ/mÃ‚Â²]",  # noqa: RUF001
        ),
    )
    EmbodiedEnergyStdDev: float = Field(
        0,
        title="Standard deviation of embodied energy [MJ/unit]",
        validation_alias="EmbodiedEnergyStdDev",
        ge=0,
    )
    EmbodiedCarbon: float = Field(
        ...,
        title="Embodied carbon [kgCO2eq/unit]",
        validation_alias=AliasChoices(
            "EmbodiedCarbon [kgCO2eq/Kg]",
            "EmbodiedCarbon",
            "EmbodiedCarbon [kgCO2eq/m²]",
            "EmbodiedCarbon [kgCO2eq/mÂ²]",
            "EmbodiedCarbon [kgCO2eq/mÃ‚Â²]",  # noqa: RUF001
        ),
    )
    EmbodiedCarbonStdDev: float = Field(
        0,
        title="Standard deviation of embodied carbon [kgCO2eq/unit]",
        validation_alias="EmbodiedCarbonStdDev",
        ge=0,
    )


class LifecycleData(BaseModel):
    """Lifecycle data for a material or construction."""

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
            "Cost [$/mÃ‚Â²]",  # noqa: RUF001
        ),
        ge=0,
    )
    Life: float = Field(
        ...,
        title="Life [years]",
        validation_alias="Life [yr]",
        ge=0,
    )


class ClimateStudioMetadata(BaseModel):
    """Metadata for a climate studio table object."""

    Category: str = Field(..., title="Category of the object")
    Comment: NanStr = Field(..., title="Comment on the object")
    DataSource: NanStr = Field(..., title="Data source of the object")
    ClimateZone: str = Field(..., title="Climate zone of the object")
    Standard: str = Field(..., title="Standard of the object")
    Program: str = Field(..., title="Program of the object")
    Version: NanStr | None = Field(default=None, title="Version of the object")


class StandardMaterializedMetadata(
    EmbodiedCarbonData, LifecycleData, ClimateStudioMetadata
):
    """Standard metadata for a climate studio table."""

    pass


class MaterialWithThickness(BaseModel, populate_by_name=True):
    """Material with a thickness."""

    Thickness: float = Field(
        ...,
        title="Thickness of the material [m]",
        validation_alias="Thickness [m]",
        ge=0,
    )


class GasMaterial(
    NamedObject, MaterialWithThickness, StandardMaterializedMetadata, extra="forbid"
):
    """Gas Material object."""

    Model: Literal["Gas"] = Field(default="Gas", title="Model of the gas material")
    GasType1: str = Field(..., title="Type of the gas material")
    GasType2: str = Field(..., title="Type of the gas material")
    GasType3: str = Field(..., title="Type of the gas material")
    GasesInMix: int = Field(..., title="Number of gases in the mix", ge=1)
    Ratio1: float = Field(..., title="Ratio of the gas material", ge=0, le=1)
    Ratio2: float = Field(..., title="Ratio of the gas material", ge=0, le=1)
    Ratio3: float = Field(..., title="Ratio of the gas material", ge=0, le=1)
    ConductivityCoefficientA: float = Field(
        ..., title="Conductivity coefficient A", ge=0
    )
    ConductivityCoefficientB: float = Field(
        ..., title="Conductivity coefficient B", ge=0
    )
    ConductivityCoefficientC: float = Field(
        ..., title="Conductivity coefficient C", ge=0
    )
    MolecularWeight: float = Field(..., title="Molecular weight", ge=0)
    SpecificHeatCoefficientA: float = Field(
        ..., title="Specific heat coefficient A", ge=0
    )
    SpecificHeatCoefficientB: float = Field(
        ..., title="Specific heat coefficient B", ge=0
    )
    SpecificHeatCoefficientC: float = Field(
        ..., title="Specific heat coefficient C", ge=0
    )
    SpecificHeatRatio: float = Field(..., title="Specific heat ratio", ge=0)
    ViscosityCoefficientA: float = Field(..., title="Viscosity coefficient A", ge=0)
    ViscosityCoefficientB: float = Field(..., title="Viscosity coefficient B", ge=0)
    ViscosityCoefficientC: float = Field(..., title="Viscosity coefficient C", ge=0)


class ManufacturerData(BaseModel):
    """Manufacturer data for a construction."""

    Manufacturer: NanStr = Field(..., title="Manufacturer of the object")
    ProductName: NanStr = Field(..., title="Product name of the object")
    Appearance: NanStr = Field(..., title="Appearance of the glazing construction")


WindowType = Literal["Single", "Double", "Triple"]


class GlazingConstructionSimple(
    NamedObject,
    StandardMaterializedMetadata,
    ManufacturerData,
    extra="forbid",
    populate_by_name=True,
):
    """Simple glazing construction object."""

    SHGF: float = Field(..., title="Solar heat gain factor", ge=0, le=1)
    UValue: float = Field(
        ...,
        title="U-value [W/m²K]",
        validation_alias="UValue [W/m2-k]",
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


class CommonMaterialProperties(BaseModel):
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


class GlazingMaterialProperties(CommonMaterialProperties):
    """Properties of a glazing material."""

    Optical: str = Field(..., title="Optical properties of the glazing material")
    OpticalDataName: NanStr = Field(
        ..., title="Optical data name of the glazing material"
    )
    NFRC_ID: int = Field(..., title="NFRC ID of the glazing material")
    Glazing_ID: int = Field(..., title="Glazing ID of the glazing material")
    CoatingSide: NanStr = Field(..., title="Coating side of the glazing material")
    SpectralDataPointWavelength: FloatListStr = Field(
        ...,
        title="Spectral data point wavelength",
        validation_alias="SpectralDataPointWavelength [Microns]",
    )
    SpectralDataPointTransmittance: FloatListStr = Field(
        ...,
        title="Spectral data point transmittance",
        validation_alias="SpectralDataPointTransmittance [0-1]",
    )
    SpectralDataPointFrontReflectance: FloatListStr = Field(
        ...,
        title="Spectral data point front reflectance",
        validation_alias="SpectralDataPointFrontReflectance [0-1]",
    )
    SpectralDataPointBackReflectance: FloatListStr = Field(
        ...,
        title="Spectral data point back reflectance",
        validation_alias="SpectralDataPointBackReflectance [0-1]",
    )
    SolarTransmittance: float = Field(
        ...,
        title="Solar transmittance of the glazing material",
        ge=0,
        le=1,
        validation_alias="SolarTransmittance [0-1]",
    )
    SolarReflectanceFront: float = Field(
        ...,
        title="Solar reflectance front of the glazing material",
        ge=0,
        le=1,
        validation_alias="SolarReflectanceFront [0-1]",
    )
    SolarReflectanceBack: float = Field(
        ...,
        title="Solar reflectance back of the glazing material",
        ge=0,
        le=1,
        validation_alias="SolarReflectanceBack [0-1]",
    )
    VisibleTransmittance: float = Field(
        ...,
        title="Visible transmittance of the glazing material",
        ge=0,
        le=1,
        validation_alias="VisibleTransmittance [0-1]",
    )
    VisibleReflectanceFront: float = Field(
        ...,
        title="Visible reflectance front of the glazing material",
        ge=0,
        le=1,
        validation_alias="VisibleReflectanceFront [0-1]",
    )
    VisibleReflectanceBack: float = Field(
        ...,
        title="Visible reflectance back of the glazing material",
        ge=0,
        le=1,
        validation_alias="VisibleReflectanceBack [0-1]",
    )
    IRTransmittance: float = Field(
        ...,
        title="IR transmittance of the glazing material",
        ge=0,
        le=1,
        validation_alias="IRTransmittance [0-1]",
    )
    IREmissivityFront: float = Field(
        ...,
        title="IR emissivity front of the glazing material",
        ge=0,
        le=1,
        validation_alias="IREmissivityFront [0-1]",
    )
    IREmissivityBack: float = Field(
        ...,
        title="IR emissivity back of the glazing material",
        ge=0,
        le=1,
        validation_alias="IREmissivityBack [0-1]",
    )
    DirtFactor: float = Field(
        ...,
        title="Dirt factor of the glazing material",
        ge=0,
        le=1,
        validation_alias="DirtFactor [0-1]",
    )
    Type: str = Field(..., title="Type of the glazing material")


class GlazingMaterial(
    GlazingMaterialProperties,
    MaterialWithThickness,
    StandardMaterializedMetadata,
    NamedObject,
    extra="forbid",
):
    """Glazing material object."""

    pass


OpaqueMaterialType = Literal[
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
]


class OpaqueMaterialProperties(CommonMaterialProperties, populate_by_name=True):
    """Properties of an opaque material."""

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
    VisibleAbsorptance: float = Field(
        ...,
        title="Visible absorptance",
        ge=0,
        le=1,
        validation_alias="VisibleAbsorptance [0-1]",
    )
    PhaseChange: BoolStr = Field(
        ...,
        title="Phase change",
        validation_alias="PhaseChange [Bool]",
    )
    VariableConductivity: BoolStr = Field(
        ...,
        title="Variable conductivity",
        validation_alias="VariableConductivity [Bool]",
    )
    TemperatureCoefficientThermalConductivity: float = Field(
        ...,
        # a superscript 2 looks like this:
        title="Temperature coefficient of thermal conductivity [W/m.K2²]",
        ge=0,
        validation_alias="TemperatureCoefficientThermalConductivity [W/m-K2]",
    )
    TemperatureArray: FloatListStr = Field(
        ...,
        title="Temperature array",
        validation_alias="TemperatureArray [C]",
    )
    EnthalpyArray: FloatListStr = Field(
        ...,
        title="Enthalpy array",
        validation_alias="EnthalpyArray [J/kg]",
    )
    VariableConductivityArray: FloatListStr = Field(
        ...,
        title="Variable conductivity array",
        validation_alias="VariableConductivityArray [W/m-K]",
    )
    Type: OpaqueMaterialType = Field(
        ..., title="Type of the opaque material", validation_alias="Type [enum]"
    )


class OpaqueMaterial(
    OpaqueMaterialProperties,
    StandardMaterializedMetadata,
    NamedObject,
    extra="forbid",
):
    """Opaque material object."""

    pass


class OpaqueConstructionLayer(MaterialWithThickness, NamedObject, extra="forbid"):
    """Layer of an opaque construction."""

    def dereference_to_material(
        self, material_defs: dict[str, OpaqueMaterial]
    ) -> Material:
        """Converts a referenced material into a direct EP material object.

        Args:
            material_defs (list[OpaqueMaterial]): List of opaque material definitions.

        Returns:
            Material: The material object.
        """
        if self.Name not in material_defs:
            raise ClimateStudioValueNotFound("Material", self.Name)

        mat_def = material_defs[self.Name]

        material = Material(
            Name=self.Name,
            Thickness=self.Thickness,
            Conductivity=mat_def.Conductivity,
            Density=mat_def.Density,
            Specific_Heat=mat_def.SpecificHeat,
            Thermal_Absorptance=mat_def.ThermalAbsorptance,
            Solar_Absorptance=mat_def.SolarAbsorptance,
            Visible_Absorptance=mat_def.VisibleAbsorptance,
            Roughness=mat_def.Roughness,
        )
        return material


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
        OpaqueConstructionLayer(Name=name, Thickness=thickness)
        for name, thickness in zip(names, thicknesses, strict=False)
    ]


LayerListStr = Annotated[
    list[OpaqueConstructionLayer], BeforeValidator(str_to_opaque_layer_list)
]


OpaqueConstructionType = Literal[
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


class OpaqueConstruction(
    NamedObject,
    StandardMaterializedMetadata,
    ManufacturerData,
    extra="forbid",
    populate_by_name=True,
):
    """Opaque construction object."""

    Layers: LayerListStr = Field(..., title="Layers of the opaque construction")
    VegetationLayer: NanStr = Field(
        ..., title="Vegetation layer of the opaque construction"
    )
    Type: OpaqueConstructionType = Field(..., title="Type of the opaque construction")

    def add_to_idf(self, idf: IDF, material_defs: dict[str, OpaqueMaterial]) -> IDF:
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


class ZoneConditioning(
    NamedObject, ClimateStudioMetadata, extra="forbid", populate_by_name=True
):
    """Zone conditioning object."""

    HeatingSetpoint: float = Field(
        ...,
        title="Heating setpoint [°C]",
        validation_alias="HeatingSetpoint [°C]",
        ge=0,
        le=100,
    )
    CoolingSetpoint: float = Field(
        ...,
        title="Cooling setpoint [°C]",
        validation_alias="CoolingSetpoint [°C]",
        ge=0,
        le=100,
    )
    # TODO: should we validate heating < cooling?
    HeatingSetpointConstant: BoolStr = Field(..., title="Heating setpoint constant")
    CoolingSetpointConstant: BoolStr = Field(..., title="Cooling setpoint constant")
    HeatingSetpointSchedule: str = Field(..., title="Heating setpoint schedule")
    CoolingSetpointSchedule: str = Field(..., title="Cooling setpoint schedule")
    MinFreshAirPerson: float = Field(
        ...,
        title="Minimum fresh air per person [L/s/p]",
        validation_alias="MinFreshAirPerson [L/s/p]",
        ge=0,
    )
    MinFreshAirArea: float = Field(
        ...,
        title="Minimum fresh air per area [L/s/m²]",
        validation_alias="MinFreshAirArea [L/s/m²]",
        ge=0,
    )
    CoolingCOP: float = Field(
        ...,
        title="Cooling Coefficient of Performance",
        ge=0,
    )
    HeatingCOP: float = Field(
        ...,
        title="Heating Coefficient of Performance",
        ge=0,
    )
    HeatIsOn: BoolStr = Field(..., title="Heat is on")
    CoolIsOn: BoolStr = Field(..., title="Cool is on")
    MechVentIsOn: BoolStr = Field(..., title="Mechanical ventilation is on")
    HumidistatIsOn: BoolStr = Field(
        ...,
        title="Humidistat is on",
        validation_alias="HumidistatIsOn [Bool]",
    )
    HeatingLimitType: IdealLoadsLimitType = Field(
        ...,
        title="Heating limit type",
        validation_alias="HeatingLimitType [enum]",
    )
    CoolingLimitType: IdealLoadsLimitType = Field(
        ...,
        title="Cooling limit type",
        validation_alias="CoolingLimitType [enum]",
    )
    MaxHeatingCapacity: float = Field(
        ...,
        title="Maximum heating capacity [W/m²]",
        validation_alias="MaxHeatingCapacity [W/m²]",
        ge=0,
    )
    MaxCoolingCapacity: float = Field(
        ...,
        title="Maximum cooling capacity [W/m²]",
        validation_alias="MaxCoolingCapacity [W/m²]",
        ge=0,
    )
    MaxHeatFlow: float = Field(
        ...,
        title="Maximum volumetric heat flow per flow area [m³/s/m²]",
        validation_alias="MaxHeatFlow [m³/s/m²]",
        ge=0,
    )
    MaxCoolFlow: float = Field(
        ...,
        title="Maximum volumetric cool flow per flow area [m³/s/m²]",
        validation_alias="MaxCoolFlow [m³/s/m²]",
        ge=0,
    )
    HeatingSchedule: str = Field(
        ...,
        title="Heating schedule",
        validation_alias="HeatingSchedule [Schedule name]",
    )
    CoolingSchedule: str = Field(
        ...,
        title="Cooling schedule",
        validation_alias="CoolingSchedule [Schedule name]",
    )
    MechVentSchedule: str = Field(
        ...,
        title="Mechanical ventilation schedule",
        validation_alias="MechVentSchedule [Schedule name]",
    )
    EconomizerType: OutdoorAirEconomizerTypeType = Field(
        ...,
        title="Economizer type",
        validation_alias="EconomizerType [enum]",
    )
    HeatRecoveryType: HeatRecoveryTypeType = Field(
        ...,
        title="Heat recovery type",
        validation_alias="HeatRecoveryType [enum]",
    )
    HeatRecoveryEfficiencySensible: float = Field(
        ...,
        title="Heat recovery efficiency sensible",
        ge=0,
        le=1,
        validation_alias="HeatRecoveryEfficiencySensible [0-1]",
    )
    HeatRecoveryEfficiencyLatent: float = Field(
        ...,
        title="Heat recovery efficiency latent",
        ge=0,
        le=1,
        validation_alias="HeatRecoveryEfficiencyLatent [0-1]",
    )
    MinHumidity: float = Field(
        ...,
        title="Minimum humidity [%]",
        ge=0,
        le=100,
        validation_alias="MinHumidity [RH%]",
    )
    MaxHumidity: float = Field(
        ...,
        title="Maximum humidity [%]",
        ge=0,
        le=100,
        validation_alias="MaxHumidity [RH%]",
    )
    EMSFanEnergyIsOn: BoolStr = Field(..., title="EMS fan energy is on")
    FanPressureRise: float = Field(
        ...,
        title="Fan pressure rise [Pa]",
        ge=0,
        validation_alias="FanPressureRise [Pa]",
    )
    MaxHeatSupplyAirTemp: float = Field(
        ...,
        title="Maximum heat supply air temperature [°C]",
        ge=0,
        validation_alias="MaxHeatSupplyAirTemp [°C]",
    )
    MinCoolSupplyAirTemp: float = Field(
        ...,
        title="Minimum cool supply air temperature [°C]",
        ge=0,
        validation_alias="MinCoolSupplyAirTemp [°C]",
    )
    HeatingSizingFactor: float = Field(
        ...,
        title="Heating sizing factor",
        ge=0,
        validation_alias="HeatingSizingFactor [Unitless]",
    )
    CoolingSizingFactor: float = Field(
        ...,
        title="Cooling sizing factor",
        ge=0,
        validation_alias="CoolingSizingFactor [Unitless]",
    )
    Autosize: BoolStr = Field(
        ...,
        title="Autosize",
        validation_alias="Autosize [Bool]",
    )
    HeatingFuelType: FuelType = Field(
        ...,
        title="Heating fuel type",
        validation_alias="HeatingFuelType [enum]",
    )
    CoolingFuelType: FuelType = Field(
        ...,
        title="Cooling fuel type",
        validation_alias="CoolingFuelType [enum]",
    )

    @property
    def schedule_names(self) -> set[str]:
        """Get the schedule names used in the object.

        Returns:
            set[str]: The schedule names.
        """
        return {
            self.HeatingSchedule,
            self.CoolingSchedule,
            self.MechVentSchedule,
            self.HeatingSetpointSchedule,
            self.CoolingSetpointSchedule,
        }

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
        if self.HumidistatIsOn:
            raise NotImplementedClimateStudioParameter(
                "HumidistatIsOn",
                self.Name,
                "Conditioning",
            )

        if self.EMSFanEnergyIsOn:
            raise NotImplementedClimateStudioParameter(
                "EMSFanEnergyIsOn",
                self.Name,
                "Conditioning",
            )

        thermostat = HVACTemplateThermostat(
            Name=f"{self.Name}_{target_zone_name}_Thermostat",
            Heating_Setpoint_Schedule_Name=(
                self.HeatingSetpointSchedule
                if not self.HeatingSetpointConstant
                else None
            ),
            Cooling_Setpoint_Schedule_Name=(
                self.CoolingSetpointSchedule
                if not self.CoolingSetpointConstant
                else None
            ),
            Constant_Cooling_Setpoint=(
                self.CoolingSetpoint if self.CoolingSetpointConstant else None
            ),
            Constant_Heating_Setpoint=(
                self.HeatingSetpoint if self.HeatingSetpointConstant else None
            ),
        )

        # TODO: better handling of alwayson/off schedule names
        # TODO: better handling of mech vent schedule
        logger.warning(
            f"Mechanical ventilation schedule is being ignored in zone {target_zone_name}."
        )
        hvac_template = HVACTemplateZoneIdealLoadsAirSystem(
            Zone_Name=target_zone_name,
            Template_Thermostat_Name=thermostat.Name,
            System_Availability_Schedule_Name="AlwaysOn",
            Heating_Availability_Schedule_Name=(
                self.HeatingSchedule if self.HeatIsOn else "AlwaysOff"
            ),
            Cooling_Availability_Schedule_Name=(
                self.CoolingSchedule if self.CoolIsOn else None
            ),
            Maximum_Heating_Supply_Air_Temperature=self.MaxHeatSupplyAirTemp,
            Maximum_Heating_Air_Flow_Rate=self.MaxHeatFlow,
            Maximum_Sensible_Heating_Capacity=self.MaxHeatingCapacity,
            Minimum_Cooling_Supply_Air_Temperature=self.MinCoolSupplyAirTemp,
            Maximum_Cooling_Air_Flow_Rate=self.MaxCoolFlow,
            Maximum_Total_Cooling_Capacity=self.MaxCoolingCapacity,
            Heating_Limit=self.HeatingLimitType,
            Cooling_Limit=self.CoolingLimitType,
            Humidification_Control_Type="None",
            Outdoor_Air_Method="Sum" if self.MechVentIsOn else "None",
            Outdoor_Air_Flow_Rate_per_Person=self.MinFreshAirPerson
            / 1000,  # convert to m3
            Outdoor_Air_Flow_Rate_per_Zone_Floor_Area=self.MinFreshAirArea
            / 1000,  # convert to m3
            Outdoor_Air_Flow_Rate_per_Zone=0,
            Demand_Controlled_Ventilation_Type="None",
            Outdoor_Air_Economizer_Type=self.EconomizerType,
            Heat_Recovery_Type=self.HeatRecoveryType,
            Sensible_Heat_Recovery_Effectiveness=self.HeatRecoveryEfficiencySensible,
            Latent_Heat_Recovery_Effectiveness=self.HeatRecoveryEfficiencyLatent,
        )

        idf = thermostat.add(idf)
        idf = hvac_template.add(idf)
        return idf


class ZoneConstruction(
    NamedObject, ClimateStudioMetadata, extra="forbid", populate_by_name=True
):
    """Zone construction object."""

    RoofConstruction: str = Field(..., title="Roof construction object name")
    FacadeConstruction: str = Field(..., title="Facade construction object name")
    SlabConstruction: str = Field(..., title="Slab construction object name")
    PartitionConstruction: str = Field(..., title="Partition construction object name")
    ExternalFloorConstruction: str = Field(
        ..., title="External floor construction object name"
    )
    GroundSlabConstruction: str = Field(
        ..., title="Ground slab construction object name"
    )
    GroundWallConstruction: str = Field(
        ..., title="Ground wall construction object name"
    )
    InternalMassConstruction: str = Field(
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


class ZoneDefinition(NamedObject, extra="forbid"):
    """Zone definition object."""

    Loads: str = Field(..., title="Loads object name")
    Conditioning: str = Field(..., title="Conditioning object name")
    NaturalVentilation: str = Field(..., title="Natural ventilation object name")
    Constructions: str = Field(..., title="Construction object name")
    HotWater: str = Field(..., title="Hot water object name")
    Infiltration: str = Field(..., title="Infiltration object name")
    DataSource: NanStr = Field(
        ..., title="Data source of the object", validation_alias="Data Source"
    )


# InfCalculationMethodType = Literal["FlowExtArea", "ACH"]


class ZoneInfiltration(
    NamedObject, ClimateStudioMetadata, extra="forbid", populate_by_name=True
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


class WindowDefinition(NamedObject, ClimateStudioMetadata, extra="ignore"):
    """Window definition object."""

    Construction: str = Field(..., title="Construction object name")

    @property
    def schedule_names(self) -> set[str]:
        """Get the schedule names used in the object.

        Returns:
            set[str]: The schedule names.
        """
        return set()


class Foundation(BaseModel, extra="ignore"):
    """Foundation object."""

    pass


class OtherSettings(BaseModel, extra="ignore"):
    """Other settings object."""

    pass


class ZoneEnvelope(NamedObject, ClimateStudioMetadata, extra="forbid"):
    """Zone envelope object."""

    Constructions: ZoneConstruction
    Infiltration: ZoneInfiltration
    WindowDefinition: WindowDefinition | None
    WWR: float | None = Field(
        default=0.1, description="Window to wall ratio", ge=0, le=1
    )
    Foundation: Foundation | None
    OtherSettings: OtherSettings | None
    BuildingType: str | int = Field(..., title="Building type")

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


DimmingTypeType = Literal["Off", "Stepped", "Continuous"]


class ZoneLoad(
    NamedObject, ClimateStudioMetadata, extra="forbid", populate_by_name=True
):
    """Zone load object."""

    BuildingType: str | int = Field(..., title="Building type")
    PeopleDensity: float = Field(
        ...,
        title="People density [people/m²]",
        ge=0,
        validation_alias="PeopleDensity [P/m²]",
    )
    MetabolicRate: float = Field(
        ...,
        title="Metabolic rate [met]",
        ge=0,
        validation_alias="MetabolicRate [met]",
    )
    AirspeedSchedule: str = Field(
        ..., title="Airspeed schedule", validation_alias="AirspeedSchedule [m/s]"
    )
    EquipmentPowerDensity: float = Field(
        ...,
        title="Equipment power density [W/m²]",
        ge=0,
        validation_alias="EquipmentPowerDensity [W/m²]",
    )
    LightingPowerDensity: float = Field(
        ...,
        title="Lighting power density [W/m²]",
        ge=0,
        validation_alias="LightingPowerDensity [W/m²]",
    )
    IlluminanceTarget: float = Field(
        ...,
        title="Illuminance target [lux]",
        ge=0,
        validation_alias="IlluminanceTarget [Lux]",
    )
    OccupancySchedule: str = Field(..., title="Occupancy schedule")
    EquipmentAvailabilitySchedule: str = Field(
        ...,
        title="Equipment availability schedule",
        validation_alias="EquipmentAvailibilitySchedule",  # known typo in cs
    )
    LightsAvailabilitySchedule: str = Field(
        ...,
        title="Lighting availability schedule",
        validation_alias="LightsAvailibilitySchedule",  # known typo in cs
    )
    DimmingType: DimmingTypeType = Field(
        ...,
        title="Dimming type",
    )
    PeopleIsOn: BoolStr = Field(..., title="People are on")
    EquipmentIsOn: BoolStr = Field(..., title="Equipment is on")
    LightsIsOn: BoolStr = Field(..., title="Lights are on")

    @property
    def schedule_names(self) -> set[str]:
        """Get the schedule names used in the object.

        Returns:
            set[str]: The schedule names.
        """
        return {
            # self.AirspeedSchedule,
            self.OccupancySchedule,
            self.EquipmentAvailabilitySchedule,
            self.LightsAvailabilitySchedule,
        }

    @property
    def MetabolicRate_W(self):
        """Get the metabolic rate in Watts."""
        avg_human_weight_kg = 80
        conversion_factor = 1.162  # W/kg
        return self.MetabolicRate * avg_human_weight_kg * conversion_factor

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
            raise NotImplementedClimateStudioParameter(
                "DimmingType:On", self.Name, "Lights"
            )

        logger.warning(
            f"Adding lights to zone with schedule {self.LightsAvailabilitySchedule}.  Make sure this schedule exists."
        )

        logger.warning(
            f"Ignoring IlluminanceTarget for zone(s) {target_zone_or_zone_list_name}."
        )
        lights = Lights(
            Name=f"{target_zone_or_zone_list_name}_{self.Name.join('_')}_Lights",
            Zone_or_ZoneList_Name=target_zone_or_zone_list_name,
            Schedule_Name=self.LightsAvailabilitySchedule,
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
            Values=[self.MetabolicRate_W] * 8760,
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
            People_per_Floor_Area=self.PeopleDensity,
            Fraction_Radiant=0.3,
            Sensible_Heat_Fraction="autocalculate",
            Activity_Level_Schedule_Name=activity_sch_year.Name,
        )

        idf = people.add(idf)
        return idf

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
            f"Adding equipment to zone with schedule {self.EquipmentAvailabilitySchedule}.  Make sure this schedule exists."
        )

        equipment = ElectricEquipment(
            Name=f"{target_zone_or_zone_list_name}_{self.Name.join('_')}_Equipment",
            Zone_or_ZoneList_Name=target_zone_or_zone_list_name,
            Schedule_Name=self.EquipmentAvailabilitySchedule,
            Design_Level_Calculation_Method="Watts/Area",
            Watts_per_Zone_Floor_Area=self.EquipmentPowerDensity,
            Watts_per_Person=None,
            Fraction_Latent=0,
            Fraction_Radiant=0.2,
            Fraction_Lost=0,
            EndUse_Subcategory=None,
        )
        idf = equipment.add(idf)
        return idf

    def add_loads_to_idf_zone(self, idf: IDF, target_zone_name: str) -> IDF:
        """Add the loads to an IDF zone.

        This will add the people, equipment, and lights to the zone.

        nb: remember to add the schedules.

        Args:
            idf (IDF): The IDF object to add the loads to.
            target_zone_name (str): The name of the zone to add the loads to.

        Returns:
            IDF: The updated IDF object.
        """
        idf = self.add_lights_to_idf_zone(idf, target_zone_name)
        idf = self.add_people_to_idf_zone(idf, target_zone_name)
        idf = self.add_equipment_to_idf_zone(idf, target_zone_name)
        return idf


class ZoneHotWater(
    NamedObject, ClimateStudioMetadata, extra="ignore", populate_by_name=True
):
    """Zone Hot Water object."""

    @property
    def schedule_names(self) -> set[str]:
        """Get the schedule names used in the object.

        Returns:
            set[str]: The schedule names.
        """
        return set()


class ZoneUse(
    NamedObject, ClimateStudioMetadata, extra="forbid", populate_by_name=True
):
    """Zone use object."""

    Conditioning: ZoneConditioning
    Loads: ZoneLoad
    HotWater: ZoneHotWater

    def add_loads_to_idf_zone(self, idf: IDF, target_zone_name: str) -> IDF:
        """Add the loads to an IDF zone.

        This will add the people, equipment, and lights to the zone.

        nb: remember to add the schedules.

        Args:
            idf (IDF): The IDF object to add the loads to.
            target_zone_name (str): The name of the zone to add the loads to.

        Returns:
            IDF: The updated IDF object.
        """
        idf = self.Loads.add_loads_to_idf_zone(idf, target_zone_name)
        return idf

    def add_conditioning_to_idf_zone(self, idf: IDF, target_zone_name: str) -> IDF:
        """Add the conditioning to an IDF zone.

        Args:
            idf (IDF): The IDF object to add the conditioning to.
            target_zone_name (str): The name of the zone to add the conditioning to.

        Returns:
            IDF: The updated IDF object.
        """
        idf = self.Conditioning.add_conditioning_to_idf_zone(idf, target_zone_name)
        return idf

    def add_space_use_to_idf_zone(self, idf: IDF, target_zone: str | ZoneList) -> IDF:
        """Add the use to an IDF zone.

        This will add the loads and conditioning to the zone.

        Args:
            idf (IDF): The IDF object to add the use to.
            target_zone (str | ZoneList): The name of the zone to add the use to.

        Returns:
            IDF: The updated IDF object.
        """
        loads_target = target_zone if isinstance(target_zone, str) else target_zone.Name
        idf = self.add_loads_to_idf_zone(idf, loads_target)
        if isinstance(target_zone, str):
            idf = self.add_conditioning_to_idf_zone(idf, target_zone)
        else:
            for zone in target_zone.Names:
                idf = self.add_conditioning_to_idf_zone(idf, zone)
        return idf

    @property
    def schedule_names(self) -> set[str]:
        """Get the schedule names used in the object.

        Returns:
            set[str]: The schedule names.
        """
        return (
            self.Loads.schedule_names
            | self.Conditioning.schedule_names
            | self.HotWater.schedule_names
        )


NamedType = TypeVar("NamedType", bound=NamedObject)


class ClimateStudioLibraryV2(BaseModel, arbitrary_types_allowed=True):
    """Climate Studio library object."""

    SpaceUses: dict[str, ZoneUse]
    Envelopes: dict[str, ZoneEnvelope]
    GlazingConstructions: dict[str, GlazingConstructionSimple]
    OpaqueConstructions: dict[str, OpaqueConstruction]
    OpaqueMaterials: dict[str, OpaqueMaterial]
    Schedules: dict[str, Schedule]

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


class ScheduleTransferObject(BaseModel):
    """Schedule transfer object for help with de/serialization."""

    Name: str
    Type: dict
    Values: list[float]


class ClimateStudioLibraryV1(BaseModel, arbitrary_types_allowed=True):
    """Climate Studio library object."""

    # DaySchedules: dict[str, DaySchedule]
    # DomHotWater: dict[str, DomHotWater]
    # WindowSettings: dict[str, WindowSettings]
    # NaturalVentilation: dict[str, NaturalVentilation] ?
    GasMaterials: dict[str, GasMaterial]
    GlazingConstructionSimple: dict[str, GlazingConstructionSimple]
    GlazingMaterials: dict[str, GlazingMaterial]
    OpaqueMaterials: dict[str, OpaqueMaterial]
    OpaqueConstructions: dict[str, OpaqueConstruction]
    ZoneConditioning: dict[str, ZoneConditioning]
    ZoneConstruction: dict[str, ZoneConstruction]
    ZoneDefinition: dict[str, ZoneDefinition]
    ZoneInfiltration: dict[str, ZoneInfiltration]
    ZoneLoad: dict[str, ZoneLoad]
    Schedules: dict[str, Schedule]

    @classmethod
    @validate_call
    def Load(cls, base_path: Path):
        """Load a Climate Studio library from a directory.

        The directory should have all the necessary named files.

        Args:
            base_path (Path): The base path to the library directory.

        Returns:
            lib (ClimateStudioLibrary): The Climate Studio library object.
        """
        if isinstance(base_path, str):
            base_path = Path(base_path)

        gas_materials = cls.LoadObjects(base_path, GasMaterial, pluralize=True)
        glass_consts_simple = cls.LoadObjects(base_path, GlazingConstructionSimple)
        glazing_materials = cls.LoadObjects(base_path, GlazingMaterial, pluralize=True)
        opaque_materials = cls.LoadObjects(base_path, OpaqueMaterial, pluralize=True)
        opaque_consts = cls.LoadObjects(base_path, OpaqueConstruction, pluralize=True)
        zone_constructions = cls.LoadObjects(base_path, ZoneConstruction)
        zone_definitions = cls.LoadObjects(base_path, ZoneDefinition)
        zone_conditioning = cls.LoadObjects(base_path, ZoneConditioning)
        zone_infiltrations = cls.LoadObjects(base_path, ZoneInfiltration)
        zone_loads = cls.LoadObjects(base_path, ZoneLoad)

        year_schs = pd.read_csv(base_path / "YearSchedules.csv", dtype=str)
        sch_names = year_schs.columns
        schedules_list = [extract_sch(year_schs, sch_name) for sch_name in sch_names]
        schedules = {sch.Name: sch for sch in schedules_list}
        if len(schedules) != len(schedules_list):
            raise ClimateStudioLibraryDuplicatesFound("Schedules")

        return cls(
            GasMaterials=gas_materials,
            GlazingConstructionSimple=glass_consts_simple,
            GlazingMaterials=glazing_materials,
            OpaqueMaterials=opaque_materials,
            OpaqueConstructions=opaque_consts,
            ZoneConditioning=zone_conditioning,
            ZoneConstruction=zone_constructions,
            ZoneDefinition=zone_definitions,
            ZoneInfiltration=zone_infiltrations,
            ZoneLoad=zone_loads,
            Schedules=schedules,
        )

    @classmethod
    def LoadObjects(
        cls, base_path: Path, obj_class: type[NamedType], pluralize: bool = False
    ) -> dict[str, NamedType]:
        """Handles deserializing a ClimateStudio CSV to the appropriate class.

        Args:
            base_path (Path): The base path to the library directory.
            obj_class (Type[NamedObject]): The class to deserialize to.
            pluralize (bool, optional): Whether to pluralize the filename. Defaults to False.

        Returns:
            dict[str, NamedObject]: The deserialized objects.
        """
        df = pd.read_csv(
            base_path / f"{obj_class.__name__}{'s' if pluralize else ''}.csv"
        )
        data = df.to_dict(orient="records")
        obj_list = [obj_class.model_validate(d) for d in data]
        obj_dict = {obj.Name: obj for obj in obj_list}
        if len(obj_dict) != len(obj_list):
            raise ClimateStudioLibraryDuplicatesFound(obj_class.__name__)
        return obj_dict


def extract_sch(year_schedules: pd.DataFrame, schedule_name: str) -> Schedule:
    """Extract a schedule from a climate studio schedule dataframe.

    Args:
        year_schedules (pd.DataFrame): Dataframe of year schedules
        schedule_name (str): Name of the schedule

    Returns:
        Schedule: Extracted schedule
    """
    sched_meta = year_schedules.head(5)
    sched_meta.index = pd.Index([
        "Type",
        "Periodicity",
        "Category",
        "Data Source",
        "Comment",
    ])
    meta = sched_meta[schedule_name]
    sched_type = cast(str, meta["Type"])
    last_ix = (
        8760
        if meta["Periodicity"] == "FullYear"
        else (
            24 * 7
            if meta["Periodicity"] == "RepeatingWeek"
            else (24 if meta["Periodicity"] == "RepeatingDay" else 1)
        )
    )
    sched = year_schedules[schedule_name]
    sched_vals = sched.iloc[5:]
    sched_vals = np.array(sched_vals[:last_ix].astype(float).values)
    if len(sched_vals) not in [1, 24, 24 * 7, 8760]:
        raise ScheduleParseError(schedule_name)
    if sched_type.lower() not in [
        "fraction",
        "temperature",
        "any number",
        "anynumber",
        "on/off",
    ]:
        raise ScheduleParseError(f"{schedule_name}:{meta['Type']}")
    if sched_type.lower() in ["any number", "anynumber"]:
        meta["Type"] = ScheduleTypeLimits(
            Name=meta["Type"], LowerLimit=None, UpperLimit=None
        )
    n_repeats_needed = 8760 // len(sched_vals) + 1
    repeated_schedule = np.tile(sched_vals, n_repeats_needed)[:8760]
    sched = Schedule.from_values(
        Name=schedule_name,
        Values=repeated_schedule.tolist(),
        Type=meta["Type"],  # pyright: ignore [reportArgumentType]
    )
    return sched


if __name__ == "__main__":
    from pathlib import Path

    import pandas as pd

    base_path = Path("D:/climatestudio/default")

    lib = ClimateStudioLibraryV1.Load(base_path)
