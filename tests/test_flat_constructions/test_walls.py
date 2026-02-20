"""Tests for semi-flat wall construction translation."""

import pytest

from epinterface.sbem.flat_constructions.layers import (
    ALL_CAVITY_INSULATION_MATERIALS,
    ALL_CONTINUOUS_INSULATION_MATERIALS,
    ALL_EXTERIOR_CAVITY_TYPES,
)
from epinterface.sbem.flat_constructions.materials import (
    CEMENT_MORTAR,
    CONCRETE_BLOCK_H,
    CONCRETE_RC_DENSE,
    GYPSUM_BOARD,
    SOFTWOOD_GENERAL,
    MaterialName,
)
from epinterface.sbem.flat_constructions.walls import (
    ALL_WALL_EXTERIOR_FINISHES,
    ALL_WALL_INTERIOR_FINISHES,
    ALL_WALL_STRUCTURAL_SYSTEMS,
    STRUCTURAL_TEMPLATES,
    SemiFlatWallConstruction,
    WallExteriorFinish,
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


def test_woodframe_uses_consolidated_cavity_layer() -> None:
    """Woodframe cavities should be modeled as parallel-path consolidated layers."""
    wall = SemiFlatWallConstruction(
        structural_system="woodframe",
        nominal_cavity_insulation_r=2.0,
        nominal_exterior_insulation_r=0.0,
        nominal_interior_insulation_r=0.0,
        interior_finish="none",
        exterior_finish="none",
    )
    assembly = build_facade_assembly(wall)
    woodframe_template = STRUCTURAL_TEMPLATES["woodframe"]
    cavity_layer = assembly.sorted_layers[0]

    assert cavity_layer.ConstructionMaterial.Name.startswith(
        "ConsolidatedCavity_woodframe"
    )
    assert woodframe_template.cavity_depth_m is not None
    assert woodframe_template.framing_fraction is not None

    framing_r = woodframe_template.cavity_depth_m / SOFTWOOD_GENERAL.Conductivity
    r_eq_expected = 1 / (
        woodframe_template.framing_fraction / framing_r
        + (1 - woodframe_template.framing_fraction) / 2.0
    )
    assert assembly.r_value == pytest.approx(r_eq_expected, rel=1e-6)


def test_light_gauge_steel_uses_effective_framing_path() -> None:
    """Steel framing should use an effective framing-path R, not solid steel conduction."""
    wall = SemiFlatWallConstruction(
        structural_system="light_gauge_steel",
        nominal_cavity_insulation_r=2.0,
        nominal_exterior_insulation_r=0.0,
        nominal_interior_insulation_r=0.0,
        interior_finish="none",
        exterior_finish="none",
    )
    assembly = build_facade_assembly(wall)
    steel_template = STRUCTURAL_TEMPLATES["light_gauge_steel"]
    cavity_layer = assembly.sorted_layers[0]

    assert cavity_layer.ConstructionMaterial.Name.startswith(
        "ConsolidatedCavity_light_gauge_steel"
    )
    assert steel_template.framing_fraction is not None
    assert steel_template.framing_path_r_value is not None

    r_eq_expected = 1 / (
        steel_template.framing_fraction / steel_template.framing_path_r_value
        + (1 - steel_template.framing_fraction) / 2.0
    )
    assert assembly.r_value == pytest.approx(r_eq_expected, rel=1e-6)


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
        + len(ALL_CONTINUOUS_INSULATION_MATERIALS) * 2
        + len(ALL_CAVITY_INSULATION_MATERIALS)
        + len(ALL_EXTERIOR_CAVITY_TYPES)
    )
    assert len(features) == expected_length
    assert features["FacadeStructuralSystem__deep_woodframe_24oc"] == 1.0
    assert features["FacadeInteriorFinish__plaster"] == 1.0
    assert features["FacadeExteriorFinish__fiber_cement"] == 1.0


