"""Tests for semi-flat roof and slab construction translation."""

import pytest

from epinterface.sbem.flat_constructions import build_envelope_assemblies
from epinterface.sbem.flat_constructions.roofs import (
    ALL_ROOF_EXTERIOR_FINISHES,
    ALL_ROOF_INTERIOR_FINISHES,
    ALL_ROOF_STRUCTURAL_SYSTEMS,
    SemiFlatRoofConstruction,
    build_roof_assembly,
)
from epinterface.sbem.flat_constructions.slabs import (
    ALL_SLAB_EXTERIOR_FINISHES,
    ALL_SLAB_INTERIOR_FINISHES,
    ALL_SLAB_STRUCTURAL_SYSTEMS,
    SemiFlatSlabConstruction,
    build_slab_assembly,
)
from epinterface.sbem.flat_constructions.walls import SemiFlatWallConstruction


def test_build_roof_assembly_from_nominal_r_values() -> None:
    """Roof assembly should reflect nominal roof insulation inputs."""
    roof = SemiFlatRoofConstruction(
        structural_system="poured_concrete",
        nominal_cavity_insulation_r=0.0,
        nominal_exterior_insulation_r=2.0,
        nominal_interior_insulation_r=0.3,
        interior_finish="gypsum_board",
        exterior_finish="epdm_membrane",
    )
    assembly = build_roof_assembly(roof)

    # R_total = membrane + ext_ins + concrete + int_ins + gypsum
    expected_r = (0.005 / 0.16) + 2.0 + (0.18 / 1.75) + 0.3 + (0.0127 / 0.16)
    assert assembly.Type == "FlatRoof"
    assert assembly.r_value == pytest.approx(expected_r, rel=1e-6)


def test_roof_validator_rejects_unrealistic_cavity_r_for_depth() -> None:
    """Roof cavity insulation R should be limited by assumed cavity depth."""
    with pytest.raises(
        ValueError,
        match="cavity-depth-compatible limit",
    ):
        SemiFlatRoofConstruction(
            structural_system="deep_wood_truss",
            nominal_cavity_insulation_r=6.0,
        )


def test_non_cavity_roof_treats_cavity_r_as_dead_feature() -> None:
    """Roof cavity R should become a no-op for non-cavity systems."""
    roof = SemiFlatRoofConstruction(
        structural_system="reinforced_concrete",
        nominal_cavity_insulation_r=2.0,
        nominal_exterior_insulation_r=0.0,
        nominal_interior_insulation_r=0.0,
        interior_finish="none",
        exterior_finish="none",
    )
    assembly = build_roof_assembly(roof)
    layer_material_names = [
        layer.ConstructionMaterial.Name for layer in assembly.sorted_layers
    ]

    assert roof.effective_nominal_cavity_insulation_r == 0.0
    assert "nominal_cavity_insulation_r" in roof.ignored_feature_names
    assert "FiberglassBatt" not in layer_material_names


def test_roof_feature_dict_has_fixed_length() -> None:
    """Roof feature dictionary should remain fixed-length across variants."""
    roof = SemiFlatRoofConstruction(
        structural_system="steel_joist",
        nominal_cavity_insulation_r=1.5,
        nominal_exterior_insulation_r=0.5,
        nominal_interior_insulation_r=0.2,
        interior_finish="acoustic_tile",
        exterior_finish="cool_membrane",
    )
    features = roof.to_feature_dict(prefix="Roof")

    expected_length = (
        4
        + len(ALL_ROOF_STRUCTURAL_SYSTEMS)
        + len(ALL_ROOF_INTERIOR_FINISHES)
        + len(ALL_ROOF_EXTERIOR_FINISHES)
    )
    assert len(features) == expected_length
    assert features["RoofStructuralSystem__steel_joist"] == 1.0
    assert features["RoofInteriorFinish__acoustic_tile"] == 1.0
    assert features["RoofExteriorFinish__cool_membrane"] == 1.0


