"""Tests for the geometry module."""

import itertools

import numpy as np
import pytest
from archetypal.idfclass import IDF
from shapely import Polygon

from epinterface.data import DefaultEPWPath, DefaultMinimalIDFPath
from epinterface.geometry import ShoeboxGeometry, match_idf_to_building_and_neighbors
from epinterface.settings import energyplus_settings


@pytest.fixture(scope="function")
def minimal_idf():
    """Fixture to create a fresh instance of the minimal IDF before each test."""
    idf = IDF(
        DefaultMinimalIDFPath.as_posix(),
        epw=DefaultEPWPath.as_posix(),
        as_version=energyplus_settings.energyplus_version,
    )
    yield idf


# Full factorial parameter combinations
f2f_heights = [3.5, 4.321]
num_floors = [1, 3]
zoning_types = ["core/perim", "by_storey"]
basement_options = [True, False]
roof_heights = [None, 3.5]

parameter_combinations = list(
    itertools.product(
        f2f_heights, num_floors, zoning_types, basement_options, roof_heights
    )
)


# @pytest.mark.skip("This test is too slow")
@pytest.mark.parametrize(
    "floor_2_floor_height, num_floors, zoning, basement, roof_height",
    parameter_combinations,
)
def test_height_of_building_surfaces(
    minimal_idf, floor_2_floor_height, num_floors, zoning, basement, roof_height
):
    """Test that the height of any BUILDINGSURFACE:DETAILED object matches the expected floor-to-floor height * number of floors."""
    idf = minimal_idf
    expected_max_height = floor_2_floor_height * num_floors + (roof_height or 0)
    expected_min_height = 0 if not basement else -floor_2_floor_height

    # make the shoebox geometry
    geom = ShoeboxGeometry(
        x=0,
        y=0,
        w=10,
        d=10,
        h=floor_2_floor_height,
        num_stories=num_floors,
        zoning=zoning,
        basement=basement,
        wwr=0.15,
        roof_height=roof_height,
    )
    idf = geom.add(idf)

    # Extract Z-coordinates from BUILDINGSURFACE:DETAILED objects
    z_coords = []
    for obj in idf.idfobjects["BUILDINGSURFACE:DETAILED"]:
        for i in range(1, 5):
            z_coord = getattr(obj, f"Vertex_{i}_Zcoordinate")
            if z_coord != "":  # sometimes we have triangles
                z_coords.append(float(z_coord))

    # Calculate the maximum Z-coordinate value
    max_height = max(z_coords)
    min_height = min(z_coords)

    # Assert that the maximum height matches the expected value
    assert max_height == pytest.approx(expected_max_height, rel=1e-2), (
        f"Max height {max_height} does not match expected {expected_max_height}"
    )

    # Assert that the minimum height matches the expected value
    assert min_height == pytest.approx(expected_min_height, rel=1e-2), (
        f"Min height {min_height} does not match expected {expected_min_height}"
    )


f2f_heights = [3.5]
num_floors = [1, 3]
zoning_types = ["core/perim", "by_storey"]
basement_options = [True, False]
roof_heights = [None, 3.5]

parameter_combinations = list(
    itertools.product(
        f2f_heights, num_floors, zoning_types, basement_options, roof_heights
    )
)


# @pytest.mark.skip("This test is too slow")
@pytest.mark.parametrize(
    "floor_2_floor_height, num_floors, zoning, basement, roof_height",
    parameter_combinations,
)
def test_num_window_srfs(
    minimal_idf, floor_2_floor_height, num_floors, zoning, basement, roof_height
):
    """Test that the number of windows matches the expected number of windows."""
    expected_num_windows = 4 * num_floors

    geom = ShoeboxGeometry(
        x=0,
        y=0,
        w=10,
        d=10,
        h=floor_2_floor_height,
        num_stories=num_floors,
        zoning=zoning,
        basement=basement,
        wwr=0.15,
        roof_height=roof_height,
    )

    idf = geom.add(minimal_idf)

    n_windows = len(idf.idfobjects["FENESTRATIONSURFACE:DETAILED"])

    assert n_windows == expected_num_windows, f"Expected {expected_num_windows} windows"


f2f_heights = [3.5]
num_floors = [1, 3]
zoning_types = ["core/perim", "by_storey"]
basement_options = [True, False]
roof_heights = [None, 3.5]

