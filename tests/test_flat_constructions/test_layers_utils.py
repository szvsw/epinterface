"""Tests for shared flat-construction layer helpers."""

import pytest

from epinterface.sbem.flat_constructions.layers import (
    _MIN_RESIDUAL_GAP_M,
    equivalent_framed_cavity_material,
    layer_from_nominal_r,
    resolve_material,
)
from epinterface.sbem.flat_constructions.materials import (
    ASPHALT_SHINGLE,
    CONCRETE_BLOCK_H,
    COOL_ROOF_MEMBRANE,
    FIBERGLASS_BATTS,
    NATURAL_STONE,
    RAMMED_EARTH,
    ROOF_MEMBRANE,
    SOFTWOOD_GENERAL,
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


# ---------------------------------------------------------------------------
# equivalent_framed_cavity_material -- residual air-gap correction
# ---------------------------------------------------------------------------

_CAVITY_DEPTH = 0.090  # 90mm (typical 2x4 stud bay)
_FRAMING_FRACTION = 0.23
_UNINSULATED_R = 0.17
_K_FIBERGLASS = FIBERGLASS_BATTS.Conductivity  # 0.043
_K_SOFTWOOD = SOFTWOOD_GENERAL.Conductivity  # 0.12
_FRAMING_R = _CAVITY_DEPTH / _K_SOFTWOOD


def _expected_r_eq(fill_r: float) -> float:
    """Parallel-path R_eq for the standard test fixture."""
    u = _FRAMING_FRACTION / _FRAMING_R + (1 - _FRAMING_FRACTION) / fill_r
    return 1.0 / u


def test_full_fill_cavity_has_no_air_gap_correction() -> None:
    """When insulation fills the cavity, fill_r equals the nominal R."""
    nominal_r = _CAVITY_DEPTH / _K_FIBERGLASS  # exactly fills cavity
    mat = equivalent_framed_cavity_material(
        structural_system="woodframe",
        cavity_depth_m=_CAVITY_DEPTH,
        framing_material=SOFTWOOD_GENERAL,
        framing_fraction=_FRAMING_FRACTION,
        nominal_cavity_insulation_r=nominal_r,
        uninsulated_cavity_r_value=_UNINSULATED_R,
    )
    r_eq = _CAVITY_DEPTH / mat.Conductivity
    assert r_eq == pytest.approx(_expected_r_eq(nominal_r), rel=1e-6)


def test_partial_fill_cavity_adds_air_gap_r() -> None:
    """When a significant residual gap exists, the air-layer R is added."""
    nominal_r = 1.0  # implied thickness ~43mm in 90mm cavity → ~47mm gap
    mat = equivalent_framed_cavity_material(
        structural_system="woodframe",
        cavity_depth_m=_CAVITY_DEPTH,
        framing_material=SOFTWOOD_GENERAL,
        framing_fraction=_FRAMING_FRACTION,
        nominal_cavity_insulation_r=nominal_r,
        uninsulated_cavity_r_value=_UNINSULATED_R,
    )
    corrected_fill_r = nominal_r + _UNINSULATED_R
    r_eq = _CAVITY_DEPTH / mat.Conductivity
    assert r_eq == pytest.approx(_expected_r_eq(corrected_fill_r), rel=1e-6)


def test_gap_below_threshold_gets_no_correction() -> None:
    """A residual gap smaller than the threshold is ignored."""
    gap_just_below = _MIN_RESIDUAL_GAP_M - 0.001
    insulation_thickness = _CAVITY_DEPTH - gap_just_below
    nominal_r = insulation_thickness / _K_FIBERGLASS
    mat = equivalent_framed_cavity_material(
        structural_system="woodframe",
        cavity_depth_m=_CAVITY_DEPTH,
        framing_material=SOFTWOOD_GENERAL,
        framing_fraction=_FRAMING_FRACTION,
        nominal_cavity_insulation_r=nominal_r,
        uninsulated_cavity_r_value=_UNINSULATED_R,
    )
    r_eq = _CAVITY_DEPTH / mat.Conductivity
    assert r_eq == pytest.approx(_expected_r_eq(nominal_r), rel=1e-6)


def test_uninsulated_cavity_uses_fallback_r() -> None:
    """With zero cavity insulation, fill_r falls back to the air-cavity R."""
    mat = equivalent_framed_cavity_material(
        structural_system="woodframe",
        cavity_depth_m=_CAVITY_DEPTH,
        framing_material=SOFTWOOD_GENERAL,
        framing_fraction=_FRAMING_FRACTION,
        nominal_cavity_insulation_r=0.0,
        uninsulated_cavity_r_value=_UNINSULATED_R,
    )
    r_eq = _CAVITY_DEPTH / mat.Conductivity
    assert r_eq == pytest.approx(_expected_r_eq(_UNINSULATED_R), rel=1e-6)