def test_build_slab_assembly_from_nominal_r_values() -> None:
    """Slab assembly should reflect nominal slab insulation inputs."""
    slab = SemiFlatSlabConstruction(
        structural_system="slab_on_grade",
        nominal_under_slab_insulation_r=1.5,
        nominal_above_slab_insulation_r=0.5,
        nominal_cavity_insulation_r=0.0,
        interior_finish="tile",
        exterior_finish="none",
    )
    assembly = build_slab_assembly(slab)

    # R_total = interior tile + above insulation + concrete slab + under insulation
    expected_r = (0.015 / 0.8) + 0.5 + (0.15 / 1.75) + 1.5
    assert assembly.Type == "GroundSlab"
    assert assembly.r_value == pytest.approx(expected_r, rel=1e-6)


def test_non_ground_slab_treats_under_slab_r_as_dead_feature() -> None:
    """Under-slab insulation should become a no-op for suspended slabs."""
    slab = SemiFlatSlabConstruction(
        structural_system="reinforced_concrete_suspended",
        nominal_under_slab_insulation_r=2.0,
        nominal_above_slab_insulation_r=0.0,
        nominal_cavity_insulation_r=0.0,
        interior_finish="none",
        exterior_finish="none",
    )
    assembly = build_slab_assembly(slab)
    layer_material_names = [
        layer.ConstructionMaterial.Name for layer in assembly.sorted_layers
    ]

    assert slab.effective_nominal_under_slab_insulation_r == 0.0
    assert "nominal_under_slab_insulation_r" in slab.ignored_feature_names
    assert "XPSBoard" not in layer_material_names


def test_slab_validator_rejects_unrealistic_cavity_r_for_depth() -> None:
    """Slab cavity insulation R should be limited by assumed cavity depth."""
    with pytest.raises(
        ValueError,
        match="cavity-depth-compatible limit",
    ):
        SemiFlatSlabConstruction(
            structural_system="mass_timber_deck",
            nominal_cavity_insulation_r=3.3,
        )


def test_slab_feature_dict_has_fixed_length() -> None:
    """Slab feature dictionary should remain fixed-length across variants."""
    slab = SemiFlatSlabConstruction(
        structural_system="precast_hollow_core",
        nominal_under_slab_insulation_r=0.0,
        nominal_above_slab_insulation_r=0.8,
        nominal_cavity_insulation_r=1.6,
        interior_finish="carpet",
        exterior_finish="gypsum_board",
    )
    features = slab.to_feature_dict(prefix="Slab")

    expected_length = (
        5
        + len(ALL_SLAB_STRUCTURAL_SYSTEMS)
        + len(ALL_SLAB_INTERIOR_FINISHES)
        + len(ALL_SLAB_EXTERIOR_FINISHES)
    )
    assert len(features) == expected_length
    assert features["SlabStructuralSystem__precast_hollow_core"] == 1.0
    assert features["SlabInteriorFinish__carpet"] == 1.0
    assert features["SlabExteriorFinish__gypsum_board"] == 1.0


def test_build_envelope_assemblies_with_surface_specific_specs() -> None:
    """Envelope assemblies should use dedicated wall/roof/slab constructors."""
    envelope_assemblies = build_envelope_assemblies(
        facade_wall=SemiFlatWallConstruction(
            structural_system="woodframe",
            nominal_cavity_insulation_r=2.0,
            nominal_exterior_insulation_r=0.5,
            nominal_interior_insulation_r=0.0,
            interior_finish="drywall",
            exterior_finish="fiber_cement",
        ),
        roof=SemiFlatRoofConstruction(
            structural_system="steel_joist",
            nominal_cavity_insulation_r=1.5,
            nominal_exterior_insulation_r=1.2,
            nominal_interior_insulation_r=0.0,
            interior_finish="acoustic_tile",
            exterior_finish="cool_membrane",
        ),
        slab=SemiFlatSlabConstruction(
            structural_system="slab_on_grade",
            nominal_under_slab_insulation_r=1.4,
            nominal_above_slab_insulation_r=0.2,
            nominal_cavity_insulation_r=0.0,
            interior_finish="tile",
            exterior_finish="none",
        ),
    )

    assert envelope_assemblies.FacadeAssembly.Type == "Facade"
    assert envelope_assemblies.FlatRoofAssembly.Type == "FlatRoof"
    assert envelope_assemblies.GroundSlabAssembly.Type == "GroundSlab"