parameter_combinations = list(
    itertools.product(
        f2f_heights, num_floors, zoning_types, basement_options, roof_heights
    )
)


# @pytest.mark.skip("This test is too slow")
@pytest.mark.parametrize(
    "floor_2_floor_height, num_floors, zoning, basement, roof_height",
    parameter_combinations,
)
def test_num_zones(
    minimal_idf, floor_2_floor_height, num_floors, zoning, basement, roof_height
):
    """Test that the number of zones matches the expected number of zones."""
    floor_ct = num_floors + (1 if basement else 0)
    zones_per_floor = 1 if zoning == "by_storey" else 5
    expected_num_zones = floor_ct * zones_per_floor + (
        1 if roof_height is not None else 0
    )

    geom = ShoeboxGeometry(
        x=0,
        y=0,
        w=10,
        d=10,
        h=floor_2_floor_height,
        num_stories=num_floors,
        zoning=zoning,
        basement=basement,
        wwr=0.15,
        roof_height=roof_height,
    )

    idf = geom.add(minimal_idf)

    n_zones = len(idf.idfobjects["ZONE"])

    assert n_zones == expected_num_zones, (
        f"Expected {expected_num_zones} zones, found {n_zones}."
    )

    zone_names = [zone.Name for zone in idf.idfobjects["ZONE"]]
    zones_with_attic_in_name = [zone for zone in zone_names if "attic" in zone.lower()]
    expected_attic_ct = 1 if roof_height is not None else 0
    assert len(zones_with_attic_in_name) == (expected_attic_ct), (
        f"Expected {expected_attic_ct} attic zones, found {len(zones_with_attic_in_name)}."
    )

    if basement:
        suffix = geom.basement_suffix
        zones_with_basement_suffix = [
            zone for zone in zone_names if zone.lower().endswith(suffix.lower())
        ]

        expected_basement_suffices = 1 if zoning == "by_storey" else 5
        assert len(zones_with_basement_suffix) == expected_basement_suffices, (
            f"Expected {expected_basement_suffices} zones with basement suffix, found {len(zones_with_basement_suffix)}."
        )


f2f_heights = [3.5]
num_floors = [1, 3]
zoning_types = ["core/perim", "by_storey"]
basement_options = [True]
roof_heights = [None, 3.5]

parameter_combinations = list(
    itertools.product(
        f2f_heights, num_floors, zoning_types, basement_options, roof_heights
    )
)


# @pytest.mark.skip("This test is too slow")
@pytest.mark.parametrize(
    "floor_2_floor_height, num_floors, zoning, basement, roof_height",
    parameter_combinations,
)
def test_num_roof_srfs(
    minimal_idf, floor_2_floor_height, num_floors, zoning, basement, roof_height
):
    """Test that the number of roof surfaces matches the expected number of roof surfaces."""
    expected_num_rf_srfs = (
        2 if roof_height is not None else (5 if zoning == "core/perim" else 1)
    )

    geom = ShoeboxGeometry(
        x=0,
        y=0,
        w=10,
        d=10,
        h=floor_2_floor_height,
        num_stories=num_floors,
        zoning=zoning,
        basement=basement,
        wwr=0.15,
        roof_height=roof_height,
    )

    idf = geom.add(minimal_idf)

    n_rf_srfs = len([
        srf
        for srf in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
        if srf.Surface_Type.lower() == "roof"
    ])

    assert expected_num_rf_srfs == n_rf_srfs, (
        f"Expected {expected_num_rf_srfs} roof surfaces, found {n_rf_srfs}."
    )


f2f_heights = [3.5]
num_floors = [1, 3]
zoning_types = ["core/perim", "by_storey"]
basement_options = [True, False]
roof_heights = [None, 3.5]

parameter_combinations = list(
    itertools.product(
        f2f_heights, num_floors, zoning_types, basement_options, roof_heights
    )
)


