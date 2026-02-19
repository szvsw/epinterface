"""Tests for semi-flat roof and slab construction translation."""

import pytest

from epinterface.sbem.flat_constructions import build_envelope_assemblies
from epinterface.sbem.flat_constructions.layers import (
    ALL_CONTINUOUS_INSULATION_MATERIALS,
    ALL_EXTERIOR_CAVITY_TYPES,
)
from epinterface.sbem.flat_constructions.materials import (
    CERAMIC_TILE,
    CONCRETE_RC_DENSE,
    GYPSUM_BOARD,
    ROOF_MEMBRANE,
    SOFTWOOD_GENERAL,
)
from epinterface.sbem.flat_constructions.roofs import (
    ALL_ROOF_EXTERIOR_FINISHES,
    ALL_ROOF_INTERIOR_FINISHES,
    ALL_ROOF_STRUCTURAL_SYSTEMS,
    SemiFlatRoofConstruction,
    build_roof_assembly,
)
from epinterface.sbem.flat_constructions.roofs import (
    STRUCTURAL_TEMPLATES as ROOF_STRUCTURAL_TEMPLATES,
)
from epinterface.sbem.flat_constructions.slabs import (
    ALL_SLAB_EXTERIOR_FINISHES,
    ALL_SLAB_INSULATION_PLACEMENTS,
    ALL_SLAB_INTERIOR_FINISHES,
    ALL_SLAB_STRUCTURAL_SYSTEMS,
    SemiFlatSlabConstruction,
    build_slab_assembly,
)
from epinterface.sbem.flat_constructions.slabs import (
    STRUCTURAL_TEMPLATES as SLAB_STRUCTURAL_TEMPLATES,
)
from epinterface.sbem.flat_constructions.walls import (
    SemiFlatWallConstruction,
    build_facade_assembly,
)


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
    poured_template = ROOF_STRUCTURAL_TEMPLATES["poured_concrete"]
    expected_r = (
        (0.005 / ROOF_MEMBRANE.Conductivity)
        + 2.0
        + (poured_template.thickness_m / CONCRETE_RC_DENSE.Conductivity)
        + 0.3
        + (0.0127 / GYPSUM_BOARD.Conductivity)
    )
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
        + len(ALL_CONTINUOUS_INSULATION_MATERIALS) * 2
        + len(ALL_EXTERIOR_CAVITY_TYPES)
    )
    assert len(features) == expected_length
    assert features["RoofStructuralSystem__steel_joist"] == 1.0
    assert features["RoofInteriorFinish__acoustic_tile"] == 1.0
    assert features["RoofExteriorFinish__cool_membrane"] == 1.0


def test_light_wood_truss_uses_consolidated_cavity_layer() -> None:
    """Wood truss roofs should use a consolidated parallel-path cavity layer."""
    roof = SemiFlatRoofConstruction(
        structural_system="light_wood_truss",
        nominal_cavity_insulation_r=3.0,
        nominal_exterior_insulation_r=0.0,
        nominal_interior_insulation_r=0.0,
        interior_finish="none",
        exterior_finish="none",
    )
    assembly = build_roof_assembly(roof)
    truss_template = ROOF_STRUCTURAL_TEMPLATES["light_wood_truss"]
    cavity_layer = assembly.sorted_layers[0]

    assert cavity_layer.ConstructionMaterial.Name.startswith(
        "ConsolidatedCavity_light_wood_truss"
    )
    assert truss_template.cavity_depth_m is not None
    assert truss_template.framing_fraction is not None

    framing_r = truss_template.cavity_depth_m / SOFTWOOD_GENERAL.Conductivity
    r_eq_expected = 1 / (
        truss_template.framing_fraction / framing_r
        + (1 - truss_template.framing_fraction) / 3.0
    )
    assert assembly.r_value == pytest.approx(r_eq_expected, rel=1e-6)


