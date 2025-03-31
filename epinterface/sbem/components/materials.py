"""Materials for the SBEM library."""

from typing import Literal

from pydantic import BaseModel, Field

from epinterface.sbem.common import MetadataMixin, NamedObject


# TODO: Add this to the template format? Leaving here for flexibility for now
class EnvironmentalMixin(BaseModel):
    """Environmental data for a SBEM template table object."""

    Cost: float | None = Field(
        default=None, title="Cost", ge=0, description="Cost of the material/unit"
    )
    RateUnit: Literal["m3", "m2", "m", "kg"] | None = Field(
        default=None,
        description="The base unit for cost and embodied carbon, i.e. $/unit",
    )
    Life: float | None = Field(
        default=None, title="Life [years]", ge=0, description="Life of the material"
    )
    EmbodiedCarbon: float | None = Field(
        default=None, title="Embodied carbon [kgCO2e/unit]", ge=0
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
        ge=0,
    )
    Density: float = Field(
        ...,
        title="Density [kg/m3]",
        ge=0,
    )


ConstructionComponentSurfaceType = Literal[
    "FlatRoof",
    "AtticRoof",
    "AtticFloor",
    "Facade",
    "Slab",
    "Partition",
    "ExternalFloor",
    "ExteriorFloor",
    "GroundSlab",
    "GroundWall",
    "BasementCeiling",
    "GroundFloor",
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


class ConstructionMaterialProperties(
    CommonMaterialPropertiesMixin,
    extra="forbid",
):
    """Properties of an opaque material."""

    # add in the commonMaterialsPropertis
    Roughness: str = Field(..., title="Roughness of the opaque material")
    SpecificHeat: float = Field(
        ...,
        title="Specific heat [J/kgK]",
        ge=0,
    )
    ThermalAbsorptance: float = Field(
        ...,
        title="Thermal absorptance [0-1]",
        ge=0,
        le=1,
    )
    SolarAbsorptance: float = Field(
        ...,
        title="Solar absorptance [0-1]",
        ge=0,
        le=1,
    )
    VisibleAbsorptance: float = Field(
        ...,
        title="Visible absorptance [0-1]",
        ge=0,
        le=1,
    )

    TemperatureCoefficientThermalConductivity: float = Field(
        ...,
        # a superscript 2 looks like this:
        title="Temperature coefficient of thermal conductivity [W/m.K2²]",
        ge=0,
    )
    # TODO: material type should be dynamic user entry or enum
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
