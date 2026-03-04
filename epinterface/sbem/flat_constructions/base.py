"""An AB base class for flat construction objects which defines the interface for all flat construction objects."""

from typing import Literal

from pydantic.dataclasses import dataclass

from epinterface.sbem.components.materials import ConstructionMaterialComponent
from epinterface.sbem.flat_constructions.materials import (
    MATERIALS_BY_NAME,
    MaterialName,
)

SheathingMaterialName = Literal[
    "Plywood",
    "OSB",
    "ParticleBoard",
    "Fiberboard",
    "ConcreteMC_Light",
    # "MetalSheathing",
    # "Masonry",
]
CavityInsulationMaterialName = Literal[
    "FiberglassBatt",
    "MineralWoolBatt",
    "CelluloseBatt",
]
ContinuousInsulationMaterialName = Literal[
    "XPSBoard",
    "PolyisoBoard",
    "EPSBoard",
    "MineralWoolBoard",
]
FramingMaterialName = Literal[
    "SoftwoodGeneral",
    "ConcreteMC_Light",
    "ConcreteRC_Dense",
    # "LightGaugeSteel",
    # "StructuralSteel",
    # "CMU",
]

MonolithicInfillMaterialName = Literal[
    "ConcreteMC_Light",
    "ConcreteRC_Dense",
    "ClayBrick",
]

MonolithicFramingMaterialName = Literal[
    "ConcreteMC_Light",
    "ConcreteRC_Dense",
    "StructuralSteel",
]

BasicGroundSlabMaterialName = Literal[
    "ConcreteMC_Light",
    "ConcreteRC_Dense",
]


def get_sheathing_material(
    sheathing_material_name: SheathingMaterialName,
) -> ConstructionMaterialComponent:
    """Get the sheathing material component from the material name."""
    return MATERIALS_BY_NAME[sheathing_material_name]


@dataclass(frozen=True)
class MatWithThickness:
    """A material with a thickness."""

    material: ConstructionMaterialComponent
    thickness_m: float


def get_cavity_insulation_material(
    cavity_insulation_material_name: CavityInsulationMaterialName,
    nominal_r_value: float,
) -> MatWithThickness:
    """Get the cavity insulation material component and thickness from the material name and nominal R-value.

    Args:
        cavity_insulation_material_name (CavityInsulationMaterialName): The name of the cavity insulation material.
        nominal_r_value (float): The nominal R-value of the cavity insulation material.

    Returns:
        material_with_thickness (MatWithThickness): The cavity insulation material component and thickness.
    """
    mat = MATERIALS_BY_NAME[cavity_insulation_material_name]
    thickness_m = nominal_r_value * mat.Conductivity
    return MatWithThickness(material=mat, thickness_m=thickness_m)


def get_continuous_insulation_material(
    continuous_insulation_material_name: ContinuousInsulationMaterialName,
    nominal_r_value: float,
) -> MatWithThickness:
    """Get the continuous insulation material component and thickness from the material name and nominal R-value.

    Args:
        continuous_insulation_material_name (ContinuousInsulationMaterialName): The name of the continuous insulation material.
        nominal_r_value (float): The nominal R-value of the continuous insulation material.

    Returns:
        material_with_thickness (MatWithThickness): The continuous insulation material component and thickness.
    """
    mat = MATERIALS_BY_NAME[continuous_insulation_material_name]
    thickness_m = nominal_r_value * mat.Conductivity
    return MatWithThickness(material=mat, thickness_m=thickness_m)


def get_framing_material(
    framing_material_name: FramingMaterialName,
) -> ConstructionMaterialComponent:
    """Get the framing material component from the material name."""
    return MATERIALS_BY_NAME[framing_material_name]


def get_monolithic_framing_material(
    monolithic_framing_material_name: MonolithicFramingMaterialName,
) -> ConstructionMaterialComponent:
    """Get the monolithic framing material component from the material name."""
    return MATERIALS_BY_NAME[monolithic_framing_material_name]


def get_monolithic_infill_material(
    monolithic_infill_material_name: MonolithicInfillMaterialName,
) -> ConstructionMaterialComponent:
    """Get the monolithic infill material component from the material name."""
    return MATERIALS_BY_NAME[monolithic_infill_material_name]


def get_basic_ground_slab_material(
    basic_ground_slab_material_name: BasicGroundSlabMaterialName,
) -> ConstructionMaterialComponent:
    """Get the basic ground slab material component from the material name."""
    return MATERIALS_BY_NAME[basic_ground_slab_material_name]


@dataclass(frozen=True)
class FinishTemplate:
    """Default finish material and thickness assumptions."""

    material_name: MaterialName
    thickness_m: float