def test_steel_joist_uses_effective_framing_path() -> None:
    """Steel joists should use an effective framing-path R-value model."""
    roof = SemiFlatRoofConstruction(
        structural_system="steel_joist",
        nominal_cavity_insulation_r=3.0,
        nominal_exterior_insulation_r=0.0,
        nominal_interior_insulation_r=0.0,
        interior_finish="none",
        exterior_finish="none",
    )
    assembly = build_roof_assembly(roof)
    joist_template = ROOF_STRUCTURAL_TEMPLATES["steel_joist"]
    cavity_layer = assembly.sorted_layers[0]

    assert cavity_layer.ConstructionMaterial.Name.startswith(
        "ConsolidatedCavity_steel_joist"
    )
    assert joist_template.framing_fraction is not None
    assert joist_template.framing_path_r_value is not None

    r_eq_expected = 1 / (
        joist_template.framing_fraction / joist_template.framing_path_r_value
        + (1 - joist_template.framing_fraction) / 3.0
    )
    assert assembly.r_value == pytest.approx(r_eq_expected, rel=1e-6)


def test_build_slab_assembly_from_nominal_r_values() -> None:
    """Slab assembly should reflect nominal slab insulation inputs."""
    slab = SemiFlatSlabConstruction(
        structural_system="slab_on_grade",
        nominal_insulation_r=1.5,
        insulation_placement="auto",
        interior_finish="tile",
        exterior_finish="none",
    )
    assembly = build_slab_assembly(slab)

    slab_template = SLAB_STRUCTURAL_TEMPLATES["slab_on_grade"]
    # R_total = interior tile + concrete slab + under-slab insulation
    expected_r = (
        (0.015 / CERAMIC_TILE.Conductivity)
        + (slab_template.thickness_m / CONCRETE_RC_DENSE.Conductivity)
        + 1.5
    )
    assert assembly.Type == "GroundSlab"
    assert assembly.r_value == pytest.approx(expected_r, rel=1e-6)


def test_non_ground_slab_treats_under_slab_r_as_dead_feature() -> None:
    """Under-slab insulation should become a no-op for suspended slabs."""
    slab = SemiFlatSlabConstruction(
        structural_system="reinforced_concrete_suspended",
        nominal_insulation_r=2.0,
        insulation_placement="under_slab",
        interior_finish="none",
        exterior_finish="none",
    )
    assembly = build_slab_assembly(slab)
    layer_material_names = [
        layer.ConstructionMaterial.Name for layer in assembly.sorted_layers
    ]

    assert slab.effective_nominal_insulation_r == 0.0
    assert "nominal_insulation_r" in slab.ignored_feature_names
    assert "XPSBoard" not in layer_material_names


def test_slab_auto_placement_uses_under_slab_for_ground_supported_system() -> None:
    """Auto placement should use under-slab insulation when support exists."""
    slab = SemiFlatSlabConstruction(
        structural_system="slab_on_grade",
        nominal_insulation_r=1.0,
        insulation_placement="auto",
    )
    assert slab.effective_insulation_placement == "under_slab"


def test_slab_feature_dict_has_fixed_length() -> None:
    """Slab feature dictionary should remain fixed-length across variants."""
    slab = SemiFlatSlabConstruction(
        structural_system="precast_hollow_core",
        nominal_insulation_r=0.8,
        insulation_placement="above_slab",
        interior_finish="carpet",
        exterior_finish="gypsum_board",
    )
    features = slab.to_feature_dict(prefix="Slab")

    expected_length = (
        2
        + len(ALL_SLAB_STRUCTURAL_SYSTEMS)
        + len(ALL_SLAB_INSULATION_PLACEMENTS) * 2
        + len(ALL_SLAB_INTERIOR_FINISHES)
        + len(ALL_SLAB_EXTERIOR_FINISHES)
        + len(ALL_CONTINUOUS_INSULATION_MATERIALS)
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
            nominal_insulation_r=1.4,
            insulation_placement="auto",
            interior_finish="tile",
            exterior_finish="none",
        ),
    )

    assert envelope_assemblies.FacadeAssembly.Type == "Facade"
    assert envelope_assemblies.FlatRoofAssembly.Type == "FlatRoof"
    assert envelope_assemblies.GroundSlabAssembly.Type == "GroundSlab"


