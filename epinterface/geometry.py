"""Geometry utilities for the UBEM construction."""

from collections.abc import Sequence
from typing import Literal, cast

import numpy as np
from archetypal.idfclass import IDF
from geomeppy.geom.polygons import Polygon3D
from geomeppy.geom.vectors import Vector2D
from pydantic import BaseModel, Field
from shapely import LineString, Polygon, from_wkt
from shapely.affinity import translate


def match_idf_to_building_and_neighbors(
    idf: IDF,
    building: Polygon | str,
    neighbor_polys: list[Polygon | str | None],
    neighbor_floors: list[float | int | None],
    neighbor_f2f_height: float,
    target_short_length: float,
    target_long_length: float,
    rotation_angle: float,
) -> IDF:
    """Match an IDF model to a building and neighbors by scaling and rotating the IDF model and adding shading blocks for neighbors.

    Args:
        idf (IDF): The IDF model to match.
        building (Polygon | str): The building to match.
        neighbor_polys (list[Polygon | str | None]): The neighbors to inject as shading.
        neighbor_floors (list[float | int | None]): The counts of the neighbors.
        neighbor_f2f_height (float | None): The height of the building to match
        target_short_length (float): The target short length of the building.
        target_long_length (float): The target long length of the building.
        rotation_angle (float): The rotation angle of the building (radians).

    Returns:
        idf (IDF): The matched IDF model.
    """
    building_geo = (
        cast(Polygon, from_wkt(building)) if isinstance(building, str) else building
    )
    neighbor_geos = [
        (cast(Polygon, from_wkt(n)), h * neighbor_f2f_height)
        if isinstance(n, str)
        else (n, h * neighbor_f2f_height)
        for n, h in zip(neighbor_polys, neighbor_floors, strict=True)
        if n is not None and h is not None
    ]
    centroid = building_geo.centroid
    translated_neighbors = [
        (translate(n, xoff=-centroid.x, yoff=-centroid.y), h) for n, h in neighbor_geos
    ]
    idf_lengths = {(e.p1 - e.p2).length for e in idf.bounding_box().edges}
    idf_x_coords = [e.p1.x for e in idf.bounding_box().edges]
    x_span = max(idf_x_coords) - min(idf_x_coords)
    idf_y_coords = [e.p1.y for e in idf.bounding_box().edges]
    y_span = max(idf_y_coords) - min(idf_y_coords)
    # TODO: better handling for boxes that aren't [(0,0),...]
    if x_span < y_span:
        raise NotImplementedError(
            "This function assumes that the long edge is the x-axis, which is not the case."
        )
    x_min = min(idf_x_coords)
    y_min = min(idf_y_coords)
    if abs(x_min) > 1e-3 or abs(y_min) > 1e-3:
        raise NotImplementedError(
            "This function assumes that the building has the lowerleft corner at the origin, which is not the case."
        )
    if len(idf_lengths) > 2:
        raise NotImplementedError(
            "The IDF model is not a rectangle, which is not yet supported."
        )

    long_length = max(idf_lengths)
    short_length = min(idf_lengths)

    idf.scale(target_long_length / long_length, anchor=Vector2D(0, 0), axes="x")
    idf.scale(target_short_length / short_length, anchor=Vector2D(0, 0), axes="y")
    idf.translate((
        -target_long_length / 2,
        -target_short_length / 2,
        0,
    ))  # This translation makes an assumption that the source building is at [(0,0),(0,w),...]
    idf.rotate(rotation_angle * 180 / np.pi)
    for i, (geom, height) in enumerate(translated_neighbors):
        if not height:
            height = 3.5 * 2
        if np.isnan(height):
            height = 3.5 * 2
        idf.add_shading_block(
            name=f"shading_{i}",
            coordinates=[Vector2D(*coord) for coord in geom.exterior.coords[:-1]],
            height=height,
        )
    return idf