# @pytest.mark.skip("This test is too slow")
@pytest.mark.parametrize(
    "floor_2_floor_height, num_floors, zoning, basement, roof_height",
    parameter_combinations,
)
def test_num_wall_srfs(
    minimal_idf, floor_2_floor_height, num_floors, zoning, basement, roof_height
):
    """Test that the number of roof surfaces matches the expected number of roof surfaces."""
    expected_number_of_wall_srfs = 4 * (num_floors + (1 if basement else 0)) + (
        2 if roof_height is not None else 0
    )
    expected_number_of_gnd_walls = 4 if basement else 0
    expected_number_of_exposed_walls = (
        expected_number_of_wall_srfs - expected_number_of_gnd_walls
    )

    expected_number_partition_srfs = (
        8 * (num_floors + (1 if basement else 0)) if zoning == "core/perim" else 0
    ) * 2  # doubled because of adjoining zones

    geom = ShoeboxGeometry(
        x=0,
        y=0,
        w=10,
        d=10,
        h=floor_2_floor_height,
        num_stories=num_floors,
        zoning=zoning,
        basement=basement,
        wwr=0.15,
        roof_height=roof_height,
    )

    idf = geom.add(minimal_idf)

    n_wall_srfs = len([
        srf
        for srf in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
        if srf.Surface_Type.lower() == "wall"
        and srf.Outside_Boundary_Condition.lower() != "surface"
    ])

    n_partition_srfs = len([
        srf
        for srf in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
        if srf.Surface_Type.lower() == "wall"
        and srf.Outside_Boundary_Condition.lower() == "surface"
    ])

    n_gnd_wall_srfs = len([
        srf
        for srf in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
        if srf.Outside_Boundary_Condition.lower() == "ground"
        and srf.Surface_Type.lower() == "wall"
    ])

    n_exposed_wall_srfs = len([
        srf
        for srf in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
        if srf.Outside_Boundary_Condition.lower() == "outdoors"
        and srf.Surface_Type.lower() == "wall"
    ])

    assert expected_number_of_wall_srfs == n_wall_srfs, (
        f"Expected {expected_number_of_wall_srfs} wall surfaces, found {n_wall_srfs}."
    )

    assert expected_number_of_gnd_walls == n_gnd_wall_srfs, (
        f"Expected {expected_number_of_gnd_walls} ground wall surfaces, found {n_gnd_wall_srfs}."
    )

    assert expected_number_of_exposed_walls == n_exposed_wall_srfs, (
        f"Expected {expected_number_of_exposed_walls} exposed wall surfaces, found {n_exposed_wall_srfs}."
    )

    assert expected_number_partition_srfs == n_partition_srfs, (
        f"Expected {expected_number_partition_srfs} partition wall surfaces, found {n_partition_srfs}."
    )


f2f_heights = [3.5]
num_floors = [1, 3]
zoning_types = ["core/perim", "by_storey"]
basement_options = [True, False]
roof_heights = [None, 3.5]

parameter_combinations = list(
    itertools.product(
        f2f_heights, num_floors, zoning_types, basement_options, roof_heights
    )
)


# @pytest.mark.skip("This test is too slow")
@pytest.mark.parametrize(
    "floor_2_floor_height, num_floors, zoning, basement, roof_height",
    parameter_combinations,
)
def test_num_floor_sfs(
    minimal_idf, floor_2_floor_height, num_floors, zoning, basement, roof_height
):
    """Test that the number of roof surfaces matches the expected number of roof surfaces."""
    expected_number_of_any_floor_srfs = (5 if zoning == "core/perim" else 1) * (
        num_floors + (1 if basement else 0) + (1 if roof_height is not None else 0)
    )
    expected_number_of_ground_floor_srfs = 5 if zoning == "core/perim" else 1
    expected_number_of_floor_srfs = (
        expected_number_of_any_floor_srfs - expected_number_of_ground_floor_srfs
    )
    geom = ShoeboxGeometry(
        x=0,
        y=0,
        w=10,
        d=10,
        h=floor_2_floor_height,
        num_stories=num_floors,
        zoning=zoning,
        basement=basement,
        wwr=0.15,
        roof_height=roof_height,
    )

    idf = geom.add(minimal_idf)

    n_floor_srfs = len([
        srf
        for srf in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
        if srf.Surface_Type.lower() == "floor"
    ])

    n_gnd_floor_srfs = len([
        srf
        for srf in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
        if srf.Outside_Boundary_Condition.lower() == "ground"
        and srf.Surface_Type.lower() == "floor"
    ])

    n_non_gnd_floor_srfs = len([
        srf
        for srf in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
        if srf.Outside_Boundary_Condition.lower() == "surface"
        and srf.Surface_Type.lower() == "floor"
    ])

    assert expected_number_of_any_floor_srfs == n_floor_srfs, (
        f"Expected {expected_number_of_any_floor_srfs} floor surfaces, found {n_floor_srfs}."
    )

    assert expected_number_of_ground_floor_srfs == n_gnd_floor_srfs, (
        f"Expected {expected_number_of_ground_floor_srfs} ground floor surfaces, found {n_gnd_floor_srfs}."
    )

    assert expected_number_of_floor_srfs == n_non_gnd_floor_srfs, (
        f"Expected {expected_number_of_floor_srfs} non-ground floor surfaces, found {n_non_gnd_floor_srfs}."
    )


