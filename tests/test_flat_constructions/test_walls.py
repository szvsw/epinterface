"""Tests for semi-flat wall construction translation."""

import pytest

from epinterface.sbem.flat_constructions.materials import (
    CEMENT_MORTAR,
    CONCRETE_BLOCK_H,
    GYPSUM_BOARD,
)
from epinterface.sbem.flat_constructions.walls import (
    ALL_WALL_EXTERIOR_FINISHES,
    ALL_WALL_INTERIOR_FINISHES,
    ALL_WALL_STRUCTURAL_SYSTEMS,
    STRUCTURAL_TEMPLATES,
    SemiFlatWallConstruction,
    build_facade_assembly,
)


def test_build_facade_assembly_from_nominal_r_values() -> None:
    """Facade assembly should reflect nominal wall insulation inputs."""
    wall = SemiFlatWallConstruction(
        structural_system="cmu",
        nominal_cavity_insulation_r=1.0,
        nominal_exterior_insulation_r=2.0,
        nominal_interior_insulation_r=0.5,
        interior_finish="drywall",
        exterior_finish="stucco",
    )

    assembly = build_facade_assembly(wall)

    # R_total = stucco + ext_ins + cmu + cavity + int_ins + drywall
    cmu_template = STRUCTURAL_TEMPLATES["cmu"]
    expected_r = (
        0.020 / CEMENT_MORTAR.Conductivity
        + 2.0
        + (cmu_template.thickness_m / CONCRETE_BLOCK_H.Conductivity)
        + (1.0 * cmu_template.cavity_r_correction_factor)
        + 0.5
        + (0.0127 / GYPSUM_BOARD.Conductivity)
    )
    assert assembly.Type == "Facade"
    assert assembly.r_value == pytest.approx(expected_r, rel=1e-6)


def test_validator_rejects_unrealistic_cavity_r_for_depth() -> None:
    """Cavity insulation R should be limited by assumed cavity depth."""
    with pytest.raises(
        ValueError,
        match="cavity-depth-compatible limit",
    ):
        SemiFlatWallConstruction(
            structural_system="woodframe",
            nominal_cavity_insulation_r=3.0,
        )


def test_non_cavity_structural_system_treats_cavity_r_as_dead_feature() -> None:
    """Cavity R should become a no-op when structural system has no cavity."""
    wall = SemiFlatWallConstruction(
        structural_system="poured_concrete",
        nominal_cavity_insulation_r=2.0,
    )
    assembly = build_facade_assembly(wall)
    layer_material_names = [
        layer.ConstructionMaterial.Name for layer in assembly.sorted_layers
    ]

    assert wall.effective_nominal_cavity_insulation_r == 0.0
    assert "nominal_cavity_insulation_r" in wall.ignored_feature_names
    assert "FiberglassBatt" not in layer_material_names


def test_wall_feature_dict_has_fixed_length() -> None:
    """Feature dictionary should remain fixed-length across wall variants."""
    wall = SemiFlatWallConstruction(
        structural_system="deep_woodframe_24oc",
        nominal_cavity_insulation_r=2.8,
        nominal_exterior_insulation_r=0.5,
        nominal_interior_insulation_r=0.0,
        interior_finish="plaster",
        exterior_finish="fiber_cement",
    )
    features = wall.to_feature_dict(prefix="Facade")

    expected_length = (
        4
        + len(ALL_WALL_STRUCTURAL_SYSTEMS)
        + len(ALL_WALL_INTERIOR_FINISHES)
        + len(ALL_WALL_EXTERIOR_FINISHES)
    )
    assert len(features) == expected_length
    assert features["FacadeStructuralSystem__deep_woodframe_24oc"] == 1.0
    assert features["FacadeInteriorFinish__plaster"] == 1.0
    assert features["FacadeExteriorFinish__fiber_cement"] == 1.0
