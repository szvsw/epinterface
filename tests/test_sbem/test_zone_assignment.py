"""Tests for typed zone assignment resolution."""

import pytest
from pydantic import ValidationError

from epinterface.geometry import ShoeboxGeometry
from epinterface.sbem.zone_assignment import (
    FloorBand,
    PartialZoneTemplate,
    ZoneAssignmentResolver,
    ZoneRole,
    parse_zone_key,
)


def test_parse_zone_key_by_storey() -> None:
    """By-storey zones resolve to floor roles and zero-based floor indices."""
    geometry = ShoeboxGeometry(
        x=0,
        y=0,
        w=10,
        d=10,
        h=3,
        num_stories=2,
        zoning="by_storey",
        wwr=0.2,
    )

    key = parse_zone_key("Block shoebox Storey 1", geometry)

    assert key.ep_storey_index == 1
    assert key.floor_index == 1
    assert key.role == ZoneRole.floor
    assert key.category == "main"


def test_parse_zone_key_core_perim() -> None:
    """Core/perim zones resolve to their perimeter or core role."""
    geometry = ShoeboxGeometry(
        x=0,
        y=0,
        w=12,
        d=12,
        h=3,
        num_stories=2,
        zoning="core/perim",
        wwr=0.2,
    )

    key = parse_zone_key("Block Perimeter_Zone_3 Storey 0", geometry)
    core_key = parse_zone_key("Block Core_Zone Storey 1", geometry)

    assert key.floor_index == 0
    assert key.role == ZoneRole.perim_3
    assert core_key.floor_index == 1
    assert core_key.role == ZoneRole.core


def test_resolver_precedence(base_zone_template) -> None:
    """Role overrides take precedence over floor templates and defaults."""
    resolver = ZoneAssignmentResolver(
        defaults=base_zone_template,
        n_floors=2,
        floor_bands=[
            FloorBand(
                start=1,
                stop=2,
                template=PartialZoneTemplate(LightingPowerDensity=12, WWR=0.4),
                role_overrides={
                    ZoneRole.core: PartialZoneTemplate(LightingPowerDensity=4)
                },
            )
        ],
    )
    geometry = ShoeboxGeometry(
        x=0,
        y=0,
        w=12,
        d=12,
        h=3,
        num_stories=2,
        zoning="core/perim",
        wwr=0.2,
    )

    core_params = resolver.resolve_zone("Block Core_Zone Storey 1", geometry).params
    perim_params = resolver.resolve_zone(
        "Block Perimeter_Zone_1 Storey 1", geometry
    ).params
    default_params = resolver.resolve_zone(
        "Block Perimeter_Zone_1 Storey 0", geometry
    ).params

    assert core_params.LightingPowerDensity == 4
    assert core_params.WWR == 0.4
    assert perim_params.LightingPowerDensity == 12
    assert (
        default_params.LightingPowerDensity == base_zone_template.LightingPowerDensity
    )


def test_floor_band_validation_rejects_overlap(base_zone_template) -> None:
    """Overlapping floor bands fail during resolver validation."""
    with pytest.raises(ValueError, match="Overlapping floor bands"):
        ZoneAssignmentResolver(
            defaults=base_zone_template,
            n_floors=3,
            floor_bands=[
                FloorBand(start=0, stop=2),
                FloorBand(start=1, stop=3),
            ],
        )


def test_partial_template_rejects_unknown_fields() -> None:
    """Sparse templates are typed and reject unknown override fields."""
    with pytest.raises(ValidationError):
        PartialZoneTemplate.model_validate({"NotARealField": 1})


@pytest.mark.parametrize("field", ["RoofRValue", "SlabRValue"])
def test_partial_template_rejects_boundary_envelope_fields(field: str) -> None:
    """Roof/slab R-values cannot be set per floor; they are building-wide.

    They are deliberately absent from PartialZoneTemplate so an override that
    could never reach the IDF fails at model-creation time instead of silently.
    """
    with pytest.raises(ValidationError):
        PartialZoneTemplate.model_validate({field: 3.0})


def test_floor_band_rejects_wwr_override_on_core() -> None:
    """Core zones have no exterior walls, so a core WWR override is rejected."""
    with pytest.raises(ValueError, match="WWR cannot be overridden on core"):
        FloorBand(
            start=0,
            stop=1,
            role_overrides={ZoneRole.core: PartialZoneTemplate(WWR=0.4)},
        )


def test_floor_band_allows_non_wwr_core_override() -> None:
    """A core role override that does not touch WWR is allowed."""
    band = FloorBand(
        start=0,
        stop=1,
        role_overrides={ZoneRole.core: PartialZoneTemplate(LightingPowerDensity=4)},
    )
    assert band.role_overrides[ZoneRole.core].LightingPowerDensity == 4


def test_parse_zone_key_attic() -> None:
    """Attic zones parse to the attic category with no above-grade floor index."""
    geometry = ShoeboxGeometry(
        x=0, y=0, w=10, d=10, h=3, num_stories=2, zoning="by_storey", wwr=0.2
    )
    key = parse_zone_key("Block shoebox attic", geometry)
    assert key.category == "attic"
    assert key.role == ZoneRole.attic
    assert key.floor_index is None


def test_parse_zone_key_basement_by_storey() -> None:
    """A by-storey basement (Storey -1) parses to the basement category."""
    geometry = ShoeboxGeometry(
        x=0,
        y=0,
        w=10,
        d=10,
        h=3,
        num_stories=2,
        zoning="by_storey",
        wwr=0.2,
        basement=True,
    )
    key = parse_zone_key("Block shoebox Storey -1", geometry)
    assert key.category == "basement"
    assert key.floor_index is None

    above = parse_zone_key("Block shoebox Storey 0", geometry)
    assert above.category == "main"
    assert above.floor_index == 0


def test_parse_zone_key_basement_core_perim_offsets_floor_index() -> None:
    """With a core/perim basement, above-grade floor indices start at 0."""
    geometry = ShoeboxGeometry(
        x=0,
        y=0,
        w=12,
        d=12,
        h=3,
        num_stories=2,
        zoning="core/perim",
        wwr=0.2,
        basement=True,
    )
    basement = parse_zone_key("Block Core_Zone Storey 0", geometry)
    assert basement.category == "basement"
    assert basement.floor_index is None

    first_floor = parse_zone_key("Block Core_Zone Storey 1", geometry)
    assert first_floor.category == "main"
    assert first_floor.floor_index == 0


def test_resolver_scales_unconditioned_basement_loads(base_zone_template) -> None:
    """Unconditioned basements scale loads by use fraction and disable systems."""
    resolver = ZoneAssignmentResolver(defaults=base_zone_template, n_floors=2)
    geometry = ShoeboxGeometry(
        x=0,
        y=0,
        w=10,
        d=10,
        h=3,
        num_stories=2,
        zoning="by_storey",
        wwr=0.2,
        basement=True,
    )
    params = resolver.resolve_zone(
        "Block shoebox Storey -1",
        geometry,
        basement_use_fraction=0.5,
        basement_conditioned=False,
    ).params

    assert params.LightingPowerDensity == base_zone_template.LightingPowerDensity * 0.5
    assert params.OccupantDensity == base_zone_template.OccupantDensity * 0.5
    assert params.VentProvider == "None"
    assert params.IdealLoadsHeatingOn is False
    assert params.IdealLoadsCoolingOn is False
