"""Tests for neighbor shading geometry (shading_fence_closed_ring, prepare_neighbor_shading_for_idf)."""

import numpy as np
import pytest
from shapely import Polygon

from epinterface.geometry import (
    compute_shading_mask,
    prepare_neighbor_shading_for_idf,
    shading_fence_closed_ring,
)


def test_shading_fence_closed_ring():
    """Test shading_fence_closed_ring output shapes and cyclic closure."""
    elevations = np.array([0.1, 0.2, 0.3])
    d = 100.0

    az, p0, p1, h, w = shading_fence_closed_ring(elevations=elevations, d=d)

    assert az.shape == (3,)
    assert p0.shape == (3, 2)
    assert p1.shape == (3, 2)
    assert h.shape == (3,)
    assert isinstance(w, float)

    # Cyclic closure: p1[k] == p0[(k+1) % N] (within floating point tolerance)
    for k in range(3):
        np.testing.assert_allclose(p1[k], p0[(k + 1) % 3], atol=1e-12)

    # Heights: h[k] == d * tan(elevations[k])
    expected_h = d * np.tan(elevations)
    np.testing.assert_allclose(h, expected_h, rtol=1e-10)


def test_shading_fence_closed_ring_raises_for_n_less_than_3():
    """Test that shading_fence_closed_ring raises ValueError for N < 3."""
    elevations = np.array([0.1, 0.2])

    with pytest.raises(ValueError, match="at least 3 elevations"):
        shading_fence_closed_ring(elevations=elevations, d=100)


def test_prepare_neighbor_shading_for_idf_no_neighbors():
    """Test prepare_neighbor_shading_for_idf with no neighbors (default 48 azimuths)."""
    building = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])

    mask_polys, neighbor_floors = prepare_neighbor_shading_for_idf(
        building=building,
        neighbors=[],
        neighbor_heights=[],
        f2f_height=3.0,
    )

    assert len(mask_polys) == 48
    assert len(neighbor_floors) == 48

    for poly in mask_polys:
        assert poly.is_valid
        assert not poly.is_empty
        assert len(poly.exterior.coords) >= 4  # closed ring has repeated first point


def test_prepare_neighbor_shading_for_idf_with_neighbors():
    """Test prepare_neighbor_shading_for_idf with one neighbor."""
    building = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    neighbor = Polygon([(20, 5), (25, 5), (25, 15), (20, 15)])
    neighbor_height = 10.0

    mask_polys, neighbor_floors = prepare_neighbor_shading_for_idf(
        building=building,
        neighbors=[neighbor],
        neighbor_heights=[neighbor_height],
        f2f_height=3.0,
    )

    assert len(mask_polys) == 48
    assert len(neighbor_floors) == 48

    for poly in mask_polys:
        assert poly.is_valid
        assert not poly.is_empty


def test_shading_mask_from_real_geometry_matches_shading_mask_from_fake_ring():
    """Shading mask from real neighbor geometry equals shading mask from the fake ring.

    Manually construct a main building with neighbors scattered around it. Compute the
    shading mask from these real polygons. Then build the fake ring (mask_polys) from
    that shading mask and compute the shading mask again from the fake ring. The two
    masks should match, since the fake ring is designed to reproduce the same elevation
    angles when rays are cast from the building centroid.
    """
    azimuthal_angle = 2 * np.pi / 48
    fence_radius = 100.0

    # Main building: 10x10 square centered at (5, 5) - centroid at (5, 5)
    building = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])

    # Neighbors: rectangles to the east, north, and northwest with different heights.
    # Building centroid is (5, 5). Rays will intersect these at various distances.
    neighbor_east = Polygon([(15, 2), (25, 2), (25, 8), (15, 8)])  # east, height 12m
    neighbor_north = Polygon([(2, 15), (8, 15), (8, 22), (2, 22)])  # north, height 9m
    neighbor_nw = Polygon([
        (-5, 8),
        (-2, 8),
        (-2, 12),
        (-5, 12),
    ])  # northwest, height 6m

    neighbors = [neighbor_east, neighbor_north, neighbor_nw]
    neighbor_heights = [12.0, 9.0, 6.0]

    # Shading mask from real geometry
    mask_from_real = compute_shading_mask(
        building=building,
        neighbors=neighbors,
        neighbor_heights=neighbor_heights,
        azimuthal_angle=azimuthal_angle,
    )

    # Build the fake ring from this mask
    mask_polys, _neighbor_floors = prepare_neighbor_shading_for_idf(
        building=building,
        neighbors=neighbors,
        neighbor_heights=neighbor_heights,
        azimuthal_angle=azimuthal_angle,
        fence_radius=fence_radius,
        f2f_height=3.0,
    )

    # Heights of the fake ring fences: h = d * tan(elevation) for each azimuth.
    # We need these exact heights (not the floor-discretized ones) for an exact match.
    _, _, _, fence_heights, _ = shading_fence_closed_ring(
        elevations=mask_from_real, d=fence_radius
    )

    # Shading mask from the fake ring (using exact fence heights)
    mask_from_fake_ring = compute_shading_mask(
        building=building,
        neighbors=mask_polys,
        neighbor_heights=fence_heights.tolist(),
        azimuthal_angle=azimuthal_angle,
    )

    np.testing.assert_allclose(
        mask_from_real,
        mask_from_fake_ring,
        atol=1e-10,
        err_msg="Shading mask from real geometry should match shading mask from fake ring",
    )