def compute_shading_mask(
    building: Polygon | str,
    neighbors: Sequence[Polygon | str | None],
    neighbor_heights: Sequence[float | int | None],
    azimuthal_angle: float,
) -> np.ndarray:
    """Compute the shading mask for the building.

    This will emit a ray from the center of the building in
    every direction according to the azimuthal angle division
    of a circle.

    It will compute the intersection of each ray with all the neighbor edges,
    and then determine the height of the each edge that intersects the ray.

    That height is then used to determine an elevation angle; the max of the elevation
    angles for each ray is then the shading mask value for that direction.

    Note that this checks all edges, so its crucial that the neighbors have
    already been culled to the relevant building to avoid unnecessary computation.

    Args:
        building (Polygon | str): The building to compute the shading mask for.
        neighbors (list[Polygon | str | None]): The neighbors to compute the shading mask for.
        neighbor_heights (list[float | int | None]): The heights of the neighbors.
        azimuthal_angle (float): The azimuthal angle to compute the shading mask for.

    Returns:
        shading_mask (np.ndarray): The shading mask for the building.
    """
    building_geom = building if isinstance(building, Polygon) else from_wkt(building)

    neighbor_geo_and_height = [
        (cast(Polygon, from_wkt(n)), float(h)) if isinstance(n, str) else (n, float(h))
        for n, h in zip(neighbors, neighbor_heights, strict=True)
        if n is not None and h is not None
    ]
    safe_neighbor_geoms = [geom for geom, _ in neighbor_geo_and_height]
    safe_neighbor_heights = [height for _, height in neighbor_geo_and_height]

    # first we compute the number of rays we need to cast
    # along with the angles at which to cast them
    n_rays = int(2 * np.pi / azimuthal_angle)
    ray_angles = np.linspace(0, 2 * np.pi - azimuthal_angle, n_rays)
    ray_distance = 9999  # an arbitrarily large distance

    # extract the relevant geometry data
    centroid = building_geom.centroid

    shading_mask = np.zeros(n_rays)

    for ray_angle_idx, ray_angle in enumerate(ray_angles):
        # create the ray as a line segment
        # using basic trig
        x_off, y_off = (
            ray_distance * np.cos(ray_angle),
            ray_distance * np.sin(ray_angle),
        )
        centroid_moved = translate(centroid, x_off, y_off)
        ray = LineString([centroid, centroid_moved])

        # track the max elevation angle for this ray so far
        max_elevation_angle = 0

        for geom, height in zip(
            safe_neighbor_geoms, safe_neighbor_heights, strict=True
        ):
            # create the line segments of the boundary
            x_coords = np.array(geom.boundary.xy[0])
            y_coords = np.array(geom.boundary.xy[1])

            for x0, y0, x1, y1 in zip(
                x_coords[:-1],
                y_coords[:-1],
                x_coords[1:],
                y_coords[1:],
                strict=True,
            ):
                line = LineString([(x0, y0), (x1, y1)])

                # compute the intersection and continue
                # if there is no intersection
                intersection = ray.intersection(line)
                if intersection.is_empty:
                    continue

                # compute the elevation angle and store it if it
                # is greater than the current max
                distance = intersection.distance(centroid)
                elevation_angle = np.arctan2(height, distance)
                max_elevation_angle = max(max_elevation_angle, elevation_angle)

        shading_mask[ray_angle_idx] = max_elevation_angle
    return shading_mask


ZoningType = Literal["core/perim", "by_storey"]


