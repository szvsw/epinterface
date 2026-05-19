"""Interface for EnergyPlus IDF objects."""

from collections.abc import Sequence
from logging import getLogger
from typing import Annotated, Any, ClassVar, Literal

import numpy as np
from archetypal.idfclass import IDF
from archetypal.schedule import Schedule
from pydantic import (
    BaseModel,
    BeforeValidator,
    Field,
    ValidationError,
    computed_field,
    field_validator,
    model_validator,
)

from epinterface.settings import energyplus_settings

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self  # noqa: UP035

logger = getLogger(__name__)


class BaseObj(BaseModel):
    """Base class for EnergyPlus IDF objects.

    The class should be inherited by all EnergyPlus IDF objects. It provides
    methods to add and extract objects from an IDF object.
    """

    key: ClassVar[str]

    def add(self, idf: IDF):
        """Add the object to the IDF object.

        Args:
            idf (IDF): The IDF object to add the object to.

        Returns:
            idf (IDF): The updated IDF object.
        """
        idf.newidfobject(self.key, **self.model_dump())
        return idf

    @classmethod
    def extract(cls, idf: IDF) -> Sequence[Self]:
        """Extract objects from an IDF object.

        Args:
            idf (IDF): The IDF object to extract objects from.

        Returns:
            objs (list[BaseObj]): A list of objects extracted from the IDF object.
        """
        objs = idf.idfobjects[cls.key]
        try:
            return [cls(**obj) for obj in objs]
        except ValidationError:
            return [cls(**obj.to_dict()) for obj in objs]


class ScheduleTypeLimits(BaseObj, extra="ignore"):
    """ScheduleTypeLimits object."""

    key: ClassVar[str] = "SCHEDULETYPELIMITS"
    Name: str
    Lower_Limit_Value: float | None = None
    Upper_Limit_Value: float | None = None
    Numeric_Type: Literal["Continuous", "Discrete"] | None = None
    Unit_Type: (
        Literal[
            "Dimensionless",
            "Temperature",
            "DeltaTemperature",
            "PrecipitationRate",
            "Angle",
            "ConvectionCoefficient",
            "ActivityLevel",
            "Velocity",
            "Capacity",
            "Power",
            "Availability",
            "Percent",
            "Control",
            "Mode",
        ]
        | None
    ) = None


class SimulationControl(BaseObj, extra="ignore"):
    """SimulationControl object."""

    key: ClassVar[str] = "SIMULATIONCONTROL"
    Do_Zone_Sizing_Calculation: Literal["Yes", "No"] = "Yes"
    Do_System_Sizing_Calculation: Literal["Yes", "No"] = "Yes"
    Do_Plant_Sizing_Calculation: Literal["Yes", "No"] = "Yes"
    Run_Simulation_for_Sizing_Periods: Literal["Yes", "No"] = "Yes"
    Run_Simulation_for_Weather_File_Run_Periods: Literal["Yes", "No"] = "Yes"
    Do_HVAC_Sizing_Simulation_for_Sizing_Periods: Literal["Yes", "No"] = "Yes"
    Maximum_Number_of_HVAC_Sizing_Simulation_Passes: int = 1


class RunPeriod(BaseObj, extra="ignore"):
    """RunPeriod object."""

    key: ClassVar[str] = "RUNPERIOD"
    Name: str
    Begin_Month: int
    Begin_Day_of_Month: int
    Begin_Year: int | None = None
    End_Month: int
    End_Day_of_Month: int
    End_Year: int | None = None
    Day_of_Week_for_Start_Day: Literal[
        "Sunday",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
    ] = "Sunday"
    Use_Weather_File_Daylight_Saving_Period: Literal["Yes", "No"] = "No"
    Use_Weather_File_Holidays_and_Special_Days: Literal["Yes", "No"] = "No"
    Apply_Weekend_Holiday_Rule: Literal["Yes", "No"] = "Yes"
    Use_Weather_File_Rain_Indicators: Literal["Yes", "No"] = "No"
    Use_Weather_File_Snow_Indicators: Literal["Yes", "No"] = "No"


class Timestep(BaseObj, extra="ignore"):
    """Timestep object."""

    key: ClassVar[str] = "TIMESTEP"
    Number_of_Timesteps_per_Hour: int = 6


class SizingParameters(BaseObj, extra="ignore"):
    """SizingParameters object."""

    key: ClassVar[str] = "SIZING:PARAMETERS"
    Heating_Sizing_Factor: float
    Cooling_Sizing_Factor: float


class SiteGroundTemperature(BaseObj, extra="ignore"):
    """GroundTemperature object."""

    key: ClassVar[str] = "SITE:GROUNDTEMPERATURE:BUILDINGSURFACE"
    January_Ground_Temperature: float
    February_Ground_Temperature: float
    March_Ground_Temperature: float
    April_Ground_Temperature: float
    May_Ground_Temperature: float
    June_Ground_Temperature: float
    July_Ground_Temperature: float
    August_Ground_Temperature: float
    September_Ground_Temperature: float
    October_Ground_Temperature: float
    November_Ground_Temperature: float
    December_Ground_Temperature: float

    @classmethod
    def FromValues(cls, values: list[float]):
        """Create a new SiteGroundTemperature object from a list of 12 monthly values.

        Args:
            values (list[float]): A list of 12 monthly values.

        Returns:
            ground_temp (SiteGroundTemperature): The new SiteGroundTemperature object.
        """
        if len(values) != 12:
            raise ValueError(f"GROUNDTEMP:EXPECTED_12:RECEIVED_{len(values)}")
        return cls(
            January_Ground_Temperature=values[0],
            February_Ground_Temperature=values[1],
            March_Ground_Temperature=values[2],
            April_Ground_Temperature=values[3],
            May_Ground_Temperature=values[4],
            June_Ground_Temperature=values[5],
            July_Ground_Temperature=values[6],
            August_Ground_Temperature=values[7],
            September_Ground_Temperature=values[8],
            October_Ground_Temperature=values[9],
            November_Ground_Temperature=values[10],
            December_Ground_Temperature=values[11],
        )


class InternalMass(BaseObj, extra="ignore"):
    """InternalMass object."""

    key: ClassVar[str] = "INTERNALMASS"
    Name: str
    Zone_or_ZoneList_Name: str
    Construction_Name: str
    Surface_Area: float