f2f_heights = [3.5]
num_floors = [1, 3]
zoning_types = ["core/perim", "by_storey"]
basement_options = [True, False]
roof_heights = [None, 3.5]

parameter_combinations = list(
    itertools.product(
        f2f_heights, num_floors, zoning_types, basement_options, roof_heights
    )
)


# @pytest.mark.skip("This test is too slow")
@pytest.mark.parametrize(
    "floor_2_floor_height, num_floors, zoning, basement, roof_height",
    parameter_combinations,
)
def test_num_ceil_sfs(
    minimal_idf, floor_2_floor_height, num_floors, zoning, basement, roof_height
):
    """Test that the number of roof surfaces matches the expected number of roof surfaces."""
    expected_number_ceiling_srfs = (
        num_floors - (1 if roof_height is None else 0) + (1 if basement else 0)
    ) * (5 if zoning == "core/perim" else 1)
    geom = ShoeboxGeometry(
        x=0,
        y=0,
        w=10,
        d=10,
        h=floor_2_floor_height,
        num_stories=num_floors,
        zoning=zoning,
        basement=basement,
        wwr=0.15,
        roof_height=roof_height,
    )

    idf = geom.add(minimal_idf)

    n_ceiling_srfs = len([
        srf
        for srf in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
        if srf.Surface_Type.lower() == "ceiling"
    ])

    assert expected_number_ceiling_srfs == n_ceiling_srfs, (
        f"Expected {expected_number_ceiling_srfs} ceiling surfaces, found {n_ceiling_srfs}."
    )


widths = [10, 20]
depths = [10, 20]
rotation_angle = [0, 37, 153, 289, 360]
target_length = [9, 11]