class ShoeboxGeometry(BaseModel):
    """A simple shoebox constructor for the IDF model.

    Can create gables, basements, and various zoning strategies.
    """

    x: float
    y: float
    w: float
    d: float
    h: float
    num_stories: int = Field(
        ...,
        title="Number of stories",
        ge=1,
        description="The number of stories in the building.",
    )
    zoning: ZoningType = Field(
        ...,
        title="Zoning type",
        description="Whether to use core/perim or full-floor zones.",
    )
    perim_depth: float = Field(
        default=3,
        title="Perimeter depth",
        description="Sets the perimeter depth when using core/perim zoning.  Ignored otherwise.",
    )
    roof_height: float | None = Field(
        default=None,
        title="Roof gable height",
        description="The height of the roof gable.  If None, a flat roof is assumed.",
    )
    basement: bool = Field(
        default=False,
        title="Basement",
        description="Whether or not to use a basement with same f2f height as building.",
    )
    wwr: float = Field(
        default=0.15,
        title="Window-to-wall ratio",
        description="The window-to-wall ratio of the building.",
        ge=0,
        le=1,
    )

    @property
    def basement_storey_count(self) -> int:
        """Return the number of basement stories."""
        return 1 if self.basement else 0

    @property
    def attic_storey_count(self) -> int:
        """Return the number of attic stories."""
        return 1 if self.roof_height else 0

    @property
    def zones_height(self) -> float:
        """Return the total height of the zones, excluding any gabling."""
        return self.h * (self.num_stories)

    @property
    def total_height_with_gabling(self) -> float:
        """Return the total height of the building, including any gabling."""
        return self.zones_height + (self.roof_height or 0)

    @property
    def footprint_area(self) -> float:
        """Return the total floor area of the building."""
        return self.w * self.d

    @property
    def total_living_area(self) -> float:
        """Return the total living area of the building (does not include attic/basement)."""
        return self.footprint_area * self.num_stories

    @property
    def total_area(self) -> float:
        """Return the total area of the building."""
        return (
            self.total_living_area
            + self.footprint_area * self.basement_storey_count
            + self.footprint_area * (1 if self.roof_height else 0)
        )

    @property
    def basement_suffix(self) -> str:
        """Return the basement suffix for the building."""
        if not self.basement:
            msg = "Building has no basement."
            raise ValueError(msg)
        return "Storey 0" if self.zoning == "core/perim" else "Storey -1"

    @property
    def zones_per_storey(self) -> int:
        """Return the number of zones per storey."""
        if self.zoning == "core/perim":
            return 5
        else:
            return 1

    def add(self, idf: IDF) -> IDF:
        """Constructs a simple shoebox geometry in the IDF model.

        Takes advantage of the geomeppy methods to do so.

        Can create gables, basements, and various zoning strategies.

        Args:
            idf: The IDF model to add the geometry to.

        Returns:
            The IDF model with the added geometry.
        """
        lower_left_corner = (self.x, self.y)
        lower_right_corner = (self.x + self.w, self.y)
        upper_right_corner = (self.x + self.w, self.y + self.d)
        upper_left_corner = (self.x, self.y + self.d)
        bottom_plane = [
            lower_left_corner,
            lower_right_corner,
            upper_right_corner,
            upper_left_corner,
        ]
        idf.add_block(
            name="shoebox",
            coordinates=bottom_plane,
            height=self.zones_height
            + (self.h if self.basement and self.zoning == "core/perim" else 0),
            num_stories=self.num_stories + self.basement_storey_count,
            zoning=self.zoning,
            perim_depth=self.perim_depth,
            below_ground_stories=self.basement_storey_count,
            below_ground_storey_height=self.h,
        )
        if self.basement and self.zoning == "core/perim":
            idf.translate((0, 0, -self.h))

        if self.roof_height:
            # we need to convert the old roof surfaces to ceilings;
            # additionally, we will track them so that we can create the
            # corresponding floor surfaces for the attic in a manner
            # that avoids having to subdivide surfaces with intersect/match
            old_roof_srfs = []
            for srf in idf.idfobjects["BUILDINGSURFACE:DETAILED"]:
                if srf.Surface_Type.lower() == "roof":
                    srf.Surface_Type = "ceiling"
                    old_roof_srfs.append(srf)
            if len(old_roof_srfs) not in [1, 5]:
                msg = "Too many roof surfaces were found; expected 1 (by_storey) or 5 "
                f" (core/perim), but found {len(old_roof_srfs)}."
                raise ValueError(msg)

            # create the zone
            idf.newidfobject("ZONE", Name="Attic")

            roof_centerline = self.x + self.w / 2
            vert_0 = (self.x, self.y + self.d, self.zones_height)
            vert_1 = (self.x, self.y, self.zones_height)
            vert_2 = (roof_centerline, self.y, self.total_height_with_gabling)
            vert_3 = (roof_centerline, self.y + self.d, self.total_height_with_gabling)
            idf.newidfobject(
                "BUILDINGSURFACE:DETAILED",
                Name="Gable1",
                Surface_Type="Roof",
                Number_of_Vertices=4,
                View_Factor_to_Ground=0,
                Vertex_1_Xcoordinate=vert_0[0],
                Vertex_1_Ycoordinate=vert_0[1],
                Vertex_1_Zcoordinate=vert_0[2],
                Vertex_2_Xcoordinate=vert_1[0],
                Vertex_2_Ycoordinate=vert_1[1],
                Vertex_2_Zcoordinate=vert_1[2],
                Vertex_3_Xcoordinate=vert_2[0],
                Vertex_3_Ycoordinate=vert_2[1],
                Vertex_3_Zcoordinate=vert_2[2],
                Vertex_4_Xcoordinate=vert_3[0],
                Vertex_4_Ycoordinate=vert_3[1],
                Vertex_4_Zcoordinate=vert_3[2],
                Zone_Name="Attic",
            )

            vert_0 = (self.x + self.w, self.y, self.zones_height)
            vert_1 = (self.x + self.w, self.y + self.d, self.zones_height)
            vert_2 = (roof_centerline, self.y + self.d, self.total_height_with_gabling)
            vert_3 = (roof_centerline, self.y, self.total_height_with_gabling)
            idf.newidfobject(
                "BUILDINGSURFACE:DETAILED",
                Name="Gable2",
                Surface_Type="Roof",
                Number_of_Vertices=4,
                View_Factor_to_Ground=0,
                Vertex_1_Xcoordinate=vert_0[0],
                Vertex_1_Ycoordinate=vert_0[1],
                Vertex_1_Zcoordinate=vert_0[2],
                Vertex_2_Xcoordinate=vert_1[0],
                Vertex_2_Ycoordinate=vert_1[1],
                Vertex_2_Zcoordinate=vert_1[2],
                Vertex_3_Xcoordinate=vert_2[0],
                Vertex_3_Ycoordinate=vert_2[1],
                Vertex_3_Zcoordinate=vert_2[2],
                Vertex_4_Xcoordinate=vert_3[0],
                Vertex_4_Ycoordinate=vert_3[1],
                Vertex_4_Zcoordinate=vert_3[2],
                Zone_Name="Attic",
            )

            # make triangular endcaps
            vert_0 = (self.x, self.y, self.zones_height)
            vert_1 = (self.x + self.w, self.y, self.zones_height)
            vert_2 = (roof_centerline, self.y, self.total_height_with_gabling)

            idf.newidfobject(
                "BUILDINGSURFACE:DETAILED",
                Name="Endcap1",
                Surface_Type="Wall",
                Number_of_Vertices=3,
                Vertex_1_Xcoordinate=vert_0[0],
                Vertex_1_Ycoordinate=vert_0[1],
                Vertex_1_Zcoordinate=vert_0[2],
                Vertex_2_Xcoordinate=vert_1[0],
                Vertex_2_Ycoordinate=vert_1[1],
                Vertex_2_Zcoordinate=vert_1[2],
                Vertex_3_Xcoordinate=vert_2[0],
                Vertex_3_Ycoordinate=vert_2[1],
                Vertex_3_Zcoordinate=vert_2[2],
                Zone_Name="Attic",
            )

            vert_0 = (self.x + self.w, self.y + self.d, self.zones_height)
            vert_1 = (self.x, self.y + self.d, self.zones_height)
            vert_2 = (roof_centerline, self.y + self.d, self.total_height_with_gabling)
            idf.newidfobject(
                "BUILDINGSURFACE:DETAILED",
                Name="Endcap2",
                Surface_Type="Wall",
                Number_of_Vertices=3,
                Vertex_1_Xcoordinate=vert_0[0],
                Vertex_1_Ycoordinate=vert_0[1],
                Vertex_1_Zcoordinate=vert_0[2],
                Vertex_2_Xcoordinate=vert_1[0],
                Vertex_2_Ycoordinate=vert_1[1],
                Vertex_2_Zcoordinate=vert_1[2],
                Vertex_3_Xcoordinate=vert_2[0],
                Vertex_3_Ycoordinate=vert_2[1],
                Vertex_3_Zcoordinate=vert_2[2],
                Zone_Name="Attic",
            )

            # We will create identical floor surfaces for the attic to match
            # the zone below.  While we could just add a single plane and let
            # the `intersect_match` handle it, this is more robust; the geomeppy
            # method occasionally results in numerical floating point errors where
            # very small overhang area is created with an outside boundary
            # condition.
            # we use a vertex order of 1, 4, 3, 2 to match the orientation of the
            # roof surfaces below it, i.e. CCW vs CW.
            for i, srf in enumerate(old_roof_srfs):
                idf.newidfobject(
                    "BUILDINGSURFACE:DETAILED",
                    Name=f"attic_bottom_plane_{i}",
                    Surface_Type="Floor",
                    Number_of_Vertices=4,
                    Vertex_1_Xcoordinate=srf.Vertex_1_Xcoordinate,
                    Vertex_1_Ycoordinate=srf.Vertex_1_Ycoordinate,
                    Vertex_1_Zcoordinate=srf.Vertex_1_Zcoordinate,
                    Vertex_2_Xcoordinate=srf.Vertex_4_Xcoordinate,
                    Vertex_2_Ycoordinate=srf.Vertex_4_Ycoordinate,
                    Vertex_2_Zcoordinate=srf.Vertex_4_Zcoordinate,
                    Vertex_3_Xcoordinate=srf.Vertex_3_Xcoordinate,
                    Vertex_3_Ycoordinate=srf.Vertex_3_Ycoordinate,
                    Vertex_3_Zcoordinate=srf.Vertex_3_Zcoordinate,
                    Vertex_4_Xcoordinate=srf.Vertex_2_Xcoordinate,
                    Vertex_4_Ycoordinate=srf.Vertex_2_Ycoordinate,
                    Vertex_4_Zcoordinate=srf.Vertex_2_Zcoordinate,
                    Zone_Name="Attic",
                )

        idf.intersect_match()

        idf.set_default_constructions()

        # Handle Windows
        window_walls = [
            w
            for w in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
            if w.Outside_Boundary_Condition.lower() == "outdoors"
            and "attic" not in w.Zone_Name.lower()
            and (
                not w.Zone_Name.lower().endswith(self.basement_suffix.lower())
                if self.basement
                else True
            )
            and w.Surface_Type.lower() == "wall"
        ]
        idf.set_wwr(
            wwr=self.wwr,
            construction="Project External Window",
            force=True,
            surfaces=window_walls,
        )
        return idf