class BaseMaterial(BaseModel, extra="ignore", populate_by_name=True):
    """A base material object for storing material definitions.

    Note that this is not an EnergyPlus object, but a base class for creating new
    material objects which can be turned into EP objects once assigned thicknesses.
    """

    Name: str
    Roughness: str
    Conductivity: float = Field(..., ge=0, validation_alias="Conductivity [W/m.K]")
    Density: float = Field(..., ge=0, validation_alias="Density [kg/m3]")
    Specific_Heat: float = Field(..., ge=0, validation_alias="SpecificHeat [J/kg.K]")
    Thermal_Absorptance: float | None = Field(
        default=None, validation_alias="ThermalAbsorptance [0-1]", ge=0, le=1
    )
    Solar_Absorptance: float | None = Field(
        default=None, validation_alias="SolarAbsorptance [0-1]", ge=0, le=1
    )
    Visible_Absorptance: float | None = Field(
        default=None, validation_alias="VisibleAbsorptance [0-1]", ge=0, le=1
    )

    def as_layer(self, thickness: float):
        """Create a new material object with a given thickness.

        Args:
            thickness (float): The thickness of the material.

        Returns:
            mat (Material): The new material object with the given thickness.
        """
        name = f"{self.Name}_{thickness}m"
        return Material(
            Name=name, Thickness=thickness, **self.model_dump(exclude={"Name"})
        )


wood = BaseMaterial(
    # also see:
    # https://www.engineersedge.com/heat_transfer/thermal_properties_13785.htm
    # https://www.researchgate.net/figure/Specific-heat-and-density-of-the-wood-stud-composite-layer-advanced-framing_tbl5_332911394
    # https://thermalenvelope.ca/pdf/material_data_sheet_8.6.2.pdf?version=v1.7.3
    Name="Wood",
    Roughness="MediumSmooth",
    Density=540,
    Conductivity=0.12,
    Specific_Heat=1210,
    Thermal_Absorptance=0.9,
    Solar_Absorptance=0.7,
    Visible_Absorptance=0.7,
)
gypsum = BaseMaterial(
    Name="Gypsum",
    Roughness="Rough",
    Conductivity=0.15862,
    Density=640,
    Specific_Heat=1129.6,
    Thermal_Absorptance=0.9,
    Solar_Absorptance=0.4,
    Visible_Absorptance=0.1,
)
drywall = BaseMaterial(
    Name="Drywall",
    Roughness="MediumSmooth",
    Conductivity=0.16009,
    Density=800,
    Specific_Heat=1087.8,
)
osb = BaseMaterial(
    Name="OSB",
    Roughness="MediumSmooth",
    Conductivity=0.1163,
    Density=544,
    Specific_Heat=1213,
)
concrete = BaseMaterial(
    Name="Concrete",
    Roughness="Rough",
    Conductivity=1.312098,
    Density=2242,
    Specific_Heat=465.2,
)
insulation = BaseMaterial(
    Name="Insulation",
    Roughness="MediumRough",
    Conductivity=0.04,
    Density=32,
    Specific_Heat=836,
    Thermal_Absorptance=0.9,
    Solar_Absorptance=0.7,
    Visible_Absorptance=0.7,
)
stucco = BaseMaterial(
    Name="Stucco",
    Roughness="MediumSmooth",
    Conductivity=0.721,
    Density=1865,
    Specific_Heat=878,
)


class DefaultMaterialLibrary(BaseModel):
    """Default material library for storing some common material defs."""

    wood: BaseMaterial = wood
    gypsum: BaseMaterial = gypsum
    drywall: BaseMaterial = drywall
    osb: BaseMaterial = osb
    concrete: BaseMaterial = concrete
    insulation: BaseMaterial = insulation
    stucco: BaseMaterial = stucco


class Material(BaseObj, BaseMaterial, extra="ignore"):
    """Material object."""

    key: ClassVar[str] = "MATERIAL"
    Name: str
    Thickness: float

    @field_validator("Thermal_Absorptance", mode="before")
    def str_cast(cls, v):
        """Cast the value to a float if it is a string or empty.

        Args:
            v (Any): The value to cast.

        Returns:
            v (float): The casted value.
        """
        if v == "" or v is None:
            return None
        return float(v)

    @property
    def r(self):
        """Return the R of the material."""
        return self.Thickness / self.Conductivity


class SimpleGlazingMaterial(BaseObj, extra="ignore"):
    """SimpleGlazingMaterial object."""

    key: ClassVar[str] = "WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM"
    Name: str
    UFactor: float
    Solar_Heat_Gain_Coefficient: float
    Visible_Transmittance: float


class AirGapMaterial(BaseObj, extra="ignore"):
    """AirGapMaterial object."""

    key: ClassVar[str] = "MATERIAL:AIRGAP"
    Name: str
    Thermal_Resistance: float


class NoMassMaterial(BaseObj, extra="ignore"):
    """NoMassMaterial object."""

    key: ClassVar[str] = "MATERIAL:NOMASS"
    Name: str
    Roughness: str
    Thermal_Resistance: float


class Construction(BaseObj, extra="ignore"):
    """Construction object."""

    key: ClassVar[str] = "CONSTRUCTION"
    name: str
    layers: Sequence[Material | AirGapMaterial | SimpleGlazingMaterial | NoMassMaterial]

    @property
    def r_value(self):
        """Return the R-value of the construction.

        Computed using the formula: R = sum(thickness_i / conductivity_i)

        Returns:
            r (float): The R-value of the construction (units: m^2.K/W).
        """
        return (
            sum([layer.r for layer in self.layers if isinstance(layer, Material)])
            + sum([
                layer.Thermal_Resistance
                for layer in self.layers
                if isinstance(layer, AirGapMaterial)
            ])
            + sum([
                layer.Thermal_Resistance
                for layer in self.layers
                if isinstance(layer, NoMassMaterial)
            ])
            + sum([
                1 / layer.UFactor
                for layer in self.layers
                if isinstance(layer, SimpleGlazingMaterial)
            ])
        )

    @classmethod
    def extract(cls, idf: IDF):
        """Extract objects from an IDF object.

        Args:
            idf (IDF): The IDF object to extract objects from.

        Returns:
            constructions (list[Construction]): A list of objects extracted from the IDF object.
        """
        constructions = idf.idfobjects["CONSTRUCTION"]
        res: list[Construction] = []
        for construction in constructions:
            const_dict = construction.to_dict()
            layer_names = [
                const_dict[key]
                for key in [
                    "Outside_Layer",
                    "Layer_2",
                    "Layer_3",
                    "Layer_4",
                    "Layer_5",
                    "Layer_6",
                    "Layer_7",
                    "Layer_8",
                    "Layer_9",
                    "Layer_10",
                ]
                if key in const_dict
            ]

            layer_names = [n for n in layer_names if n != "" and n]
            material_defs = [
                idf.getobject("MATERIAL", name) for name in layer_names
            ]  # TODO: handle air layers
            airgap_material_defs = [
                idf.getobject("MATERIAL:AIRGAP", name) for name in layer_names
            ]
            simple_glazing_material_defs = [
                idf.getobject("WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM", name)
                for name in layer_names
            ]
            no_mass_material_defs = [
                idf.getobject("MATERIAL:NOMASS", name) for name in layer_names
            ]
            materials = [Material(**m.to_dict()) if m else None for m in material_defs]
            airgap_materials = [
                AirGapMaterial(**m.to_dict()) if m else None
                for m in airgap_material_defs
            ]
            simple_glazing_materials = [
                SimpleGlazingMaterial(**m.to_dict()) if m else None
                for m in simple_glazing_material_defs
            ]
            nomass_materials = [
                NoMassMaterial(**m.to_dict()) if m else None
                for m in no_mass_material_defs
            ]

            layers = [
                m if m else (n if n else (o if o else p))
                for m, n, o, p in zip(
                    materials,
                    airgap_materials,
                    simple_glazing_materials,
                    nomass_materials,
                    strict=False,
                )
            ]

            valid_layers = [layer for layer in layers if layer is not None]
            if len(valid_layers) != len(layers):
                logger.warning(
                    f"Construction {construction.Name} has missing layers. "
                    f"Expected {len(layers)} layers, got {len(valid_layers)}."
                    f"Skipping construction extraction."
                )
                continue
            construction = cls(name=construction.Name, layers=valid_layers)
            res.append(construction)
        return res

    def add(self, idf: IDF):
        """Add the object to the IDF object.

        Args:
            idf (IDF): The IDF object to add the object to.

        Returns:
            idf (IDF): The updated IDF object.
        """
        for layer in self.layers:
            idf = layer.add(idf)
        idf.newidfobject(
            self.key,
            Name=self.name,
            **{
                (f"Layer_{i + 1}" if i != 0 else "Outside_Layer"): layer.Name
                for i, layer in enumerate(self.layers)
            },
        )
        return idf


