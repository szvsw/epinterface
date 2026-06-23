"""IDF-build tests for floor-aware assignment models."""

from pathlib import Path
from typing import cast

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


_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def _ground_temperatures(idf) -> list[float]:
    """Return the 12 monthly site ground temperatures from the built IDF."""
    objs = idf.idfobjects["SITE:GROUNDTEMPERATURE:BUILDINGSURFACE"]
    assert len(objs) == 1
    return [float(getattr(objs[0], f"{month}_Ground_Temperature")) for month in _MONTHS]


def _names_for_type(idf, key: str) -> list[str]:
    """Return the identifier field of every object of a given IDF type.

    Most objects use ``Name`` as their first field, but some (e.g.
    ``HVACTEMPLATE:ZONE:IDEALLOADSAIRSYSTEM``) are keyed by ``Zone_Name``. The
    first field value (index 1, after the object-type key) is the identifier in
    every case, so use that uniformly.
    """
    names: list[str] = []
    for obj in idf.idfobjects[key]:
        values = obj.fieldvalues
        names.append(str(values[1] if len(values) > 1 else values[0]))
    return names


def test_ground_temperature_only_driven_by_ground_contact_floor(
    tmp_path: Path,
    base_zone_template,
) -> None:
    """Only the lowest (ground-contact) floor's setpoints drive ground temps.

    Two by-storey buildings share an identical floor 0 but differ wildly on floor
    1's heating setpoint. Because ground-contact heat transfer is driven by floor
    0 only, the computed site ground temperatures must be identical.
    """

    def build(top_floor_hsp: float):
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
                    template=PartialZoneTemplate(HeatingSetpointBase=21),
                ),
                FloorBand(
                    start=1,
                    stop=2,
                    template=PartialZoneTemplate(HeatingSetpointBase=top_floor_hsp),
                ),
            ],
        )
        return model.build_idf(output_dir=tmp_path / f"hsp_{int(top_floor_hsp)}")

    same_top = _ground_temperatures(build(21))
    cold_top = _ground_temperatures(build(5))

    assert same_top == pytest.approx(cold_top)


def test_heterogeneous_core_perim_object_names_are_unique(
    tmp_path: Path,
    base_zone_template,
) -> None:
    """A heterogeneous core/perim build must not produce duplicate object names."""
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
                template=PartialZoneTemplate(
                    LightingPowerDensity=5,
                    EquipmentPowerDensity=8,
                    WWR=0.1,
                    FacadeRValue=3.0,
                    WindowUValue=2.0,
                ),
            ),
            FloorBand(
                start=1,
                stop=2,
                template=PartialZoneTemplate(
                    LightingPowerDensity=12,
                    EquipmentPowerDensity=20,
                    WWR=0.4,
                    FacadeRValue=5.0,
                    WindowUValue=4.0,
                ),
                role_overrides={
                    ZoneRole.core: PartialZoneTemplate(LightingPowerDensity=3)
                },
            ),
        ],
    )

    idf = model.build_idf(output_dir=tmp_path)

    checked_types = [
        "LIGHTS",
        "PEOPLE",
        "ELECTRICEQUIPMENT",
        "ZONEINFILTRATION:DESIGNFLOWRATE",
        "HVACTEMPLATE:ZONE:IDEALLOADSAIRSYSTEM",
        "HVACTEMPLATE:THERMOSTAT",
        "SCHEDULE:YEAR",
        "SCHEDULE:WEEK:DAILY",
        "CONSTRUCTION",
    ]
    present = False
    for key in checked_types:
        names = _names_for_type(idf, key)
        if not names:
            continue
        present = True
        duplicates = {name for name in names if names.count(name) > 1}
        assert not duplicates, f"Duplicate {key} names: {sorted(duplicates)}"
    assert present, "Expected at least one of the checked object types to be present."


def test_core_perim_floor_summary_collapses_to_one_row_per_floor(
    tmp_path: Path,
    base_zone_template,
) -> None:
    """Ten core/perim zones aggregate to exactly NFloors floor rows.

    Also checks the as-built WWR reporting: core zones (no exterior walls) report
    actual_wwr == 0, and the floor-level actual_wwr reflects the perimeter facade.
    """
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
            FloorBand(start=0, stop=1, template=PartialZoneTemplate(WWR=0.1)),
            FloorBand(start=1, stop=2, template=PartialZoneTemplate(WWR=0.4)),
        ],
    )

    idf = model.build_idf(output_dir=tmp_path)
    zone_summary = model.zone_assignment_summary(idf=idf)
    floor_summary = model.floor_assignment_summary(idf=idf)

    main_zones = zone_summary[zone_summary["category"] == "main"]
    assert len(main_zones) == 10
    assert set(floor_summary["floor_index"]) == {0, 1}

    # Core zones have no exterior walls, so their as-built WWR is 0 regardless of
    # the requested WWR; perimeter zones carry the glazing.
    core_rows = zone_summary[zone_summary["role"] == "core"]
    assert (core_rows["actual_wwr"] == 0).all()

    # The floor-level as-built WWR is wall-area-weighted and follows the request.
    floor_summary = floor_summary.set_index("floor_index")
    wwr_floor_1 = cast(float, floor_summary.loc[1, "actual_wwr"])
    wwr_floor_0 = cast(float, floor_summary.loc[0, "actual_wwr"])
    assert wwr_floor_1 > wwr_floor_0


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
