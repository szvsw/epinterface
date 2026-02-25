"""Semi-flat slab schema and translators for SBEM assemblies."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
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
    MaterialRef,
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
    "suspended_timber_floor",
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
    "suspended_timber_floor": StructuralTemplate(
        material_name="SoftwoodGeneral",
        thickness_m=0.022,
        supports_under_insulation=True,
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


@dataclass
class _SlabLayerAccumulator:
    """Track slab layers while keeping layer-order assignments consistent."""

    layers: list[ConstructionLayerComponent] = field(default_factory=list)
    next_layer_order: int = 0

    def add_material_layer(self, *, material: MaterialRef, thickness_m: float) -> None:
        """Append a layer with an explicit material and thickness."""
        self.layers.append(
            ConstructionLayerComponent(
                ConstructionMaterial=resolve_material(material),
                Thickness=thickness_m,
                LayerOrder=self.next_layer_order,
            )
        )
        self.next_layer_order += 1

    def add_nominal_r_layer(
        self,
        *,
        material: MaterialRef,
        nominal_r_value: float,
    ) -> None:
        """Append a layer by back-solving thickness from nominal R."""
        self.layers.append(
            layer_from_nominal_r(
                material=material,
                nominal_r_value=nominal_r_value,
                layer_order=self.next_layer_order,
            )
        )
        self.next_layer_order += 1


class _SlabAssemblyBuilder(ABC):
    """Abstract slab assembly strategy."""

    def __init__(
        self,
        *,
        structural_system: SlabStructuralSystem,
        template: StructuralTemplate,
    ) -> None:
        self.structural_system = structural_system
        self.template = template

    @property
    @abstractmethod
    def default_auto_insulation_placement(self) -> SlabInsulationPlacement:
        """Return the placement resolved from `auto` for this strategy."""

    def effective_insulation_placement(
        self,
        insulation_placement: SlabInsulationPlacement,
    ) -> SlabInsulationPlacement:
        """Resolve user-selected insulation placement under strategy rules."""
        if insulation_placement != "auto":
            return insulation_placement
        return self.default_auto_insulation_placement

    def effective_nominal_insulation_r(
        self,
        *,
        nominal_insulation_r: float,
        insulation_placement: SlabInsulationPlacement,
    ) -> float:
        """Return effective nominal slab insulation after compatibility defaults."""
        if nominal_insulation_r == 0:
            return 0.0
        effective_placement = self.effective_insulation_placement(insulation_placement)
        if (
            effective_placement == "under_slab"
            and not self.template.supports_under_insulation
        ):
            return 0.0
        return nominal_insulation_r

    def ignored_feature_names(
        self,
        *,
        nominal_insulation_r: float,
        insulation_placement: SlabInsulationPlacement,
    ) -> tuple[str, ...]:
        """Return input names that are semantic no-ops for this builder."""
        if (
            insulation_placement == "under_slab"
            and not self.template.supports_under_insulation
            and nominal_insulation_r > 0
        ):
            return ("nominal_insulation_r", "insulation_placement")
        return ()

    @abstractmethod
    def build_layers(
        self,
        *,
        nominal_insulation_r: float,
        insulation_material: ContinuousInsulationMaterial,
        insulation_placement: SlabInsulationPlacement,
        interior_finish: SlabInteriorFinish,
        exterior_finish: SlabExteriorFinish,
    ) -> list[ConstructionLayerComponent]:
        """Build slab layers from high-level assembly inputs."""


class _SingleCoreSlabAssemblyBuilder(_SlabAssemblyBuilder):
    """Slab strategy for single-core assemblies with optional insulation layers."""

    def build_layers(
        self,
        *,
        nominal_insulation_r: float,
        insulation_material: ContinuousInsulationMaterial,
        insulation_placement: SlabInsulationPlacement,
        interior_finish: SlabInteriorFinish,
        exterior_finish: SlabExteriorFinish,
    ) -> list[ConstructionLayerComponent]:
        """Build slab layers outside-in while applying placement logic."""
        layers = _SlabLayerAccumulator()
        exterior_finish_template = EXTERIOR_FINISH_TEMPLATES[exterior_finish]
        if exterior_finish_template is not None:
            layers.add_material_layer(
                material=exterior_finish_template.material_name,
                thickness_m=exterior_finish_template.thickness_m,
            )

        slab_ins_material = CONTINUOUS_INSULATION_MATERIAL_MAP[insulation_material]
        effective_placement = self.effective_insulation_placement(insulation_placement)
        effective_nominal_r = self.effective_nominal_insulation_r(
            nominal_insulation_r=nominal_insulation_r,
            insulation_placement=insulation_placement,
        )
        if effective_placement == "under_slab" and effective_nominal_r > 0:
            layers.add_nominal_r_layer(
                material=slab_ins_material,
                nominal_r_value=effective_nominal_r,
            )

        layers.add_material_layer(
            material=self.template.material_name,
            thickness_m=self.template.thickness_m,
        )

        if effective_placement == "above_slab" and effective_nominal_r > 0:
            layers.add_nominal_r_layer(
                material=slab_ins_material,
                nominal_r_value=effective_nominal_r,
            )

        interior_finish_template = INTERIOR_FINISH_TEMPLATES[interior_finish]
        if interior_finish_template is not None:
            layers.add_material_layer(
                material=interior_finish_template.material_name,
                thickness_m=interior_finish_template.thickness_m,
            )
        return layers.layers


class _GroundSupportedSlabAssemblyBuilder(_SingleCoreSlabAssemblyBuilder):
    """Slab strategy whose default auto placement is under-slab."""

    @property
    def default_auto_insulation_placement(self) -> SlabInsulationPlacement:
        """Resolve auto placement for ground-supported slabs."""
        return "under_slab"


class _SuspendedSlabAssemblyBuilder(_SingleCoreSlabAssemblyBuilder):
    """Slab strategy whose default auto placement is above-slab."""

    @property
    def default_auto_insulation_placement(self) -> SlabInsulationPlacement:
        """Resolve auto placement for suspended slabs."""
        return "above_slab"


def _make_slab_assembly_builder(
    structural_system: SlabStructuralSystem,
    template: StructuralTemplate,
) -> _SlabAssemblyBuilder:
    """Return the slab builder strategy for a structural system."""
    if template.supports_under_insulation:
        return _GroundSupportedSlabAssemblyBuilder(
            structural_system=structural_system,
            template=template,
        )
    return _SuspendedSlabAssemblyBuilder(
        structural_system=structural_system,
        template=template,
    )


STRUCTURAL_BUILDERS: dict[SlabStructuralSystem, _SlabAssemblyBuilder] = {
    structural_system: _make_slab_assembly_builder(structural_system, template)
    for structural_system, template in STRUCTURAL_TEMPLATES.items()
}
_missing_builder_systems = set(ALL_SLAB_STRUCTURAL_SYSTEMS) - set(STRUCTURAL_BUILDERS)
if _missing_builder_systems:
    msg = "Slab builder registry does not cover all structural systems: " + ", ".join(
        sorted(_missing_builder_systems)
    )
    raise ValueError(msg)


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
        builder = STRUCTURAL_BUILDERS[self.structural_system]
        return builder.effective_insulation_placement(self.insulation_placement)

    @property
    def effective_nominal_insulation_r(self) -> float:
        """Return insulation R-value after applying compatibility defaults."""
        builder = STRUCTURAL_BUILDERS[self.structural_system]
        return builder.effective_nominal_insulation_r(
            nominal_insulation_r=self.nominal_insulation_r,
            insulation_placement=self.insulation_placement,
        )

    @property
    def ignored_feature_names(self) -> tuple[str, ...]:
        """Return feature names that are semantic no-ops for this slab."""
        builder = STRUCTURAL_BUILDERS[self.structural_system]
        return builder.ignored_feature_names(
            nominal_insulation_r=self.nominal_insulation_r,
            insulation_placement=self.insulation_placement,
        )

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
    builder = STRUCTURAL_BUILDERS[slab.structural_system]
    layers = builder.build_layers(
        nominal_insulation_r=slab.nominal_insulation_r,
        insulation_material=slab.insulation_material,
        insulation_placement=slab.insulation_placement,
        interior_finish=slab.interior_finish,
        exterior_finish=slab.exterior_finish,
    )
    return ConstructionAssemblyComponent(
        Name=name,
        Type="GroundSlab",
        Layers=layers,
    )
