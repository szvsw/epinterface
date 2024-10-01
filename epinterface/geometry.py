"""Geometry utilities for the UBEM construction."""

from typing import Literal, cast

import geopandas as gpd
import numpy as np
from archetypal.idfclass import IDF
from geomeppy.geom.vectors import Vector2D
from pydantic import BaseModel, Field
from shapely import Polygon, from_wkt
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
    if len(idf_lengths) > 2:
        raise NotImplementedError(
            "The IDF model is not a rectangle, which is not yet supported."
        )

    long_length = max(idf_lengths)
    short_length = min(idf_lengths)
    idf.scale(target_long_length / long_length, anchor=Vector2D(0, 0), axes="x")
    idf.scale(target_short_length / short_length, anchor=Vector2D(0, 0), axes="y")
    idf.translate((-target_long_length / 2, -target_short_length / 2, 0))
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


def match_idf_to_scene(
    idf: IDF,
    gdf_buildings: gpd.GeoDataFrame,
    building_ix: int,
    neighbor_threshold: float = 50,
    apply_z_scale: bool = False,
):
    """Match an IDF model to a scene of buildings by scaling and rotating the IDF model.

    Additionally adds shading blocks for neighboring buildings.

    Args:
        idf (IDF): The IDF model to match.
        gdf_buildings (gpd.GeoDataFrame): The scene of buildings.
        building_ix (int): The index of the building in the scene to match.
        neighbor_threshold (float): The distance threshold for a building to be considered a neighbor.
        apply_z_scale (bool): Whether to scale the IDF model in the z direction.


    Returns:
        idf (IDF): The matched IDF model.
    """
    # TODO: add PANDERA schema validation
    center = gdf_buildings.iloc[building_ix].rotated_rectangle
    is_neighbor_mask = gdf_buildings.rotated_rectangle.apply(
        lambda x: x.distance(center) < neighbor_threshold
    )
    is_neighbor_mask.iloc[building_ix] = False
    neighbor_intersects = gdf_buildings.rotated_rectangle[is_neighbor_mask].apply(
        lambda x: x.intersects(center)
    )
    is_non_intersecting_neighbor = (
        ~neighbor_intersects.reindex(gdf_buildings.index, fill_value=False)
        & is_neighbor_mask
    )
    non_intersecting_neighbor_geometry = gdf_buildings.rotated_rectangle[
        is_non_intersecting_neighbor
    ]
    translated_neighbors = non_intersecting_neighbor_geometry.apply(
        lambda x: translate(x, xoff=-center.centroid.x, yoff=-center.centroid.y)
    )
    translated_neighbor_heights = gdf_buildings.height[is_non_intersecting_neighbor]

    idf_lengths = {(e.p1 - e.p2).length for e in idf.bounding_box().edges}
    # TODO: handle the case where the idf model building is not a rectangle
    # TODO: errors/warnings on scaling factors being too large or aspect ratio too
    # TODO: handle cases where the base idf building is rotated
    # different
    if len(idf_lengths) != 2:
        raise NotImplementedError(
            "The IDF model is not a rectangle, which is not yet supported."
        )
    short_length = min(idf_lengths)
    long_length = max(idf_lengths)
    z_coords = [
        obj[f"Vertex_{i}_Zcoordinate"]
        for obj in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
        for i in range(1, 5)
    ]
    z_coords = [float(z) for z in z_coords if z]
    model_height = max(z_coords)
    building_short_length = gdf_buildings.iloc[building_ix].short_edge
    building_long_length = gdf_buildings.iloc[building_ix].long_edge
    building_height = gdf_buildings.iloc[building_ix].height
    idf.scale(building_long_length / long_length, anchor=Vector2D(0, 0), axes="x")
    idf.scale(building_short_length / short_length, anchor=Vector2D(0, 0), axes="y")
    if apply_z_scale:
        idf.scale(building_height / model_height, anchor=Vector2D(0, 0), axes="z")

    idf.translate((-building_long_length / 2, -building_short_length / 2, 0))
    rotation_angle = gdf_buildings.iloc[building_ix].long_edge_angle
    idf.rotate(rotation_angle * 180 / np.pi)

    # add the neighbors as shading blocks
    for i, geom in enumerate(translated_neighbors):
        height = translated_neighbor_heights.iloc[i]
        if not height:
            height = 3.5
        if np.isnan(height):
            height = 3.5
        idf.add_shading_block(
            name=f"shading_{i}",
            coordinates=[Vector2D(*coord) for coord in geom.exterior.coords[:-1]],
            height=height,
        )
    return idf


ZoningType = Literal["core/perim", "by_storey"]


