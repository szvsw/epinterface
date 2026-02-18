"""Tests for neighbor shading geometry (shading_fence_closed_ring, prepare_neighbor_shading_for_idf)."""

import numpy as np
import pytest
from shapely import Polygon

from epinterface.geometry import (
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
