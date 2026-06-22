"""IDF-build tests for floor-aware assignment models."""

from pathlib import Path

import pytest

from epinterface.data import DefaultEPWZipPath
from epinterface.geometry import get_zone_glazed_area
from epinterface.sbem.building_flat_model import BuildingFlatModel, BuildingShell
from epinterface.sbem.zone_assignment import (
    FloorBand,
    PartialZoneTemplate,
    ZoneRole,
)


def _light_power_by_zone(idf) -> dict[str, float]:
    """Return LIGHTS density keyed by assigned zone name."""
    out: dict[str, float] = {}
    for lights in idf.idfobjects["LIGHTS"]:
        zone_field = next(
            name
            for name in lights.fieldnames
            if "Zone_or_ZoneList" in name or "Zone_or_Space" in name
        )
        watts_field = next(
            name
            for name in lights.fieldnames
            if name
            in {
                "Watts_per_Zone_Floor_Area",
                "Watts_per_Space_Floor_Area",
                "Watts_per_Floor_Area",
            }
        )
        out[str(getattr(lights, zone_field))] = float(getattr(lights, watts_field))
    return out


def _exterior_wall_constructions_by_zone(idf) -> dict[str, set[str]]:
    """Return exterior wall construction names by zone."""
    out: dict[str, set[str]] = {}
    for surface in idf.idfobjects["BUILDINGSURFACE:DETAILED"]:
        if (
            str(surface.Surface_Type).lower() == "wall"
            and str(surface.Outside_Boundary_Condition).lower() == "outdoors"
        ):
            out.setdefault(str(surface.Zone_Name), set()).add(
                str(surface.Construction_Name)
            )
    return out


def _window_constructions_by_zone(idf) -> dict[str, set[str]]:
    """Return fenestration construction names by parent wall zone."""
    walls = {
        str(wall.Name): str(wall.Zone_Name)
        for wall in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
    }
    out: dict[str, set[str]] = {}
    for window in idf.idfobjects["FENESTRATIONSURFACE:DETAILED"]:
        zone_name = walls[str(window.Building_Surface_Name)]
        out.setdefault(zone_name, set()).add(str(window.Construction_Name))
    return out


def test_by_storey_floor_assignments_change_lpd_wwr_and_constructions(
    tmp_path: Path,
    base_zone_template,
) -> None:
    """By-storey floor bands visibly change IDF loads, windows, and constructions."""
    model = BuildingFlatModel(
        shell=BuildingShell(
            EPWURI=DefaultEPWZipPath,
            zoning="by_storey",
            Width=10,
            Depth=10,
            F2FHeight=3,
            NFloors=2,
        ),
        defaults=base_zone_template,
        floor_bands=[
            FloorBand(
                start=0,
                stop=1,
                template=PartialZoneTemplate(
                    LightingPowerDensity=5,
                    WWR=0.1,
                    FacadeRValue=3.0,
                    WindowUValue=2.0,
                ),
            ),
            FloorBand(
                start=1,
                stop=2,
                template=PartialZoneTemplate(
                    LightingPowerDensity=15,
                    WWR=0.5,
                    FacadeRValue=5.0,
                    WindowUValue=4.0,
                ),
            ),
        ],
    )

    idf = model.build_idf(output_dir=tmp_path)
    light_power = _light_power_by_zone(idf)
    zone_0 = "Block shoebox Storey 0"
    zone_1 = "Block shoebox Storey 1"

    assert light_power[zone_0] == 5
    assert light_power[zone_1] == 15
    assert get_zone_glazed_area(idf, zone_1) > get_zone_glazed_area(idf, zone_0) * 4

    wall_constructions = _exterior_wall_constructions_by_zone(idf)
    window_constructions = _window_constructions_by_zone(idf)
    assert wall_constructions[zone_0] != wall_constructions[zone_1]
    assert window_constructions[zone_0] != window_constructions[zone_1]


def test_core_perim_floor_and_role_assignments(
    tmp_path: Path,
    base_zone_template,
) -> None:
    """Core/perim models apply floor templates to all roles, then role overrides."""
    model = BuildingFlatModel(
        shell=BuildingShell(
            EPWURI=DefaultEPWZipPath,
            zoning="core/perim",
            Width=12,
            Depth=12,
            F2FHeight=3,
            NFloors=2,
        ),
        defaults=base_zone_template,
        floor_bands=[
            FloorBand(
                start=0,
                stop=1,
                template=PartialZoneTemplate(LightingPowerDensity=5, WWR=0.1),
            ),
            FloorBand(
                start=1,
                stop=2,
                template=PartialZoneTemplate(LightingPowerDensity=10, WWR=0.4),
                role_overrides={
                    ZoneRole.core: PartialZoneTemplate(LightingPowerDensity=4)
                },
            ),
        ],
    )

    idf = model.build_idf(output_dir=tmp_path)
    light_power = _light_power_by_zone(idf)

    assert len(light_power) == 10
    assert light_power["Block Core_Zone Storey 1"] == 4
    assert light_power["Block Perimeter_Zone_1 Storey 1"] == 10
    assert light_power["Block Perimeter_Zone_1 Storey 0"] == 5
    assert get_zone_glazed_area(idf, "Block Perimeter_Zone_1 Storey 1") > (
        get_zone_glazed_area(idf, "Block Perimeter_Zone_1 Storey 0") * 3
    )


def test_invalid_role_for_zoning_is_rejected(base_zone_template) -> None:
    """A core role override is not valid for by-storey zoning."""
    with pytest.raises(ValueError, match="Invalid role override"):
        BuildingFlatModel(
            shell=BuildingShell(
                EPWURI=DefaultEPWZipPath,
                zoning="by_storey",
                Width=10,
                Depth=10,
                F2FHeight=3,
                NFloors=2,
            ),
            defaults=base_zone_template,
            floor_bands=[
                FloorBand(
                    start=0,
                    stop=1,
                    role_overrides={
                        ZoneRole.core: PartialZoneTemplate(LightingPowerDensity=4)
                    },
                )
            ],
        )