def test_asphalt_shingle_exterior_finish_round_trip() -> None:
    """Asphalt shingle finish should produce a valid roof assembly."""
    roof = SemiFlatRoofConstruction(
        structural_system="light_wood_truss",
        nominal_cavity_insulation_r=3.0,
        nominal_exterior_insulation_r=0.0,
        nominal_interior_insulation_r=0.0,
        interior_finish="gypsum_board",
        exterior_finish="asphalt_shingle",
    )
    assembly = build_roof_assembly(roof)
    outer_layer = assembly.sorted_layers[0]
    assert outer_layer.ConstructionMaterial.Name == "AsphaltShingle"
    assert outer_layer.Thickness == pytest.approx(0.006)
    assert assembly.r_value > 0


def test_wood_shake_exterior_finish_round_trip() -> None:
    """Wood shake finish should produce a valid roof assembly."""
    roof = SemiFlatRoofConstruction(
        structural_system="light_wood_truss",
        nominal_cavity_insulation_r=3.0,
        nominal_exterior_insulation_r=0.0,
        nominal_interior_insulation_r=0.0,
        interior_finish="none",
        exterior_finish="wood_shake",
    )
    assembly = build_roof_assembly(roof)
    outer_layer = assembly.sorted_layers[0]
    assert outer_layer.ConstructionMaterial.Name == "SoftwoodGeneral"
    assert outer_layer.Thickness == pytest.approx(0.012)
    assert assembly.r_value > 0


# --- Phase 4: new roof finishes ---


def test_thatch_roof_finish_round_trip() -> None:
    """Thatch finish should produce a valid roof assembly with ThatchReed."""
    roof = SemiFlatRoofConstruction(
        structural_system="light_wood_truss",
        nominal_cavity_insulation_r=0.0,
        exterior_finish="thatch",
        interior_finish="none",
    )
    assembly = build_roof_assembly(roof)
    outer_layer = assembly.sorted_layers[0]
    assert outer_layer.ConstructionMaterial.Name == "ThatchReed"
    assert outer_layer.Thickness == pytest.approx(0.200)
    assert assembly.r_value > 0


def test_fiber_cement_sheet_roof_finish_round_trip() -> None:
    """Fiber cement sheet finish should produce a thin corrugated layer."""
    roof = SemiFlatRoofConstruction(
        structural_system="poured_concrete",
        exterior_finish="fiber_cement_sheet",
    )
    assembly = build_roof_assembly(roof)
    outer_layer = assembly.sorted_layers[0]
    assert outer_layer.ConstructionMaterial.Name == "FiberCementBoard"
    assert outer_layer.Thickness == pytest.approx(0.006)


# --- Phase 2: roof insulation material selection ---


def test_roof_exterior_insulation_material_affects_assembly() -> None:
    """Switching roof insulation material should change the layer material."""
    for mat_key, expected_name in [
        ("polyiso", "PolyisoBoard"),
        ("eps", "EPSBoard"),
        ("mineral_wool", "MineralWoolBoard"),
    ]:
        roof = SemiFlatRoofConstruction(
            structural_system="poured_concrete",
            nominal_exterior_insulation_r=2.0,
            exterior_insulation_material=mat_key,  # pyright: ignore[reportArgumentType]
        )
        assembly = build_roof_assembly(roof)
        ins_layers = [
            layer
            for layer in assembly.sorted_layers
            if layer.ConstructionMaterial.Name == expected_name
        ]
        assert len(ins_layers) == 1


# --- Phase 6: roof ventilated cavity ---


def test_roof_well_ventilated_cavity_omits_exterior_finish() -> None:
    """Well-ventilated roof cavity should omit the exterior finish per ISO 6946."""
    roof_vent = SemiFlatRoofConstruction(
        structural_system="poured_concrete",
        exterior_finish="tile_roof",
        exterior_cavity_type="well_ventilated",
    )
    roof_none = SemiFlatRoofConstruction(
        structural_system="poured_concrete",
        exterior_finish="tile_roof",
        exterior_cavity_type="none",
    )
    a_vent = build_roof_assembly(roof_vent)
    a_none = build_roof_assembly(roof_none)
    names_vent = [layer.ConstructionMaterial.Name for layer in a_vent.sorted_layers]
    assert "CeramicTile" not in names_vent
    assert a_vent.r_value < a_none.r_value


