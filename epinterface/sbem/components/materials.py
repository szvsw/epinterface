"""Materials for the SBEM library."""

from typing import Literal

from pydantic import AliasChoices, BaseModel, Field

from epinterface.sbem.common import MetadataMixin, NamedObject


# TODO: Add this to the template format? Leaving here for flexibility for now
class EnvironmentalMixin(BaseModel):
    """Environmental data for a SBEM template table object."""

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
            "Cost [$/mÃ]",
        ),
        ge=0,
    )
    Life: float = Field(
        ...,
        title="Life [years]",
        validation_alias="Life [yr]",
        ge=0,
    )
    EmbodiedCarbon: float = Field(
        ...,
        title="Embodied carbon [kgCO2e/unit]",
        # a superscript 3 looks like this:
        validation_alias=AliasChoices(
            "Embodied carbon [kgCO2e/m³]",
            "Embodied carbon [kgCO2e/m3]",
            "Embodied carbon [kgCO2e/m²]",
            "Embodied carbon [kgCO2e/m2]",
            "Embodied carbon [kgCO2e/m]",
            "Embodied carbon [kgCO2e/kg]",
        ),
        ge=0,
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


ConstructionComponentSurfaceType = Literal[
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


class MaterialWithThickness(BaseModel, populate_by_name=True):
    """Material with a thickness."""

    Thickness: float = Field(
        ...,
        title="Thickness of the material [m]",
        validation_alias="Thickness [m]",
        ge=0,
    )


class ConstructionMaterialProperties(
    CommonMaterialPropertiesMixin, populate_by_name=True
):
    """Properties of an opaque material."""

    # add in the commonMaterialsPropertis
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

    TemperatureCoefficientThermalConductivity: float = Field(
        ...,
        # a superscript 2 looks like this:
        title="Temperature coefficient of thermal conductivity [W/m.K2²]",
        ge=0,
        validation_alias="TemperatureCoefficientThermalConductivity [W/m-K2]",
    )
    # TODO: material type should be dynamic user entry or enum
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

    Type: ConstructionMaterialType = Field(
        ..., title="Type of the opaque material", validation_alias="Type [enum]"
    )


class ConstructionMaterialComponent(
    ConstructionMaterialProperties,
    StandardMaterialMetadataMixin,
    NamedObject,
    MetadataMixin,
    extra="forbid",
):
    """Construction material object."""

    pass