IdealLoadsLimitType = Literal[
    "NoLimit", "LimitFlowRate", "LimitCapacity", "LimitFlowRateAndCapacity"
]


DehumidificationControlTypeType = Literal[
    "ConstantSensibleHeatRatio", "Humidistat", "None", "ConstantSupplyHumidityRatio"
]


HumidificationControlTypeType = Literal[
    "None", "Humidistat", "ConstantSupplyHumidityRatio"
]


OutdoorAirMethodType = Literal[
    "None",
    "Flow/Person",
    "Flow/Area",
    "Flow/Zone",
    "Sum",
    "Maximum",
    "DetailedSpecification",
]


DemandControlledVentilationTypeType = Literal[
    "None", "OccupancySchedule", "CO2Setpoint"
]
OutdoorAirEconomizerTypeType = Literal[
    "NoEconomizer", "DifferentialDryBulb", "DifferentialEnthalpy"
]


HeatRecoveryTypeType = Annotated[
    Literal["None", "Sensible", "Enthalpy"],
    BeforeValidator(
        lambda x: (
            x
            if isinstance(x, str)
            else ("None" if x is None else ("None" if np.isnan(x) else x))
        )
    ),
]

# TODO: convert templates into BaseObjs?
# TODO: Schedule referencing more richly?

ThermostatType = Literal[
    "SingleHeating", "SingleCooling", "SingleHeatingOrCooling", "DualSetpoint"
]


class HVACTemplateThermostat(BaseModel):
    """HVACTemplateThermostat object."""

    Name: str
    Heating_Setpoint_Schedule_Name: str | None = None
    Constant_Heating_Setpoint: float | None = 21
    Cooling_Setpoint_Schedule_Name: str | None = None
    Constant_Cooling_Setpoint: float | None = 24

    def add(self, idf: IDF):
        """Add the object to the IDF object.

        Args:
            idf (IDF): The IDF object to add the object to.

        Returns:
            idf (IDF): The updated IDF object
        """
        idf.newidfobject("HVACTEMPLATE:THERMOSTAT", **self.model_dump())
        return idf


class HVACTemplateZoneIdealLoadsAirSystem(BaseModel):
    """HVACTemplateZoneIdealLoadsAirSystem object."""

    Zone_Name: str
    Template_Thermostat_Name: str
    System_Availability_Schedule_Name: str | None = None
    Heating_Availability_Schedule_Name: str | None = None
    Cooling_Availability_Schedule_Name: str | None = None
    Maximum_Heating_Supply_Air_Temperature: float = 30
    Minimum_Cooling_Supply_Air_Temperature: float = 18
    Maximum_Heating_Supply_Air_Humidity_Ratio: float = 0.0156
    Minimum_Cooling_Supply_Air_Humidity_Ratio: float = 0.0077
    Heating_Limit: IdealLoadsLimitType = "NoLimit"
    Maximum_Heating_Air_Flow_Rate: float | None | Literal["autosize"] = None
    Maximum_Sensible_Heating_Capacity: float | None | Literal["autosize"] = None
    Cooling_Limit: IdealLoadsLimitType = "NoLimit"
    Maximum_Cooling_Air_Flow_Rate: float | None | Literal["autosize"] = None
    Maximum_Total_Cooling_Capacity: float | None | Literal["autosize"] = None
    Dehumidification_Control_Type: DehumidificationControlTypeType = "None"
    Cooling_Sensible_Heat_Ratio: float = 0.7
    Dehumidification_Setpoint: float = 60
    Humidification_Control_Type: HumidificationControlTypeType = "None"
    Humidification_Setpoint: float = 30
    Outdoor_Air_Method: OutdoorAirMethodType = "None"
    Outdoor_Air_Flow_Rate_per_Person: float = 0.00944
    Outdoor_Air_Flow_Rate_per_Zone_Floor_Area: float = 0.00025
    Outdoor_Air_Flow_Rate_per_Zone: float = 0.0
    # Design_Specification_Outdoor_Air_Object_Name: Optional[str] = None
    Demand_Controlled_Ventilation_Type: DemandControlledVentilationTypeType = "None"
    Outdoor_Air_Economizer_Type: OutdoorAirEconomizerTypeType = "NoEconomizer"
    Heat_Recovery_Type: HeatRecoveryTypeType = "None"
    Sensible_Heat_Recovery_Effectiveness: float = 0.7
    Latent_Heat_Recovery_Effectiveness: float = 0.65

    def add(self, idf: IDF):
        """Add the object to the IDF object.

        Args:
            idf (IDF): The IDF object to add the object to.

        Returns:
            idf (IDF): The updated IDF object
        """
        idf.newidfobject("HVACTEMPLATE:ZONE:IDEALLOADSAIRSYSTEM", **self.model_dump())
        return idf


DesignLevelCalculationMethodType = Literal["Watts/Area", "Watts/Person", "Watts"]


def _energyplus_version_gte(major: float) -> bool:
    """Return True if configured EnergyPlus version is >= major (e.g. 24.0)."""
    try:
        return energyplus_settings.archetypal_energyplus_version.major >= major
    except (ValueError, IndexError):
        return False


