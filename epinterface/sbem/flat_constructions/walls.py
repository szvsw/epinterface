"""Semi-flat wall schema and translators for SBEM assemblies."""

from dataclasses import dataclass
from typing import Literal, get_args

from pydantic import BaseModel, Field, model_validator

from epinterface.sbem.components.envelope import (
    ConstructionAssemblyComponent,
    ConstructionLayerComponent,
)
from epinterface.sbem.components.materials import ConstructionMaterialComponent
from epinterface.sbem.flat_constructions.materials import (
    CEMENT_MORTAR,
    CLAY_BRICK,
    CONCRETE_BLOCK_H,
    CONCRETE_RC_DENSE,
    FIBER_CEMENT_BOARD,
    FIBERGLASS_BATTS,
    GYPSUM_BOARD,
    GYPSUM_PLASTER,
    MATERIALS_BY_NAME,
    RAMMED_EARTH,
    SIP_CORE,
    SOFTWOOD_GENERAL,
    STEEL_PANEL,
    XPS_BOARD,
)

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
    "cmu",
    "double_layer_cmu",
    "precast_concrete",
    "poured_concrete",
    "masonry",
    "rammed_earth",
    "reinforced_concrete",
    "sip",
]

WallInteriorFinish = Literal["none", "drywall", "plaster", "wood_panel"]
WallExteriorFinish = Literal[
    "none",
    "brick_veneer",
    "stucco",
    "fiber_cement",
    "metal_panel",
]

ALL_WALL_STRUCTURAL_SYSTEMS = get_args(WallStructuralSystem)
ALL_WALL_INTERIOR_FINISHES = get_args(WallInteriorFinish)
ALL_WALL_EXTERIOR_FINISHES = get_args(WallExteriorFinish)


@dataclass(frozen=True)
class StructuralTemplate:
    """Default structural wall assumptions for a structural system."""

    material_name: str
    thickness_m: float
    supports_cavity_insulation: bool
    cavity_depth_m: float | None
    framing_material_name: str | None = None
    framing_fraction: float | None = None
    uninsulated_cavity_r_value: float = 0.17
    cavity_r_correction_factor: float = 1.0


@dataclass(frozen=True)
class FinishTemplate:
    """Default finish material and thickness assumptions."""

    material_name: str
    thickness_m: float


