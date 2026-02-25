"""Semi-flat wall schema and translators for SBEM assemblies."""

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
    AIR_GAP_WALL,
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

WallStructuralSystem = Literal[
    "none",
    "sheet_metal",
    "light_gauge_steel",
    "structural_steel",
    "woodframe",
    "deep_woodframe",
    "woodframe_24oc",
    "deep_woodframe_24oc",
    "engineered_timber",
    "timber_panel",
    "cmu",
    "double_layer_cmu",
    "precast_concrete",
    "poured_concrete",
    "masonry",
    "cavity_masonry",
    "rammed_earth",
    "thick_rammed_earth",
    "reinforced_concrete",
    "sip",
    "icf",
    "aac",
    "thick_aac",
    "hollow_clay_block",
    "thick_hollow_clay_block",
    "sandcrete_block",
    "thick_sandcrete_block",
    "stabilized_soil_block",
    "wattle_and_daub",
    "adobe_block",
    "compressed_earth_block",
    "cob",
    "laterite_stone",
    "stone_wall",
    "confined_masonry",
    "rc_frame_masonry_infill",
    "corrugated_metal_sheet",
    "insulated_metal_panel",
    "bamboo_frame",
]

WallInteriorFinish = Literal[
    "none", "drywall", "plaster", "cement_plaster", "wood_panel"
]
WallExteriorFinish = Literal[
    "none",
    "brick_veneer",
    "stucco",
    "fiber_cement",
    "metal_panel",
    "vinyl_siding",
    "wood_siding",
    "stone_veneer",
]

ALL_WALL_STRUCTURAL_SYSTEMS = get_args(WallStructuralSystem)
ALL_WALL_INTERIOR_FINISHES = get_args(WallInteriorFinish)
ALL_WALL_EXTERIOR_FINISHES = get_args(WallExteriorFinish)


@dataclass(frozen=True)
class StructuralTemplate:
    """Default structural wall assumptions for a structural system."""

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
    """Default finish material and thickness assumptions."""

    material_name: MaterialName
    thickness_m: float


