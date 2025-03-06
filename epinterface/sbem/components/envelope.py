"""Envelope components for the SBEM library."""

from typing import Literal

from archetypal.idfclass import IDF
from archetypal.schedule import Schedule
from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator

from epinterface.interface import (
    Construction,
    InfDesignFlowRateCalculationMethodType,
    Material,
    SimpleGlazingMaterial,
    ZoneInfiltrationDesignFlowRate,
)
from epinterface.sbem.common import BoolStr, MetadataMixin, NamedObject, NanStr
from epinterface.sbem.components.materials import (
    ConstructionComponentSurfaceType,
    ConstructionMaterialComponent,
    StandardMaterialMetadataMixin,
)

# CONSTRUCTION CLASSES


# TODO: why is this a class? shouldn't thickness just be an attribute in the material consutruction class?


WindowType = Literal["Single", "Double", "Triple"]


class GlazingConstructionSimpleComponent(
    NamedObject,
    StandardMaterialMetadataMixin,
    MetadataMixin,
    extra="forbid",
    populate_by_name=True,
):
    """Glazing construction object."""

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


class InfiltrationComponent(
    NamedObject, MetadataMixin, extra="forbid", populate_by_name=True
):
    """Zone infiltration object."""

    # TODO: add assumed_constants
    IsOn: BoolStr = Field(..., title="Infiltration is on")
    ConstantCoefficient: float = Field(
        ...,
        title="Infiltration constant coefficient",
    )
    TemperatureCoefficient: float = Field(
        ...,
        title="Infiltration temperature coefficient",
    )
    WindVelocityCoefficient: float = Field(
        ...,
        title="Infiltration wind velocity coefficient",
    )
    WindVelocitySquaredCoefficient: float = Field(
        ...,
        title="Infiltration wind velocity squared coefficient",
    )
    AFNAirMassFlowCoefficientCrack: float = Field(
        ...,
        title="AFN air mass flow coefficient crack",
    )

    AirChangesPerHour: float = Field(
        ...,
        title="Infiltration air changes per hour [ACH]",
        ge=0,
    )
    FlowPerExteriorSurfaceArea: float = Field(
        ...,
        title="Infiltration flow per exterior surface area [m3/s/m2]",
        ge=0,
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
        if not self.IsOn:
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
            Flow_Rate_per_Exterior_Surface_Area=self.FlowPerExteriorSurfaceArea,
            Air_Changes_per_Hour=self.AirChangesPerHour,
            Flow_Rate_per_Floor_Area=None,
            Design_Flow_Rate=None,
            Constant_Term_Coefficient=self.ConstantCoefficient,
            Temperature_Term_Coefficient=self.TemperatureCoefficient,
            Velocity_Term_Coefficient=self.WindVelocityCoefficient,
            Velocity_Squared_Term_Coefficient=self.WindVelocitySquaredCoefficient,
        )
        idf = inf.add(idf)
        return idf


class ConstructionLayerComponent(BaseModel):
    """Layer of an opaque construction."""

    Thickness: float = Field(..., title="Thickness of the layer [m]")
    LayerOrder: int
    ConstructionMaterial: ConstructionMaterialComponent

    @property
    def name(self):
        """Return the name of the layer."""
        return f"{self.LayerOrder}_{self.ConstructionMaterial.Name}_{self.Thickness}m"

    @property
    def ep_material(self):
        """Return the EP material for the layer."""
        return Material(
            Name=self.name,
            Thickness=self.Thickness,
            Conductivity=self.ConstructionMaterial.Conductivity,
            Density=self.ConstructionMaterial.Density,
            Specific_Heat=self.ConstructionMaterial.SpecificHeat,
            Thermal_Absorptance=self.ConstructionMaterial.ThermalAbsorptance,
            Solar_Absorptance=self.ConstructionMaterial.SolarAbsorptance,
            Roughness=self.ConstructionMaterial.Roughness,
            Visible_Absorptance=self.ConstructionMaterial.VisibleAbsorptance,
        )


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
    Type: ConstructionComponentSurfaceType = Field(
        ..., title="Type of the opaque construction"
    )

    @field_validator("Layers", mode="after")
    def validate_layers(cls, v: list[ConstructionLayerComponent]):
        """Validate the layers of the construction."""
        if len(v) == 0:
            msg = "At least one layer is required"
            raise ValueError(msg)
        layer_orders = [layer.LayerOrder for layer in v]
        if set(layer_orders) != set(range(0, len(v))):
            msg = "Layer orders must be consecutive integers starting from 0"
            raise ValueError(msg)
        v = sorted(v, key=lambda x: x.LayerOrder)
        return v

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
        layers = [layer.ep_material for layer in self.Layers]

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

    RoofAssembly: ConstructionAssemblyComponent = Field(
        ..., title="Roof construction object name"
    )
    FacadeAssembly: ConstructionAssemblyComponent = Field(
        ..., title="Facade construction object name"
    )
    SlabAssembly: ConstructionAssemblyComponent = Field(
        ..., title="Slab construction object name"
    )
    PartitionAssembly: ConstructionAssemblyComponent = Field(
        ..., title="Partition construction object name"
    )
    ExternalFloorAssembly: ConstructionAssemblyComponent = Field(
        ..., title="External floor construction object name"
    )
    GroundSlabAssembly: ConstructionAssemblyComponent = Field(
        ..., title="Ground slab construction object name"
    )
    GroundWallAssembly: ConstructionAssemblyComponent = Field(
        ..., title="Ground wall construction object name"
    )
    InternalMassAssembly: ConstructionAssemblyComponent | None = Field(
        ..., title="Internal mass construction object name"
    )
    InternalMassExposedAreaPerArea: float | None = Field(
        ...,
        title="Internal mass exposed area per area [m²/m²]",
        validation_alias="InternalMassExposedAreaPerArea [area / floor (m2/m2)]",
        ge=0,
    )
    GroundIsAdiabatic: BoolStr = Field(..., title="Ground is adiabatic")
    RoofIsAdiabatic: BoolStr = Field(..., title="Roof is adiabatic")
    FacadeIsAdiabatic: BoolStr = Field(..., title="Facade is adiabatic")
    SlabIsAdiabatic: BoolStr = Field(..., title="Slab is adiabatic")
    PartitionIsAdiabatic: BoolStr = Field(..., title="Partition is adiabatic")

    @model_validator(mode="after")
    def validate_internal_mass_exposed_area_per_area(self):
        """Validate that either both internal mass assembly and internal mass exposed area are provided, or neither."""
        if self.InternalMassAssembly and self.InternalMassExposedAreaPerArea is None:
            msg = "Internal mass assembly must be provided if internal mass exposed area per area is provided"
            raise ValueError(msg)
        if (
            self.InternalMassExposedAreaPerArea is not None
            and self.InternalMassAssembly is None
        ):
            msg = "Internal mass exposed area per area must be provided if internal mass assembly is provided"
            raise ValueError(msg)
        return self


class ZoneEnvelopeComponent(NamedObject, MetadataMixin, extra="forbid"):
    """Zone envelope object."""

    Assemblies: EnvelopeAssemblyComponent
    Infiltration: InfiltrationComponent
    Window: GlazingConstructionSimpleComponent | None

    # Foundation: Foundation | None
    # OtherSettings: OtherSettings | None


# TODO: add envelope to idf zone
# (currently in builder)