# TODO: add water mains?
class WaterUseEquipment(BaseObj, extra="ignore"):
    """WaterUseEquipment object."""

    key: ClassVar[str] = "WATERUSE:EQUIPMENT"
    Name: str
    EndUse_Subcategory: str | None = None
    Peak_Flow_Rate: float
    Flow_Rate_Fraction_Schedule_Name: str | None = None
    Target_Temperature_Schedule_Name: str | None = None
    Hot_Water_Supply_Temperature_Schedule_Name: str | None = None
    Cold_Water_Supply_Temperature_Schedule_Name: str | None = None
    Zone_Name: str | None = None
    Sensible_Fraction_Schedule_Name: str | None = None
    Latent_Fraction_Schedule_Name: str | None = None


class ElectricEquipment(BaseObj, extra="ignore"):
    """ElectricEquipment object."""

    key: ClassVar[str] = "ELECTRICEQUIPMENT"
    Name: str
    Zone_or_ZoneList_Name: str
    Schedule_Name: str
    Design_Level_Calculation_Method: DesignLevelCalculationMethodType = "Watts/Area"
    Design_Level: float | None = None
    Watts_per_Zone_Floor_Area: float | None = None
    Watts_per_Person: float | None = None
    Fraction_Latent: float = 0.00
    Fraction_Radiant: float = 0.2
    Fraction_Lost: float = 0
    EndUse_Subcategory: str | None = None

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Dump model to dict; use Watts_per_Floor_Area alias when EnergyPlus >= 24.0."""
        data = super().model_dump(**kwargs)
        if _energyplus_version_gte(24.0) and "Watts_per_Zone_Floor_Area" in data:
            data["Watts_per_Floor_Area"] = data.pop("Watts_per_Zone_Floor_Area")
        return data


class Lights(BaseObj, extra="ignore"):
    """Lights object."""

    key: ClassVar[str] = "LIGHTS"
    Name: str
    Zone_or_ZoneList_Name: str
    Schedule_Name: str
    Design_Level_Calculation_Method: DesignLevelCalculationMethodType = "Watts/Area"
    Lighting_Level: float | None = None
    Watts_per_Zone_Floor_Area: float | None = None
    Watts_per_Person: float | None = None
    Return_Air_Fraction: float = 0
    Fraction_Radiant: float = 0.42
    Fraction_Visible: float = 0.18
    Fraction_Replaceable: float | None = 1
    EndUse_Subcategory: str | None = None

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Dump model to dict; use Watts_per_Floor_Area alias when EnergyPlus >= 24.0."""
        data = super().model_dump(**kwargs)
        if _energyplus_version_gte(24.0) and "Watts_per_Zone_Floor_Area" in data:
            data["Watts_per_Floor_Area"] = data.pop("Watts_per_Zone_Floor_Area")
        return data


InfDesignFlowRateCalculationMethodType = Literal[
    "Flow/Zone",
    "Flow/Area",
    "Flow/ExteriorArea",
    "Flow/ExteriorWallArea",
    "AirChanges/Hour",
]
VentDesignFlowRateCalculationMethodType = Literal[
    "Flow/Zone", "Flow/Area", "Flow/Person", "AirChanges/Hour"
]

VentilationType = Literal["Natural", "Exhaust", "Intake", "Balanced"]


class ZoneVentilationWindAndStackOpenArea(BaseObj, extra="ignore"):
    """ZoneVentilationWindAndStackOpenArea object."""

    key: ClassVar[str] = "ZONEVENTILATION:WINDANDSTACKOPENAREA"
    Name: str
    Zone_or_Space_Name: str
    Opening_Area: float
    Opening_Area_Fraction_Schedule_Name: str
    Opening_Effectiveness: str = "AutoCalculate"
    Effective_Angle: float = 0
    Height_Difference: float
    Discharge_Coefficient_for_Opening: str = "AutoCalculate"
    Minimum_Indoor_Temperature: float | None = None
    Minimum_Indoor_Temperature_Schedule_Name: str | None = None
    Maximum_Indoor_Temperature: float | None = None
    Maximum_Indoor_Temperature_Schedule_Name: str | None = None
    Delta_Temperature: float | None = None
    Delta_Temperature_Schedule_Name: str | None = None
    Minimum_Outdoor_Temperature: float | None = None
    Minimum_Outdoor_Temperature_Schedule_Name: str | None = None
    Maximum_Outdoor_Temperature: float | None = None
    Maximum_Outdoor_Temperature_Schedule_Name: str | None = None
    Maximum_Wind_Speed: float = 40


class ZoneInfiltrationDesignFlowRate(BaseObj, extra="ignore"):
    """ZoneInfiltrationDesignFlowRate object."""

    key: ClassVar[str] = "ZONEINFILTRATION:DESIGNFLOWRATE"
    Name: str
    Zone_or_ZoneList_Name: str
    Schedule_Name: str
    Design_Flow_Rate_Calculation_Method: InfDesignFlowRateCalculationMethodType
    Design_Flow_Rate: float | None = None
    Flow_Rate_per_Floor_Area: float | None = None
    Flow_Rate_per_Exterior_Surface_Area: float | None = None
    Air_Changes_per_Hour: float | None = None
    # Constant_Term_Coefficient: float = 0.606
    # Temperature_Term_Coefficient: float = 3.6359996e-2
    # Velocity_Term_Coefficient: float = 0.117765
    Constant_Term_Coefficient: float = 1  # updated to assume that we have the actual infiltration values - the more detailed coefficient methodology would likely overestimate the infiltration rate, as there are many days where the tmperature deltas exceeds 10 degrees.
    Temperature_Term_Coefficient: float = 0
    Velocity_Term_Coefficient: float = 0
    Velocity_Squared_Term_Coefficient: float = (
        0  # updated as we don't make assumptions about the wind velocity
    )


def _filter_idd_fields(
    idf: IDF, object_type: str, fields: dict[str, Any]
) -> dict[str, Any]:
    """Keep only fields present on the IDF object for this EnergyPlus version."""
    valid = set(idf.anidfobject(object_type).fieldnames)
    return {k: v for k, v in fields.items() if k in valid}


AFNControl = Literal[
    "MultizoneWithDistribution",
    "MultizoneWithoutDistribution",
    "MultizoneWithDistributionOnlyDuringFanOperation",
    "NoMultizoneOrDistribution",
]
WPCType = Literal["Input", "SurfaceAverageCalculation"]
HeightSelection = Literal["ExternalNode", "OpeningHeight"]
BuildingType = Literal["LowRise", "HighRise"]
InitializationType = Literal["LinearInitializationMethod", "ZeroNodePressures"]
HeightDependence = Literal["Yes", "No"]
AllowUnsupportedZoneEquipment = Literal["Yes", "No"]


