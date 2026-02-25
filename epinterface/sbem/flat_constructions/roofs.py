"""Semi-flat roof schema and translators for SBEM assemblies."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal, get_args

from pydantic import BaseModel, Field, model_validator

from epinterface.sbem.components.envelope import (
    ConstructionAssemblyComponent,
    ConstructionLayerComponent,
)
from epinterface.sbem.flat_constructions.layers import (
    _AIR_GAP_THICKNESS_M,
    AIR_GAP_ROOF,
    ALL_CAVITY_INSULATION_MATERIALS,
    ALL_CONTINUOUS_INSULATION_MATERIALS,
    ALL_EXTERIOR_CAVITY_TYPES,
    CAVITY_INSULATION_MATERIAL_MAP,
    CONTINUOUS_INSULATION_MATERIAL_MAP,
    CavityInsulationMaterial,
    ContinuousInsulationMaterial,
    ExteriorCavityType,
    MaterialRef,
    equivalent_framed_cavity_material,
    layer_from_nominal_r,
    resolve_material,
)
from epinterface.sbem.flat_constructions.materials import MaterialName

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
    "corrugated_metal",
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
    "asphalt_shingle",
    "wood_shake",
    "thatch",
    "fiber_cement_sheet",
]

ALL_ROOF_STRUCTURAL_SYSTEMS = get_args(RoofStructuralSystem)
ALL_ROOF_INTERIOR_FINISHES = get_args(RoofInteriorFinish)
ALL_ROOF_EXTERIOR_FINISHES = get_args(RoofExteriorFinish)


@dataclass(frozen=True)
class StructuralTemplate:
    """Default structural roof assumptions for a structural system."""

    material_name: MaterialName
    thickness_m: float
    supports_cavity_insulation: bool
    cavity_depth_m: float | None
    framing_material_name: MaterialName | None = None
    framing_fraction: float | None = None
    framing_path_r_value: float | None = None
    uninsulated_cavity_r_value: float = 0.17
    cavity_r_correction_factor: float = 1.0


@dataclass(frozen=True)
class FinishTemplate:
    """Default roof finish material and thickness assumptions."""

    material_name: MaterialName
    thickness_m: float


STRUCTURAL_TEMPLATES: dict[RoofStructuralSystem, StructuralTemplate] = {
    "none": StructuralTemplate(
        material_name="GypsumBoard",
        thickness_m=0.005,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "light_wood_truss": StructuralTemplate(
        material_name="SoftwoodGeneral",
        thickness_m=0.0,
        supports_cavity_insulation=True,
        cavity_depth_m=0.140,
        framing_material_name="SoftwoodGeneral",
        framing_fraction=0.14,
    ),
    "deep_wood_truss": StructuralTemplate(
        material_name="SoftwoodGeneral",
        thickness_m=0.0,
        supports_cavity_insulation=True,
        cavity_depth_m=0.240,
        framing_material_name="SoftwoodGeneral",
        framing_fraction=0.12,
    ),
    "steel_joist": StructuralTemplate(
        material_name="SteelPanel",
        thickness_m=0.0,
        supports_cavity_insulation=True,
        cavity_depth_m=0.180,
        framing_material_name="SteelPanel",
        framing_fraction=0.08,
        # Calibrated to reproduce ~60-65% effective batt R for steel-joist roofs
        # with 7in (180mm) joist depth at typical spacing. Not directly applicable
        # to EU lightweight steel roof framing conventions.
        # References:
        # - ASHRAE Standard 90.1 Appendix A (metal-framing correction methodology)
        # - COMcheck steel-framed roof U-factor datasets (effective-R behavior)
        framing_path_r_value=0.35,
    ),
    "metal_deck": StructuralTemplate(
        material_name="SteelPanel",
        thickness_m=0.0015,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "mass_timber": StructuralTemplate(
        material_name="SoftwoodGeneral",
        thickness_m=0.180,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "precast_concrete": StructuralTemplate(
        material_name="ConcreteRC_Dense",
        thickness_m=0.180,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "poured_concrete": StructuralTemplate(
        material_name="ConcreteRC_Dense",
        thickness_m=0.180,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "reinforced_concrete": StructuralTemplate(
        material_name="ConcreteRC_Dense",
        thickness_m=0.200,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "sip": StructuralTemplate(
        material_name="SIPCore",
        thickness_m=0.160,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "corrugated_metal": StructuralTemplate(
        material_name="SteelPanel",
        thickness_m=0.0005,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
}

INTERIOR_FINISH_TEMPLATES: dict[RoofInteriorFinish, FinishTemplate | None] = {
    "none": None,
    "gypsum_board": FinishTemplate(
        material_name="GypsumBoard",
        thickness_m=0.0127,
    ),
    "acoustic_tile": FinishTemplate(
        material_name="AcousticTile",
        thickness_m=0.019,
    ),
    "wood_panel": FinishTemplate(
        material_name="SoftwoodGeneral",
        thickness_m=0.012,
    ),
}

EXTERIOR_FINISH_TEMPLATES: dict[RoofExteriorFinish, FinishTemplate | None] = {
    "none": None,
    "epdm_membrane": FinishTemplate(
        material_name="RoofMembrane",
        thickness_m=0.005,
    ),
    "cool_membrane": FinishTemplate(
        material_name="CoolRoofMembrane",
        thickness_m=0.005,
    ),
    "built_up_roof": FinishTemplate(
        material_name="CementMortar",
        thickness_m=0.02,
    ),
    "metal_roof": FinishTemplate(
        material_name="SteelPanel",
        thickness_m=0.001,
    ),
    "tile_roof": FinishTemplate(
        material_name="CeramicTile",
        thickness_m=0.02,
    ),
    "asphalt_shingle": FinishTemplate(
        material_name="AsphaltShingle",
        thickness_m=0.006,
    ),
    "wood_shake": FinishTemplate(
        material_name="SoftwoodGeneral",
        thickness_m=0.012,
    ),
    "thatch": FinishTemplate(
        material_name="ThatchReed",
        thickness_m=0.200,
    ),
    "fiber_cement_sheet": FinishTemplate(
        material_name="FiberCementBoard",
        thickness_m=0.006,
    ),
}


@dataclass
class _RoofLayerAccumulator:
    """Track roof layers while keeping layer-order assignments consistent."""

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


class _RoofAssemblyBuilder(ABC):
    """Abstract roof assembly strategy."""

    def __init__(
        self,
        *,
        structural_system: RoofStructuralSystem,
        template: StructuralTemplate,
    ) -> None:
        self.structural_system = structural_system
        self.template = template

    def effective_nominal_cavity_insulation_r(
        self,
        nominal_cavity_insulation_r: float,
    ) -> float:
        """Return cavity R after structural-system compatibility rules."""
        if not self.template.supports_cavity_insulation:
            return 0.0
        return nominal_cavity_insulation_r

    def ignored_feature_names(
        self,
        nominal_cavity_insulation_r: float,
    ) -> tuple[str, ...]:
        """Return input names that are semantic no-ops for this builder."""
        if (
            not self.template.supports_cavity_insulation
            and nominal_cavity_insulation_r > 0
        ):
            return ("nominal_cavity_insulation_r",)
        return ()

    def validate_nominal_cavity_insulation_r(
        self,
        *,
        nominal_cavity_insulation_r: float,
        cavity_insulation_material: CavityInsulationMaterial,
    ) -> None:
        """Raise if the requested cavity R exceeds cavity-depth assumptions."""
        if (
            not self.template.supports_cavity_insulation
            or self.template.cavity_depth_m is None
            or nominal_cavity_insulation_r == 0
        ):
            return

        cavity_mat_name = CAVITY_INSULATION_MATERIAL_MAP[cavity_insulation_material]
        cavity_mat = resolve_material(cavity_mat_name)
        max_nominal_r = self.template.cavity_depth_m / cavity_mat.Conductivity
        tolerance_r = 0.2
        if nominal_cavity_insulation_r > max_nominal_r + tolerance_r:
            msg = (
                f"Nominal cavity insulation R-value ({nominal_cavity_insulation_r:.2f} "
                f"m²K/W) exceeds the assumed cavity-depth-compatible limit for "
                f"{self.structural_system} ({max_nominal_r:.2f} m²K/W)."
            )
            raise ValueError(msg)

    @abstractmethod
    def build_layers(
        self,
        *,
        nominal_cavity_insulation_r: float,
        nominal_exterior_insulation_r: float,
        nominal_interior_insulation_r: float,
        exterior_insulation_material: ContinuousInsulationMaterial,
        interior_insulation_material: ContinuousInsulationMaterial,
        cavity_insulation_material: CavityInsulationMaterial,
        interior_finish: RoofInteriorFinish,
        exterior_finish: RoofExteriorFinish,
        exterior_cavity_type: ExteriorCavityType,
    ) -> list[ConstructionLayerComponent]:
        """Build roof layers from high-level assembly inputs."""


class _ComposedRoofAssemblyBuilder(_RoofAssemblyBuilder, ABC):
    """Shared roof-builder flow with subclassed structural logic."""

    def build_layers(
        self,
        *,
        nominal_cavity_insulation_r: float,
        nominal_exterior_insulation_r: float,
        nominal_interior_insulation_r: float,
        exterior_insulation_material: ContinuousInsulationMaterial,
        interior_insulation_material: ContinuousInsulationMaterial,
        cavity_insulation_material: CavityInsulationMaterial,
        interior_finish: RoofInteriorFinish,
        exterior_finish: RoofExteriorFinish,
        exterior_cavity_type: ExteriorCavityType,
    ) -> list[ConstructionLayerComponent]:
        """Build roof layers outside-in while delegating structural core logic."""
        layers = _RoofLayerAccumulator()

        self._append_exterior_layers(
            layers=layers,
            exterior_finish=exterior_finish,
            exterior_cavity_type=exterior_cavity_type,
        )

        if nominal_exterior_insulation_r > 0:
            ext_ins_material = CONTINUOUS_INSULATION_MATERIAL_MAP[
                exterior_insulation_material
            ]
            layers.add_nominal_r_layer(
                material=ext_ins_material,
                nominal_r_value=nominal_exterior_insulation_r,
            )

        self._append_structural_layers(
            layers=layers,
            effective_nominal_cavity_insulation_r=(
                self.effective_nominal_cavity_insulation_r(
                    nominal_cavity_insulation_r=nominal_cavity_insulation_r
                )
            ),
            cavity_insulation_material=cavity_insulation_material,
        )

        if nominal_interior_insulation_r > 0:
            int_ins_material = CONTINUOUS_INSULATION_MATERIAL_MAP[
                interior_insulation_material
            ]
            layers.add_nominal_r_layer(
                material=int_ins_material,
                nominal_r_value=nominal_interior_insulation_r,
            )

        self._append_interior_finish(
            layers=layers,
            interior_finish=interior_finish,
        )
        return layers.layers

    def _append_exterior_layers(
        self,
        *,
        layers: _RoofLayerAccumulator,
        exterior_finish: RoofExteriorFinish,
        exterior_cavity_type: ExteriorCavityType,
    ) -> None:
        exterior_finish_template = EXTERIOR_FINISH_TEMPLATES[exterior_finish]

        # ISO 6946:2017 Section 6.9 -- for well-ventilated cavities, cladding and
        # air-layer resistance are disregarded.
        if (
            exterior_finish_template is not None
            and exterior_cavity_type != "well_ventilated"
        ):
            layers.add_material_layer(
                material=exterior_finish_template.material_name,
                thickness_m=exterior_finish_template.thickness_m,
            )

        # ISO 6946:2017 Section 6.9 -- for unventilated cavities, include a still
        # air-gap thermal resistance layer.
        if (
            exterior_cavity_type == "unventilated"
            and exterior_finish_template is not None
        ):
            layers.add_material_layer(
                material=AIR_GAP_ROOF,
                thickness_m=_AIR_GAP_THICKNESS_M,
            )

    def _append_interior_finish(
        self,
        *,
        layers: _RoofLayerAccumulator,
        interior_finish: RoofInteriorFinish,
    ) -> None:
        interior_finish_template = INTERIOR_FINISH_TEMPLATES[interior_finish]
        if interior_finish_template is None:
            return
        layers.add_material_layer(
            material=interior_finish_template.material_name,
            thickness_m=interior_finish_template.thickness_m,
        )

    @abstractmethod
    def _append_structural_layers(
        self,
        *,
        layers: _RoofLayerAccumulator,
        effective_nominal_cavity_insulation_r: float,
        cavity_insulation_material: CavityInsulationMaterial,
    ) -> None:
        """Append system-specific structural layers."""


class _LayeredRoofAssemblyBuilder(_ComposedRoofAssemblyBuilder):
    """Roof strategy for monolithic/solid assemblies with optional cavity layer."""

    def _append_structural_layers(
        self,
        *,
        layers: _RoofLayerAccumulator,
        effective_nominal_cavity_insulation_r: float,
        cavity_insulation_material: CavityInsulationMaterial,
    ) -> None:
        if self.template.thickness_m > 0:
            layers.add_material_layer(
                material=self.template.material_name,
                thickness_m=self.template.thickness_m,
            )

        if (
            effective_nominal_cavity_insulation_r > 0
            and self.template.supports_cavity_insulation
        ):
            cavity_ins_material = CAVITY_INSULATION_MATERIAL_MAP[
                cavity_insulation_material
            ]
            effective_cavity_r = (
                effective_nominal_cavity_insulation_r
                * self.template.cavity_r_correction_factor
            )
            layers.add_nominal_r_layer(
                material=cavity_ins_material,
                nominal_r_value=effective_cavity_r,
            )


class _FramedCavityRoofAssemblyBuilder(_ComposedRoofAssemblyBuilder):
    """Roof strategy for framed systems using consolidated cavity materials."""

    def _append_structural_layers(
        self,
        *,
        layers: _RoofLayerAccumulator,
        effective_nominal_cavity_insulation_r: float,
        cavity_insulation_material: CavityInsulationMaterial,
    ) -> None:
        if (
            self.template.cavity_depth_m is None
            or self.template.framing_material_name is None
            or self.template.framing_fraction is None
        ):
            msg = (
                f"Framed roof builder for '{self.structural_system}' is missing "
                "framing metadata."
            )
            raise ValueError(msg)

        cavity_ins_mat_name = CAVITY_INSULATION_MATERIAL_MAP[cavity_insulation_material]
        consolidated_cavity_material = equivalent_framed_cavity_material(
            structural_system=self.structural_system,
            cavity_depth_m=self.template.cavity_depth_m,
            framing_material=self.template.framing_material_name,
            framing_fraction=self.template.framing_fraction,
            framing_path_r_value=self.template.framing_path_r_value,
            nominal_cavity_insulation_r=effective_nominal_cavity_insulation_r,
            uninsulated_cavity_r_value=self.template.uninsulated_cavity_r_value,
            cavity_insulation_material=cavity_ins_mat_name,
        )
        layers.add_material_layer(
            material=consolidated_cavity_material,
            thickness_m=self.template.cavity_depth_m,
        )


def _make_roof_assembly_builder(
    structural_system: RoofStructuralSystem,
    template: StructuralTemplate,
) -> _RoofAssemblyBuilder:
    """Return the roof builder strategy for a structural system."""
    uses_framed_cavity_consolidation = (
        template.supports_cavity_insulation
        and template.cavity_depth_m is not None
        and template.framing_material_name is not None
        and template.framing_fraction is not None
    )
    if uses_framed_cavity_consolidation:
        return _FramedCavityRoofAssemblyBuilder(
            structural_system=structural_system,
            template=template,
        )

    return _LayeredRoofAssemblyBuilder(
        structural_system=structural_system,
        template=template,
    )


STRUCTURAL_BUILDERS: dict[RoofStructuralSystem, _RoofAssemblyBuilder] = {
    structural_system: _make_roof_assembly_builder(structural_system, template)
    for structural_system, template in STRUCTURAL_TEMPLATES.items()
}
_missing_builder_systems = set(ALL_ROOF_STRUCTURAL_SYSTEMS) - set(STRUCTURAL_BUILDERS)
if _missing_builder_systems:
    msg = "Roof builder registry does not cover all structural systems: " + ", ".join(
        sorted(_missing_builder_systems)
    )
    raise ValueError(msg)


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
    exterior_insulation_material: ContinuousInsulationMaterial = Field(
        default="polyiso",
        title="Exterior continuous roof insulation material",
    )
    interior_insulation_material: ContinuousInsulationMaterial = Field(
        default="polyiso",
        title="Interior continuous roof insulation material",
    )
    cavity_insulation_material: CavityInsulationMaterial = Field(
        default="fiberglass",
        title="Cavity insulation material for framed roof systems",
    )
    interior_finish: RoofInteriorFinish = Field(
        default="gypsum_board",
        title="Interior roof finish selection",
    )
    exterior_finish: RoofExteriorFinish = Field(
        default="epdm_membrane",
        title="Exterior roof finish selection",
    )
    exterior_cavity_type: ExteriorCavityType = Field(
        default="none",
        title="Exterior ventilation cavity type per ISO 6946:2017 Section 6.9",
    )

    @property
    def effective_nominal_cavity_insulation_r(self) -> float:
        """Return cavity insulation R-value after applying compatibility defaults."""
        builder = STRUCTURAL_BUILDERS[self.structural_system]
        return builder.effective_nominal_cavity_insulation_r(
            self.nominal_cavity_insulation_r
        )

    @property
    def ignored_feature_names(self) -> tuple[str, ...]:
        """Return feature names that are semantic no-ops for this roof."""
        builder = STRUCTURAL_BUILDERS[self.structural_system]
        return builder.ignored_feature_names(self.nominal_cavity_insulation_r)

    @model_validator(mode="after")
    def validate_cavity_r_against_assumed_depth(self):
        """Guard impossible cavity R-values for cavity-compatible systems."""
        builder = STRUCTURAL_BUILDERS[self.structural_system]
        builder.validate_nominal_cavity_insulation_r(
            nominal_cavity_insulation_r=self.nominal_cavity_insulation_r,
            cavity_insulation_material=self.cavity_insulation_material,
        )
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
        for ins_mat in ALL_CONTINUOUS_INSULATION_MATERIALS:
            features[f"{prefix}ExteriorInsulationMaterial__{ins_mat}"] = float(
                self.exterior_insulation_material == ins_mat
            )
            features[f"{prefix}InteriorInsulationMaterial__{ins_mat}"] = float(
                self.interior_insulation_material == ins_mat
            )
        for cav_ins_mat in ALL_CAVITY_INSULATION_MATERIALS:
            features[f"{prefix}CavityInsulationMaterial__{cav_ins_mat}"] = float(
                self.cavity_insulation_material == cav_ins_mat
            )
        for cavity_type in ALL_EXTERIOR_CAVITY_TYPES:
            features[f"{prefix}ExteriorCavityType__{cavity_type}"] = float(
                self.exterior_cavity_type == cavity_type
            )
        return features


def build_roof_assembly(
    roof: SemiFlatRoofConstruction,
    *,
    name: str = "Roof",
) -> ConstructionAssemblyComponent:
    """Translate semi-flat roof inputs into a concrete roof assembly."""
    builder = STRUCTURAL_BUILDERS[roof.structural_system]
    layers = builder.build_layers(
        nominal_cavity_insulation_r=roof.nominal_cavity_insulation_r,
        nominal_exterior_insulation_r=roof.nominal_exterior_insulation_r,
        nominal_interior_insulation_r=roof.nominal_interior_insulation_r,
        exterior_insulation_material=roof.exterior_insulation_material,
        interior_insulation_material=roof.interior_insulation_material,
        cavity_insulation_material=roof.cavity_insulation_material,
        interior_finish=roof.interior_finish,
        exterior_finish=roof.exterior_finish,
        exterior_cavity_type=roof.exterior_cavity_type,
    )
    return ConstructionAssemblyComponent(
        Name=name,
        Type="FlatRoof",
        Layers=layers,
    )
