"""Tests for shared flat-construction layer helpers."""

import pytest

from epinterface.sbem.flat_constructions.layers import (
    layer_from_nominal_r,
    resolve_material,
)
from epinterface.sbem.flat_constructions.materials import (
    COOL_ROOF_MEMBRANE,
    ROOF_MEMBRANE,
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
