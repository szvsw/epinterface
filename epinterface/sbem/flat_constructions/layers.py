"""Shared layer and equivalent-material helpers for flat constructions."""

from typing import Literal, get_args

from epinterface.sbem.components.envelope import ConstructionLayerComponent
from epinterface.sbem.components.materials import ConstructionMaterialComponent
from epinterface.sbem.flat_constructions.materials import (
    FIBERGLASS_BATTS,
    MATERIALS_BY_NAME,
    MaterialName,
)

type MaterialRef = ConstructionMaterialComponent | MaterialName

ContinuousInsulationMaterial = Literal["xps", "polyiso", "eps", "mineral_wool"]
ALL_CONTINUOUS_INSULATION_MATERIALS = get_args(ContinuousInsulationMaterial)

# TODO: do we really need this map?
CONTINUOUS_INSULATION_MATERIAL_MAP: dict[ContinuousInsulationMaterial, MaterialName] = {
    "xps": "XPSBoard",
    "polyiso": "PolyisoBoard",
    "eps": "EPSBoard",
    "mineral_wool": "MineralWoolBoard",
}

ExteriorCavityType = Literal["none", "unventilated", "well_ventilated"]
ALL_EXTERIOR_CAVITY_TYPES = get_args(ExteriorCavityType)

# ISO 6946:2017 Table 2 -- thermal resistance of unventilated air layers.
# Vertical (walls): ~0.18 m2K/W for 25mm gap.
# Horizontal heat-flow-up (roofs): ~0.16 m2K/W for 25mm gap.
UNVENTILATED_AIR_R_WALL = 0.18
UNVENTILATED_AIR_R_ROOF = 0.16
_AIR_GAP_THICKNESS_M = 0.025


# TODO: should this be a NoMass or AirGap Material instead? Also, make sure it is not on the outside!
def _make_air_gap_material(r_value: float) -> ConstructionMaterialComponent:
    """Create a virtual material representing an unventilated air gap."""
    effective_conductivity = _AIR_GAP_THICKNESS_M / r_value
    return ConstructionMaterialComponent(
        Name=f"AirGap_R{r_value:.2f}",
        Conductivity=effective_conductivity,
        Density=1.2,
        SpecificHeat=1005,
        ThermalAbsorptance=0.9,
        SolarAbsorptance=0.0,
        VisibleAbsorptance=0.0,
        TemperatureCoefficientThermalConductivity=0.0,
        Roughness="Smooth",
        Type="Other",
    )


AIR_GAP_WALL = _make_air_gap_material(UNVENTILATED_AIR_R_WALL)
AIR_GAP_ROOF = _make_air_gap_material(UNVENTILATED_AIR_R_ROOF)


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
