"""Semi-flat roof schema and translators for SBEM assemblies."""

from dataclasses import dataclass
from typing import Literal, get_args

from pydantic import BaseModel, Field, model_validator

from epinterface.sbem.components.envelope import (
    ConstructionAssemblyComponent,
    ConstructionLayerComponent,
)
from epinterface.sbem.flat_constructions.materials import (
    ACOUSTIC_TILE,
    CEMENT_MORTAR,
    CERAMIC_TILE,
    CONCRETE_RC_DENSE,
    COOL_ROOF_MEMBRANE,
    FIBERGLASS_BATTS,
    GYPSUM_BOARD,
    MATERIALS_BY_NAME,
    POLYISO_BOARD,
    ROOF_MEMBRANE,
    SIP_CORE,
    SOFTWOOD_GENERAL,
    STEEL_PANEL,
)

RoofStructuralSystem = Literal[
    "none",
    "light_wood_truss",
    "deep_wood_truss",
    "steel_joist",
    "metal_deck",
    "mass_timber",
    "precast_concrete",
    "poured_concrete",
    "reinforced_concrete",
    "sip",
]

RoofInteriorFinish = Literal[
    "none",
    "gypsum_board",
    "acoustic_tile",
    "wood_panel",
]
RoofExteriorFinish = Literal[
    "none",
    "epdm_membrane",
    "cool_membrane",
    "built_up_roof",
    "metal_roof",
    "tile_roof",
]

ALL_ROOF_STRUCTURAL_SYSTEMS = get_args(RoofStructuralSystem)
ALL_ROOF_INTERIOR_FINISHES = get_args(RoofInteriorFinish)
ALL_ROOF_EXTERIOR_FINISHES = get_args(RoofExteriorFinish)


@dataclass(frozen=True)
class StructuralTemplate:
    """Default structural roof assumptions for a structural system."""

    material_name: str
    thickness_m: float
    supports_cavity_insulation: bool
    cavity_depth_m: float | None
    cavity_r_correction_factor: float = 1.0


@dataclass(frozen=True)
class FinishTemplate:
    """Default roof finish material and thickness assumptions."""

    material_name: str
    thickness_m: float


