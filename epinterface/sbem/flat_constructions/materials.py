"""Shared opaque materials used by semi-flat construction builders."""

from epinterface.sbem.components.materials import ConstructionMaterialComponent


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

CONCRETE_MC_LIGHT = _material(
    name="ConcreteMC_Light",
    conductivity=1.65,
    density=2100,
    specific_heat=1040,
    mat_type="Concrete",
)

CONCRETE_RC_DENSE = _material(
    name="ConcreteRC_Dense",
    conductivity=1.75,
    density=2400,
    specific_heat=840,
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
    conductivity=0.13,
    density=496,
    specific_heat=1630,
    mat_type="Timber",
)

CLAY_BRICK = _material(
    name="ClayBrick",
    conductivity=0.41,
    density=1000,
    specific_heat=920,
    mat_type="Masonry",
)

CONCRETE_BLOCK_H = _material(
    name="ConcreteBlockH",
    conductivity=1.25,
    density=880,
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
    conductivity=0.8,
    density=1900,
    specific_heat=840,
    mat_type="Other",
)

CERAMIC_TILE = _material(
    name="CeramicTile",
    conductivity=0.8,
    density=2243,
    specific_heat=840,
    mat_type="Finishes",
)

URETHANE_CARPET = _material(
    name="UrethaneCarpet",
    conductivity=0.045,
    density=110,
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
    conductivity=1.30,
    density=2000,
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
    conductivity=0.30,
    density=1300,
    specific_heat=840,
    mat_type="Siding",
)
