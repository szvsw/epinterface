"""Materials for the SBEM library."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from epinterface.sbem.common import MetadataMixin, NamedObject


# TODO: Add this to the template format? Leaving here for flexibility for now
class EnvironmentalMixin(BaseModel):
    """Environmental data for a SBEM template table object."""

    Cost: float | None = Field(
        default=None,
        title="Cost of material",
        ge=0,
        description="Expected cost of the material per unit",
    )
    RateUnit: Literal["m3", "m2", "m", "kg"] | None = Field(
        default=None,
        title="Rate unit",
        description="The base unit for cost and embodied carbon, i.e. $/unit",
    )
    Life: float | None = Field(
        default=None,
        title="Life [years]",
        ge=0,
        description="Expected lifetime of the material",
    )
    EmbodiedCarbon: float | None = Field(
        default=None,
        title="Embodied carbon [kgCO2e/unit]",
        ge=0,
        description="Expected embodied carbon of the material per unit",
    )


class StandardMaterialMetadataMixin(EnvironmentalMixin, MetadataMixin):
    """Standard metadata for a SBEM data."""

    pass


# TODO: remove? feels redundant
class CommonMaterialPropertiesMixin(BaseModel):
    """Common material properties for glazing and opaque materials."""

    Conductivity: float = Field(
        ...,
        title="Conductivity [W/mK]",
        description="Conductivity property of the material at standard conditions",
        ge=0,
    )
    Density: float = Field(
        ...,
        title="Density [kg/m3]",
        description="Density property of the material at standard conditions",
        ge=0,
    )


ConstructionComponentSurfaceType = Literal[
    "FlatRoof",
    "AtticRoof",
    "AtticFloor",
    "Facade",
    "FloorCeiling",
    "Partition",
    "ExternalFloor",
    "ExteriorFloor",
    "GroundSlab",
    "GroundWall",
    "BasementCeiling",
    "InternalMass",
    "InteriorFloor",
]


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

MaterialRoughness = Literal[
    "VeryRough",
    "Rough",
    "MediumRough",
    "MediumSmooth",
    "Smooth",
    "VerySmooth",
]


class ConstructionMaterialProperties(
    CommonMaterialPropertiesMixin,
    extra="forbid",
):
    """Properties of an opaque material in a construction component."""

    # add in the commonMaterialsPropertis
    Roughness: MaterialRoughness = Field(
        ...,
        title="Roughness of the opaque material",
        description="Roughness property of the material as defined by EnergyPlus",
    )
    SpecificHeat: float = Field(
        ...,
        title="Specific heat [J/kgK]",
        description="Specific heat property of the material",
        ge=0,
    )
    ThermalAbsorptance: float = Field(
        ...,
        title="Thermal absorptance",
        description="Thermal absorptance property of the material, between 0 and 1",
        ge=0,
        le=1,
    )
    SolarAbsorptance: float = Field(
        ...,
        title="Solar absorptance",
        description="Solar absorptance property of the material, between 0 and 1",
        ge=0,
        le=1,
    )
    VisibleAbsorptance: float = Field(
        ...,
        title="Visible absorptance",
        description="Visible absorptance property of the material, between 0 and 1",
        ge=0,
        le=1,
    )

    TemperatureCoefficientThermalConductivity: float = Field(
        ...,
        # a superscript 2 looks like this:
        title="Temperature coefficient [W/m.K2²]",
        description="Temperature coefficient of thermal conductivity property of the material",
        ge=0,
    )

    # model validator to check if material properties are larger than 0
    @model_validator(mode="after")
    def check_material_properties(self):
        """Check that material properties are larger than 0."""
        if self.Conductivity <= 0:
            msg = "Conductivity must be larger than 0"
            raise ValueError(msg)
        if self.Density <= 0:
            msg = "Density must be larger than 0"
            raise ValueError(msg)
        if self.ThermalAbsorptance <= 0:
            msg = "Thermal absorptance must be larger than 0"
            raise ValueError(msg)
        if self.SolarAbsorptance <= 0:
            msg = "Solar absorptance must be larger than 0"
            raise ValueError(msg)
        if self.VisibleAbsorptance <= 0:
            msg = "Visible absorptance must be larger than 0"
            raise ValueError(msg)
        return self

    Type: ConstructionMaterialType = Field(..., title="Type of the opaque material")


class ConstructionMaterialComponent(
    ConstructionMaterialProperties,
    StandardMaterialMetadataMixin,
    NamedObject,
    MetadataMixin,
    extra="forbid",
):
    """Construction material object."""

    pass