STRUCTURAL_TEMPLATES: dict[WallStructuralSystem, StructuralTemplate] = {
    "none": StructuralTemplate(
        material_name="GypsumBoard",
        thickness_m=0.005,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "sheet_metal": StructuralTemplate(
        material_name="SteelPanel",
        thickness_m=0.001,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "light_gauge_steel": StructuralTemplate(
        material_name="SteelPanel",
        thickness_m=0.0,
        supports_cavity_insulation=True,
        cavity_depth_m=0.090,
        framing_material_name="SteelPanel",
        framing_fraction=0.12,
        # Calibrated to reproduce ~55% effective batt R for 3.5in (89mm) steel-stud
        # walls at 16" o.c. spacing. Not directly applicable to EU lightweight steel
        # framing, which uses different stud profiles and spacing conventions.
        # References:
        # - ASHRAE Standard 90.1 Appendix A (metal-framing correction methodology)
        # - COMcheck steel-framed wall U-factor datasets (effective-R behavior)
        framing_path_r_value=0.26,
    ),
    "structural_steel": StructuralTemplate(
        material_name="SteelPanel",
        thickness_m=0.006,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "woodframe": StructuralTemplate(
        material_name="SoftwoodGeneral",
        thickness_m=0.0,
        supports_cavity_insulation=True,
        cavity_depth_m=0.090,
        framing_material_name="SoftwoodGeneral",
        framing_fraction=0.23,
    ),
    "deep_woodframe": StructuralTemplate(
        material_name="SoftwoodGeneral",
        thickness_m=0.0,
        supports_cavity_insulation=True,
        cavity_depth_m=0.140,
        framing_material_name="SoftwoodGeneral",
        framing_fraction=0.23,
    ),
    "woodframe_24oc": StructuralTemplate(
        material_name="SoftwoodGeneral",
        thickness_m=0.0,
        supports_cavity_insulation=True,
        cavity_depth_m=0.090,
        framing_material_name="SoftwoodGeneral",
        framing_fraction=0.17,
    ),
    "deep_woodframe_24oc": StructuralTemplate(
        material_name="SoftwoodGeneral",
        thickness_m=0.0,
        supports_cavity_insulation=True,
        cavity_depth_m=0.140,
        framing_material_name="SoftwoodGeneral",
        framing_fraction=0.17,
    ),
    "engineered_timber": StructuralTemplate(
        material_name="SoftwoodGeneral",
        thickness_m=0.160,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "cmu": StructuralTemplate(
        material_name="ConcreteBlockH",
        thickness_m=0.190,
        supports_cavity_insulation=True,
        cavity_depth_m=0.090,
        cavity_r_correction_factor=0.90,
    ),
    "double_layer_cmu": StructuralTemplate(
        material_name="ConcreteBlockH",
        thickness_m=0.290,
        supports_cavity_insulation=True,
        cavity_depth_m=0.140,
        cavity_r_correction_factor=0.92,
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
    "masonry": StructuralTemplate(
        material_name="ClayBrick",
        thickness_m=0.190,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "rammed_earth": StructuralTemplate(
        material_name="RammedEarth",
        thickness_m=0.350,
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
        thickness_m=0.150,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "icf": StructuralTemplate(
        material_name="ConcreteRC_Dense",
        thickness_m=0.150,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "timber_panel": StructuralTemplate(
        material_name="SoftwoodGeneral",
        thickness_m=0.018,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    # UK/EU two-leaf cavity wall: inner leaf (block) + cavity + outer leaf (brick
    # veneer via exterior finish). The template represents the inner leaf; the
    # cavity supports injected or partial-fill insulation. Outer leaf is applied
    # via the exterior_finish field (e.g. "brick_veneer").
    "cavity_masonry": StructuralTemplate(
        material_name="ConcreteBlockH",
        thickness_m=0.100,
        supports_cavity_insulation=True,
        cavity_depth_m=0.075,
        cavity_r_correction_factor=0.90,
    ),
    "thick_rammed_earth": StructuralTemplate(
        material_name="RammedEarth",
        thickness_m=0.500,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "aac": StructuralTemplate(
        material_name="AACBlock",
        thickness_m=0.200,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "thick_aac": StructuralTemplate(
        material_name="AACBlock",
        thickness_m=0.300,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "hollow_clay_block": StructuralTemplate(
        material_name="HollowClayBlock",
        thickness_m=0.250,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "thick_hollow_clay_block": StructuralTemplate(
        material_name="HollowClayBlock",
        thickness_m=0.365,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "sandcrete_block": StructuralTemplate(
        material_name="SandcreteBlock",
        thickness_m=0.150,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "thick_sandcrete_block": StructuralTemplate(
        material_name="SandcreteBlock",
        thickness_m=0.225,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "stabilized_soil_block": StructuralTemplate(
        material_name="StabilizedSoilBlock",
        thickness_m=0.150,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "wattle_and_daub": StructuralTemplate(
        material_name="WattleDaub",
        thickness_m=0.150,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "adobe_block": StructuralTemplate(
        material_name="AdobeBlock",
        thickness_m=0.300,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "compressed_earth_block": StructuralTemplate(
        material_name="CompressedEarthBlock",
        thickness_m=0.200,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "cob": StructuralTemplate(
        material_name="CobEarth",
        thickness_m=0.400,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "laterite_stone": StructuralTemplate(
        material_name="NaturalStone",
        thickness_m=0.300,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "stone_wall": StructuralTemplate(
        material_name="NaturalStone",
        thickness_m=0.450,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    # Confined masonry: masonry panels confined by RC tie-columns/beams.
    # Area-weighted blend of ~85% clay brick + ~15% RC concrete.
    "confined_masonry": StructuralTemplate(
        material_name="ConfinedMasonryEffective",
        thickness_m=0.150,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    # RC frame with masonry infill: ~75% masonry + ~25% RC frame members.
    "rc_frame_masonry_infill": StructuralTemplate(
        material_name="RCFrameInfillEffective",
        thickness_m=0.200,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "corrugated_metal_sheet": StructuralTemplate(
        material_name="SteelPanel",
        thickness_m=0.0005,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    # IMP: foam core only; builder emits outer/inner steel skins separately.
    "insulated_metal_panel": StructuralTemplate(
        material_name="SIPCore",
        thickness_m=0.075,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "bamboo_frame": StructuralTemplate(
        material_name="BambooComposite",
        thickness_m=0.050,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
}

INTERIOR_FINISH_TEMPLATES: dict[WallInteriorFinish, FinishTemplate | None] = {
    "none": None,
    "drywall": FinishTemplate(
        material_name="GypsumBoard",
        thickness_m=0.0127,
    ),
    "plaster": FinishTemplate(
        material_name="GypsumPlaster",
        thickness_m=0.013,
    ),
    "cement_plaster": FinishTemplate(
        material_name="CementMortar",
        thickness_m=0.015,
    ),
    "wood_panel": FinishTemplate(
        material_name="SoftwoodGeneral",
        thickness_m=0.012,
    ),
}

EXTERIOR_FINISH_TEMPLATES: dict[WallExteriorFinish, FinishTemplate | None] = {
    "none": None,
    "brick_veneer": FinishTemplate(
        material_name="ClayBrick",
        thickness_m=0.090,
    ),
    "stucco": FinishTemplate(
        material_name="CementMortar",
        thickness_m=0.020,
    ),
    "fiber_cement": FinishTemplate(
        material_name="FiberCementBoard",
        thickness_m=0.012,
    ),
    "metal_panel": FinishTemplate(
        material_name="SteelPanel",
        thickness_m=0.001,
    ),
    "vinyl_siding": FinishTemplate(
        material_name="VinylSiding",
        thickness_m=0.0015,
    ),
    "wood_siding": FinishTemplate(
        material_name="SoftwoodGeneral",
        thickness_m=0.018,
    ),
    "stone_veneer": FinishTemplate(
        material_name="NaturalStone",
        thickness_m=0.025,
    ),
}


@dataclass
class _WallLayerAccumulator:
    """Track wall layers while keeping layer-order assignments consistent."""

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


class _WallAssemblyBuilder(ABC):
    """Abstract wall assembly strategy."""

    def __init__(
        self,
        *,
        structural_system: WallStructuralSystem,
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
        interior_finish: WallInteriorFinish,
        exterior_finish: WallExteriorFinish,
        exterior_cavity_type: ExteriorCavityType,
    ) -> list[ConstructionLayerComponent]:
        """Build wall layers from high-level assembly inputs."""


class _ComposedWallAssemblyBuilder(_WallAssemblyBuilder, ABC):
    """Shared wall-builder flow with subclassed structural logic."""

    def build_layers(
        self,
        *,
        nominal_cavity_insulation_r: float,
        nominal_exterior_insulation_r: float,
        nominal_interior_insulation_r: float,
        exterior_insulation_material: ContinuousInsulationMaterial,
        interior_insulation_material: ContinuousInsulationMaterial,
        cavity_insulation_material: CavityInsulationMaterial,
        interior_finish: WallInteriorFinish,
        exterior_finish: WallExteriorFinish,
        exterior_cavity_type: ExteriorCavityType,
    ) -> list[ConstructionLayerComponent]:
        """Build wall layers outside-in while delegating structural core logic."""
        layers = _WallLayerAccumulator()

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
        layers: _WallLayerAccumulator,
        exterior_finish: WallExteriorFinish,
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
                material=AIR_GAP_WALL,
                thickness_m=_AIR_GAP_THICKNESS_M,
            )

    def _append_interior_finish(
        self,
        *,
        layers: _WallLayerAccumulator,
        interior_finish: WallInteriorFinish,
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
        layers: _WallLayerAccumulator,
        effective_nominal_cavity_insulation_r: float,
        cavity_insulation_material: CavityInsulationMaterial,
    ) -> None:
        """Append system-specific structural layers."""


class _LayeredWallAssemblyBuilder(_ComposedWallAssemblyBuilder):
    """Wall strategy for monolithic/solid assemblies with optional cavity layer."""

    def _append_structural_layers(
        self,
        *,
        layers: _WallLayerAccumulator,
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


class _FramedCavityWallAssemblyBuilder(_ComposedWallAssemblyBuilder):
    """Wall strategy for framed systems using consolidated cavity materials."""

    def _append_structural_layers(
        self,
        *,
        layers: _WallLayerAccumulator,
        effective_nominal_cavity_insulation_r: float,
        cavity_insulation_material: CavityInsulationMaterial,
    ) -> None:
        if (
            self.template.cavity_depth_m is None
            or self.template.framing_material_name is None
            or self.template.framing_fraction is None
        ):
            msg = (
                f"Framed wall builder for '{self.structural_system}' is missing "
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


class _InsulatedMetalPanelWallAssemblyBuilder(_ComposedWallAssemblyBuilder):
    """Wall strategy for insulated metal panels (outer skin + core + inner skin)."""

    _skin_thickness_m = 0.0005

    def _append_structural_layers(
        self,
        *,
        layers: _WallLayerAccumulator,
        effective_nominal_cavity_insulation_r: float,
        cavity_insulation_material: CavityInsulationMaterial,
    ) -> None:
        del effective_nominal_cavity_insulation_r, cavity_insulation_material
        layers.add_material_layer(
            material="SteelPanel",
            thickness_m=self._skin_thickness_m,
        )
        if self.template.thickness_m > 0:
            layers.add_material_layer(
                material=self.template.material_name,
                thickness_m=self.template.thickness_m,
            )
        layers.add_material_layer(
            material="SteelPanel",
            thickness_m=self._skin_thickness_m,
        )


def _make_wall_assembly_builder(
    structural_system: WallStructuralSystem,
    template: StructuralTemplate,
) -> _WallAssemblyBuilder:
    """Return the wall builder strategy for a structural system."""
    if structural_system == "insulated_metal_panel":
        return _InsulatedMetalPanelWallAssemblyBuilder(
            structural_system=structural_system,
            template=template,
        )

    uses_framed_cavity_consolidation = (
        template.supports_cavity_insulation
        and template.cavity_depth_m is not None
        and template.framing_material_name is not None
        and template.framing_fraction is not None
    )
    if uses_framed_cavity_consolidation:
        return _FramedCavityWallAssemblyBuilder(
            structural_system=structural_system,
            template=template,
        )

    return _LayeredWallAssemblyBuilder(
        structural_system=structural_system,
        template=template,
    )


STRUCTURAL_BUILDERS: dict[WallStructuralSystem, _WallAssemblyBuilder] = {
    structural_system: _make_wall_assembly_builder(structural_system, template)
    for structural_system, template in STRUCTURAL_TEMPLATES.items()
}
_missing_builder_systems = set(ALL_WALL_STRUCTURAL_SYSTEMS) - set(STRUCTURAL_BUILDERS)
if _missing_builder_systems:
    msg = "Wall builder registry does not cover all structural systems: " + ", ".join(
        sorted(_missing_builder_systems)
    )
    raise ValueError(msg)


class SemiFlatWallConstruction(BaseModel):
    """Semantic wall representation for fixed-length flat model vectors."""

    structural_system: WallStructuralSystem = Field(
        default="cmu",
        title="Structural system for thermal mass assumptions",
    )
    nominal_cavity_insulation_r: float = Field(
        default=0.0,
        ge=0,
        title="Nominal cavity insulation R-value [m²K/W]",
    )
    nominal_exterior_insulation_r: float = Field(
        default=0.0,
        ge=0,
        title="Nominal exterior continuous insulation R-value [m²K/W]",
    )
    nominal_interior_insulation_r: float = Field(
        default=0.0,
        ge=0,
        title="Nominal interior continuous insulation R-value [m²K/W]",
    )
    exterior_insulation_material: ContinuousInsulationMaterial = Field(
        default="xps",
        title="Exterior continuous insulation material",
    )
    interior_insulation_material: ContinuousInsulationMaterial = Field(
        default="xps",
        title="Interior continuous insulation material",
    )
    cavity_insulation_material: CavityInsulationMaterial = Field(
        default="fiberglass",
        title="Cavity insulation material for framed/cavity systems",
    )
    interior_finish: WallInteriorFinish = Field(
        default="drywall",
        title="Interior finish selection",
    )
    exterior_finish: WallExteriorFinish = Field(
        default="none",
        title="Exterior finish selection",
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
        """Return feature names that are semantic no-ops for this wall."""
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

    def to_feature_dict(self, prefix: str = "Facade") -> dict[str, float]:
        """Return a fixed-length numeric feature dictionary for ML workflows."""
        features: dict[str, float] = {
            f"{prefix}NominalCavityInsulationRValue": self.nominal_cavity_insulation_r,
            f"{prefix}NominalExteriorInsulationRValue": self.nominal_exterior_insulation_r,
            f"{prefix}NominalInteriorInsulationRValue": self.nominal_interior_insulation_r,
            f"{prefix}EffectiveNominalCavityInsulationRValue": (
                self.effective_nominal_cavity_insulation_r
            ),
        }

        for structural_system in ALL_WALL_STRUCTURAL_SYSTEMS:
            features[f"{prefix}StructuralSystem__{structural_system}"] = float(
                self.structural_system == structural_system
            )
        for interior_finish in ALL_WALL_INTERIOR_FINISHES:
            features[f"{prefix}InteriorFinish__{interior_finish}"] = float(
                self.interior_finish == interior_finish
            )
        for exterior_finish in ALL_WALL_EXTERIOR_FINISHES:
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


def build_facade_assembly(
    wall: SemiFlatWallConstruction,
    *,
    name: str = "Facade",
) -> ConstructionAssemblyComponent:
    """Translate semi-flat wall inputs into a concrete facade assembly."""
    builder = STRUCTURAL_BUILDERS[wall.structural_system]
    layers = builder.build_layers(
        nominal_cavity_insulation_r=wall.nominal_cavity_insulation_r,
        nominal_exterior_insulation_r=wall.nominal_exterior_insulation_r,
        nominal_interior_insulation_r=wall.nominal_interior_insulation_r,
        exterior_insulation_material=wall.exterior_insulation_material,
        interior_insulation_material=wall.interior_insulation_material,
        cavity_insulation_material=wall.cavity_insulation_material,
        interior_finish=wall.interior_finish,
        exterior_finish=wall.exterior_finish,
        exterior_cavity_type=wall.exterior_cavity_type,
    )
    return ConstructionAssemblyComponent(
        Name=name,
        Type="Facade",
        Layers=layers,
    )
