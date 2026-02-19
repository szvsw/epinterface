"""Semi-flat slab schema and translators for SBEM assemblies."""

from dataclasses import dataclass
from typing import Literal, get_args

from pydantic import BaseModel, Field

from epinterface.sbem.components.envelope import (
    ConstructionAssemblyComponent,
    ConstructionLayerComponent,
)
from epinterface.sbem.flat_constructions.layers import (
    ALL_CONTINUOUS_INSULATION_MATERIALS,
    CONTINUOUS_INSULATION_MATERIAL_MAP,
    ContinuousInsulationMaterial,
    layer_from_nominal_r,
    resolve_material,
)
from epinterface.sbem.flat_constructions.materials import MaterialName

SlabStructuralSystem = Literal[
    "none",
    "slab_on_grade",
    "thickened_edge_slab",
    "reinforced_concrete_suspended",
    "precast_hollow_core",
    "mass_timber_deck",
    "sip_floor",
    "compacted_earth_floor",
]
SlabInsulationPlacement = Literal["auto", "under_slab", "above_slab"]

SlabInteriorFinish = Literal[
    "none",
    "polished_concrete",
    "tile",
    "carpet",
    "wood_floor",
    "cement_screed",
]
SlabExteriorFinish = Literal["none", "gypsum_board", "plaster"]

ALL_SLAB_STRUCTURAL_SYSTEMS = get_args(SlabStructuralSystem)
ALL_SLAB_INSULATION_PLACEMENTS = get_args(SlabInsulationPlacement)
ALL_SLAB_INTERIOR_FINISHES = get_args(SlabInteriorFinish)
ALL_SLAB_EXTERIOR_FINISHES = get_args(SlabExteriorFinish)


@dataclass(frozen=True)
class StructuralTemplate:
    """Default structural slab assumptions for a structural system."""

    material_name: MaterialName
    thickness_m: float
    supports_under_insulation: bool


@dataclass(frozen=True)
class FinishTemplate:
    """Default slab finish material and thickness assumptions."""

    material_name: MaterialName
    thickness_m: float


STRUCTURAL_TEMPLATES: dict[SlabStructuralSystem, StructuralTemplate] = {
    "none": StructuralTemplate(
        material_name="ConcreteMC_Light",
        thickness_m=0.05,
        supports_under_insulation=False,
    ),
    "slab_on_grade": StructuralTemplate(
        material_name="ConcreteRC_Dense",
        thickness_m=0.15,
        supports_under_insulation=True,
    ),
    "thickened_edge_slab": StructuralTemplate(
        material_name="ConcreteRC_Dense",
        thickness_m=0.20,
        supports_under_insulation=True,
    ),
    "reinforced_concrete_suspended": StructuralTemplate(
        material_name="ConcreteRC_Dense",
        thickness_m=0.18,
        supports_under_insulation=False,
    ),
    "precast_hollow_core": StructuralTemplate(
        material_name="ConcreteMC_Light",
        thickness_m=0.20,
        supports_under_insulation=False,
    ),
    "mass_timber_deck": StructuralTemplate(
        material_name="SoftwoodGeneral",
        thickness_m=0.18,
        supports_under_insulation=False,
    ),
    "sip_floor": StructuralTemplate(
        material_name="SIPCore",
        thickness_m=0.18,
        supports_under_insulation=False,
    ),
    "compacted_earth_floor": StructuralTemplate(
        material_name="RammedEarth",
        thickness_m=0.10,
        supports_under_insulation=False,
    ),
}

INTERIOR_FINISH_TEMPLATES: dict[SlabInteriorFinish, FinishTemplate | None] = {
    "none": None,
    "polished_concrete": FinishTemplate(
        material_name="CementMortar",
        thickness_m=0.015,
    ),
    "tile": FinishTemplate(
        material_name="CeramicTile",
        thickness_m=0.015,
    ),
    "carpet": FinishTemplate(
        material_name="UrethaneCarpet",
        thickness_m=0.012,
    ),
    "wood_floor": FinishTemplate(
        material_name="SoftwoodGeneral",
        thickness_m=0.015,
    ),
    "cement_screed": FinishTemplate(
        material_name="CementMortar",
        thickness_m=0.02,
    ),
}

EXTERIOR_FINISH_TEMPLATES: dict[SlabExteriorFinish, FinishTemplate | None] = {
    "none": None,
    "gypsum_board": FinishTemplate(
        material_name="GypsumBoard",
        thickness_m=0.0127,
    ),
    "plaster": FinishTemplate(
        material_name="GypsumPlaster",
        thickness_m=0.013,
    ),
}