class AirflowNetworkSimulationControl(BaseModel):
    """AirflowNetwork:SimulationControl — unique top-level controller.

    Sets the multizone simulation mode and the wind-pressure-coefficient source.
    Only one of these may exist in the IDF.
    """

    Name: str = Field(default="AFN_Control", title="Name")
    AirflowNetwork_Control: AFNControl = Field(
        default="MultizoneWithoutDistribution",
        title="AirflowNetwork Control",
        description="Multizone-only mode: pressure network solved across zones; no ducts.",
    )
    Wind_Pressure_Coefficient_Type: WPCType = Field(
        default="SurfaceAverageCalculation",
        title="Wind Pressure Coefficient Type",
        description=(
            "SurfaceAverageCalculation: EnergyPlus computes Cp from Swami-Chandra "
            "for low-rise rectangular buildings. Input: user-provided Cp arrays."
        ),
    )
    Height_Selection_for_Local_Wind_Pressure_Calculation: HeightSelection = Field(
        default="OpeningHeight",
        title="Height Selection for Local Wind Pressure Calculation",
    )
    Building_Type: BuildingType = Field(default="LowRise", title="Building Type")
    Maximum_Number_of_Iterations: int = Field(
        default=500, title="Maximum Number of Iterations", ge=1, le=30000
    )
    Initialization_Type: InitializationType = Field(
        default="ZeroNodePressures", title="Initialization Type"
    )
    Relative_Airflow_Convergence_Tolerance: float = Field(
        default=1.0e-4, title="Relative Airflow Convergence Tolerance", gt=0
    )
    Absolute_Airflow_Convergence_Tolerance: float = Field(
        default=1.0e-6, title="Absolute Airflow Convergence Tolerance", gt=0
    )
    Convergence_Acceleration_Limit: float = Field(
        default=-0.5,
        title="Convergence Acceleration Limit",
        ge=-1.0,
        le=1.0,
    )
    Azimuth_Angle_of_Long_Axis_of_Building: float = Field(
        default=0.0,
        title="Azimuth Angle of Long Axis of Building [deg]",
        ge=0.0,
        le=180.0,
    )
    Ratio_of_Building_Width_Along_Short_Axis_to_Width_Along_Long_Axis: float = Field(
        default=0.5,
        title="Ratio of Building Width Along Short Axis to Width Along Long Axis",
        gt=0.0,
        le=1.0,
        description="For SurfaceAverageCalculation Cp model.",
    )
    Height_Dependence_of_External_Node_Temperature: HeightDependence = Field(
        default="No",
        title="Height Dependence of External Node Temperature",
    )
    Allow_Unsupported_Zone_Equipment: AllowUnsupportedZoneEquipment = Field(
        default="No", title="Allow Unsupported Zone Equipment"
    )

    def add(self, idf):
        """Add this object to the IDF. Returns the updated IDF."""
        key = "AIRFLOWNETWORK:SIMULATIONCONTROL"
        fields = _filter_idd_fields(
            idf, key, {k: v for k, v in self.model_dump().items() if v is not None}
        )
        idf.newidfobject(key, **fields)
        return idf


VentilationControlMode = Literal[
    "Temperature",
    "Enthalpy",
    "Constant",
    "ASHRAE55Adaptive",
    "CEN15251Adaptive",
    "NoVent",
    "ZoneLevel",  # surface-only; falls through to zone setting
    "AdjacentTemperature",
    "AdjacentEnthalpy",
]

EquivalentRectangleMethod = Literal[
    "PolygonHeight", "BaseSurfaceAspectRatio", "UserDefinedAspectRatio"
]


class AirflowNetworkMultiZoneZone(BaseModel):
    """AirflowNetwork:MultiZone:Zone — per-thermal-zone AFN declaration.

    Use Ventilation_Control_Mode='Constant' to drive opening behavior entirely
    from per-surface schedules (the operational input the surrogate consumes).
    """

    Zone_Name: str = Field(..., title="Zone Name")
    Ventilation_Control_Mode: VentilationControlMode = Field(
        default="Constant", title="Ventilation Control Mode"
    )
    Ventilation_Control_Zone_Temperature_Setpoint_Schedule_Name: str | None = Field(
        default=None,
        title="Ventilation Control Zone Temperature Setpoint Schedule Name",
    )
    Minimum_Venting_Open_Factor: float = Field(
        default=0.0, title="Minimum Venting Open Factor", ge=0.0, le=1.0
    )
    Indoor_and_Outdoor_Temperature_Difference_Lower_Limit_For_Maximum_Venting_Open_Factor: float = Field(
        default=0.0,
        title="Indoor/Outdoor T Difference Lower Limit for Max Venting Open Factor [deltaC]",
        ge=0.0,
        le=100.0,
    )
    Indoor_and_Outdoor_Temperature_Difference_Upper_Limit_for_Minimum_Venting_Open_Factor: float = Field(
        default=100.0,
        title="Indoor/Outdoor T Difference Upper Limit for Min Venting Open Factor [deltaC]",
        gt=0.0,
        le=100.0,
    )
    Indoor_and_Outdoor_Enthalpy_Difference_Lower_Limit_For_Maximum_Venting_Open_Factor: float = Field(
        default=0.0,
        title="Indoor/Outdoor h Difference Lower Limit for Max Venting Open Factor [J/kg]",
        ge=0.0,
        le=300000.0,
    )
    Indoor_and_Outdoor_Enthalpy_Difference_Upper_Limit_for_Minimum_Venting_Open_Factor: float = Field(
        default=300000.0,
        title="Indoor/Outdoor h Difference Upper Limit for Min Venting Open Factor [J/kg]",
        gt=0.0,
        le=300000.0,
    )
    Venting_Availability_Schedule_Name: str | None = Field(
        default=None, title="Venting Availability Schedule Name"
    )
    Single_Sided_Wind_Pressure_Coefficient_Algorithm: Literal[
        "Standard", "Advanced"
    ] = Field(
        default="Standard", title="Single Sided Wind Pressure Coefficient Algorithm"
    )
    Facade_Width: float = Field(default=10.0, title="Facade Width [m]", ge=0.0)
    Occupant_Ventilation_Control_Name: str | None = Field(
        default=None, title="Occupant Ventilation Control Name"
    )

    def add(self, idf):
        """Add this object to the IDF. Returns the updated IDF."""
        key = "AIRFLOWNETWORK:MULTIZONE:ZONE"
        fields = _filter_idd_fields(
            idf, key, {k: v for k, v in self.model_dump().items() if v is not None}
        )
        idf.newidfobject(key, **fields)
        return idf


