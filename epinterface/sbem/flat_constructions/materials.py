"""Shared opaque materials used by semi-flat construction builders."""

from typing import Literal, cast, get_args

from epinterface.sbem.components.materials import ConstructionMaterialComponent

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

MATERIAL_NAME_VALUES: tuple[MaterialName, ...] = get_args(MaterialName)


def _material(
    *,
    name: str,
    conductivity: float,
    density: float,
    specific_heat: float,
    mat_type: str,
) -> ConstructionMaterialComponent:
    """Create a construction material component with common optical defaults."""
    return ConstructionMaterialComponent(
        Name=name,
        Conductivity=conductivity,
        Density=density,
        SpecificHeat=specific_heat,
        ThermalAbsorptance=0.9,
        SolarAbsorptance=0.6,
        VisibleAbsorptance=0.6,
        TemperatureCoefficientThermalConductivity=0.0,
        Roughness="MediumRough",
        Type=mat_type,  # pyright: ignore[reportArgumentType]
    )


XPS_BOARD = _material(
    name="XPSBoard",
    conductivity=0.037,
    density=40,
    specific_heat=1200,
    mat_type="Insulation",
)

POLYISO_BOARD = _material(
    name="PolyisoBoard",
    conductivity=0.024,
    density=32,
    specific_heat=1400,
    mat_type="Insulation",
)

CONCRETE_MC_LIGHT = _material(
    name="ConcreteMC_Light",
    conductivity=1.20,
    density=1700,
    specific_heat=900,
    mat_type="Concrete",
)

CONCRETE_RC_DENSE = _material(
    name="ConcreteRC_Dense",
    conductivity=1.95,
    density=2300,
    specific_heat=900,
    mat_type="Concrete",
)

GYPSUM_BOARD = _material(
    name="GypsumBoard",
    conductivity=0.16,
    density=950,
    specific_heat=840,
    mat_type="Finishes",
)

GYPSUM_PLASTER = _material(
    name="GypsumPlaster",
    conductivity=0.42,
    density=900,
    specific_heat=840,
    mat_type="Finishes",
)

SOFTWOOD_GENERAL = _material(
    name="SoftwoodGeneral",
    conductivity=0.12,
    density=500,
    specific_heat=1630,
    mat_type="Timber",
)

CLAY_BRICK = _material(
    name="ClayBrick",
    conductivity=0.69,
    density=1700,
    specific_heat=840,
    mat_type="Masonry",
)

CONCRETE_BLOCK_H = _material(
    name="ConcreteBlockH",
    conductivity=0.51,
    density=1100,
    specific_heat=840,
    mat_type="Concrete",
)

FIBERGLASS_BATTS = _material(
    name="FiberglassBatt",
    conductivity=0.043,
    density=12,
    specific_heat=840,
    mat_type="Insulation",
)

CEMENT_MORTAR = _material(
    name="CementMortar",
    conductivity=0.72,
    density=1850,
    specific_heat=840,
    mat_type="Other",
)

CERAMIC_TILE = _material(
    name="CeramicTile",
    conductivity=1.05,
    density=2000,
    specific_heat=840,
    mat_type="Finishes",
)

URETHANE_CARPET = _material(
    name="UrethaneCarpet",
    conductivity=0.06,
    density=160,
    specific_heat=840,
    mat_type="Finishes",
)

STEEL_PANEL = _material(
    name="SteelPanel",
    conductivity=45.0,
    density=7850,
    specific_heat=500,
    mat_type="Metal",
)

RAMMED_EARTH = _material(
    name="RammedEarth",
    conductivity=1.10,
    density=1900,
    specific_heat=1000,
    mat_type="Masonry",
)

SIP_CORE = _material(
    name="SIPCore",
    conductivity=0.026,
    density=35,
    specific_heat=1400,
    mat_type="Insulation",
)

FIBER_CEMENT_BOARD = _material(
    name="FiberCementBoard",
    conductivity=0.35,
    density=1350,
    specific_heat=840,
    mat_type="Siding",
)

ROOF_MEMBRANE = _material(
    name="RoofMembrane",
    conductivity=0.17,
    density=1200,
    specific_heat=900,
    mat_type="Sealing",
)

COOL_ROOF_MEMBRANE = _material(
    name="CoolRoofMembrane",
    conductivity=0.17,
    density=1200,
    specific_heat=900,
    mat_type="Sealing",
)

ACOUSTIC_TILE = _material(
    name="AcousticTile",
    conductivity=0.065,
    density=280,
    specific_heat=840,
    mat_type="Boards",
)

_ALL_MATERIALS = (
    XPS_BOARD,
    POLYISO_BOARD,
    CONCRETE_MC_LIGHT,
    CONCRETE_RC_DENSE,
    GYPSUM_BOARD,
    GYPSUM_PLASTER,
    SOFTWOOD_GENERAL,
    CLAY_BRICK,
    CONCRETE_BLOCK_H,
    FIBERGLASS_BATTS,
    CEMENT_MORTAR,
    CERAMIC_TILE,
    URETHANE_CARPET,
    STEEL_PANEL,
    RAMMED_EARTH,
    SIP_CORE,
    FIBER_CEMENT_BOARD,
    ROOF_MEMBRANE,
    COOL_ROOF_MEMBRANE,
    ACOUSTIC_TILE,
)

MATERIALS_BY_NAME: dict[MaterialName, ConstructionMaterialComponent] = {
    cast(MaterialName, mat.Name): mat for mat in _ALL_MATERIALS
}

_names_in_map = set(MATERIALS_BY_NAME.keys())
_expected_names = set(MATERIAL_NAME_VALUES)
if _names_in_map != _expected_names:
    missing = sorted(_expected_names - _names_in_map)
    extra = sorted(_names_in_map - _expected_names)
    msg = (
        f"Material name definitions are out of sync. Missing={missing}, Extra={extra}."
    )
    raise ValueError(msg)