def get_zone_floor_area(idf: IDF, zone_name: str) -> float:
    """Get the floor area of a zone by iterating over building surfaces that are of type 'floor'.

    If more than one floor is found, for now we will return an error; it could be possible in an
    attic where the floor below has perim/core zoning...

    Args:
        idf (IDF): The IDF model to get the floor area from.
        zone_name (str): The name of the zone to get the floor area from.

    Returns:
        area (float): The floor area of the zone [m2].
    """
    area = 0
    area_ct = 0
    for srf in idf.idfobjects["BUILDINGSURFACE:DETAILED"]:
        # TODO: ensure that this still works for basements and attics.
        if srf.Zone_Name == zone_name and srf.Surface_Type.lower() == "floor":
            poly = Polygon3D(srf.coords)
            if poly.area == 0:
                raise ValueError(f"INVALID_FLOOR:{zone_name}:{srf.Name}")
            area += float(poly.area)
            area_ct += 1
    if area_ct not in [1, 5]:
        raise ValueError(f"TOO_MANY_FLOORS:{zone_name}:{area_ct}")
    if area == 0 or area_ct == 0:
        raise ValueError(f"NO_AREA:{zone_name}")

    return area


def get_zone_glazed_area_alt(idf: IDF, zone_name: str) -> float:
    """Calculate the total area of windows for a specific zone in the IDF model.

    Args:
        idf (IDF): The IDF model.
        zone_name (str): The name of the zone to calculate the window area for.

    Returns:
        float: The total area of windows in the specified zone.
    """
    total_window_area = 0.0
    total_windows = 0

    for window in idf.idfobjects["FENESTRATIONSURFACE:DETAILED"]:
        parent_srf = idf.getobject(
            "BUILDINGSURFACE:DETAILED", window.Building_Surface_Name
        )
        if parent_srf is None:
            msg = f"BUILDINGSURFACE:DETAILED:{window.Building_Surface_Name} not found"
            raise ValueError(msg)
        if (
            parent_srf.Zone_Name.lower() == zone_name.lower()
            and window.Surface_Type.lower() == "window"
        ):
            vertices = [
                (
                    window.Vertex_1_Xcoordinate,
                    window.Vertex_1_Ycoordinate,
                    window.Vertex_1_Zcoordinate,
                ),
                (
                    window.Vertex_2_Xcoordinate,
                    window.Vertex_2_Ycoordinate,
                    window.Vertex_2_Zcoordinate,
                ),
                (
                    window.Vertex_3_Xcoordinate,
                    window.Vertex_3_Ycoordinate,
                    window.Vertex_3_Zcoordinate,
                ),
                (
                    window.Vertex_4_Xcoordinate,
                    window.Vertex_4_Ycoordinate,
                    window.Vertex_4_Zcoordinate,
                ),
            ]
            # Assuming the window is a quadrilateral, calculate its area
            # This is a simplified calculation assuming the window is a rectangle
            width = (
                (vertices[1][0] - vertices[0][0]) ** 2
                + (vertices[1][1] - vertices[0][1]) ** 2
                + (vertices[1][2] - vertices[0][2]) ** 2
            ) ** 0.5
            height = (
                (vertices[2][0] - vertices[1][0]) ** 2
                + (vertices[2][1] - vertices[1][1]) ** 2
                + (vertices[2][2] - vertices[1][2]) ** 2
            ) ** 0.5
            area = width * height
            total_window_area += area
            total_windows += 1

    if total_windows not in [0, 1, 4]:
        msg = f"TOO_MANY_WINDOWS:{zone_name}:{total_windows}"
        raise ValueError(msg)

    alt_window_area = get_zone_glazed_area_alt(idf, zone_name)
    if not np.allclose(total_window_area, alt_window_area):
        msg = f"GLAZED_AREA_MISMATCH:{zone_name}:{total_window_area}:{alt_window_area}"
        raise ValueError(msg)
    return total_window_area


def get_zone_glazed_area(idf: IDF, zone_name: str) -> float:
    """Calculate the total area of windows for a specific zone in the IDF model.

    Args:
        idf (IDF): The IDF model.
        zone_name (str): The name of the zone to calculate the window area for.

    Returns:
        float: The total area of windows in the specified zone.
    """
    total_window_area = 0.0
    total_windows = 0

    for window in idf.idfobjects["FENESTRATIONSURFACE:DETAILED"]:
        parent_srf = idf.getobject(
            "BUILDINGSURFACE:DETAILED", window.Building_Surface_Name
        )
        if parent_srf is None:
            msg = f"BUILDINGSURFACE:DETAILED:{window.Building_Surface_Name} not found"
            raise ValueError(msg)
        if (
            parent_srf.Zone_Name.lower() == zone_name.lower()
            and window.Surface_Type.lower() == "window"
        ):
            poly = Polygon3D(window.coords)
            total_window_area += float(poly.area)
            total_windows += 1

    if total_windows not in [0, 1, 4]:
        msg = f"TOO_MANY_WINDOWS:{zone_name}:{total_windows}"
        raise ValueError(msg)

    return total_window_area
