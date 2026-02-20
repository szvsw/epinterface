"""Tests for shared flat-construction layer helpers."""

import pytest

from epinterface.sbem.flat_constructions.layers import (
    layer_from_nominal_r,
    resolve_material,
)
from epinterface.sbem.flat_constructions.materials import (
    ASPHALT_SHINGLE,
    CONCRETE_BLOCK_H,
    COOL_ROOF_MEMBRANE,
    NATURAL_STONE,
    RAMMED_EARTH,
    ROOF_MEMBRANE,
    STEEL_PANEL,
    VINYL_SIDING,
    XPS_BOARD,
)


def test_layer_from_nominal_r_accepts_material_name_literal() -> None:
    """Nominal-R helper should resolve named materials safely."""
    layer = layer_from_nominal_r(
        material="XPSBoard",
        nominal_r_value=2.0,
        layer_order=1,
    )
    assert layer.ConstructionMaterial.Name == "XPSBoard"
    assert layer.Thickness == pytest.approx(2.0 * XPS_BOARD.Conductivity)


def test_layer_from_nominal_r_accepts_material_component() -> None:
    """Nominal-R helper should also accept material components directly."""
    layer = layer_from_nominal_r(
        material=XPS_BOARD,
        nominal_r_value=1.5,
        layer_order=2,
    )
    assert layer.ConstructionMaterial is XPS_BOARD
    assert layer.Thickness == pytest.approx(1.5 * XPS_BOARD.Conductivity)


def test_resolve_material_returns_same_component_for_objects() -> None:
    """Material resolver should pass through component inputs unchanged."""
    assert resolve_material(XPS_BOARD) is XPS_BOARD


def test_cool_roof_membrane_uses_lower_absorptance_than_dark_membrane() -> None:
    """Cool roof optical properties should differ from generic dark membrane."""
    assert ROOF_MEMBRANE.SolarAbsorptance == pytest.approx(0.88)
    assert ROOF_MEMBRANE.VisibleAbsorptance == pytest.approx(0.88)
    assert COOL_ROOF_MEMBRANE.SolarAbsorptance == pytest.approx(0.30)
    assert COOL_ROOF_MEMBRANE.VisibleAbsorptance == pytest.approx(0.30)
    assert COOL_ROOF_MEMBRANE.SolarAbsorptance < ROOF_MEMBRANE.SolarAbsorptance


def test_xps_board_retains_default_optical_properties() -> None:
    """Materials without overrides should continue using helper defaults."""
    assert XPS_BOARD.ThermalAbsorptance == pytest.approx(0.9)
    assert XPS_BOARD.SolarAbsorptance == pytest.approx(0.6)
    assert XPS_BOARD.VisibleAbsorptance == pytest.approx(0.6)


def test_rammed_earth_has_explicit_absorptances() -> None:
    """Rammed earth should have explicit solar/visible absorptance for exterior exposure."""
    assert RAMMED_EARTH.SolarAbsorptance == pytest.approx(0.70)
    assert RAMMED_EARTH.VisibleAbsorptance == pytest.approx(0.70)


def test_concrete_block_has_explicit_absorptances() -> None:
    """Concrete block should have explicit solar/visible absorptance for exterior exposure."""
    assert CONCRETE_BLOCK_H.SolarAbsorptance == pytest.approx(0.65)
    assert CONCRETE_BLOCK_H.VisibleAbsorptance == pytest.approx(0.65)


def test_roughness_overrides_applied_correctly() -> None:
    """Materials with non-default roughness should have the correct value."""
    assert STEEL_PANEL.Roughness == "Smooth"
    assert ROOF_MEMBRANE.Roughness == "Smooth"
    assert COOL_ROOF_MEMBRANE.Roughness == "Smooth"
    assert XPS_BOARD.Roughness == "MediumRough"


def test_new_materials_have_expected_properties() -> None:
    """Newly added materials should have correct key properties."""
    assert VINYL_SIDING.Conductivity == pytest.approx(0.17)
    assert VINYL_SIDING.SolarAbsorptance == pytest.approx(0.55)
    assert VINYL_SIDING.Roughness == "Smooth"

    assert ASPHALT_SHINGLE.Conductivity == pytest.approx(0.06)
    assert ASPHALT_SHINGLE.SolarAbsorptance == pytest.approx(0.85)
    assert ASPHALT_SHINGLE.Roughness == "Rough"

    assert NATURAL_STONE.Conductivity == pytest.approx(2.90)
    assert NATURAL_STONE.SolarAbsorptance == pytest.approx(0.55)
    assert NATURAL_STONE.Density == pytest.approx(2500)
