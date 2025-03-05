"""Envelope components for the SBEM library."""

from typing import Literal

from archetypal.idfclass import IDF
from archetypal.schedule import Schedule
from pydantic import AliasChoices, Field

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
    MaterialWithThickness,
    StandardMaterialMetadataMixin,
)
from epinterface.sbem.exceptions import ValueNotFound

# CONSTRUCTION CLASSES


# construction helper function
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
        ConstructionLayerComponent(Name=name, Thickness=thickness)
        for name, thickness in zip(names, thicknesses, strict=False)
    ]


# TODO: why is this a class? shouldn't thickness just be an attribute in the material consutruction class?
class ConstructionLayerComponent(
    MaterialWithThickness, MetadataMixin, NamedObject, extra="forbid"
):
    """Layer of an opaque construction."""

    def dereference_to_material(
        self, material_defs: dict[str, ConstructionMaterialComponent]
    ) -> Material:
        """Converts a referenced material into a direct EP material object.

        Args:
            material_defs (list[OpaqueMaterial]): List of opaque material definitions.

        Returns:
            Material: The material object.
        """
        if self.Name not in material_defs:
            raise ValueNotFound("Material", self.Name)

        mat_def = material_defs[self.Name]

        material = Material(
            Name=f"{self.Name}_{self.Thickness}",
            Thickness=self.Thickness,
            Conductivity=mat_def.Conductivity,
            Density=mat_def.Density,
            Specific_Heat=mat_def.SpecificHeat,
            Thermal_Absorptance=mat_def.ThermalAbsorptance,
            Solar_Absorptance=mat_def.SolarAbsorptance,
            Roughness=mat_def.Roughness,
        )
        return material


class GlazingConstructionSimpleComponent(
    NamedObject,
    StandardMaterialMetadataMixin,
    MetadataMixin,
    extra="forbid",
    populate_by_name=True,
):
    """Glazing construction object."""

    WindowType = Literal["Single", "Double", "Triple"]
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
        layers = [layer.dereference_to_material(material_defs) for layer in self.Layers]

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

    RoofAssembly: str = Field(..., title="Roof construction object name")
    FacadeAssembly: str = Field(..., title="Facade construction object name")
    SlabAssembly: str = Field(..., title="Slab construction object name")
    PartitionAssembly: str = Field(..., title="Partition construction object name")
    ExternalFloorAssembly: str = Field(
        ..., title="External floor construction object name"
    )
    GroundSlabAssembly: str = Field(..., title="Ground slab construction object name")
    GroundWallAssembly: str = Field(..., title="Ground wall construction object name")
    InternalMassAssembly: str = Field(
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


class ZoneEnvelopeComponent(NamedObject, MetadataMixin, extra="forbid"):
    """Zone envelope object."""

    Assemblies: EnvelopeAssemblyComponent
    Infiltration: InfiltrationComponent
    Window: GlazingConstructionSimpleComponent | None

    # Foundation: Foundation | None
    # OtherSettings: OtherSettings | None


# TODO: add envelope to idf zone
# (currently in builder)