@pytest.mark.parametrize(
    "width, depth, rotation_angle, target_length",
    list(itertools.product(widths, depths, rotation_angle, target_length)),
)
def test_match_idf_to_geometry_neighbors(
    minimal_idf, width, depth, rotation_angle, target_length
):
    """Test that the geometry is correctly matched to the building and neighbors."""
    idf = minimal_idf
    # make the shoebox geometry
    target_short_length = target_length - 2
    target_long_length = target_length
    geom = ShoeboxGeometry(
        x=0,
        y=0,
        w=width,
        d=depth,
        h=3.5,
        num_stories=2,
        zoning="core/perim",
        basement=False,
        wwr=0.15,
        roof_height=None,
    )
    idf = geom.add(idf)

    neighbors: list[Polygon | str | None] = [
        Polygon(
            [
                (-10, -10),
                (-15, -10),
                (-15, -15),
                (-10, -15),
            ],
        ),
        Polygon(
            [
                (30, 30),
                (35, 30),
                (35, 35),
                (30, 35),
            ],
        ),
    ]
    building = Polygon([
        [7, 14],
        [7, 5],
        [15, 5],
        [15, 14],
    ])

    if width < depth:
        with pytest.raises(NotImplementedError):
            idf = match_idf_to_building_and_neighbors(
                idf=idf,
                building=building,
                neighbor_polys=neighbors,
                neighbor_f2f_height=3.5,
                neighbor_floors=[2, 4],
                target_long_length=target_long_length,
                target_short_length=target_short_length,
                rotation_angle=rotation_angle,
            )
    else:
        idf = match_idf_to_building_and_neighbors(
            idf=idf,
            building=building,
            neighbor_polys=neighbors,
            neighbor_f2f_height=3.5,
            neighbor_floors=[2, 4],
            target_long_length=target_long_length,
            target_short_length=target_short_length,
            rotation_angle=rotation_angle,
        )
        # get a list of the shading surfaces
        shading_surfaces = idf.idfobjects["SHADING:SITE:DETAILED"]

        assert len(shading_surfaces) == 8
        # get the z coordinates of the surfaces
        z_coordinates = (
            [float(srf.Vertex_1_Zcoordinate) for srf in shading_surfaces]
            + [float(srf.Vertex_2_Zcoordinate) for srf in shading_surfaces]
            + [float(srf.Vertex_3_Zcoordinate) for srf in shading_surfaces]
            + [float(srf.Vertex_4_Zcoordinate) for srf in shading_surfaces]
        )
        # get the unique z coordinates
        unique_z_coordinates = set(z_coordinates)
        unique_z = np.array(sorted(unique_z_coordinates))
        expected_z = np.array([0, 3.5 * 2, 3.5 * 4])
        assert np.allclose(unique_z, expected_z), (
            f"Expected: {expected_z}, found: {unique_z}"
        )

        assert len(unique_z_coordinates) == 3

        building_surfaces = idf.idfobjects["BUILDINGSURFACE:DETAILED"]
        x_coords = (
            [float(srf.Vertex_1_Xcoordinate) for srf in building_surfaces]
            + [float(srf.Vertex_2_Xcoordinate) for srf in building_surfaces]
            + [float(srf.Vertex_3_Xcoordinate) for srf in building_surfaces]
            + [float(srf.Vertex_4_Xcoordinate) for srf in building_surfaces]
        )
        x_max = max(x_coords)
        x_min = min(x_coords)

        y_coords = (
            [float(srf.Vertex_1_Ycoordinate) for srf in building_surfaces]
            + [float(srf.Vertex_2_Ycoordinate) for srf in building_surfaces]
            + [float(srf.Vertex_3_Ycoordinate) for srf in building_surfaces]
            + [float(srf.Vertex_4_Ycoordinate) for srf in building_surfaces]
        )
        y_max = max(y_coords)
        y_min = min(y_coords)
        # compute where (x,y) moves to after a rotation around the origin by c degrees counterclockwise
        lower_right_corner = np.array([
            target_long_length / 2,
            -target_short_length / 2,
        ])
        upper_right_corner = np.array([target_long_length / 2, target_short_length / 2])
        lower_left_corner = np.array([
            -target_long_length / 2,
            -target_short_length / 2,
        ])
        upper_left_corner = np.array([-target_long_length / 2, target_short_length / 2])
        rotation_matrix = np.array([
            [np.cos(rotation_angle), -np.sin(rotation_angle)],
            [np.sin(rotation_angle), np.cos(rotation_angle)],
        ])
        new_lower_right = np.dot(rotation_matrix, lower_right_corner)
        new_upper_right = np.dot(rotation_matrix, upper_right_corner)
        new_lower_left = np.dot(rotation_matrix, lower_left_corner)
        new_upper_left = np.dot(rotation_matrix, upper_left_corner)
        new_x_max_expected = max(
            new_lower_right[0], new_upper_right[0], new_lower_left[0], new_upper_left[0]
        )
        new_x_min_expected = min(
            new_lower_right[0], new_upper_right[0], new_lower_left[0], new_upper_left[0]
        )
        new_y_max_expected = max(
            new_lower_right[1], new_upper_right[1], new_lower_left[1], new_upper_left[1]
        )
        new_y_min_expected = min(
            new_lower_right[1], new_upper_right[1], new_lower_left[1], new_upper_left[1]
        )

        assert pytest.approx(new_x_max_expected, rel=1e-2) == x_max, (
            f"Expected x_max to be {new_x_max_expected}, found {x_max}"
        )
        assert pytest.approx(new_x_min_expected, rel=1e-2) == x_min, (
            f"Expected x_min to be {new_x_min_expected}, found {x_min}"
        )
        assert pytest.approx(new_y_max_expected, rel=1e-2) == y_max, (
            f"Expected y_max to be {new_y_max_expected}, found {y_max}"
        )
        assert pytest.approx(new_y_min_expected, rel=1e-2) == y_min, (
            f"Expected y_min to be {new_y_min_expected}, found {y_min}"
        )