class SemiFlatSlabConstruction(BaseModel):
    """Semantic slab representation for fixed-length flat model vectors."""

    structural_system: SlabStructuralSystem = Field(
        default="slab_on_grade",
        title="Slab structural system for mass assumptions",
    )
    nominal_insulation_r: float = Field(
        default=0.0,
        ge=0,
        title="Nominal slab insulation R-value [m²K/W]",
    )
    insulation_material: ContinuousInsulationMaterial = Field(
        default="xps",
        title="Slab insulation material",
    )
    insulation_placement: SlabInsulationPlacement = Field(
        default="auto",
        title="Slab insulation placement",
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
    def effective_insulation_placement(self) -> SlabInsulationPlacement:
        """Return insulation placement after applying compatibility defaults."""
        if self.insulation_placement != "auto":
            return self.insulation_placement
        template = STRUCTURAL_TEMPLATES[self.structural_system]
        return "under_slab" if template.supports_under_insulation else "above_slab"

    @property
    def effective_nominal_insulation_r(self) -> float:
        """Return insulation R-value after applying compatibility defaults."""
        if self.nominal_insulation_r == 0:
            return 0.0
        template = STRUCTURAL_TEMPLATES[self.structural_system]
        if (
            self.effective_insulation_placement == "under_slab"
            and not template.supports_under_insulation
        ):
            return 0.0
        return self.nominal_insulation_r

    @property
    def ignored_feature_names(self) -> tuple[str, ...]:
        """Return feature names that are semantic no-ops for this slab."""
        ignored: list[str] = []
        template = STRUCTURAL_TEMPLATES[self.structural_system]
        if (
            self.insulation_placement == "under_slab"
            and not template.supports_under_insulation
            and self.nominal_insulation_r > 0
        ):
            ignored.append("nominal_insulation_r")
            ignored.append("insulation_placement")
        return tuple(ignored)

    def to_feature_dict(self, prefix: str = "Slab") -> dict[str, float]:
        """Return a fixed-length numeric feature dictionary for ML workflows."""
        features: dict[str, float] = {
            f"{prefix}NominalInsulationRValue": self.nominal_insulation_r,
            f"{prefix}EffectiveNominalInsulationRValue": (
                self.effective_nominal_insulation_r
            ),
        }
        for structural_system in ALL_SLAB_STRUCTURAL_SYSTEMS:
            features[f"{prefix}StructuralSystem__{structural_system}"] = float(
                self.structural_system == structural_system
            )
        for placement in ALL_SLAB_INSULATION_PLACEMENTS:
            features[f"{prefix}InsulationPlacement__{placement}"] = float(
                self.insulation_placement == placement
            )
            features[f"{prefix}EffectiveInsulationPlacement__{placement}"] = float(
                self.effective_insulation_placement == placement
            )
        for interior_finish in ALL_SLAB_INTERIOR_FINISHES:
            features[f"{prefix}InteriorFinish__{interior_finish}"] = float(
                self.interior_finish == interior_finish
            )
        for exterior_finish in ALL_SLAB_EXTERIOR_FINISHES:
            features[f"{prefix}ExteriorFinish__{exterior_finish}"] = float(
                self.exterior_finish == exterior_finish
            )
        for ins_mat in ALL_CONTINUOUS_INSULATION_MATERIALS:
            features[f"{prefix}InsulationMaterial__{ins_mat}"] = float(
                self.insulation_material == ins_mat
            )
        return features


def build_slab_assembly(
    slab: SemiFlatSlabConstruction,
    *,
    name: str = "GroundSlabAssembly",
) -> ConstructionAssemblyComponent:
    """Translate semi-flat slab inputs into a concrete slab assembly."""
    # EnergyPlus convention: layer 0 is outermost (outside -> inside).
    template = STRUCTURAL_TEMPLATES[slab.structural_system]
    layers: list[ConstructionLayerComponent] = []
    layer_order = 0

    exterior_finish = EXTERIOR_FINISH_TEMPLATES[slab.exterior_finish]
    if exterior_finish is not None:
        layers.append(
            ConstructionLayerComponent(
                ConstructionMaterial=resolve_material(exterior_finish.material_name),
                Thickness=exterior_finish.thickness_m,
                LayerOrder=layer_order,
            )
        )
        layer_order += 1

    slab_ins_material = CONTINUOUS_INSULATION_MATERIAL_MAP[slab.insulation_material]

    if (
        slab.effective_insulation_placement == "under_slab"
        and slab.effective_nominal_insulation_r > 0
    ):
        layers.append(
            layer_from_nominal_r(
                material=slab_ins_material,
                nominal_r_value=slab.effective_nominal_insulation_r,
                layer_order=layer_order,
            )
        )
        layer_order += 1

    layers.append(
        ConstructionLayerComponent(
            ConstructionMaterial=resolve_material(template.material_name),
            Thickness=template.thickness_m,
            LayerOrder=layer_order,
        )
    )
    layer_order += 1

    if (
        slab.effective_insulation_placement == "above_slab"
        and slab.effective_nominal_insulation_r > 0
    ):
        layers.append(
            layer_from_nominal_r(
                material=slab_ins_material,
                nominal_r_value=slab.effective_nominal_insulation_r,
                layer_order=layer_order,
            )
        )
        layer_order += 1

    interior_finish = INTERIOR_FINISH_TEMPLATES[slab.interior_finish]
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
        Type="GroundSlab",
        Layers=layers,
    )