def test_vinyl_siding_exterior_finish_round_trip() -> None:
    """Vinyl siding finish should produce a valid assembly with the correct outer layer."""
    wall = SemiFlatWallConstruction(
        structural_system="woodframe",
        nominal_cavity_insulation_r=2.0,
        nominal_exterior_insulation_r=0.5,
        nominal_interior_insulation_r=0.0,
        interior_finish="drywall",
        exterior_finish="vinyl_siding",
    )
    assembly = build_facade_assembly(wall)
    outer_layer = assembly.sorted_layers[0]
    assert outer_layer.ConstructionMaterial.Name == "VinylSiding"
    assert outer_layer.Thickness == pytest.approx(0.0015)
    assert assembly.r_value > 0


def test_icf_structural_system_round_trip() -> None:
    """ICF wall should produce a concrete-core assembly with continuous insulation layers."""
    wall = SemiFlatWallConstruction(
        structural_system="icf",
        nominal_cavity_insulation_r=0.0,
        nominal_exterior_insulation_r=2.0,
        nominal_interior_insulation_r=1.5,
        interior_finish="drywall",
        exterior_finish="none",
    )
    assembly = build_facade_assembly(wall)
    icf_template = STRUCTURAL_TEMPLATES["icf"]

    expected_r = (
        2.0
        + (icf_template.thickness_m / CONCRETE_RC_DENSE.Conductivity)
        + 1.5
        + (0.0127 / GYPSUM_BOARD.Conductivity)
    )
    assert assembly.Type == "Facade"
    assert assembly.r_value == pytest.approx(expected_r, rel=1e-6)


def test_wood_siding_and_stone_veneer_produce_valid_assemblies() -> None:
    """New exterior finishes should each produce valid assemblies."""
    finishes: list[tuple[WallExteriorFinish, MaterialName]] = [
        ("wood_siding", "SoftwoodGeneral"),
        ("stone_veneer", "NaturalStone"),
    ]
    for finish, mat_name in finishes:
        wall = SemiFlatWallConstruction(
            structural_system="woodframe",
            nominal_cavity_insulation_r=2.0,
            exterior_finish=finish,
        )
        assembly = build_facade_assembly(wall)
        outer_layer = assembly.sorted_layers[0]
        assert outer_layer.ConstructionMaterial.Name == mat_name
        assert assembly.r_value > 0


# --- Phase 3: new structural systems ---


@pytest.mark.parametrize(
    "system,expected_material,expected_thickness",
    [
        ("aac", "AACBlock", 0.200),
        ("thick_aac", "AACBlock", 0.300),
        ("hollow_clay_block", "HollowClayBlock", 0.250),
        ("thick_hollow_clay_block", "HollowClayBlock", 0.365),
        ("sandcrete_block", "SandcreteBlock", 0.150),
        ("thick_sandcrete_block", "SandcreteBlock", 0.225),
        ("stabilized_soil_block", "StabilizedSoilBlock", 0.150),
        ("wattle_and_daub", "WattleDaub", 0.150),
        ("timber_panel", "SoftwoodGeneral", 0.018),
        ("thick_rammed_earth", "RammedEarth", 0.500),
    ],
)
def test_new_structural_systems_produce_valid_assemblies(
    system: str, expected_material: str, expected_thickness: float
) -> None:
    """Each new structural system should produce a valid assembly with the correct core."""
    wall = SemiFlatWallConstruction(
        structural_system=system,  # pyright: ignore[reportArgumentType]
        interior_finish="none",
        exterior_finish="none",
    )
    assembly = build_facade_assembly(wall)
    assert assembly.r_value > 0
    struct_layer = assembly.sorted_layers[0]
    assert struct_layer.ConstructionMaterial.Name == expected_material
    assert struct_layer.Thickness == pytest.approx(expected_thickness)


def test_thick_variants_have_higher_r_than_thin() -> None:
    """Thicker variants of the same material should have higher structural R."""
    pairs = [
        ("aac", "thick_aac"),
        ("hollow_clay_block", "thick_hollow_clay_block"),
        ("sandcrete_block", "thick_sandcrete_block"),
        ("rammed_earth", "thick_rammed_earth"),
    ]
    for thin, thick in pairs:
        thin_wall = SemiFlatWallConstruction(
            structural_system=thin,  # pyright: ignore[reportArgumentType]
            interior_finish="none",
            exterior_finish="none",
        )
        thick_wall = SemiFlatWallConstruction(
            structural_system=thick,  # pyright: ignore[reportArgumentType]
            interior_finish="none",
            exterior_finish="none",
        )
        thin_r = build_facade_assembly(thin_wall).r_value
        thick_r = build_facade_assembly(thick_wall).r_value
        assert thick_r > thin_r, (
            f"{thick} R ({thick_r:.3f}) should exceed {thin} R ({thin_r:.3f})"
        )