def test_roof_unventilated_cavity_adds_air_gap() -> None:
    """Unventilated roof cavity should add an air gap layer."""
    roof = SemiFlatRoofConstruction(
        structural_system="poured_concrete",
        exterior_finish="metal_roof",
        exterior_cavity_type="unventilated",
    )
    assembly = build_roof_assembly(roof)
    layer_names = [layer.ConstructionMaterial.Name for layer in assembly.sorted_layers]
    assert any("AirGap" in n for n in layer_names)


# --- Phase 5: slab additions ---


def test_compacted_earth_floor_round_trip() -> None:
    """Compacted earth floor should produce a valid assembly with RammedEarth."""
    slab = SemiFlatSlabConstruction(
        structural_system="compacted_earth_floor",
        interior_finish="none",
        exterior_finish="none",
    )
    assembly = build_slab_assembly(slab)
    struct_layer = assembly.sorted_layers[0]
    assert struct_layer.ConstructionMaterial.Name == "RammedEarth"
    assert struct_layer.Thickness == pytest.approx(0.10)


def test_cement_screed_slab_finish_round_trip() -> None:
    """Cement screed interior finish should map to CementMortar."""
    slab = SemiFlatSlabConstruction(
        structural_system="slab_on_grade",
        interior_finish="cement_screed",
    )
    assembly = build_slab_assembly(slab)
    inner_layer = assembly.sorted_layers[-1]
    assert inner_layer.ConstructionMaterial.Name == "CementMortar"
    assert inner_layer.Thickness == pytest.approx(0.02)


def test_slab_insulation_material_affects_assembly() -> None:
    """Switching slab insulation material should change the insulation layer."""
    slab_xps = SemiFlatSlabConstruction(
        structural_system="slab_on_grade",
        nominal_insulation_r=2.0,
        insulation_material="xps",
    )
    slab_eps = SemiFlatSlabConstruction(
        structural_system="slab_on_grade",
        nominal_insulation_r=2.0,
        insulation_material="eps",
    )
    a_xps = build_slab_assembly(slab_xps)
    a_eps = build_slab_assembly(slab_eps)
    xps_names = [layer.ConstructionMaterial.Name for layer in a_xps.sorted_layers]
    eps_names = [layer.ConstructionMaterial.Name for layer in a_eps.sorted_layers]
    assert "XPSBoard" in xps_names
    assert "EPSBoard" in eps_names


# --- Informal settlement archetype integration tests ---


def test_corrugated_iron_shack_archetype() -> None:
    """A corrugated iron shack should be expressible with existing + new systems."""
    wall = SemiFlatWallConstruction(
        structural_system="sheet_metal",
        interior_finish="none",
        exterior_finish="none",
    )
    roof = SemiFlatRoofConstruction(
        structural_system="none",
        exterior_finish="metal_roof",
        interior_finish="none",
    )
    slab = SemiFlatSlabConstruction(
        structural_system="compacted_earth_floor",
        interior_finish="none",
        exterior_finish="none",
    )
    wall_a = build_facade_assembly(wall)
    roof_a = build_roof_assembly(roof)
    slab_a = build_slab_assembly(slab)
    assert wall_a.r_value > 0
    assert roof_a.r_value > 0
    assert slab_a.r_value > 0


def test_mud_and_pole_with_cgi_roof_archetype() -> None:
    """A mud-and-pole wall + corrugated iron roof should be expressible."""
    wall = SemiFlatWallConstruction(
        structural_system="wattle_and_daub",
        interior_finish="cement_plaster",
        exterior_finish="none",
    )
    roof = SemiFlatRoofConstruction(
        structural_system="light_wood_truss",
        exterior_finish="metal_roof",
        interior_finish="none",
    )
    slab = SemiFlatSlabConstruction(
        structural_system="compacted_earth_floor",
        interior_finish="cement_screed",
    )
    wall_a = build_facade_assembly(wall)
    roof_a = build_roof_assembly(roof)
    slab_a = build_slab_assembly(slab)
    assert wall_a.r_value > 0
    assert roof_a.r_value > 0
    assert slab_a.r_value > 0
