"""Shared layer and equivalent-material helpers for flat constructions."""

from typing import Literal

from epinterface.sbem.components.envelope import ConstructionLayerComponent
from epinterface.sbem.components.materials import ConstructionMaterialComponent
from epinterface.sbem.flat_constructions.materials import (
    FIBERGLASS_BATTS,
    MATERIALS_BY_NAME,
)

MaterialName = Literal[
    "XPSBoard",
    "PolyisoBoard",
    "ConcreteMC_Light",
    "ConcreteRC_Dense",
    "GypsumBoard",
    "GypsumPlaster",
    "SoftwoodGeneral",
    "ClayBrick",
    "ConcreteBlockH",
    "FiberglassBatt",
    "CementMortar",
    "CeramicTile",
    "UrethaneCarpet",
    "SteelPanel",
    "RammedEarth",
    "SIPCore",
    "FiberCementBoard",
    "RoofMembrane",
    "CoolRoofMembrane",
    "AcousticTile",
]
# Keep `str` in the union so callers with broader string types remain ergonomic,
# while still documenting preferred known names via `MaterialName`.
type MaterialRef = ConstructionMaterialComponent | MaterialName | str


def resolve_material(material: MaterialRef) -> ConstructionMaterialComponent:
    """Resolve a material name or component into a material component."""
    return MATERIALS_BY_NAME[material] if isinstance(material, str) else material


def layer_from_nominal_r(
    *,
    material: MaterialRef,
    nominal_r_value: float,
    layer_order: int,
) -> ConstructionLayerComponent:
    """Create a layer by back-solving thickness from nominal R-value."""
    resolved_material = resolve_material(material)
    thickness_m = nominal_r_value * resolved_material.Conductivity
    return ConstructionLayerComponent(
        ConstructionMaterial=resolved_material,
        Thickness=thickness_m,
        LayerOrder=layer_order,
    )


def equivalent_framed_cavity_material(
    *,
    structural_system: str,
    cavity_depth_m: float,
    framing_material: MaterialRef,
    framing_fraction: float,
    nominal_cavity_insulation_r: float,
    uninsulated_cavity_r_value: float,
    framing_path_r_value: float | None = None,
) -> ConstructionMaterialComponent:
    """Create an equivalent material for a framed cavity layer.

    Uses a parallel-path estimate:
      U_eq = f_frame / R_frame + (1-f_frame) / R_fill
    where R_fill is nominal cavity insulation R (or an uninsulated fallback).
    """
    resolved_framing_material = resolve_material(framing_material)
    fill_r = (
        nominal_cavity_insulation_r
        if nominal_cavity_insulation_r > 0
        else uninsulated_cavity_r_value
    )
    framing_r = (
        framing_path_r_value
        if framing_path_r_value is not None
        else cavity_depth_m / resolved_framing_material.Conductivity
    )
    u_eq = framing_fraction / framing_r + (1 - framing_fraction) / fill_r
    r_eq = 1 / u_eq
    conductivity_eq = cavity_depth_m / r_eq

    density_eq = (
        framing_fraction * resolved_framing_material.Density
        + (1 - framing_fraction) * FIBERGLASS_BATTS.Density
    )
    specific_heat_eq = (
        framing_fraction * resolved_framing_material.SpecificHeat
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