STRUCTURAL_TEMPLATES: dict[WallStructuralSystem, StructuralTemplate] = {
    "none": StructuralTemplate(
        material_name=GYPSUM_BOARD.Name,
        thickness_m=0.005,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "sheet_metal": StructuralTemplate(
        material_name=STEEL_PANEL.Name,
        thickness_m=0.001,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "light_gauge_steel": StructuralTemplate(
        material_name=STEEL_PANEL.Name,
        thickness_m=0.004,
        supports_cavity_insulation=True,
        cavity_depth_m=0.090,
        cavity_r_correction_factor=0.55,
    ),
    "structural_steel": StructuralTemplate(
        material_name=STEEL_PANEL.Name,
        thickness_m=0.006,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "woodframe": StructuralTemplate(
        material_name=SOFTWOOD_GENERAL.Name,
        thickness_m=0.0,
        supports_cavity_insulation=True,
        cavity_depth_m=0.090,
        framing_material_name=SOFTWOOD_GENERAL.Name,
        framing_fraction=0.23,
    ),
    "deep_woodframe": StructuralTemplate(
        material_name=SOFTWOOD_GENERAL.Name,
        thickness_m=0.0,
        supports_cavity_insulation=True,
        cavity_depth_m=0.140,
        framing_material_name=SOFTWOOD_GENERAL.Name,
        framing_fraction=0.23,
    ),
    "woodframe_24oc": StructuralTemplate(
        material_name=SOFTWOOD_GENERAL.Name,
        thickness_m=0.0,
        supports_cavity_insulation=True,
        cavity_depth_m=0.090,
        framing_material_name=SOFTWOOD_GENERAL.Name,
        framing_fraction=0.17,
    ),
    "deep_woodframe_24oc": StructuralTemplate(
        material_name=SOFTWOOD_GENERAL.Name,
        thickness_m=0.0,
        supports_cavity_insulation=True,
        cavity_depth_m=0.140,
        framing_material_name=SOFTWOOD_GENERAL.Name,
        framing_fraction=0.17,
    ),
    "engineered_timber": StructuralTemplate(
        material_name=SOFTWOOD_GENERAL.Name,
        thickness_m=0.160,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "cmu": StructuralTemplate(
        material_name=CONCRETE_BLOCK_H.Name,
        thickness_m=0.190,
        supports_cavity_insulation=True,
        cavity_depth_m=0.090,
        cavity_r_correction_factor=0.90,
    ),
    "double_layer_cmu": StructuralTemplate(
        material_name=CONCRETE_BLOCK_H.Name,
        thickness_m=0.290,
        supports_cavity_insulation=True,
        cavity_depth_m=0.140,
        cavity_r_correction_factor=0.92,
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
    "masonry": StructuralTemplate(
        material_name=CLAY_BRICK.Name,
        thickness_m=0.190,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
    "rammed_earth": StructuralTemplate(
        material_name=RAMMED_EARTH.Name,
        thickness_m=0.350,
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
        thickness_m=0.150,
        supports_cavity_insulation=False,
        cavity_depth_m=None,
    ),
}

INTERIOR_FINISH_TEMPLATES: dict[WallInteriorFinish, FinishTemplate | None] = {
    "none": None,
    "drywall": FinishTemplate(
        material_name=GYPSUM_BOARD.Name,
        thickness_m=0.0127,
    ),
    "plaster": FinishTemplate(
        material_name=GYPSUM_PLASTER.Name,
        thickness_m=0.013,
    ),
    "wood_panel": FinishTemplate(
        material_name=SOFTWOOD_GENERAL.Name,
        thickness_m=0.012,
    ),
}

EXTERIOR_FINISH_TEMPLATES: dict[WallExteriorFinish, FinishTemplate | None] = {
    "none": None,
    "brick_veneer": FinishTemplate(
        material_name=CLAY_BRICK.Name,
        thickness_m=0.090,
    ),
    "stucco": FinishTemplate(
        material_name=CEMENT_MORTAR.Name,
        thickness_m=0.020,
    ),
    "fiber_cement": FinishTemplate(
        material_name=FIBER_CEMENT_BOARD.Name,
        thickness_m=0.012,
    ),
    "metal_panel": FinishTemplate(
        material_name=STEEL_PANEL.Name,
        thickness_m=0.001,
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
    interior_finish: WallInteriorFinish = Field(
        default="drywall",
        title="Interior finish selection",
    )
    exterior_finish: WallExteriorFinish = Field(
        default="none",
        title="Exterior finish selection",
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


def _make_layer_from_material(
    *,
    material: ConstructionMaterialComponent,
    thickness_m: float,
    layer_order: int,
) -> ConstructionLayerComponent:
    """Create a construction layer from a material component."""
    return ConstructionLayerComponent(
        ConstructionMaterial=material,
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


def _make_consolidated_cavity_material(
    *,
    structural_system: WallStructuralSystem,
    cavity_depth_m: float,
    framing_material_name: str,
    framing_fraction: float,
    nominal_cavity_insulation_r: float,
    uninsulated_cavity_r_value: float,
) -> ConstructionMaterialComponent:
    """Create an equivalent material for a framed cavity layer.

    Uses a simple parallel-path estimate:
      U_eq = f_frame / R_frame + (1-f_frame) / R_fill
    where R_fill is the user-provided nominal cavity insulation R-value
    (or a default uninsulated cavity R-value when nominal is 0).
    """
    framing_material = MATERIALS_BY_NAME[framing_material_name]
    fill_r = (
        nominal_cavity_insulation_r
        if nominal_cavity_insulation_r > 0
        else uninsulated_cavity_r_value
    )
    framing_r = cavity_depth_m / framing_material.Conductivity
    u_eq = framing_fraction / framing_r + (1 - framing_fraction) / fill_r
    r_eq = 1 / u_eq
    conductivity_eq = cavity_depth_m / r_eq

    density_eq = (
        framing_fraction * framing_material.Density
        + (1 - framing_fraction) * FIBERGLASS_BATTS.Density
    )
    specific_heat_eq = (
        framing_fraction * framing_material.SpecificHeat
        + (1 - framing_fraction) * FIBERGLASS_BATTS.SpecificHeat
    )

    return ConstructionMaterialComponent(
        Name=(
            f"ConsolidatedCavity_{structural_system}_"
            f"Rfill{fill_r:.3f}_f{framing_fraction:.3f}"
        ),
        Conductivity=conductivity_eq,
        Density=density_eq,
        SpecificHeat=specific_heat_eq,
        ThermalAbsorptance=0.9,
        SolarAbsorptance=0.6,
        VisibleAbsorptance=0.6,
        TemperatureCoefficientThermalConductivity=0.0,
        Roughness="MediumRough",
        Type="Other",
    )


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
    if exterior_finish is not None:
        layers.append(
            _make_layer(
                material_name=exterior_finish.material_name,
                thickness_m=exterior_finish.thickness_m,
                layer_order=layer_order,
            )
        )
        layer_order += 1

    if wall.nominal_exterior_insulation_r > 0:
        layers.append(
            _nominal_r_insulation_layer(
                material_name=XPS_BOARD.Name,
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
        consolidated_cavity_material = _make_consolidated_cavity_material(
            structural_system=wall.structural_system,
            cavity_depth_m=template.cavity_depth_m or 0.0,
            framing_material_name=template.framing_material_name
            or SOFTWOOD_GENERAL.Name,
            framing_fraction=template.framing_fraction or 0.0,
            nominal_cavity_insulation_r=wall.effective_nominal_cavity_insulation_r,
            uninsulated_cavity_r_value=template.uninsulated_cavity_r_value,
        )
        layers.append(
            _make_layer_from_material(
                material=consolidated_cavity_material,
                thickness_m=template.cavity_depth_m or 0.0,
                layer_order=layer_order,
            )
        )
        layer_order += 1
    else:
        if template.thickness_m > 0:
            layers.append(
                _make_layer(
                    material_name=template.material_name,
                    thickness_m=template.thickness_m,
                    layer_order=layer_order,
                )
            )
            layer_order += 1

        if wall.effective_nominal_cavity_insulation_r > 0:
            effective_cavity_r = (
                wall.effective_nominal_cavity_insulation_r
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

    if wall.nominal_interior_insulation_r > 0:
        layers.append(
            _nominal_r_insulation_layer(
                material_name=FIBERGLASS_BATTS.Name,
                nominal_r_value=wall.nominal_interior_insulation_r,
                layer_order=layer_order,
            )
        )
        layer_order += 1

    interior_finish = INTERIOR_FINISH_TEMPLATES[wall.interior_finish]
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
        Type="Facade",
        Layers=layers,
    )
