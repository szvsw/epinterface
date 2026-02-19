"""Semi-flat roof schema and translators for SBEM assemblies."""

from dataclasses import dataclass
from typing import Literal, get_args

from pydantic import BaseModel, Field, model_validator

from epinterface.sbem.components.envelope import (
    ConstructionAssemblyComponent,
    ConstructionLayerComponent,
)
from epinterface.sbem.flat_constructions.layers import (
    equivalent_framed_cavity_material,
    layer_from_nominal_r,
    resolve_material,
)
from epinterface.sbem.flat_constructions.materials import (
    ACOUSTIC_TILE,
    CEMENT_MORTAR,
    CERAMIC_TILE,
    CONCRETE_RC_DENSE,
    COOL_ROOF_MEMBRANE,
    FIBERGLASS_BATTS,
    GYPSUM_BOARD,
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
    framing_material_name: str | None = None
    framing_fraction: float | None = None
    framing_path_r_value: float | None = None
    uninsulated_cavity_r_value: float = 0.17
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
        thickness_m=0.0,
        supports_cavity_insulation=True,
        cavity_depth_m=0.140,
        framing_material_name=SOFTWOOD_GENERAL.Name,
        framing_fraction=0.14,
    ),
    "deep_wood_truss": StructuralTemplate(
        material_name=SOFTWOOD_GENERAL.Name,
        thickness_m=0.0,
        supports_cavity_insulation=True,
        cavity_depth_m=0.240,
        framing_material_name=SOFTWOOD_GENERAL.Name,
        framing_fraction=0.12,
    ),
    "steel_joist": StructuralTemplate(
        material_name=STEEL_PANEL.Name,
        thickness_m=0.0,
        supports_cavity_insulation=True,
        cavity_depth_m=0.180,
        framing_material_name=STEEL_PANEL.Name,
        framing_fraction=0.08,
        # Calibrated to reproduce ~60-65% effective batt R for steel-joist roofs.
        # References:
        # - ASHRAE Standard 90.1 Appendix A (metal-framing correction methodology)
        # - COMcheck steel-framed roof U-factor datasets (effective-R behavior)
        framing_path_r_value=0.35,
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
            ConstructionLayerComponent(
                ConstructionMaterial=resolve_material(exterior_finish.material_name),
                Thickness=exterior_finish.thickness_m,
                LayerOrder=layer_order,
            )
        )
        layer_order += 1

    if roof.nominal_exterior_insulation_r > 0:
        layers.append(
            layer_from_nominal_r(
                material=POLYISO_BOARD.Name,
                nominal_r_value=roof.nominal_exterior_insulation_r,
                layer_order=layer_order,
            )
        )
        layer_order += 1

    uses_framed_cavity_consolidation = (
        template.supports_cavity_insulation
        and template.cavity_depth_m is not None
        and template.framing_material_name is not None
        and template.framing_fraction is not None
    )

    if uses_framed_cavity_consolidation:
        consolidated_cavity_material = equivalent_framed_cavity_material(
            structural_system=roof.structural_system,
            cavity_depth_m=template.cavity_depth_m or 0.0,
            framing_material=template.framing_material_name or SOFTWOOD_GENERAL.Name,
            framing_fraction=template.framing_fraction or 0.0,
            framing_path_r_value=template.framing_path_r_value,
            nominal_cavity_insulation_r=roof.effective_nominal_cavity_insulation_r,
            uninsulated_cavity_r_value=template.uninsulated_cavity_r_value,
        )
        layers.append(
            ConstructionLayerComponent(
                ConstructionMaterial=consolidated_cavity_material,
                Thickness=template.cavity_depth_m or 0.0,
                LayerOrder=layer_order,
            )
        )
        layer_order += 1
    else:
        if template.thickness_m > 0:
            layers.append(
                ConstructionLayerComponent(
                    ConstructionMaterial=resolve_material(template.material_name),
                    Thickness=template.thickness_m,
                    LayerOrder=layer_order,
                )
            )
            layer_order += 1

        if roof.effective_nominal_cavity_insulation_r > 0:
            effective_cavity_r = (
                roof.effective_nominal_cavity_insulation_r
                * template.cavity_r_correction_factor
            )
            layers.append(
                layer_from_nominal_r(
                    material=FIBERGLASS_BATTS.Name,
                    nominal_r_value=effective_cavity_r,
                    layer_order=layer_order,
                )
            )
            layer_order += 1

    if roof.nominal_interior_insulation_r > 0:
        layers.append(
            layer_from_nominal_r(
                material=FIBERGLASS_BATTS.Name,
                nominal_r_value=roof.nominal_interior_insulation_r,
                layer_order=layer_order,
            )
        )
        layer_order += 1

    interior_finish = INTERIOR_FINISH_TEMPLATES[roof.interior_finish]
    if interior_finish is not None:
        layers.append(
            ConstructionLayerComponent(
                ConstructionMaterial=resolve_material(interior_finish.material_name),
                Thickness=interior_finish.thickness_m,
                LayerOrder=layer_order,
            )
        )

    return ConstructionAssemblyComponent(
        Name=name,
        Type="FlatRoof",
        Layers=layers,
    )