STRUCTURAL_TEMPLATES: dict[RoofStructuralSystem, StructuralTemplate] = {
    "none": StructuralTemplate(
        material_name=GYPSUM_BOARD.Name,
        thickness_m=0.005,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "light_wood_truss": StructuralTemplate(
        material_name=SOFTWOOD_GENERAL.Name,
        thickness_m=0.040,
        supports_cavity_insulation=True,
        cavity_depth_m=0.140,
        cavity_r_correction_factor=0.82,
    ),
    "deep_wood_truss": StructuralTemplate(
        material_name=SOFTWOOD_GENERAL.Name,
        thickness_m=0.060,
        supports_cavity_insulation=True,
        cavity_depth_m=0.240,
        cavity_r_correction_factor=0.82,
    ),
    "steel_joist": StructuralTemplate(
        material_name=STEEL_PANEL.Name,
        thickness_m=0.006,
        supports_cavity_insulation=True,
        cavity_depth_m=0.180,
        cavity_r_correction_factor=0.62,
    ),
    "metal_deck": StructuralTemplate(
        material_name=STEEL_PANEL.Name,
        thickness_m=0.0015,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "mass_timber": StructuralTemplate(
        material_name=SOFTWOOD_GENERAL.Name,
        thickness_m=0.180,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "precast_concrete": StructuralTemplate(
        material_name=CONCRETE_RC_DENSE.Name,
        thickness_m=0.180,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "poured_concrete": StructuralTemplate(
        material_name=CONCRETE_RC_DENSE.Name,
        thickness_m=0.180,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "reinforced_concrete": StructuralTemplate(
        material_name=CONCRETE_RC_DENSE.Name,
        thickness_m=0.200,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "sip": StructuralTemplate(
        material_name=SIP_CORE.Name,
        thickness_m=0.160,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
}

INTERIOR_FINISH_TEMPLATES: dict[RoofInteriorFinish, FinishTemplate | None] = {
    "none": None,
    "gypsum_board": FinishTemplate(
        material_name=GYPSUM_BOARD.Name,
        thickness_m=0.0127,
    ),
    "acoustic_tile": FinishTemplate(
        material_name=ACOUSTIC_TILE.Name,
        thickness_m=0.019,
    ),
    "wood_panel": FinishTemplate(
        material_name=SOFTWOOD_GENERAL.Name,
        thickness_m=0.012,
    ),
}

EXTERIOR_FINISH_TEMPLATES: dict[RoofExteriorFinish, FinishTemplate | None] = {
    "none": None,
    "epdm_membrane": FinishTemplate(
        material_name=ROOF_MEMBRANE.Name,
        thickness_m=0.005,
    ),
    "cool_membrane": FinishTemplate(
        material_name=COOL_ROOF_MEMBRANE.Name,
        thickness_m=0.005,
    ),
    "built_up_roof": FinishTemplate(
        material_name=CEMENT_MORTAR.Name,
        thickness_m=0.02,
    ),
    "metal_roof": FinishTemplate(
        material_name=STEEL_PANEL.Name,
        thickness_m=0.001,
    ),
    "tile_roof": FinishTemplate(
        material_name=CERAMIC_TILE.Name,
        thickness_m=0.02,
    ),
}


class SemiFlatRoofConstruction(BaseModel):
    """Semantic roof representation for fixed-length flat model vectors."""

    structural_system: RoofStructuralSystem = Field(
        default="poured_concrete",
        title="Structural roof system for thermal-mass assumptions",
    )
    nominal_cavity_insulation_r: float = Field(
        default=0.0,
        ge=0,
        title="Nominal cavity insulation R-value [m²K/W]",
    )
    nominal_exterior_insulation_r: float = Field(
        default=0.0,
        ge=0,
        title="Nominal exterior continuous roof insulation R-value [m²K/W]",
    )
    nominal_interior_insulation_r: float = Field(
        default=0.0,
        ge=0,
        title="Nominal interior continuous roof insulation R-value [m²K/W]",
    )
    interior_finish: RoofInteriorFinish = Field(
        default="gypsum_board",
        title="Interior roof finish selection",
    )
    exterior_finish: RoofExteriorFinish = Field(
        default="epdm_membrane",
        title="Exterior roof finish selection",
    )

    @property
    def effective_nominal_cavity_insulation_r(self) -> float:
        """Return cavity insulation R-value after applying compatibility defaults."""
        template = STRUCTURAL_TEMPLATES[self.structural_system]
        if not template.supports_cavity_insulation:
            return 0.0
        return self.nominal_cavity_insulation_r

    @property
    def ignored_feature_names(self) -> tuple[str, ...]:
        """Return feature names that are semantic no-ops for this roof."""
        ignored: list[str] = []
        template = STRUCTURAL_TEMPLATES[self.structural_system]
        if (
            not template.supports_cavity_insulation
            and self.nominal_cavity_insulation_r > 0
        ):
            ignored.append("nominal_cavity_insulation_r")
        return tuple(ignored)

    @model_validator(mode="after")
    def validate_cavity_r_against_assumed_depth(self):
        """Guard impossible cavity R-values for cavity-compatible systems."""
        template = STRUCTURAL_TEMPLATES[self.structural_system]
        if (
            not template.supports_cavity_insulation
            or template.cavity_depth_m is None
            or self.nominal_cavity_insulation_r == 0
        ):
            return self

        assumed_cavity_insulation_conductivity = FIBERGLASS_BATTS.Conductivity
        max_nominal_r = template.cavity_depth_m / assumed_cavity_insulation_conductivity
        tolerance_r = 0.2
        if self.nominal_cavity_insulation_r > max_nominal_r + tolerance_r:
            msg = (
                f"Nominal cavity insulation R-value ({self.nominal_cavity_insulation_r:.2f} "
                f"m²K/W) exceeds the assumed cavity-depth-compatible limit for "
                f"{self.structural_system} ({max_nominal_r:.2f} m²K/W)."
            )
            raise ValueError(msg)
        return self

    def to_feature_dict(self, prefix: str = "Roof") -> dict[str, float]:
        """Return a fixed-length numeric feature dictionary for ML workflows."""
        features: dict[str, float] = {
            f"{prefix}NominalCavityInsulationRValue": self.nominal_cavity_insulation_r,
            f"{prefix}NominalExteriorInsulationRValue": self.nominal_exterior_insulation_r,
            f"{prefix}NominalInteriorInsulationRValue": self.nominal_interior_insulation_r,
            f"{prefix}EffectiveNominalCavityInsulationRValue": (
                self.effective_nominal_cavity_insulation_r
            ),
        }
        for structural_system in ALL_ROOF_STRUCTURAL_SYSTEMS:
            features[f"{prefix}StructuralSystem__{structural_system}"] = float(
                self.structural_system == structural_system
            )
        for interior_finish in ALL_ROOF_INTERIOR_FINISHES:
            features[f"{prefix}InteriorFinish__{interior_finish}"] = float(
                self.interior_finish == interior_finish
            )
        for exterior_finish in ALL_ROOF_EXTERIOR_FINISHES:
            features[f"{prefix}ExteriorFinish__{exterior_finish}"] = float(
                self.exterior_finish == exterior_finish
            )
        return features


def _make_layer(
    *,
    material_name: str,
    thickness_m: float,
    layer_order: int,
) -> ConstructionLayerComponent:
    """Create a construction layer from a registered material."""
    return ConstructionLayerComponent(
        ConstructionMaterial=MATERIALS_BY_NAME[material_name],
        Thickness=thickness_m,
        LayerOrder=layer_order,
    )


def _nominal_r_insulation_layer(
    *,
    material_name: str,
    nominal_r_value: float,
    layer_order: int,
) -> ConstructionLayerComponent:
    """Create a layer by back-solving thickness from nominal R-value."""
    material = MATERIALS_BY_NAME[material_name]
    thickness_m = nominal_r_value * material.Conductivity
    return _make_layer(
        material_name=material_name,
        thickness_m=thickness_m,
        layer_order=layer_order,
    )


def build_roof_assembly(
    roof: SemiFlatRoofConstruction,
    *,
    name: str = "Roof",
) -> ConstructionAssemblyComponent:
    """Translate semi-flat roof inputs into a concrete roof assembly."""
    template = STRUCTURAL_TEMPLATES[roof.structural_system]
    layers: list[ConstructionLayerComponent] = []
    layer_order = 0

    exterior_finish = EXTERIOR_FINISH_TEMPLATES[roof.exterior_finish]
    if exterior_finish is not None:
        layers.append(
            _make_layer(
                material_name=exterior_finish.material_name,
                thickness_m=exterior_finish.thickness_m,
                layer_order=layer_order,
            )
        )
        layer_order += 1

    if roof.nominal_exterior_insulation_r > 0:
        layers.append(
            _nominal_r_insulation_layer(
                material_name=POLYISO_BOARD.Name,
                nominal_r_value=roof.nominal_exterior_insulation_r,
                layer_order=layer_order,
            )
        )
        layer_order += 1

    layers.append(
        _make_layer(
            material_name=template.material_name,
            thickness_m=template.thickness_m,
            layer_order=layer_order,
        )
    )
    layer_order += 1

    if roof.effective_nominal_cavity_insulation_r > 0:
        effective_cavity_r = (
            roof.effective_nominal_cavity_insulation_r
            * template.cavity_r_correction_factor
        )
        layers.append(
            _nominal_r_insulation_layer(
                material_name=FIBERGLASS_BATTS.Name,
                nominal_r_value=effective_cavity_r,
                layer_order=layer_order,
            )
        )
        layer_order += 1

    if roof.nominal_interior_insulation_r > 0:
        layers.append(
            _nominal_r_insulation_layer(
                material_name=FIBERGLASS_BATTS.Name,
                nominal_r_value=roof.nominal_interior_insulation_r,
                layer_order=layer_order,
            )
        )
        layer_order += 1

    interior_finish = INTERIOR_FINISH_TEMPLATES[roof.interior_finish]
    if interior_finish is not None:
        layers.append(
            _make_layer(
                material_name=interior_finish.material_name,
                thickness_m=interior_finish.thickness_m,
                layer_order=layer_order,
            )
        )

    return ConstructionAssemblyComponent(
        Name=name,
        Type="FlatRoof",
        Layers=layers,
    )
