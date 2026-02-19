"""Semi-flat slab schema and translators for SBEM assemblies."""

from dataclasses import dataclass
from typing import Literal, get_args

from pydantic import BaseModel, Field, model_validator

from epinterface.sbem.components.envelope import (
    ConstructionAssemblyComponent,
    ConstructionLayerComponent,
)
from epinterface.sbem.flat_constructions.materials import (
    CEMENT_MORTAR,
    CERAMIC_TILE,
    CONCRETE_MC_LIGHT,
    CONCRETE_RC_DENSE,
    FIBERGLASS_BATTS,
    GYPSUM_BOARD,
    GYPSUM_PLASTER,
    MATERIALS_BY_NAME,
    SIP_CORE,
    SOFTWOOD_GENERAL,
    URETHANE_CARPET,
    XPS_BOARD,
)

SlabStructuralSystem = Literal[
    "none",
    "slab_on_grade",
    "thickened_edge_slab",
    "reinforced_concrete_suspended",
    "precast_hollow_core",
    "mass_timber_deck",
    "sip_floor",
]

SlabInteriorFinish = Literal[
    "none",
    "polished_concrete",
    "tile",
    "carpet",
    "wood_floor",
]
SlabExteriorFinish = Literal["none", "gypsum_board", "plaster"]

ALL_SLAB_STRUCTURAL_SYSTEMS = get_args(SlabStructuralSystem)
ALL_SLAB_INTERIOR_FINISHES = get_args(SlabInteriorFinish)
ALL_SLAB_EXTERIOR_FINISHES = get_args(SlabExteriorFinish)


@dataclass(frozen=True)
class StructuralTemplate:
    """Default structural slab assumptions for a structural system."""

    material_name: str
    thickness_m: float
    supports_under_insulation: bool
    supports_cavity_insulation: bool
    cavity_depth_m: float | None


@dataclass(frozen=True)
class FinishTemplate:
    """Default slab finish material and thickness assumptions."""

    material_name: str
    thickness_m: float


