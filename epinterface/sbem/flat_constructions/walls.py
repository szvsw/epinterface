"""Semi-flat wall schema and translators for SBEM assemblies."""

from dataclasses import dataclass
from typing import Literal, get_args

from pydantic import BaseModel, Field, model_validator

from epinterface.sbem.components.envelope import (
    ConstructionAssemblyComponent,
    ConstructionLayerComponent,
)
from epinterface.sbem.flat_constructions.layers import (
    _AIR_GAP_THICKNESS_M,
    AIR_GAP_WALL,
    ALL_CONTINUOUS_INSULATION_MATERIALS,
    ALL_EXTERIOR_CAVITY_TYPES,
    CONTINUOUS_INSULATION_MATERIAL_MAP,
    ContinuousInsulationMaterial,
    ExteriorCavityType,
    equivalent_framed_cavity_material,
    layer_from_nominal_r,
    resolve_material,
)
from epinterface.sbem.flat_constructions.materials import FIBERGLASS_BATTS, MaterialName

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
        # Calibrated to reproduce ~55% effective batt R for 3.5in steel-stud walls.
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
        template = STRUCTURAL_TEMPLATES[self.structural_system]
        if not template.supports_cavity_insulation:
            return 0.0
        return self.nominal_cavity_insulation_r

    @property
    def ignored_feature_names(self) -> tuple[str, ...]:
        """Return feature names that are semantic no-ops for this wall."""
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
    template = STRUCTURAL_TEMPLATES[wall.structural_system]
    layers: list[ConstructionLayerComponent] = []
    layer_order = 0

    exterior_finish = EXTERIOR_FINISH_TEMPLATES[wall.exterior_finish]

    # ISO 6946:2017 Section 6.9 -- well-ventilated cavities: disregard cladding
    # and air layer R. We omit the finish layer entirely; EnergyPlus applies its
    # own exterior surface coefficient to the next layer inward.
    if exterior_finish is not None and wall.exterior_cavity_type != "well_ventilated":
        layers.append(
            ConstructionLayerComponent(
                ConstructionMaterial=resolve_material(exterior_finish.material_name),
                Thickness=exterior_finish.thickness_m,
                LayerOrder=layer_order,
            )
        )
        layer_order += 1

    # ISO 6946:2017 Section 6.9 -- unventilated cavities: add equivalent
    # still-air thermal resistance (~0.18 m2K/W for 25mm vertical gap).
    # TODO: use a proper air gap material here
    if wall.exterior_cavity_type == "unventilated" and exterior_finish is not None:
        layers.append(
            ConstructionLayerComponent(
                ConstructionMaterial=AIR_GAP_WALL,
                Thickness=_AIR_GAP_THICKNESS_M,
                LayerOrder=layer_order,
            )
        )
        layer_order += 1

    if wall.nominal_exterior_insulation_r > 0:
        ext_ins_material = CONTINUOUS_INSULATION_MATERIAL_MAP[
            wall.exterior_insulation_material
        ]
        layers.append(
            layer_from_nominal_r(
                material=ext_ins_material,
                nominal_r_value=wall.nominal_exterior_insulation_r,
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
            structural_system=wall.structural_system,
            cavity_depth_m=template.cavity_depth_m or 0.0,
            framing_material=template.framing_material_name or "SoftwoodGeneral",
            framing_fraction=template.framing_fraction or 0.0,
            framing_path_r_value=template.framing_path_r_value,
            nominal_cavity_insulation_r=wall.effective_nominal_cavity_insulation_r,
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

        if (
            wall.effective_nominal_cavity_insulation_r > 0
            and template.supports_cavity_insulation
        ):
            effective_cavity_r = (
                wall.effective_nominal_cavity_insulation_r
                * template.cavity_r_correction_factor
            )
            layers.append(
                layer_from_nominal_r(
                    # TODO: make this configurable with a CavityInsulationMaterial field
                    # e.g. blown cellulose, fiberglass, etc.
                    material="FiberglassBatt",
                    nominal_r_value=effective_cavity_r,
                    layer_order=layer_order,
                )
            )
            layer_order += 1

    if wall.nominal_interior_insulation_r > 0:
        int_ins_material = CONTINUOUS_INSULATION_MATERIAL_MAP[
            wall.interior_insulation_material
        ]
        layers.append(
            layer_from_nominal_r(
                material=int_ins_material,
                nominal_r_value=wall.nominal_interior_insulation_r,
                layer_order=layer_order,
            )
        )
        layer_order += 1

    interior_finish = INTERIOR_FINISH_TEMPLATES[wall.interior_finish]
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
        Type="Facade",
        Layers=layers,
    )