class AirflowNetworkMultiZoneSurface(BaseModel):
    """AirflowNetwork:MultiZone:Surface — per-surface flow path.

    One per AFN linkage: window, doorway, or envelope crack.
    """

    Surface_Name: str = Field(..., title="Surface Name")
    Leakage_Component_Name: str = Field(..., title="Leakage Component Name")
    External_Node_Name: str | None = Field(
        default=None,
        title="External Node Name",
        description="Blank when WPC type is SurfaceAverageCalculation.",
    )
    Window_or_Door_Opening_Factor_or_Crack_Factor: float = Field(
        default=1.0,
        title="Window/Door Opening Factor, or Crack Factor",
        ge=0.0,
        le=1.0,
    )
    Ventilation_Control_Mode: VentilationControlMode = Field(
        default="ZoneLevel",
        title="Ventilation Control Mode (surface override)",
    )
    Ventilation_Control_Zone_Temperature_Setpoint_Schedule_Name: str | None = Field(
        default=None,
        title="Ventilation Control Zone Temperature Setpoint Schedule Name",
    )
    Minimum_Venting_Open_Factor: float = Field(
        default=0.0, title="Minimum Venting Open Factor", ge=0.0, le=1.0
    )
    Indoor_and_Outdoor_Temperature_Difference_Lower_Limit_For_Maximum_Venting_Open_Factor: float = Field(
        default=0.0,
        title="Indoor/Outdoor T Diff Lower Limit for Max Venting [deltaC]",
        ge=0.0,
        le=100.0,
    )
    Indoor_and_Outdoor_Temperature_Difference_Upper_Limit_for_Minimum_Venting_Open_Factor: float = Field(
        default=100.0,
        title="Indoor/Outdoor T Diff Upper Limit for Min Venting [deltaC]",
        gt=0.0,
        le=100.0,
    )
    Indoor_and_Outdoor_Enthalpy_Difference_Lower_Limit_For_Maximum_Venting_Open_Factor: float = Field(
        default=0.0,
        title="Indoor/Outdoor h Diff Lower Limit for Max Venting [J/kg]",
        ge=0.0,
        le=300000.0,
    )
    Indoor_and_Outdoor_Enthalpy_Difference_Upper_Limit_for_Minimum_Venting_Open_Factor: float = Field(
        default=300000.0,
        title="Indoor/Outdoor h Diff Upper Limit for Min Venting [J/kg]",
        gt=0.0,
        le=300000.0,
    )
    Venting_Availability_Schedule_Name: str | None = Field(
        default=None,
        title="Venting Availability Schedule Name",
        description="The per-opening time series — the operational input the surrogate consumes.",
    )
    Occupant_Ventilation_Control_Name: str | None = Field(
        default=None, title="Occupant Ventilation Control Name"
    )
    Equivalent_Rectangle_Method: EquivalentRectangleMethod = Field(
        default="PolygonHeight", title="Equivalent Rectangle Method"
    )
    Equivalent_Rectangle_Aspect_Ratio: float = Field(
        default=1.0, title="Equivalent Rectangle Aspect Ratio", gt=0.0
    )

    def add(self, idf):
        """Add this object to the IDF. Returns the updated IDF."""
        key = "AIRFLOWNETWORK:MULTIZONE:SURFACE"
        fields = _filter_idd_fields(
            idf, key, {k: v for k, v in self.model_dump().items() if v is not None}
        )
        idf.newidfobject(key, **fields)
        return idf


class AirflowNetworkMultiZoneReferenceCrackConditions(BaseModel):
    """AirflowNetwork:MultiZone:ReferenceCrackConditions.

    Reference T/P/RH at which crack flow coefficients are defined; EnergyPlus
    rescales the coefficient to the actual zone air conditions at runtime.
    """

    Name: str = Field(default="ReferenceCrackConditions", title="Name")
    Reference_Temperature: float = Field(
        default=20.0, title="Reference Temperature [degC]", ge=-273.15
    )
    Reference_Barometric_Pressure: float = Field(
        default=101325.0,
        title="Reference Barometric Pressure [Pa]",
        ge=31000.0,
        le=120000.0,
    )
    Reference_Humidity_Ratio: float = Field(
        default=0.0, title="Reference Humidity Ratio [kgWater/kgDryAir]", ge=0.0
    )

    def add(self, idf):
        """Add this object to the IDF. Returns the updated IDF."""
        key = "AIRFLOWNETWORK:MULTIZONE:REFERENCECRACKCONDITIONS"
        fields = _filter_idd_fields(idf, key, self.model_dump())
        idf.newidfobject(key, **fields)
        return idf


class AirflowNetworkMultiZoneSurfaceCrack(BaseModel):
    """AirflowNetwork:MultiZone:Surface:Crack — power-law leakage component.

    m_dot = C * (dP)^n at reference conditions.
    """

    Name: str = Field(..., title="Name")
    Air_Mass_Flow_Coefficient_at_Reference_Conditions: float = Field(
        ...,
        title="Air Mass Flow Coefficient at Reference Conditions [kg/s @ 1 Pa]",
        gt=0.0,
    )
    Air_Mass_Flow_Exponent: float = Field(
        default=0.65, title="Air Mass Flow Exponent", ge=0.5, le=1.0
    )
    Reference_Crack_Conditions: str | None = Field(
        default=None,
        title="Reference Crack Conditions",
        description="Name of an AirflowNetwork:MultiZone:ReferenceCrackConditions object.",
    )

    def add(self, idf):
        """Add this object to the IDF. Returns the updated IDF."""
        key = "AIRFLOWNETWORK:MULTIZONE:SURFACE:CRACK"
        fields = _filter_idd_fields(
            idf, key, {k: v for k, v in self.model_dump().items() if v is not None}
        )
        idf.newidfobject(key, **fields)
        return idf


LVOType = Literal["NonPivoted", "HorizontallyPivoted"]