def test_cavity_masonry_supports_cavity_insulation() -> None:
    """Cavity masonry should accept cavity insulation like CMU does."""
    wall = SemiFlatWallConstruction(
        structural_system="cavity_masonry",
        nominal_cavity_insulation_r=1.0,
        exterior_finish="brick_veneer",
        interior_finish="cement_plaster",
    )
    assembly = build_facade_assembly(wall)
    layer_names = [layer.ConstructionMaterial.Name for layer in assembly.sorted_layers]
    assert "CementMortar" in layer_names
    assert assembly.r_value > 1.0


def test_cement_plaster_interior_finish() -> None:
    """Cement plaster interior finish should map to CementMortar."""
    wall = SemiFlatWallConstruction(
        structural_system="masonry",
        interior_finish="cement_plaster",
    )
    assembly = build_facade_assembly(wall)
    inner_layer = assembly.sorted_layers[-1]
    assert inner_layer.ConstructionMaterial.Name == "CementMortar"
    assert inner_layer.Thickness == pytest.approx(0.015)


# --- Phase 2: insulation material selection ---


def test_exterior_insulation_material_affects_assembly() -> None:
    """Switching exterior insulation material should change the layer material."""
    for mat_key, expected_name in [
        ("xps", "XPSBoard"),
        ("eps", "EPSBoard"),
        ("mineral_wool", "MineralWoolBoard"),
        ("polyiso", "PolyisoBoard"),
    ]:
        wall = SemiFlatWallConstruction(
            structural_system="masonry",
            nominal_exterior_insulation_r=2.0,
            exterior_insulation_material=mat_key,  # pyright: ignore[reportArgumentType]
            exterior_finish="stucco",
        )
        assembly = build_facade_assembly(wall)
        ins_layer = assembly.sorted_layers[1]
        assert ins_layer.ConstructionMaterial.Name == expected_name


# --- Phase 6: ventilated cavity ---


def test_well_ventilated_cavity_omits_exterior_finish() -> None:
    """Well-ventilated cavity should omit the exterior finish layer per ISO 6946."""
    wall_none = SemiFlatWallConstruction(
        structural_system="poured_concrete",
        exterior_finish="stucco",
        exterior_cavity_type="none",
    )
    wall_vent = SemiFlatWallConstruction(
        structural_system="poured_concrete",
        exterior_finish="stucco",
        exterior_cavity_type="well_ventilated",
    )
    a_none = build_facade_assembly(wall_none)
    a_vent = build_facade_assembly(wall_vent)
    names_none = [layer.ConstructionMaterial.Name for layer in a_none.sorted_layers]
    names_vent = [layer.ConstructionMaterial.Name for layer in a_vent.sorted_layers]
    assert names_none[0] == "CementMortar"
    assert names_vent[0] != "CementMortar"
    assert a_vent.r_value < a_none.r_value


def test_unventilated_cavity_adds_air_gap() -> None:
    """Unventilated cavity should add an air gap layer between finish and insulation."""
    wall = SemiFlatWallConstruction(
        structural_system="masonry",
        exterior_finish="brick_veneer",
        nominal_exterior_insulation_r=1.0,
        exterior_cavity_type="unventilated",
    )
    assembly = build_facade_assembly(wall)
    layer_names = [layer.ConstructionMaterial.Name for layer in assembly.sorted_layers]
    assert any("AirGap" in n for n in layer_names)
    wall_no_cavity = SemiFlatWallConstruction(
        structural_system="masonry",
        exterior_finish="brick_veneer",
        nominal_exterior_insulation_r=1.0,
        exterior_cavity_type="none",
    )
    r_no_cavity = build_facade_assembly(wall_no_cavity).r_value
    assert assembly.r_value > r_no_cavity