STRUCTURAL_TEMPLATES: dict[SlabStructuralSystem, StructuralTemplate] = {
    "none": StructuralTemplate(
        material_name=CONCRETE_MC_LIGHT.Name,
        thickness_m=0.05,
        supports_under_insulation=False,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "slab_on_grade": StructuralTemplate(
        material_name=CONCRETE_RC_DENSE.Name,
        thickness_m=0.15,
        supports_under_insulation=True,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "thickened_edge_slab": StructuralTemplate(
        material_name=CONCRETE_RC_DENSE.Name,
        thickness_m=0.20,
        supports_under_insulation=True,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "reinforced_concrete_suspended": StructuralTemplate(
        material_name=CONCRETE_RC_DENSE.Name,
        thickness_m=0.18,
        supports_under_insulation=False,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "precast_hollow_core": StructuralTemplate(
        material_name=CONCRETE_MC_LIGHT.Name,
        thickness_m=0.20,
        supports_under_insulation=False,
        supports_cavity_insulation=True,
        cavity_depth_m=0.08,
    ),
    "mass_timber_deck": StructuralTemplate(
        material_name=SOFTWOOD_GENERAL.Name,
        thickness_m=0.18,
        supports_under_insulation=False,
        supports_cavity_insulation=True,
        cavity_depth_m=0.12,
    ),
    "sip_floor": StructuralTemplate(
        material_name=SIP_CORE.Name,
        thickness_m=0.18,
        supports_under_insulation=False,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
}

INTERIOR_FINISH_TEMPLATES: dict[SlabInteriorFinish, FinishTemplate | None] = {
    "none": None,
    "polished_concrete": FinishTemplate(
        material_name=CEMENT_MORTAR.Name,
        thickness_m=0.015,
    ),
    "tile": FinishTemplate(
        material_name=CERAMIC_TILE.Name,
        thickness_m=0.015,
    ),
    "carpet": FinishTemplate(
        material_name=URETHANE_CARPET.Name,
        thickness_m=0.012,
    ),
    "wood_floor": FinishTemplate(
        material_name=SOFTWOOD_GENERAL.Name,
        thickness_m=0.015,
    ),
}

EXTERIOR_FINISH_TEMPLATES: dict[SlabExteriorFinish, FinishTemplate | None] = {
    "none": None,
    "gypsum_board": FinishTemplate(
        material_name=GYPSUM_BOARD.Name,
        thickness_m=0.0127,
    ),
    "plaster": FinishTemplate(
        material_name=GYPSUM_PLASTER.Name,
        thickness_m=0.013,
    ),
}


class SemiFlatSlabConstruction(BaseModel):
    """Semantic slab representation for fixed-length flat model vectors."""

    structural_system: SlabStructuralSystem = Field(
        default="slab_on_grade",
        title="Slab structural system for mass assumptions",
    )
    nominal_under_slab_insulation_r: float = Field(
        default=0.0,
        ge=0,
        title="Nominal under-slab insulation R-value [m²K/W]",
    )
    nominal_above_slab_insulation_r: float = Field(
        default=0.0,
        ge=0,
        title="Nominal above-slab insulation R-value [m²K/W]",
    )
    nominal_cavity_insulation_r: float = Field(
        default=0.0,
        ge=0,
        title="Nominal slab cavity insulation R-value [m²K/W]",
    )
    interior_finish: SlabInteriorFinish = Field(
        default="tile",
        title="Interior slab finish selection",
    )
    exterior_finish: SlabExteriorFinish = Field(
        default="none",
        title="Exterior slab finish selection",
    )

    @property
    def effective_nominal_under_slab_insulation_r(self) -> float:
        """Return under-slab insulation R-value after compatibility defaults."""
        template = STRUCTURAL_TEMPLATES[self.structural_system]
        if not template.supports_under_insulation:
            return 0.0
        return self.nominal_under_slab_insulation_r

    @property
    def effective_nominal_cavity_insulation_r(self) -> float:
        """Return cavity insulation R-value after compatibility defaults."""
        template = STRUCTURAL_TEMPLATES[self.structural_system]
        if not template.supports_cavity_insulation:
            return 0.0
        return self.nominal_cavity_insulation_r

    @property
    def ignored_feature_names(self) -> tuple[str, ...]:
        """Return feature names that are semantic no-ops for this slab."""
        ignored: list[str] = []
        template = STRUCTURAL_TEMPLATES[self.structural_system]
        if (
            not template.supports_under_insulation
            and self.nominal_under_slab_insulation_r > 0
        ):
            ignored.append("nominal_under_slab_insulation_r")
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

    def to_feature_dict(self, prefix: str = "Slab") -> dict[str, float]:
        """Return a fixed-length numeric feature dictionary for ML workflows."""
        features: dict[str, float] = {
            f"{prefix}NominalUnderSlabInsulationRValue": (
                self.nominal_under_slab_insulation_r
            ),
            f"{prefix}NominalAboveSlabInsulationRValue": (
                self.nominal_above_slab_insulation_r
            ),
            f"{prefix}NominalCavityInsulationRValue": self.nominal_cavity_insulation_r,
            f"{prefix}EffectiveNominalUnderSlabInsulationRValue": (
                self.effective_nominal_under_slab_insulation_r
            ),
            f"{prefix}EffectiveNominalCavityInsulationRValue": (
                self.effective_nominal_cavity_insulation_r
            ),
        }
        for structural_system in ALL_SLAB_STRUCTURAL_SYSTEMS:
            features[f"{prefix}StructuralSystem__{structural_system}"] = float(
                self.structural_system == structural_system
            )
        for interior_finish in ALL_SLAB_INTERIOR_FINISHES:
            features[f"{prefix}InteriorFinish__{interior_finish}"] = float(
                self.interior_finish == interior_finish
            )
        for exterior_finish in ALL_SLAB_EXTERIOR_FINISHES:
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


def build_slab_assembly(
    slab: SemiFlatSlabConstruction,
    *,
    name: str = "GroundSlabAssembly",
) -> ConstructionAssemblyComponent:
    """Translate semi-flat slab inputs into a concrete slab assembly."""
    template = STRUCTURAL_TEMPLATES[slab.structural_system]
    layers: list[ConstructionLayerComponent] = []
    layer_order = 0

    interior_finish = INTERIOR_FINISH_TEMPLATES[slab.interior_finish]
    if interior_finish is not None:
        layers.append(
            _make_layer(
                material_name=interior_finish.material_name,
                thickness_m=interior_finish.thickness_m,
                layer_order=layer_order,
            )
        )
        layer_order += 1

    if slab.nominal_above_slab_insulation_r > 0:
        layers.append(
            _nominal_r_insulation_layer(
                material_name=XPS_BOARD.Name,
                nominal_r_value=slab.nominal_above_slab_insulation_r,
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

    if slab.effective_nominal_cavity_insulation_r > 0:
        layers.append(
            _nominal_r_insulation_layer(
                material_name=FIBERGLASS_BATTS.Name,
                nominal_r_value=slab.effective_nominal_cavity_insulation_r,
                layer_order=layer_order,
            )
        )
        layer_order += 1

    if slab.effective_nominal_under_slab_insulation_r > 0:
        layers.append(
            _nominal_r_insulation_layer(
                material_name=XPS_BOARD.Name,
                nominal_r_value=slab.effective_nominal_under_slab_insulation_r,
                layer_order=layer_order,
            )
        )
        layer_order += 1

    exterior_finish = EXTERIOR_FINISH_TEMPLATES[slab.exterior_finish]
    if exterior_finish is not None:
        layers.append(
            _make_layer(
                material_name=exterior_finish.material_name,
                thickness_m=exterior_finish.thickness_m,
                layer_order=layer_order,
            )
        )

    return ConstructionAssemblyComponent(
        Name=name,
        Type="GroundSlab",
        Layers=layers,
    )