class AirflowNetworkMultiZoneComponentDetailedOpening(BaseModel):
    """AirflowNetwork:MultiZone:Component:DetailedOpening — operable openings.

    Two opening factors (closed + fully open). The DetailedOpening object in
    EnergyPlus supports up to 4 opening factors, but 2 is the simplest and
    sufficient for v0.

    The width/height factors at each opening factor define the effective open
    area:  open_area = surface_area * width_factor * height_factor.
    """

    Name: str = Field(..., title="Name")
    Air_Mass_Flow_Coefficient_When_Opening_is_Closed: float = Field(
        default=0.001,
        title="Air Mass Flow Coefficient When Opening is Closed [kg/s-m @ 1 Pa]",
        gt=0.0,
    )
    Air_Mass_Flow_Exponent_When_Opening_is_Closed: float = Field(
        default=0.65,
        title="Air Mass Flow Exponent When Opening Is Closed",
        ge=0.5,
        le=1.0,
    )
    Type_of_Rectangular_Large_Vertical_Opening: LVOType = Field(
        default="NonPivoted",
        title="Type of Rectangular Large Vertical Opening (LVO)",
    )
    Extra_Crack_Length_or_Height_of_Pivoting_Axis: float = Field(
        default=0.0,
        title="Extra Crack Length or Height of Pivoting Axis [m]",
        ge=0.0,
    )
    Number_of_Sets_of_Opening_Factor_Data: int = Field(
        default=2, title="Number of Sets of Opening Factor Data", ge=2, le=4
    )
    Opening_Factor_1: float = Field(
        default=0.0, title="Opening Factor 1", ge=0.0, le=1.0
    )
    Discharge_Coefficient_for_Opening_Factor_1: float = Field(
        default=0.001,
        title="Discharge Coefficient for Opening Factor 1",
        gt=0.0,
        le=1.0,
    )
    Width_Factor_for_Opening_Factor_1: float = Field(
        default=0.0, title="Width Factor for Opening Factor 1", ge=0.0, le=1.0
    )
    Height_Factor_for_Opening_Factor_1: float = Field(
        default=1.0, title="Height Factor for Opening Factor 1", ge=0.0, le=1.0
    )
    Start_Height_Factor_for_Opening_Factor_1: float = Field(
        default=0.0, title="Start Height Factor for Opening Factor 1", ge=0.0, le=1.0
    )
    Opening_Factor_2: float = Field(
        default=1.0, title="Opening Factor 2", ge=0.0, le=1.0
    )
    Discharge_Coefficient_for_Opening_Factor_2: float = Field(
        default=0.6,
        title="Discharge Coefficient for Opening Factor 2",
        gt=0.0,
        le=1.0,
    )
    Width_Factor_for_Opening_Factor_2: float = Field(
        default=1.0, title="Width Factor for Opening Factor 2", ge=0.0, le=1.0
    )
    Height_Factor_for_Opening_Factor_2: float = Field(
        default=0.5,
        title="Height Factor for Opening Factor 2",
        ge=0.0,
        le=1.0,
        description="Half the window height opens (typical double-hung).",
    )
    Start_Height_Factor_for_Opening_Factor_2: float = Field(
        default=0.0, title="Start Height Factor for Opening Factor 2", ge=0.0, le=1.0
    )

    def add(self, idf):
        """Add this object to the IDF. Returns the updated IDF."""
        key = "AIRFLOWNETWORK:MULTIZONE:COMPONENT:DETAILEDOPENING"
        fields = _filter_idd_fields(
            idf, key, {k: v for k, v in self.model_dump().items() if v is not None}
        )
        idf.newidfobject(key, **fields)
        return idf


NumberOfPeopleCalculationMethodType = Literal["People", "People/Area", "Area/Person"]


class People(BaseObj, extra="ignore"):
    """People object."""

    key: ClassVar[str] = "PEOPLE"
    Name: str
    Zone_or_ZoneList_Name: str
    Number_of_People_Schedule_Name: str
    Number_of_People_Calculation_Method: NumberOfPeopleCalculationMethodType
    Number_of_People: float | None = None
    People_per_Floor_Area: float | None = None
    Floor_Area_per_Person: float | None = None
    Fraction_Radiant: float = 0.3
    Sensible_Heat_Fraction: float | Literal["autocalculate"] = "autocalculate"
    Activity_Level_Schedule_Name: str
    # Carbon_Dioxide_Generation_Rate: Optional[float] = None
    Enable_ASHRAE_55_Comfort_Warnings: Literal["Yes", "No"] = "No"
    # Cold_Stress_Temperature_Threshold: float = 15.56
    # Heat_Stress_Temperature_Threshold: float = 30.0
    # Mean_Radiant_Temperature_Calculation_Type: Literal["ZoneAveraged", "EnclosureAveraged"]
    # Surface_Name_Angle_Factor_List_Name: str
    # Work_Efficiency_Schedule_Name: str
    # Clothing_Insulation_Calculation_Method: str
    # Clothing_Insulation_Calculation_Method_Schedule_Name: str
    # Clothing_Insulation_Schedule_Name: str
    # Air_Velocity_Schedule_Name: str
    # Thermal_Comfort_Model_Type: str


class ScheduleDayHourly(BaseObj, extra="ignore"):
    """ScheduleDayHourly object."""

    key: ClassVar[str] = "SCHEDULE:DAY:HOURLY"
    Name: str
    Schedule_Type_Limits_Name: str
    Hour_1: float
    Hour_2: float
    Hour_3: float
    Hour_4: float
    Hour_5: float
    Hour_6: float
    Hour_7: float
    Hour_8: float
    Hour_9: float
    Hour_10: float
    Hour_11: float
    Hour_12: float
    Hour_13: float
    Hour_14: float
    Hour_15: float
    Hour_16: float
    Hour_17: float
    Hour_18: float
    Hour_19: float
    Hour_20: float
    Hour_21: float
    Hour_22: float
    Hour_23: float
    Hour_24: float


class ScheduleWeekDaily(BaseObj, extra="ignore"):
    """ScheduleWeekDaily object."""

    key: ClassVar[str] = "SCHEDULE:WEEK:DAILY"
    Name: str
    Monday_ScheduleDay_Name: str
    Tuesday_ScheduleDay_Name: str
    Wednesday_ScheduleDay_Name: str
    Thursday_ScheduleDay_Name: str
    Friday_ScheduleDay_Name: str
    Saturday_ScheduleDay_Name: str
    Sunday_ScheduleDay_Name: str
    SummerDesignDay_ScheduleDay_Name: str | None = None
    WinterDesignDay_ScheduleDay_Name: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _validate_design_day_schedules(cls, data):
        if data.get("SummerDesignDay_ScheduleDay_Name") is None:
            data["SummerDesignDay_ScheduleDay_Name"] = data["Monday_ScheduleDay_Name"]
        if data.get("WinterDesignDay_ScheduleDay_Name") is None:
            data["WinterDesignDay_ScheduleDay_Name"] = data["Monday_ScheduleDay_Name"]
        return data

    @computed_field
    @property
    def CustomDay1_ScheduleDay_Name(self) -> str:
        """Automatically set additional day schedules."""
        return self.Monday_ScheduleDay_Name

    @computed_field
    @property
    def CustomDay2_ScheduleDay_Name(self) -> str:
        """Automatically set additional day schedules."""
        return self.Monday_ScheduleDay_Name

    @computed_field
    @property
    def Holiday_ScheduleDay_Name(self) -> str:
        """Automatically set additional day schedules."""
        return self.Sunday_ScheduleDay_Name


