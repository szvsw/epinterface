"""Semi-flat roof schema and translators for SBEM assemblies."""

from dataclasses import dataclass
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

        cavity_mat_name = CAVITY_INSULATION_MATERIAL_MAP[
            self.cavity_insulation_material
        ]
        cavity_mat = resolve_material(cavity_mat_name)
        max_nominal_r = template.cavity_depth_m / cavity_mat.Conductivity
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
    # EnergyPlus convention: layer 0 is outermost (outside -> inside).
    template = STRUCTURAL_TEMPLATES[roof.structural_system]
    layers: list[ConstructionLayerComponent] = []
    layer_order = 0

    exterior_finish = EXTERIOR_FINISH_TEMPLATES[roof.exterior_finish]

    # ISO 6946:2017 Section 6.9 -- well-ventilated cavities: disregard cladding
    # and air layer R. Omit the finish layer; EnergyPlus applies its own
    # exterior surface coefficient to the next layer inward.
    if exterior_finish is not None and roof.exterior_cavity_type != "well_ventilated":
        layers.append(
            ConstructionLayerComponent(
                ConstructionMaterial=resolve_material(exterior_finish.material_name),
                Thickness=exterior_finish.thickness_m,
                LayerOrder=layer_order,
            )
        )
        layer_order += 1

    # ISO 6946:2017 Section 6.9 -- unventilated cavities: add equivalent
    # still-air thermal resistance (~0.16 m2K/W for 25mm horizontal gap).
    if roof.exterior_cavity_type == "unventilated" and exterior_finish is not None:
        layers.append(
            ConstructionLayerComponent(
                ConstructionMaterial=AIR_GAP_ROOF,
                Thickness=_AIR_GAP_THICKNESS_M,
                LayerOrder=layer_order,
            )
        )
        layer_order += 1

    if roof.nominal_exterior_insulation_r > 0:
        ext_ins_material = CONTINUOUS_INSULATION_MATERIAL_MAP[
            roof.exterior_insulation_material
        ]
        layers.append(
            layer_from_nominal_r(
                material=ext_ins_material,
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

    cavity_ins_mat_name = CAVITY_INSULATION_MATERIAL_MAP[
        roof.cavity_insulation_material
    ]

    if uses_framed_cavity_consolidation:
        consolidated_cavity_material = equivalent_framed_cavity_material(
            structural_system=roof.structural_system,
            cavity_depth_m=template.cavity_depth_m or 0.0,
            framing_material=template.framing_material_name or "SoftwoodGeneral",
            framing_fraction=template.framing_fraction or 0.0,
            framing_path_r_value=template.framing_path_r_value,
            nominal_cavity_insulation_r=roof.effective_nominal_cavity_insulation_r,
            uninsulated_cavity_r_value=template.uninsulated_cavity_r_value,
            cavity_insulation_material=cavity_ins_mat_name,
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
            roof.effective_nominal_cavity_insulation_r > 0
            and template.supports_cavity_insulation
        ):
            effective_cavity_r = (
                roof.effective_nominal_cavity_insulation_r
                * template.cavity_r_correction_factor
            )
            layers.append(
                layer_from_nominal_r(
                    material=cavity_ins_mat_name,
                    nominal_r_value=effective_cavity_r,
                    layer_order=layer_order,
                )
            )
            layer_order += 1

    if roof.nominal_interior_insulation_r > 0:
        int_ins_material = CONTINUOUS_INSULATION_MATERIAL_MAP[
            roof.interior_insulation_material
        ]
        layers.append(
            layer_from_nominal_r(
                material=int_ins_material,
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