class ZoneDimensions(BaseModel):
    """Zone dimensions object which can be used to construct new shoebox zones."""

    x: float
    y: float
    w: float
    d: float
    h: float
    num_stories: int
    zoning: ZoningType = "by_storey"
    perim_depth: float = 3
    roof_height: float | None = None

    def add(self, idf: IDF):
        """Add the zone to the IDF object.

        Creates a new zone in the IDF object which is rectangular with a variable
        number of stories and optional gabling, as well as different strategies
        for zoning.

        Args:
            idf (IDF): The IDF object to add the zone to.

        Returns:
            idf (IDF): The updated IDF object.
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
            height=self.total_height,
            num_stories=self.num_stories,
            zoning=self.zoning,
            perim_depth=self.perim_depth,
        )
        if self.roof_height:
            idf.newidfobject("ZONE", Name="Attic")
            roof_centerline = self.x + self.w / 2
            vert_0 = (self.x, self.y + self.d, self.total_height)
            vert_1 = (self.x, self.y, self.total_height)
            vert_2 = (
                roof_centerline,
                self.y,
                self.total_height + self.roof_height,
            )
            vert_3 = (
                roof_centerline,
                self.y + self.d,
                self.total_height + self.roof_height,
            )
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

            vert_0 = (self.x + self.w, self.y, self.total_height)
            vert_1 = (self.x + self.w, self.y + self.d, self.total_height)
            vert_2 = (
                roof_centerline,
                self.y + self.d,
                self.total_height + self.roof_height,
            )
            vert_3 = (
                roof_centerline,
                self.y,
                self.total_height + self.roof_height,
            )
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
            vert_0 = (self.x, self.y, self.total_height)
            vert_1 = (self.x + self.w, self.y, self.total_height)
            vert_2 = (
                roof_centerline,
                self.y,
                self.total_height + self.roof_height,
            )

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

            vert_0 = (self.x + self.w, self.y + self.d, self.total_height)
            vert_1 = (self.x, self.y + self.d, self.total_height)
            vert_2 = (
                roof_centerline,
                self.y + self.d,
                self.total_height + self.roof_height,
            )
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

            idf.newidfobject(
                "BUILDINGSURFACE:DETAILED",
                Name="attic_bottom_plane",
                Surface_Type="Floor",
                Number_of_Vertices=4,
                Vertex_1_Xcoordinate=self.x + self.w,
                Vertex_1_Ycoordinate=self.y,
                Vertex_1_Zcoordinate=self.total_height,
                Vertex_2_Xcoordinate=self.x,
                Vertex_2_Ycoordinate=self.y,
                Vertex_2_Zcoordinate=self.total_height,
                Vertex_3_Xcoordinate=self.x,
                Vertex_3_Ycoordinate=self.y + self.d,
                Vertex_3_Zcoordinate=self.total_height,
                Vertex_4_Xcoordinate=self.x + self.w,
                Vertex_4_Ycoordinate=self.y + self.d,
                Vertex_4_Zcoordinate=self.total_height,
                Zone_Name="Attic",
            )

        return idf

    @property
    def total_height(self):
        """Return the total height of the zones."""
        return self.h * self.num_stories


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
    basement_depth: float | None = Field(
        default=None,
        title="Basement depth",
        description="The depth of the basement.  If None, no basement is assumed.",
        ge=1.5,
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
        return 1 if self.basement_depth else 0

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
        """Return the total living area of the building."""
        return self.footprint_area * self.num_stories

    @property
    def total_area(self) -> float:
        """Return the total area of the building."""
        return (
            self.total_living_area
            + self.footprint_area * self.basement_storey_count
            + self.footprint_area * (1 if self.roof_height else 0)
        )

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
            height=self.zones_height,
            num_stories=self.num_stories + self.basement_storey_count,
            zoning=self.zoning,
            perim_depth=self.perim_depth,
            below_ground_stories=self.basement_storey_count,
            below_ground_storey_height=self.basement_depth or 2.5,
        )

        if self.roof_height:
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

            idf.newidfobject(
                "BUILDINGSURFACE:DETAILED",
                Name="attic_bottom_plane",
                Surface_Type="Floor",
                Number_of_Vertices=4,
                Vertex_1_Xcoordinate=self.x + self.w,
                Vertex_1_Ycoordinate=self.y,
                Vertex_1_Zcoordinate=self.zones_height,
                Vertex_2_Xcoordinate=self.x,
                Vertex_2_Ycoordinate=self.y,
                Vertex_2_Zcoordinate=self.zones_height,
                Vertex_3_Xcoordinate=self.x,
                Vertex_3_Ycoordinate=self.y + self.d,
                Vertex_3_Zcoordinate=self.zones_height,
                Vertex_4_Xcoordinate=self.x + self.w,
                Vertex_4_Ycoordinate=self.y + self.d,
                Vertex_4_Zcoordinate=self.zones_height,
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
            and not w.Zone_Name.lower().endswith("-1")
            and w.Surface_Type.lower() == "wall"
        ]
        idf.set_wwr(
            wwr=self.wwr,
            construction="Project External Window",
            force=True,
            surfaces=window_walls,
        )
        return idf
