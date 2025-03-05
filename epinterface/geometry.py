"""Geometry utilities for the UBEM construction."""

from typing import Literal, cast

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
            for srf in idf.idfobjects["BUILDINGSURFACE:DETAILED"]:
                if srf.Surface_Type.lower() == "roof":
                    srf.Surface_Type = "ceiling"
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
