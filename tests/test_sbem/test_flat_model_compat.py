"""Regression tests for the legacy FlatModel -> BuildingFlatModel adapter.

These guard the compatibility path called out in the PR review: ``ZoneTemplate``
forbids extras, so ``FlatModel.zone_template()`` must project onto only the
template fields, and a uniform ``FlatModel`` converted to a ``BuildingFlatModel``
must produce an equivalent IDF (same lighting power density and window-to-wall
ratio).
"""

from pathlib import Path

import pytest

from epinterface.data import DefaultEPWZipPath
from epinterface.geometry import (
    get_zone_exterior_wall_area,
    get_zone_glazed_area,
)
from epinterface.sbem.builder import SimulationPathConfig
from epinterface.sbem.building_flat_model import BuildingFlatModel
from epinterface.sbem.flat_model import FlatModel
from epinterface.sbem.zone_assignment import ZoneTemplate


@pytest.fixture
def uniform_flat_model(base_zone_template: ZoneTemplate) -> FlatModel:
    """A uniform FlatModel sharing the conftest template's operating params."""
    return FlatModel(
        **base_zone_template.model_dump(),
        F2FHeight=3.0,
        NFloors=1,
        Width=10.0,
        Depth=10.0,
        Rotation=0.0,
        EPWURI=DefaultEPWZipPath,
        zoning="by_storey",
    )


def _single_zone_lpd(idf) -> float:
    """Return the lighting power density for the single LIGHTS object."""
    lights = idf.idfobjects["LIGHTS"]
    assert len(lights) == 1
    watts_field = next(
        name
        for name in lights[0].fieldnames
        if name
        in {
            "Watts_per_Zone_Floor_Area",
            "Watts_per_Space_Floor_Area",
            "Watts_per_Floor_Area",
        }
    )
    return float(getattr(lights[0], watts_field))


def _single_zone_actual_wwr(idf) -> float:
    """Return glazed/exterior-wall ratio for the single main zone."""
    zone_name = idf.idfobjects["ZONE"][0].Name
    glazed = get_zone_glazed_area(idf, zone_name)
    wall = get_zone_exterior_wall_area(idf, zone_name)
    return glazed / wall


def test_flat_model_zone_template_succeeds(
    uniform_flat_model: FlatModel,
    base_zone_template: ZoneTemplate,
) -> None:
    """zone_template() projects onto ZoneTemplate without tripping extra=forbid."""
    template = uniform_flat_model.zone_template()
    assert isinstance(template, ZoneTemplate)
    assert template.LightingPowerDensity == base_zone_template.LightingPowerDensity
    assert template.EquipmentPowerDensity == base_zone_template.EquipmentPowerDensity
    assert template.WWR == base_zone_template.WWR


def test_flat_model_to_building_model_preserves_template(
    uniform_flat_model: FlatModel,
) -> None:
    """to_building_model() keeps zoning, floor count, and template values."""
    building = uniform_flat_model.to_building_model()
    assert isinstance(building, BuildingFlatModel)
    assert building.shell.zoning == uniform_flat_model.zoning
    assert building.shell.NFloors == uniform_flat_model.NFloors
    assert (
        building.defaults.LightingPowerDensity
        == uniform_flat_model.LightingPowerDensity
    )
    assert building.defaults.WWR == uniform_flat_model.WWR


def test_uniform_flat_model_and_building_model_have_same_lpd_and_wwr(
    tmp_path: Path,
    uniform_flat_model: FlatModel,
) -> None:
    """A uniform FlatModel and its converted BuildingFlatModel build equivalently."""
    flat_model_obj, callback = uniform_flat_model.to_model()
    flat_idf = flat_model_obj.build(
        SimulationPathConfig(output_dir=tmp_path / "flat"),
        post_geometry_callback=callback,
    )

    building = uniform_flat_model.to_building_model()
    building_idf = building.build_idf(output_dir=tmp_path / "building")

    assert _single_zone_lpd(flat_idf) == pytest.approx(_single_zone_lpd(building_idf))
    assert _single_zone_lpd(building_idf) == pytest.approx(
        uniform_flat_model.LightingPowerDensity
    )
    # WWR is applied geometrically (whole-shoebox vs per-zone), so compare the
    # as-built glazing ratio rather than exact areas.
    assert _single_zone_actual_wwr(flat_idf) == pytest.approx(
        _single_zone_actual_wwr(building_idf), rel=0.05
    )
    assert _single_zone_actual_wwr(building_idf) == pytest.approx(
        uniform_flat_model.WWR, rel=0.1
    )