class ScheduleYear(BaseObj, extra="ignore"):
    """ScheduleYear object."""

    key: ClassVar[str] = "SCHEDULE:YEAR"
    Name: str
    Schedule_Type_Limits_Name: str

    ScheduleWeek_Name_1: str
    Start_Month_1: int
    Start_Day_1: int
    End_Month_1: int
    End_Day_1: int

    ScheduleWeek_Name_2: str | None = None
    Start_Month_2: int | None = None
    Start_Day_2: int | None = None
    End_Month_2: int | None = None
    End_Day_2: int | None = None

    ScheduleWeek_Name_3: str | None = None
    Start_Month_3: int | None = None
    Start_Day_3: int | None = None
    End_Month_3: int | None = None
    End_Day_3: int | None = None

    ScheduleWeek_Name_4: str | None = None
    Start_Month_4: int | None = None
    Start_Day_4: int | None = None
    End_Month_4: int | None = None
    End_Day_4: int | None = None

    ScheduleWeek_Name_5: str | None = None
    Start_Month_5: int | None = None
    Start_Day_5: int | None = None
    End_Month_5: int | None = None
    End_Day_5: int | None = None

    ScheduleWeek_Name_6: str | None = None
    Start_Month_6: int | None = None
    Start_Day_6: int | None = None
    End_Month_6: int | None = None
    End_Day_6: int | None = None

    ScheduleWeek_Name_7: str | None = None
    Start_Month_7: int | None = None
    Start_Day_7: int | None = None
    End_Month_7: int | None = None
    End_Day_7: int | None = None

    ScheduleWeek_Name_8: str | None = None
    Start_Month_8: int | None = None
    Start_Day_8: int | None = None
    End_Month_8: int | None = None
    End_Day_8: int | None = None

    ScheduleWeek_Name_9: str | None = None
    Start_Month_9: int | None = None
    Start_Day_9: int | None = None
    End_Month_9: int | None = None
    End_Day_9: int | None = None

    ScheduleWeek_Name_10: str | None = None
    Start_Month_10: int | None = None
    Start_Day_10: int | None = None
    End_Month_10: int | None = None
    End_Day_10: int | None = None

    ScheduleWeek_Name_11: str | None = None
    Start_Month_11: int | None = None
    Start_Day_11: int | None = None
    End_Month_11: int | None = None
    End_Day_11: int | None = None

    ScheduleWeek_Name_12: str | None = None
    Start_Month_12: int | None = None
    Start_Day_12: int | None = None
    End_Month_12: int | None = None
    End_Day_12: int | None = None


class ZoneList(BaseModel, extra="ignore"):
    """ZoneList object."""

    Name: str
    Names: list[str]

    def add(self, idf: IDF):
        """Add the object to the IDF object.

        Args:
            idf (IDF): The IDF object to add the object to.

        Returns:
            idf (IDF): The updated IDF object.
        """
        names = {
            f"Zone_{i + 1}_Name": zone for i, zone in enumerate(self.Names) if zone
        }
        idf.newidfobject("ZONELIST", Name=self.Name, **names)
        return idf


def add_default_sim_controls(idf: IDF) -> IDF:
    """Helper to add default simulation controls to the IDF model.

    Args:
        idf (IDF): The IDF model to add the simulation controls to.

    Returns:
        IDF: The IDF model with the added simulation controls.
    """
    # Configure simulation
    sim_control = SimulationControl(
        Do_Zone_Sizing_Calculation="Yes",
        Do_System_Sizing_Calculation="Yes",
        Do_Plant_Sizing_Calculation="No",
        Run_Simulation_for_Sizing_Periods="Yes",
        Run_Simulation_for_Weather_File_Run_Periods="Yes",
        Do_HVAC_Sizing_Simulation_for_Sizing_Periods="Yes",
        Maximum_Number_of_HVAC_Sizing_Simulation_Passes=2,
    )
    sim_control.add(idf)

    # Configure run period
    run_period = RunPeriod(
        Name="Year",
        Use_Weather_File_Daylight_Saving_Period="No",
        Use_Weather_File_Rain_Indicators="No",
        Use_Weather_File_Snow_Indicators="No",
        Use_Weather_File_Holidays_and_Special_Days="No",
        Begin_Month=1,
        Begin_Day_of_Month=1,
        End_Month=12,
        End_Day_of_Month=31,
        Day_of_Week_for_Start_Day="Sunday",
    )
    run_period.add(idf)

    # configure timestep
    timestep = Timestep(
        Number_of_Timesteps_per_Hour=6,
    )
    timestep.add(idf)

    sizing = SizingParameters(
        Heating_Sizing_Factor=1.15,
        Cooling_Sizing_Factor=1.15,
    )
    sizing.add(idf)

    return idf


def add_default_schedules(idf: IDF) -> tuple[IDF, dict[str, Schedule]]:
    """Helper to add default schedules to the IDF model.

    Args:
        idf (IDF): The IDF model to add the schedules to.

    Returns:
        idf (IDF): The IDF model with the added schedules.
        scheds (dict[str, Schedule]): A dictionary of the added schedules.
    """
    # create constant scheds
    all_scheds: dict[str, Schedule] = {}
    always_on_schedule = Schedule.constant_schedule(Name="Always_On", value=1)
    always_off_schedule = Schedule.constant_schedule(Name="Always_Off", value=0)
    all_scheds["Always_On"] = always_on_schedule
    all_scheds["Always_Off"] = always_off_schedule
    year, *_ = always_on_schedule.to_year_week_day()
    year.to_epbunch(idf)
    year, *_ = always_off_schedule.to_year_week_day()
    year.to_epbunch(idf)

    always_on_schedule = Schedule.constant_schedule(Name="Always On", value=1)
    always_off_schedule = Schedule.constant_schedule(Name="Always Off", value=0)
    all_scheds["Always On"] = always_on_schedule
    all_scheds["Always Off"] = always_off_schedule
    year, *_ = always_on_schedule.to_year_week_day()
    year.to_epbunch(idf)
    year, *_ = always_off_schedule.to_year_week_day()
    year.to_epbunch(idf)

    always_on_schedule = Schedule.constant_schedule(Name="On", value=1)
    always_off_schedule = Schedule.constant_schedule(Name="Off", value=0)
    all_scheds["On"] = always_on_schedule
    all_scheds["Off"] = always_off_schedule
    year, *_ = always_on_schedule.to_year_week_day()
    year.to_epbunch(idf)
    year, *_ = always_off_schedule.to_year_week_day()
    year.to_epbunch(idf)

    always_on_schedule = Schedule.constant_schedule(Name="AllOn", value=1)
    always_off_schedule = Schedule.constant_schedule(Name="AllOff", value=0)
    all_scheds["AllOn"] = always_on_schedule
    all_scheds["AllOff"] = always_off_schedule
    year, *_ = always_on_schedule.to_year_week_day()
    year.to_epbunch(idf)
    year, *_ = always_off_schedule.to_year_week_day()
    year.to_epbunch(idf)

    always_on_schedule = Schedule.constant_schedule(Name="AlwaysOn", value=1)
    always_off_schedule = Schedule.constant_schedule(Name="AlwaysOff", value=0)
    all_scheds["AlwaysOn"] = always_on_schedule
    all_scheds["AlwaysOff"] = always_off_schedule
    year, *_ = always_on_schedule.to_year_week_day()
    year.to_epbunch(idf)
    year, *_ = always_off_schedule.to_year_week_day()
    year.to_epbunch(idf)

    return idf, all_scheds


PROTECTED_SCHEDULE_NAMES = {
    "Always_On",
    "Always_Off",
    "Always On",
    "Always Off",
    "AlwaysOn",
    "AlwaysOff",
    "On",
    "Off",
    "AllOn",
    "AllOff",
}
