"""A module for building the energy model using the SBEM template library approach."""

import asyncio
import gc
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast
from uuid import uuid4

import numpy as np
import pandas as pd
from archetypal.idfclass import IDF
from archetypal.idfclass.sql import Sql
from pydantic import BaseModel, Field, field_validator, model_validator

from epinterface.constants import assumed_constants, physical_constants
from epinterface.data import EnergyPlusArtifactDir
from epinterface.ddy_injector_bayes import DDYSizingSpec
from epinterface.geometry import ShoeboxGeometry, get_zone_floor_area
from epinterface.interface import (
    InternalMass,
    SiteGroundTemperature,
    ZoneList,
    add_default_schedules,
    add_default_sim_controls,
)
from epinterface.sbem.components.envelope import (
    ConstructionAssemblyComponent,
    EnvelopeAssemblyComponent,
    GlazingConstructionSimpleComponent,
)
from epinterface.sbem.components.systems import DHWFuelType, FuelType
from epinterface.sbem.components.zones import ZoneComponent
from epinterface.sbem.exceptions import NotImplementedParameter
from epinterface.weather import BaseWeather

DESIRED_METERS = (
    "InteriorEquipment:Electricity",
    "InteriorLights:Electricity",
    "Heating:DistrictHeating",
    "Cooling:DistrictCooling",
    "WaterSystems:DistrictHeating",
)

# TODO: add the meters for HVAC systems
DESIRED_VARIABLES = (
    "Zone Mean Air Temperature",
    "Zone Air Relative Humidity",
    "Site Outdoor Air Drybulb Temperature",
)


class TemperatureOutputConfig(BaseModel):
    """Configuration for temperature output processing."""

    mode: Literal["mean", "hours_above_threshold"] = Field(
        default="mean",
        description="Output mode: 'mean' for monthly mean temperatures, 'hours_above_threshold' for hours above threshold per month",
    )
    threshold: float | None = Field(
        default=None,
        description="Temperature threshold in °C for 'hours_above_threshold' mode. Required when mode is 'hours_above_threshold'.",
    )

    @model_validator(mode="after")
    def check_threshold_when_needed(self):
        """Ensure threshold is provided when using hours_above_threshold mode."""
        if self.mode == "hours_above_threshold" and self.threshold is None:
            msg = "threshold must be provided when mode is 'hours_above_threshold'"
            raise ValueError(msg)
        return self


class SimulationPathConfig(BaseModel):
    """The configuration for the simulation's pathing."""

    output_dir: Path = Field(
        default_factory=lambda: EnergyPlusArtifactDir / "cache" / str(uuid4())[:8],
        description="The output directory for the IDF model.",
    )
    weather_dir: Path = Field(
        default_factory=lambda: EnergyPlusArtifactDir / "cache" / "weather",
        description="The directory to store the weather files.",
    )


class SurfaceHandler(BaseModel):
    """A handler for filtering and adding surfaces to a model."""

    boundary_condition: str | None
    original_construction_name: str | None
    original_surface_type: str | None
    surface_group: Literal["glazing", "opaque", "internal_mass"]
    zone_name_contains: str | None
    outside_boundary_condition_object_contains: str | None

    @model_validator(mode="after")
    def check_no_obco_if_not_bc_surface(self):
        """An outside boundary condition object is only specifiable if the boundary condition is `surface`."""
        if (
            self.outside_boundary_condition_object_contains is not None
            and self.boundary_condition != "surface"
        ):
            msg = "An outside boundary condition object is only specifiable if the boundary condition is `surface`."
            raise ValueError(msg)
        return self

    def assign_constructions_to_objs(
        self,
        idf: IDF,
        construction: ConstructionAssemblyComponent
        | GlazingConstructionSimpleComponent,
    ) -> IDF:
        """Adds a construction (and its materials) to an IDF and assigns it to matching surfaces.

        The basic idea is to look for certain idf objects that need a construction assigned to them,
        and then assign the construction to them by name.

        Depending on the configuration of the surface handler, we will look for different types of IDF objects.

        Args:
            idf (IDF): The IDF model to add the construction to.
            construction (ConstructionAssemblyComponent | GlazingConstructionComponent): The construction to add.
        """
        # This will identify what *type* of energy plus object we need to assign a particular construction to.
        # e.g. glazing -> look for FENESTRATIONSURFACE:DETAILED
        # e.g. opaque -> look for BUILDINGSURFACE:DETAILED
        # e.g. internal mass -> look for INTERNALMASS
        obj_type_key = (
            "FENESTRATIONSURFACE:DETAILED"
            if self.surface_group == "glazing"
            else (
                "INTERNALMASS"
                if self.surface_group == "internal_mass"
                else "BUILDINGSURFACE:DETAILED"
            )
        )

        if self.boundary_condition is not None and self.surface_group == "glazing":
            raise NotImplementedParameter(
                "BoundaryCondition", self.surface_group, "Glazing"
            )

        # Now we can find the matching idf objects that need a construction.
        srfs = [srf for srf in idf.idfobjects[obj_type_key] if self.check_srf(srf)]
        idf = construction.add_to_idf(idf)

        # and then we can finally assign the construction to the surfaces.
        for srf in srfs:
            srf.Construction_Name = construction.Name
        return idf

    def check_srf(self, srf):
        """Check if the surface matches the filters.

        Args:
            srf (eppy.IDF.BLOCK): The surface to check.

        Returns:
            match (bool): True if the surface matches the filters.
        """
        return (
            self.check_construction_type(srf)
            and self.check_boundary(srf)
            and self.check_construction_name(srf)
            and self.check_zone_name(srf)
            and self.check_outside_boundary_condition_object(srf)
        )

    def check_construction_type(self, srf):
        """Check if the surface matches the construction type.

        Args:
            srf (eppy.IDF.BLOCK): The surface to check.

        Returns:
            match (bool): True if the surface matches the construction type.
        """
        if self.surface_group == "glazing":
            # Ignore the construction type check for windows
            return True
        if self.original_surface_type is None:
            # Ignore the construction type check when filter not provided
            return True
        # Check the construction type
        return self.original_surface_type.lower() == srf.Surface_Type.lower()

    def check_boundary(self, srf):
        """Check if the surface matches the boundary condition.

        Args:
            srf (eppy.IDF.BLOCK): The surface to check.

        Returns:
            match (bool): True if the surface matches the boundary condition.
        """
        if self.surface_group == "glazing":
            # Ignore the bc filter check for windows
            return True
        if self.boundary_condition is None:
            # Ignore the bc filter when filter not provided
            return True
        # Check the boundary condition
        return srf.Outside_Boundary_Condition.lower() == self.boundary_condition.lower()

    def check_construction_name(self, srf):
        """Check if the surface matches the original construction name.

        Args:
            srf (eppy.IDF.BLOCK): The surface to check.

        Returns:
            match (bool): True if the surface matches the original construction name.
        """
        if self.original_construction_name is None:
            # Ignore the original construction name check when filter not provided
            return True
        # Check the original construction name
        return srf.Construction_Name.lower() == self.original_construction_name.lower()

    # TODO: convert this to a regex for better control
    def check_zone_name(self, srf):
        """Check that the zone name for the surface contains the expected substring."""
        if self.zone_name_contains is None:
            # Ignore the zone name check when filter not provided
            return True
        if self.surface_group == "glazing":
            # Ignore the zone name check for windows
            return True
        # Check the zone name
        zone_name = srf.Zone_Name
        return self.zone_name_contains.lower() in zone_name.lower()

    def check_outside_boundary_condition_object(self, srf):
        """Check if the surface's outside boundary condition object contains the desired substring."""
        if self.outside_boundary_condition_object_contains is None:
            # Ignore the outside boundary condition object check when filter not provided
            return True
        # Check the outside boundary condition object
        if self.surface_group == "glazing":
            # Ignore the outside boundary condition object check for windows
            return True
        return (
            self.outside_boundary_condition_object_contains.lower()
            in srf.Outside_Boundary_Condition_Object.lower()
        )


class SurfaceHandlers(BaseModel):
    """A collection of surface handlers for different surface types."""

    RoofOutdoorBC: SurfaceHandler
    AtticFloorFloor: SurfaceHandler
    AtticFloorCeiling: SurfaceHandler
    Facade: SurfaceHandler
    FloorCeilingFloor: SurfaceHandler
    FloorCeilingCeiling: SurfaceHandler
    Partition: SurfaceHandler
    InternalMass: SurfaceHandler
    GroundSlab: SurfaceHandler
    GroundWall: SurfaceHandler
    BasementCeilingCeiling: SurfaceHandler
    BasementCeilingFloor: SurfaceHandler
    Window: SurfaceHandler

    @classmethod
    def Default(cls, basement_suffix: str):
        """Get the default surface handlers."""
        roof_outdoor_bc_handler = SurfaceHandler(
            boundary_condition="outdoors",
            original_construction_name=None,
            original_surface_type="roof",
            surface_group="opaque",
            zone_name_contains=None,
            outside_boundary_condition_object_contains=None,
        )

        facade_handler = SurfaceHandler(
            boundary_condition="outdoors",
            original_construction_name=None,
            original_surface_type="wall",
            surface_group="opaque",
            zone_name_contains=None,
            outside_boundary_condition_object_contains=None,
        )
        partition_handler = SurfaceHandler(
            boundary_condition="surface",
            original_construction_name=None,
            original_surface_type="wall",
            surface_group="opaque",
            zone_name_contains=None,
            outside_boundary_condition_object_contains=None,
        )
        ground_wall_handler = SurfaceHandler(
            boundary_condition="ground",
            original_construction_name=None,
            original_surface_type="wall",
            surface_group="opaque",
            zone_name_contains=None,
            outside_boundary_condition_object_contains=None,
        )
        floor_ceiling_floor_handler = SurfaceHandler(
            boundary_condition="surface",
            original_construction_name=None,
            original_surface_type="floor",
            surface_group="opaque",
            zone_name_contains=None,
            outside_boundary_condition_object_contains=None,
        )
        floor_ceiling_ceiling_handler = SurfaceHandler(
            boundary_condition="surface",
            original_construction_name=None,
            original_surface_type="ceiling",
            surface_group="opaque",
            zone_name_contains=None,
            outside_boundary_condition_object_contains=None,
        )
        ground_slab_handler = SurfaceHandler(
            boundary_condition="ground",
            original_construction_name=None,
            original_surface_type="floor",
            surface_group="opaque",
            zone_name_contains=None,
            outside_boundary_condition_object_contains=None,
        )
        basement_ceiling_ceiling_handler = SurfaceHandler(
            boundary_condition="surface",
            original_construction_name=None,
            original_surface_type="ceiling",
            surface_group="opaque",
            zone_name_contains=basement_suffix,  # this is because the basement will always `Block shoebox .* -1/0` (depends on core/perim vs by_storey)
            outside_boundary_condition_object_contains=None,
        )
        basement_ceiling_floor_handler = SurfaceHandler(
            boundary_condition="surface",
            original_construction_name=None,
            original_surface_type="floor",
            surface_group="opaque",
            zone_name_contains=None,  # this is because the basement will always `Block shoebox .* -1/0` (depends on core/perim vs by_storey)
            outside_boundary_condition_object_contains=basement_suffix,
        )
        window_handler = SurfaceHandler(
            boundary_condition=None,
            original_construction_name=None,
            original_surface_type=None,
            surface_group="glazing",
            zone_name_contains=None,
            outside_boundary_condition_object_contains=None,
        )

        internal_mass_handler = SurfaceHandler(
            boundary_condition=None,
            original_construction_name=None,
            original_surface_type=None,
            surface_group="internal_mass",
            zone_name_contains=None,
            outside_boundary_condition_object_contains=None,
        )

        attic_floor_floor_handler = SurfaceHandler(
            boundary_condition="surface",
            original_construction_name=None,
            original_surface_type="floor",
            surface_group="opaque",
            zone_name_contains="attic",
            outside_boundary_condition_object_contains=None,
        )
        attic_floor_ceiling_handler = SurfaceHandler(
            boundary_condition="surface",
            original_construction_name=None,
            original_surface_type="ceiling",
            surface_group="opaque",
            zone_name_contains=None,
            outside_boundary_condition_object_contains="attic",
        )
        return cls(
            RoofOutdoorBC=roof_outdoor_bc_handler,
            AtticFloorFloor=attic_floor_floor_handler,
            AtticFloorCeiling=attic_floor_ceiling_handler,
            Facade=facade_handler,
            FloorCeilingFloor=floor_ceiling_floor_handler,
            FloorCeilingCeiling=floor_ceiling_ceiling_handler,
            Partition=partition_handler,
            InternalMass=internal_mass_handler,
            GroundSlab=ground_slab_handler,
            GroundWall=ground_wall_handler,
            BasementCeilingCeiling=basement_ceiling_ceiling_handler,
            BasementCeilingFloor=basement_ceiling_floor_handler,
            Window=window_handler,
        )

    def handle_envelope(
        self,
        idf: IDF,
        constructions: EnvelopeAssemblyComponent,
        window: GlazingConstructionSimpleComponent | None,
        with_attic: bool,
        with_basement: bool,
        exposed_basement_frac: float = 0,
    ):
        """Assign the envelope to the IDF model.

        Note that this will add a "reversed" construction for the floorsystem slab/ceiling

        Args:
            idf (IDF): The IDF model to add the envelope to.
            constructions (ZoneConstruction): The construction names for the envelope.
            window (GlazingConstructionSimpleComponent | None): The window definition.
            with_attic (bool): Whether to add the attic floor and ceiling constructions.
            with_basement (bool): Whether to add the basement floor and ceiling constructions.
            exposed_basement_frac (float): The fraction of the basement walls that are exposed above ground.

        Returns:
            idf (IDF): The updated IDF model.
        """
        floor_ceiling_reversed = constructions.FloorCeilingAssembly.reversed
        attic_floor_reversed = constructions.AtticFloorAssembly.reversed
        basement_ceiling_reversed = constructions.BasementCeilingAssembly.reversed

        # handle the roof which will always have the "roof" surface type
        # and "outdoors" for the bc but needs a different construction.
        outdoor_roof_bc = (
            constructions.AtticRoofAssembly
            if with_attic
            else constructions.FlatRoofAssembly
        )
        idf = self.RoofOutdoorBC.assign_constructions_to_objs(
            idf=idf, construction=outdoor_roof_bc
        )

        idf = self.Facade.assign_constructions_to_objs(
            idf=idf, construction=constructions.FacadeAssembly
        )
        idf = self.Partition.assign_constructions_to_objs(
            idf=idf, construction=constructions.PartitionAssembly
        )
        idf = self.FloorCeilingFloor.assign_constructions_to_objs(
            idf=idf, construction=floor_ceiling_reversed
        )
        idf = self.FloorCeilingCeiling.assign_constructions_to_objs(
            idf=idf, construction=constructions.FloorCeilingAssembly
        )
        # NB: We must execute basement and attic floor/ceiling systems
        # AFTER the regular floor ceiling systems because the regular floor ceilings
        # will match all of the floor/ceiling surfaces
        # and we want to overwrite their constructions.
        if with_basement:
            idf = self.BasementCeilingCeiling.assign_constructions_to_objs(
                idf=idf, construction=constructions.BasementCeilingAssembly
            )
            idf = self.BasementCeilingFloor.assign_constructions_to_objs(
                idf=idf, construction=basement_ceiling_reversed
            )
        if with_attic:
            idf = self.AtticFloorFloor.assign_constructions_to_objs(
                idf=idf, construction=constructions.AtticFloorAssembly
            )
            idf = self.AtticFloorCeiling.assign_constructions_to_objs(
                idf=idf, construction=attic_floor_reversed
            )

        idf = self.GroundSlab.assign_constructions_to_objs(
            idf=idf, construction=constructions.GroundSlabAssembly
        )
        idf = self.GroundWall.assign_constructions_to_objs(
            idf=idf, construction=constructions.GroundWallAssembly
        )

        if with_basement and exposed_basement_frac > 0:
            basement_wall_surfaces = [
                srf
                for srf in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
                if srf.Outside_Boundary_Condition == "ground"
                and srf.Surface_Type == "wall"
            ]
            for srf in basement_wall_surfaces:
                coords = srf.coords
                z_coords = [c[2] for c in coords]
                min_z = min(z_coords)
                max_z = max(z_coords)
                h = max_z - min_z
                unexposed_height = h * (1 - exposed_basement_frac)
                unexposed_height = min(
                    max(unexposed_height, 0.15), h - 0.15
                )  # 15cm, approximately 6in
                cut_z = min_z + unexposed_height
                z_coords_lower_section = [z if z == min_z else cut_z for z in z_coords]
                z_coords_upper_section = [z if z == max_z else cut_z for z in z_coords]
                coords_lower_section = [
                    (c[0], c[1], z)
                    for c, z in zip(coords, z_coords_lower_section, strict=False)
                ]
                coords_upper_section = [
                    (c[0], c[1], z)
                    for c, z in zip(coords, z_coords_upper_section, strict=False)
                ]
                new_bottom_srf = idf.copyidfobject(srf)
                new_top_srf = idf.copyidfobject(srf)
                new_bottom_srf.setcoords(coords_lower_section)
                new_top_srf.setcoords(coords_upper_section)
                new_bottom_srf.Name = f"{srf.Name}_bottom"
                new_top_srf.Name = f"{srf.Name}_top"
                new_top_srf.Outside_Boundary_Condition = "outdoors"
                idf.removeidfobject(srf)

        if window:
            idf = self.Window.assign_constructions_to_objs(idf=idf, construction=window)

        if constructions.InternalMassAssembly is not None:
            # We need to create new IDF Objects since they were not added into the scene
            # yet (whereas the other buildingsurface/fenestrationsurface were added by
            # eppy during the add_block call which inits zone geometry)
            for zone in idf.idfobjects["ZONE"]:
                floor_area = get_zone_floor_area(idf, zone.Name) * (
                    constructions.InternalMassExposedAreaPerArea or 0
                )
                internal_mass = InternalMass(
                    Name=f"{zone.Name}_InternalMass",
                    Zone_or_ZoneList_Name=zone.Name,
                    Construction_Name=constructions.InternalMassAssembly.Name,
                    Surface_Area=floor_area,
                )
                idf = internal_mass.add(idf)

            # once we've guaranteed that the internal mass object exists, we can
            # assign it the constructions to them
            idf = self.InternalMass.assign_constructions_to_objs(
                idf=idf, construction=constructions.InternalMassAssembly
            )
        return idf


@dataclass
class AddedZoneLists:
    """A collection of zone lists for a model."""

    conditioned_zone_list: ZoneList
    all_zones_list: ZoneList
    occupied_zone_list: ZoneList
    attic_zone_list: ZoneList
    basement_zone_list: ZoneList
    main_zone_list: ZoneList


class AtticAssumptions(BaseModel):
    """The conditions of the attic."""

    UseFraction: float | None = Field(..., ge=0, le=1)
    Conditioned: bool


class BasementAssumptions(BaseModel):
    """The conditions of the basement."""

    UseFraction: float | None = Field(..., ge=0, le=1)
    Conditioned: bool


class Model(BaseWeather, validate_assignment=True):
    """A simple model constructor for the IDF model.

    Creates geometry as well as zone definitions.
    """

    geometry: ShoeboxGeometry
    Attic: AtticAssumptions
    Basement: BasementAssumptions
    # TODO: should we have another field for whether or not the attic is ventilated, i.e. high infiltration?
    Zone: ZoneComponent

    @field_validator("geometry", mode="after")
    @classmethod
    def check_geometry(cls, v: ShoeboxGeometry):
        """Check the geometry of the model.

        Raises:
            ValueError
        """
        # TODO: should this validator happen on the geometry object?
        if v.w < 3 or v.d < 3:
            msg = f"Geometry must be at least 3m wide and 3m long (width, depth) = ({v.w}, {v.d})."
            raise ValueError(msg)
        if (v.roof_height or 0) > (v.h * 2.5):
            msg = f"Roof Gable height must be less than two and a half times the f2f height (roof_height, f2f_height) = ({v.roof_height}, {v.h})."
            raise ValueError(msg)
        return v

    @property
    def total_conditioned_area(self) -> float:
        """The total conditioned area of the model.

        Returns:
            area (float): The total conditioned area of the model.
        """
        conditioned_area = self.geometry.total_living_area
        if self.geometry.basement and self.Basement.Conditioned:
            conditioned_area += self.geometry.footprint_area
        if self.geometry.roof_height and self.Attic.Conditioned:
            conditioned_area += self.geometry.footprint_area
        return conditioned_area

    @property
    def total_people(self) -> float:
        """The total number of people in the model.

        Returns:
            ppl (float): The total number of people in the model

        """
        raise NotImplementedError(
            "Total people is not yet implemented because of attics/basements etc."
        )
        ppl_per_m2 = (
            self.Zone.Operations.SpaceUse.Occupancy.PeopleDensity
            if self.Zone.Operations.SpaceUse.Occupancy.IsOn
            else 0
        )
        total_area = self.total_conditioned_area  # this is wrong - it should be based off of occupied area which may be different depending on attic/basement use fractions.
        total_ppl = ppl_per_m2 * total_area
        return total_ppl

        # validate the attic conditioning

    @model_validator(mode="after")
    def attic_check(self):
        """Validate the attic insulation surface and geometry.

        It is impossible to have the roof insulated but on gabling (gabling is determined by the roof height).

        It is imposisble to have a conditioned attic if there is no roof height/gabling.

        Raises:
            ValueError
        """
        # TODO: should we add a limiter for min roof height?
        if self.Attic.Conditioned and (
            self.geometry.roof_height is None or self.geometry.roof_height == 0
        ):
            msg = "Cannot have a conditioned attic if there is no roof height."
            raise ValueError(msg)

        if self.Attic.UseFraction and (
            self.geometry.roof_height is None or self.geometry.roof_height == 0
        ):
            msg = "Cannot have an occupied attic if there is no roof height."
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def basement_check(self):
        """Validate the basement insulation surface and geometry.

        It is impossible to have the basement walls insulated but have no basement.

        It is impossible to have a conditioned basement if there is no basement.

        Raises:
            ValueError
        """
        if self.Basement.Conditioned and not self.geometry.basement:
            msg = "Cannot have a conditioned basement if there is no basement in self.geometry."
            raise ValueError(msg)

        if self.Basement.UseFraction and not self.geometry.basement:
            msg = "Cannot have an occupied basement if there is no basement in self.geometry."
            raise ValueError(msg)

        return self

    def add_zone_lists(
        self,
        idf: IDF,
    ) -> tuple[IDF, AddedZoneLists]:
        """Add the zone lists to the IDF model.

        Note that this attempts to automatically determine
        the zones from the IDF model which are conditioned
        as well as a separate list for all zones.

        Args:
            idf (IDF): The IDF model to add the zone lists to.

        Returns:
            idf (IDF): The IDF model with the added zone lists
            zone_lists (AddedZoneLists): The list of zone lists
        """
        all_zone_names = [zone.Name for zone in idf.idfobjects["ZONE"]]
        all_zones_list = ZoneList(Name="All_Zones", Names=all_zone_names)

        conditioned_zone_names = []
        attic_zone_names = []
        basement_zone_names = []
        main_zone_names = []
        occupied_zone_names = []
        for zone in idf.idfobjects["ZONE"]:
            # handle attic
            is_attic = "attic" in zone.Name.lower()
            is_basement = (
                zone.Name.lower().endswith(self.geometry.basement_suffix.lower())
                if self.geometry.basement
                else False
            )
            is_normal_zone = not is_attic and not is_basement
            should_condition = (
                (is_attic and self.Attic.Conditioned)
                or (is_basement and self.Basement.Conditioned)
                or is_normal_zone
            )
            should_be_occupied = (
                (is_attic and self.Attic.UseFraction is not None)
                or (is_basement and self.Basement.UseFraction is not None)
                or is_normal_zone
            )
            if should_condition:
                conditioned_zone_names.append(zone.Name)
            if should_be_occupied:
                occupied_zone_names.append(zone.Name)
            if is_attic:
                attic_zone_names.append(zone.Name)
            if is_basement:
                basement_zone_names.append(zone.Name)
            if is_normal_zone:
                main_zone_names.append(zone.Name)

        # safety check for zone counts
        # attic never gets partitioned so it only ever contributes 1
        # to the conditioned storey count
        conditioned_storey_count = self.geometry.num_stories + (
            1 if self.Basement.Conditioned else 0
        )
        zones_per_storey = self.geometry.zones_per_storey
        expected_zone_count = conditioned_storey_count * zones_per_storey + (
            1 if self.Attic.Conditioned else 0
        )
        if len(conditioned_zone_names) != expected_zone_count:
            msg = f"Expected {expected_zone_count} zones, but found {len(conditioned_zone_names)}."
            raise ValueError(msg)

        conditioned_zone_list = ZoneList(
            Name="Conditioned_Zones", Names=conditioned_zone_names
        )
        attic_zone_list = ZoneList(Name="Attic_Zones", Names=attic_zone_names)
        basement_zone_list = ZoneList(Name="Basement_Zones", Names=basement_zone_names)
        main_zone_list = ZoneList(Name="Main_Zones", Names=main_zone_names)
        occupied_zone_list = ZoneList(Name="Occupied_Zones", Names=occupied_zone_names)

        idf = conditioned_zone_list.add(idf)
        idf = all_zones_list.add(idf)
        return idf, AddedZoneLists(
            conditioned_zone_list=conditioned_zone_list,
            all_zones_list=all_zones_list,
            occupied_zone_list=occupied_zone_list,
            attic_zone_list=attic_zone_list,
            basement_zone_list=basement_zone_list,
            main_zone_list=main_zone_list,
        )

    # part of the HVAC/conditioning system
    def compute_dhw(self) -> float:
        """Explicitly compute the domestic hot water energy demand.

        This is useful as a gut-check to make sure the DHW has been added correctly.

        Returns:
            energy (float): The annual domestic hot water energy demand (kWh/m2)
        """
        # TODO: this should be computed from the DHW schedule
        if not self.Zone.Operations.DHW.IsOn:
            return 0
        flow_rate_per_person = (
            self.Zone.Operations.SpaceUse.WaterUse.FlowRatePerPerson
        )  # m3/day/person, average
        temperature_rise = (
            self.Zone.Operations.DHW.WaterSupplyTemperature
            - self.Zone.Operations.DHW.WaterTemperatureInlet
        )  # K
        water_density = physical_constants.WaterDensity_kg_per_m3  # kg/m3
        c = physical_constants.WaterSpecificHeat_J_per_kg_degK  # J/kg.K
        total_flow_rate = flow_rate_per_person * self.total_people  # m3/day
        total_volume = total_flow_rate * 365  # m3 / yr
        total_mass = total_volume * water_density  # kg
        total_energy = total_mass * temperature_rise * c  # J / yr
        total_energy_kWh = total_energy / physical_constants.J_to_kWh  # kWh / yr
        # TODO: unit test this with parameterizations over basement presence/absence,
        # attic presence/absence, basement occupation/unoccupation, etc.
        # - total_conditioned_area now probably needs to be replaced with total_occupied_area
        total_energy_kWh_per_m2 = (
            total_energy_kWh / self.total_conditioned_area
        )  # kWh/m2 / yr
        return total_energy_kWh_per_m2

    def add_constructions(
        self,
        idf: IDF,
        constructions: EnvelopeAssemblyComponent,
        window_def: GlazingConstructionSimpleComponent | None,
    ) -> IDF:
        """Assigns the constructions to the surfaces in the model.

        Args:
            idf (IDF): The IDF model to select the surfaces from.
            constructions (ZoneConstruction): The construction template.
            window_def (WindowDefinition): The window definition template.

        Returns:
            idf (IDF): The IDF model with the selected surfaces.
        """
        handlers = SurfaceHandlers.Default(
            basement_suffix=self.geometry.basement_suffix
            if self.geometry.basement
            else "NO-OP"
        )
        idf = handlers.handle_envelope(
            idf,
            constructions,
            window_def,
            with_attic=(self.geometry.roof_height or 0) > 0,
            with_basement=self.geometry.basement,
            exposed_basement_frac=self.geometry.exposed_basement_frac,
        )

        return idf

    def build(
        self,
        config: SimulationPathConfig,
        post_geometry_callback: Callable[[IDF], IDF] | None = None,
    ) -> IDF:
        """Build the energy model using the Climate Studio API.

        Args:
            config (SimulationConfig): The configuration for the simulation.
            post_geometry_callback (Callable[[IDF],IDF] | None): A callback to run after the geometry is added.

        Returns:
            idf (IDF): The built energy model.
        """
        config.output_dir.mkdir(parents=True, exist_ok=True)
        base_filepath = EnergyPlusArtifactDir / "Minimal.idf"
        target_base_filepath = config.output_dir / "Minimal.idf"
        shutil.copy(base_filepath, target_base_filepath)
        epw_path, ddy_path = asyncio.run(self.fetch_weather(config.weather_dir))
        output_meters = (
            [
                {
                    "key": "OUTPUT:METER",
                    "Key_Name": meter,
                    "Reporting_Frequency": "Monthly",
                }
                for meter in DESIRED_METERS
            ]
            + [
                {
                    "key": "OUTPUT:METER",
                    "Key_Name": meter,
                    "Reporting_Frequency": "Hourly",
                }
                for meter in DESIRED_METERS
            ]
            + [
                {
                    "key": "OUTPUT:VARIABLE",
                    "Key_Value": "*",
                    "Variable_Name": variable,
                    "Reporting_Frequency": "Hourly",
                }
                for variable in DESIRED_VARIABLES
            ]
        )
        idf = IDF(
            target_base_filepath.as_posix(),
            as_version="22.2",  # pyright: ignore [reportArgumentType]
            prep_outputs=output_meters,  # pyright: ignore [reportArgumentType]
            epw=epw_path.as_posix(),
            output_directory=config.output_dir.as_posix(),
        )
        ddy = IDF(
            ddy_path.as_posix(),
            as_version="22.2",
            file_version="22.2",
            prep_outputs=False,
        )
        ddy_spec = DDYSizingSpec(
            match=False, conditions_types=["Summer Extreme", "Winter Extreme"]
        )
        ddy_spec.inject_ddy(idf, ddy)

        idf = add_default_sim_controls(idf)
        idf, _scheds = add_default_schedules(idf)

        idf = SiteGroundTemperature.FromValues(
            assumed_constants.SiteGroundTemperature_degC
        ).add(idf)

        idf = self.geometry.add(idf)
        if post_geometry_callback is not None:
            idf = post_geometry_callback(idf)

        # construct zone lists
        idf, added_zone_lists = self.add_zone_lists(idf)

        # Handle main zones
        for zone in added_zone_lists.main_zone_list.Names:
            self.Zone.add_to_idf_zone(idf, zone)

        # handle basements
        if self.Basement.UseFraction or self.Basement.Conditioned:
            new_zone_def = self.Zone.model_copy(deep=True)
            frac = self.Basement.UseFraction or 0
            pd = new_zone_def.Operations.SpaceUse.Occupancy.PeopleDensity
            epd = new_zone_def.Operations.SpaceUse.Equipment.PowerDensity
            lpd = new_zone_def.Operations.SpaceUse.Lighting.PowerDensity

            new_zone_def.Operations.SpaceUse.Equipment.PowerDensity = frac * epd
            new_zone_def.Operations.SpaceUse.Lighting.PowerDensity = frac * lpd
            new_zone_def.Operations.SpaceUse.Occupancy.PeopleDensity = frac * pd

            # # handle infiltration for basements, which we are assuming is 0 (or whatever is in assumed constants)
            new_zone_def.Envelope.Infiltration = (
                new_zone_def.Envelope.BasementInfiltration
            )

            if not self.Basement.Conditioned:
                new_zone_def.Operations.HVAC.Ventilation.Provider = "None"
                new_zone_def.Operations.HVAC.ConditioningSystems.Heating = None
                new_zone_def.Operations.HVAC.ConditioningSystems.Cooling = None
            else:
                # TODO: make this configurable!!!!
                print(
                    "WARNING: Basement conditioned, but Cooling disabled due to MASSACHUSETTS ASSUMPTIONS"
                )
                new_zone_def.Operations.HVAC.ConditioningSystems.Cooling = None

            for zone in added_zone_lists.basement_zone_list.Names:
                new_zone_def.add_to_idf_zone(idf, zone)

        if self.Attic.UseFraction or self.Attic.Conditioned:
            new_zone_def = self.Zone.model_copy(deep=True)
            frac = self.Attic.UseFraction or 0
            pd = new_zone_def.Operations.SpaceUse.Occupancy.PeopleDensity
            epd = new_zone_def.Operations.SpaceUse.Equipment.PowerDensity
            lpd = new_zone_def.Operations.SpaceUse.Lighting.PowerDensity

            new_zone_def.Operations.SpaceUse.Equipment.PowerDensity = frac * epd
            new_zone_def.Operations.SpaceUse.Lighting.PowerDensity = frac * lpd
            new_zone_def.Operations.SpaceUse.Occupancy.PeopleDensity = frac * pd

            # handle infiltration for roofs
            # because the *regular* infiltration object is the one that gets added, we simply copy
            # the desired attic infiltration into the relevant section.
            new_zone_def.Envelope.Infiltration = new_zone_def.Envelope.AtticInfiltration

            if not self.Attic.Conditioned:
                new_zone_def.Operations.HVAC.Ventilation.Provider = "None"
                new_zone_def.Operations.HVAC.ConditioningSystems.Heating = None
                new_zone_def.Operations.HVAC.ConditioningSystems.Cooling = None

            # TODO: handle mutating infiltration object when "ventilated attics" are set
            for zone in added_zone_lists.attic_zone_list.Names:
                new_zone_def.add_to_idf_zone(idf, zone)

        idf = self.add_constructions(
            idf, self.Zone.Envelope.Assemblies, self.Zone.Envelope.Window
        )

        # > operations
        # ----> space use
        # --------> lighting, equipment, occupancy to main zones.
        # ------------> special handling for attic, basement according to account for use fractions.
        # --------> water use
        # ------------> special handling for attic, basement according to account for use fractions.
        # ------------> needs information from DHW component
        # ------------> needs to calculate flow rates correctly.
        # --------> Thermostat (Ventilation below)
        # ----> HVAC
        # --------> ConditioningSystems can be effectively ignored, as these are just post-processing.
        # --------> Ventilation
        # ------------> HVACTemplate:IdealLoadsAirSystem + HVACTemplate:Thermostat, + DesignSpecification:OutdoorAir?
        # ------------> Needs to deal with link to thermostat.
        # ----> DHW (see water use above)
        # > envelope
        # ----> facade, roof, ground, floor/celing, partition, [external floor?], [slab], [internal mass]
        # --------> special handling for roof/basement insulation
        # --------> special handling for basement/ground heat transfer
        # ----> infiltration
        # --------> special handling for attic (if ventilated?)/basement (if present)
        # ----> window
        # --------> special handling for operable windows

        # TODO: Handle separately ventilated attic/basement?
        # idf = self.add_space_use(
        #     idf, self.space_use, added_zone_lists.conditioned_zone_list
        # )

        return idf

    # add schedules definition

    # base simulation information
    def simulate(
        self,
        config: SimulationPathConfig,
        post_geometry_callback: Callable[[IDF], IDF] | None = None,
    ) -> tuple[IDF, Sql]:
        """Build and simualte the idf model.

        Args:
            config (SimulationConfig): The configuration for the simulation.
            post_geometry_callback (Callable[[IDF],IDF] | None): A callback to run after the geometry is added.

        Returns:
            idf (IDF): The built energy model.
            sql (Sql): The sql results file with simulation data.
        """
        idf = self.build(config, post_geometry_callback)
        idf.simulate()
        sql = Sql(idf.sql_file)
        return idf, sql

    def get_warnings(self, idf: IDF) -> str:
        """Get the warning text from the idf model.

        Args:
            idf (IDF): The IDF model to get the warning text from.

        Returns:
            str: The warning text.
        """
        err_files = filter(
            lambda x: x.suffix == ".err",
            [idf.output_directory / Path(f) for f in idf.simulation_files],
        )
        err_text = "\n".join([f.read_text() for f in err_files])
        return err_text

    def _process_zone_temperatures(
        self, sql: Sql, temp_config: TemperatureOutputConfig | None = None
    ) -> pd.Series:
        """Process zone temperature data from SQL results.

        Args:
            sql (Sql): The SQL results file.
            temp_config (TemperatureOutputConfig | None): Configuration for temperature output processing.
                If None, defaults to monthly mean temperatures.

        Returns:
            pd.Series: Processed temperature data with MultiIndex (Aggregation, Zone, Month).
        """
        if temp_config is None:
            temp_config = TemperatureOutputConfig()

        _MSG_THRESHOLD_REQUIRED = "threshold required for hours_above_threshold mode"
        _MSG_UNKNOWN_MODE = "Unknown temperature output mode"

        def _raise_threshold_error() -> None:
            """Raise error for missing threshold."""
            raise ValueError(_MSG_THRESHOLD_REQUIRED)

        def _raise_unknown_mode_error(mode: str) -> None:
            """Raise error for unknown temperature mode."""
            msg = f"{_MSG_UNKNOWN_MODE}: {mode}"
            raise ValueError(msg)

        def _raise_unreachable() -> None:
            """Raise error for unreachable code."""
            raise AssertionError("Unreachable")

        try:
            zone_temp_data = sql.timeseries_by_name(DESIRED_VARIABLES, "Hourly")
            if not zone_temp_data.empty:
                zone_temp_df = zone_temp_data.droplevel("IndexGroup", axis=1)
                zone_temp_df.columns = [
                    f"{col[0]} - {col[1]}" if isinstance(col, tuple) else str(col)
                    for col in zone_temp_df.columns
                ]

                if temp_config.mode == "mean":
                    zone_temp_monthly = zone_temp_df.resample("ME").mean()
                    unit = "°C"
                    aggregation_key = "Mean"
                elif temp_config.mode == "hours_above_threshold":
                    # Count hours above threshold for each month
                    threshold = temp_config.threshold
                    if threshold is None:
                        _raise_threshold_error()
                    # Create boolean mask for values above threshold
                    above_threshold = zone_temp_df > threshold
                    # Sum hours per month (True = 1, False = 0)
                    zone_temp_monthly = above_threshold.resample("ME").sum()
                    unit = "hours"
                    aggregation_key = f"HoursAbove{threshold}°C"
                else:
                    _raise_unknown_mode_error(temp_config.mode)
                    return pd.Series()  # pyright: ignore[reportUnreachable]

                zone_temp_monthly.index = pd.RangeIndex(1, 13, 1, name="Month")
                zone_temp_monthly.columns.name = "Zone"
                zone_temp_series = cast(pd.Series, zone_temp_monthly.unstack()).rename(
                    unit
                )
                return pd.concat(
                    [zone_temp_series],
                    keys=[aggregation_key],
                    names=["Aggregation"],
                )
            return pd.Series(
                dtype=float,
                name=temp_config.mode,
                index=pd.MultiIndex.from_tuples(
                    [], names=["Aggregation", "Zone", "Month"]
                ),
            )
        except Exception as e:
            print(f"Warning: Failed to process zone temperatures: {e}")
            return pd.Series(
                dtype=float,
                name=temp_config.mode,
                index=pd.MultiIndex.from_tuples(
                    [], names=["Aggregation", "Zone", "Month"]
                ),
            )

    def _process_energy_data(
        self, raw_monthly: pd.DataFrame, raw_hourly: pd.DataFrame
    ) -> pd.Series:
        """Process energy data including end uses and utilities."""
        ops = self.Zone.Operations
        cond_sys = ops.HVAC.ConditioningSystems
        heat_cop = (
            cond_sys.Heating.effective_system_cop if cond_sys.Heating is not None else 1
        )
        cool_cop = (
            cond_sys.Cooling.effective_system_cop if cond_sys.Cooling is not None else 1
        )
        dhw_cop = ops.DHW.effective_system_cop

        heat_use = (
            raw_monthly["Heating"] / heat_cop
            if "Heating" in raw_monthly
            else (raw_monthly["Lighting"] * 0).rename("Heating")
        )
        cool_use = (
            raw_monthly["Cooling"] / cool_cop
            if "Cooling" in raw_monthly
            else (raw_monthly["Lighting"] * 0).rename("Cooling")
        )
        dhw_use = (
            raw_monthly["Domestic Hot Water"] / dhw_cop
            if "Domestic Hot Water" in raw_monthly
            else (raw_monthly["Lighting"] * 0).rename("Domestic Hot Water")
        )
        lighting_use = raw_monthly["Lighting"]
        equipment_use = raw_monthly["Equipment"]
        end_use_df = pd.concat(
            [lighting_use, equipment_use, heat_use, cool_use, dhw_use], axis=1
        )

        heat_fuel = cond_sys.Heating.Fuel if cond_sys.Heating is not None else None
        cool_fuel = cond_sys.Cooling.Fuel if cond_sys.Cooling is not None else None
        dhw_fuel = ops.DHW.FuelType
        all_fuels = {*FuelType.__args__, *DHWFuelType.__args__}
        utilities_df = pd.DataFrame(
            index=pd.RangeIndex(1, 13, 1, name="Month"),
            columns=sorted(all_fuels),
            dtype=float,
            data=np.zeros((12, len(all_fuels))),
        )
        utilities_df["Electricity"] = lighting_use + equipment_use
        if heat_fuel is not None:
            utilities_df[heat_fuel] += heat_use
        if cool_fuel is not None:
            utilities_df[cool_fuel] += cool_use
        utilities_df[dhw_fuel] += dhw_use

        if not np.allclose(utilities_df.sum().sum(), end_use_df.sum().sum()):
            msg = "Utilities df and end use df do not sum to the same value!"
            raise ValueError(msg)

        energy_dfs = (
            pd.concat(
                [raw_monthly, end_use_df, utilities_df],
                axis=1,
                keys=["Raw", "End Uses", "Utilities"],
                names=["Aggregation", "Meter"],
            )
            .unstack()
            .fillna(0)
        )
        return cast(pd.Series, energy_dfs).rename("kWh/m2")

    def _process_peak_data(
        self, raw_hourly: pd.DataFrame, raw_hourly_max: pd.Series
    ) -> pd.Series:
        """Process peak demand data."""
        ops = self.Zone.Operations
        cond_sys = ops.HVAC.ConditioningSystems
        heat_cop = (
            cond_sys.Heating.effective_system_cop if cond_sys.Heating is not None else 1
        )
        cool_cop = (
            cond_sys.Cooling.effective_system_cop if cond_sys.Cooling is not None else 1
        )
        dhw_cop = ops.DHW.effective_system_cop

        heat_use_hourly = (
            (raw_hourly["Heating"] / heat_cop)
            if "Heating" in raw_hourly
            else (raw_hourly["Lighting"] * 0).rename("Heating")
        )
        cool_use_hourly = (
            (raw_hourly["Cooling"] / cool_cop)
            if "Cooling" in raw_hourly
            else (raw_hourly["Lighting"] * 0).rename("Cooling")
        )
        dhw_use_hourly = (
            (raw_hourly["Domestic Hot Water"] / dhw_cop)
            if "Domestic Hot Water" in raw_hourly
            else (raw_hourly["Lighting"] * 0).rename("Domestic Hot Water")
        )
        lighting_use_hourly = raw_hourly["Lighting"]
        equipment_use_hourly = raw_hourly["Equipment"]

        end_use_df_hourly = pd.concat(
            [
                lighting_use_hourly,
                equipment_use_hourly,
                heat_use_hourly,
                cool_use_hourly,
                dhw_use_hourly,
            ],
            axis=1,
        )

        heat_fuel = cond_sys.Heating.Fuel if cond_sys.Heating is not None else None
        cool_fuel = cond_sys.Cooling.Fuel if cond_sys.Cooling is not None else None
        dhw_fuel = ops.DHW.FuelType
        all_fuels = {*FuelType.__args__, *DHWFuelType.__args__}
        utilities_df_hourly = pd.DataFrame(
            index=raw_hourly.index,
            columns=sorted(all_fuels),
            dtype=float,
            data=np.zeros((len(raw_hourly), len(all_fuels))),
        )
        utilities_df_hourly["Electricity"] = lighting_use_hourly + equipment_use_hourly
        if heat_fuel is not None:
            utilities_df_hourly[heat_fuel] += heat_use_hourly
        if cool_fuel is not None:
            utilities_df_hourly[cool_fuel] += cool_use_hourly
        utilities_df_hourly[dhw_fuel] += dhw_use_hourly

        if not np.allclose(
            utilities_df_hourly.sum().sum(), end_use_df_hourly.sum().sum()
        ):
            msg = "Utilities df and end use df do not sum to the same value!"
            raise ValueError(msg)

        utility_max = utilities_df_hourly.max()
        utility_monthly_hourly_max = utilities_df_hourly.resample("ME").max()
        utility_max.index.name = "Meter"
        raw_monthly_hourly_max = raw_hourly.resample("ME").max()

        max_data = pd.concat(
            [utility_max, raw_hourly_max],
            axis=0,
            keys=["Utilities", "Raw"],
            names=["Aggregation", "Meter"],
        ).fillna(0)
        max_data = cast(pd.Series, max_data).rename("kW/m2")

        utility_monthly_hourly_max.index = pd.RangeIndex(1, 13, 1, name="Month")
        raw_monthly_hourly_max.index = pd.RangeIndex(1, 13, 1, name="Month")
        max_data_monthly = pd.concat(
            [utility_monthly_hourly_max, raw_monthly_hourly_max],
            axis=1,
            keys=["Utilities", "Raw"],
            names=["Aggregation"],
        ).fillna(0)

        return cast(pd.Series, max_data_monthly.unstack()).fillna(0).rename("kW/m2")

    def standard_results_postprocess(
        self, sql: Sql, temp_config: TemperatureOutputConfig | None = None
    ) -> pd.Series:
        """Postprocess the sql file to get the standard results.

        This will return a series with three levels:
        - Measurement: "Energy", "Peak", "Temperature"
        - Aggregation: "Raw", "End Uses", "Utilities" (for Energy/Peak), "Mean" or "HoursAboveX°C" (for Temperature)
        - Meter/Zone: ["Electricity", "Cooling", "Heating", "Domestic Hot Water"], ["Electricity", "Propane", ...], or zone names (for Temperature)

        Args:
            sql (Sql): The sql file to postprocess.
            temp_config (TemperatureOutputConfig | None): Configuration for temperature output processing.
                If None, defaults to monthly mean temperatures.

        Returns:
            series (pd.Series): The postprocessed results.
        """
        raw_hourly = sql.timeseries_by_name(DESIRED_METERS, "Hourly")
        raw_monthly = sql.timeseries_by_name(DESIRED_METERS, "Monthly")
        zone_temp_series = self._process_zone_temperatures(sql, temp_config)

        raw_df = sql.tabular_data_by_name(
            "AnnualBuildingUtilityPerformanceSummary", "End Uses"
        )
        kWh_per_GJ = 277.778
        GJ_per_J = 1e-9
        normalizing_floor_area = self.total_conditioned_area

        raw_df_relevant = (
            raw_df[
                [
                    "Electricity",
                    "District Cooling",
                    "District Heating",
                ]
            ].droplevel(-1, axis=1)
            * kWh_per_GJ
        ) / normalizing_floor_area
        raw_df_others = raw_df.drop(
            columns=["Electricity", "District Cooling", "District Heating", "Water"]
        )
        if not np.allclose(raw_df_others.sum().sum(), 0):
            cols = raw_df_others.sum(axis=0)
            cols = cols[cols > 0].index.tolist()
            rows = raw_df_others.sum(axis=1)
            rows = rows[rows > 0].index.tolist()
            msg = (
                "There are end uses/fuels which are not accounted for in the standard postprocessing: "
                + ", ".join(rows)
                + " and "
                + ", ".join(cols)
            )
            raise ValueError(msg)
        raw_series_hot_water = raw_df_relevant.loc["Water Systems"]
        raw_series = raw_df_relevant.loc["Total End Uses"] - raw_series_hot_water
        raw_series["Domestic Hot Water"] = raw_series_hot_water.sum()

        raw_monthly = (
            (
                raw_monthly.droplevel(["IndexGroup", "KeyValue"], axis=1)
                * GJ_per_J
                * kWh_per_GJ
                / normalizing_floor_area
            )
            .rename(
                columns={
                    "InteriorLights:Electricity": "Lighting",
                    "InteriorEquipment:Electricity": "Equipment",
                    "Heating:DistrictHeating": "Heating",
                    "Cooling:DistrictCooling": "Cooling",
                    "WaterSystems:DistrictHeating": "Domestic Hot Water",
                }
            )
            .set_index(pd.RangeIndex(1, 13, 1, name="Month"))
        )
        raw_monthly.columns.name = "Meter"

        if not np.allclose(raw_series.sum(), raw_monthly.sum().sum(), atol=0.5):
            msg = "Raw series and raw monthly do not match: "
            msg += f"Raw series: {raw_series.sum()}"
            msg += f"Raw monthly: {raw_monthly.sum().sum()}"
            raise ValueError(msg)

        raw_hourly = (
            (raw_hourly.droplevel(["IndexGroup", "KeyValue"], axis=1))
            * GJ_per_J
            * kWh_per_GJ
            / normalizing_floor_area
        ).rename(
            columns={
                "InteriorLights:Electricity": "Lighting",
                "InteriorEquipment:Electricity": "Equipment",
                "Heating:DistrictHeating": "Heating",
                "Cooling:DistrictCooling": "Cooling",
                "WaterSystems:DistrictHeating": "Domestic Hot Water",
            }
        )
        raw_hourly.columns.name = "Meter"
        raw_hourly_max: pd.Series = raw_hourly.max(axis=0)

        energy_series = self._process_energy_data(raw_monthly, raw_hourly)
        peaks_series = self._process_peak_data(raw_hourly, raw_hourly_max)

        all_data = pd.concat(
            [energy_series, peaks_series, zone_temp_series],
            keys=["Energy", "Peak", "Temperature"],
            names=["Measurement"],
        )

        return all_data

    def extract_zone_temperatures_to_csv(
        self, sql: Sql, output_dir: Path
    ) -> Path | None:
        """Extract zone mean air temperatures and outdoor air temperature, and save to CSV.

        Args:
            sql (Sql): The SQL results file with simulation data.
            output_dir (Path): The directory to save the CSV file.

        Returns:
            csv_path (Path | None): The path to the saved CSV file, or None if extraction failed.
        """
        csv_path = output_dir / "zone_temperatures.csv"
        try:
            # Extract zone temperature data from SQL
            zone_temp_data = sql.timeseries_by_name(DESIRED_VARIABLES, "Hourly")

            # Check if we got any data
            if zone_temp_data.empty:
                print(
                    f"Warning: No zone temperature data found for variables: {DESIRED_VARIABLES}"
                )
                return None

            # Debug: print what zones we found
            if zone_temp_data.columns.nlevels > 1:
                zone_names = zone_temp_data.columns.get_level_values(
                    "KeyValue"
                ).unique()
                print(f"Found {len(zone_names)} zones in SQL results:")
                for zone in sorted(zone_names):
                    print(f"  - {zone}")

            zone_temp_df = zone_temp_data.droplevel("IndexGroup", axis=1)
            zone_temp_df.columns = [
                f"{col[0]} - {col[1]}" if isinstance(col, tuple) else str(col)
                for col in zone_temp_df.columns
            ]
            zone_temp_df = zone_temp_df.reset_index()
            # Ensure we overwrite any existing file
            if csv_path.exists():
                csv_path.unlink()
            zone_temp_df.to_csv(csv_path, index=False)
            print(f"Zone temperatures and outdoor air temperature saved to: {csv_path}")
            print(
                f"  Found {len(zone_temp_df.columns) - 1} zone variables (excluding index)"
            )
            print(
                f"  Zones: {[col for col in zone_temp_df.columns if 'Zone Mean Air Temperature' in col]}"
            )
        except Exception as e:
            print(f"Warning: Failed to extract zone temperatures to CSV: {e}")
            return None
        else:
            return csv_path

    def run(
        self,
        weather_dir: Path | None = None,
        post_geometry_callback: Callable[[IDF], IDF] | None = None,
        temp_config: TemperatureOutputConfig | None = None,
    ) -> tuple[IDF, pd.Series, str, Sql]:
        """Build and simualte the idf model.

        Args:
            weather_dir (Path): The directory to store the weather files.
            post_geometry_callback (Callable[[IDF],IDF] | None): A callback to run after the geometry is added.
            temp_config (TemperatureOutputConfig | None): Configuration for temperature output processing.
                If None, defaults to monthly mean temperatures.

        Returns:
            idf (IDF): The built energy model.
            results (pd.Series): The postprocessed results including energy, peak, and temperature data.
            err_text (str): The warning text.
            sql (Sql): The SQL results file with simulation data.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            config = (
                SimulationPathConfig(
                    output_dir=output_dir,
                    weather_dir=weather_dir,
                )
                if weather_dir is not None
                else SimulationPathConfig(output_dir=output_dir)
            )

            idf, sql = self.simulate(
                config,
                post_geometry_callback=post_geometry_callback,
            )
            results = self.standard_results_postprocess(sql, temp_config)
            err_text = self.get_warnings(idf)

            # Extract CSV while SQL file is still accessible (before temp dir cleanup)
            # Use a persistent location for CSV output
            csv_output_dir = Path.cwd()
            self.extract_zone_temperatures_to_csv(sql, csv_output_dir)

            gc.collect()
            return idf, results, err_text, sql


if __name__ == "__main__":
    import yaml

    from epinterface.sbem.components.composer import (
        construct_composer_model,
        construct_graph,
    )
    from epinterface.sbem.prisma.client import PrismaSettings

    with tempfile.TemporaryDirectory() as temp_dir:
        database_path = Path("/Users/daryaguettler/globi/data/Brazil/components-lib.db")
        component_map_path = Path(
            "/Users/daryaguettler/globi/data/Brazil/component-map.yaml"
        )
        settings = PrismaSettings(
            database_path=database_path,
            auto_register=False,
        )
        g = construct_graph(ZoneComponent)
        SelectorModel = construct_composer_model(
            g,
            ZoneComponent,
            use_children=False,
        )

        with open(component_map_path) as f:
            component_map_yaml = yaml.safe_load(f)
        selector = SelectorModel.model_validate(component_map_yaml)
        db = settings.db
        context = {
            "region": "SP",
            "income": "Low",
            "typology": "Residential",
            "scenario": "withAC",
        }
        with settings.db:
            zone = cast(ZoneComponent, selector.get_component(context=context, db=db))

        model = Model(
            Weather=(
                "https://climate.onebuilding.org/WMO_Region_3_South_America/BRA_Brazil/SP_Sao_Paulo/BRA_SP_Guaratingueta.AP.837080_TMYx.2009-2023.zip"
            ),  # pyright: ignore [reportArgumentType]
            Zone=zone,
            Attic=AtticAssumptions(
                Conditioned=False,
                UseFraction=None,
            ),
            Basement=BasementAssumptions(
                Conditioned=False,
                UseFraction=None,
            ),
            geometry=ShoeboxGeometry(
                x=0,
                y=0,
                w=20,
                d=20,
                h=3,
                wwr=0.3,
                num_stories=3,
                basement=False,
                zoning="by_storey",
                roof_height=None,
                exposed_basement_frac=0.25,
            ),
        )

        # post_geometry_callback = lambda x: x.saveas("notebooks/badgeo.idf")

        # Example 1: Default behavior - monthly mean temperatures
        _idf, results, _err_text, _sql = model.run(
            # post_geometry_callback=post_geometry_callback,
        )

        # Example 2: Hours above threshold (e.g., 26°C for comfort analysis)
        # temp_config = TemperatureOutputConfig(mode="hours_above_threshold", threshold=26.0)
        # _idf, results, _err_text, _sql = model.run(temp_config=temp_config)
        # Note: CSV extraction is now done inside run() method
        # _idf.saveas("test-out.idf")
        print(_err_text)
        print(results)

        # print zone temperature results
        # Access MultiIndex Series using .loc[] instead of attribute notation
        if "Temperature" in results.index.get_level_values("Measurement"):
            zone_temp_results = results.loc["Temperature"]
            print("Zone Temperature Results:")
            print(zone_temp_results)
        else:
            print("No temperature data found in results")
            print(
                f"Available measurements: {results.index.get_level_values('Measurement').unique().tolist()}"
            )

        # Group by Meter (first level of the Energy.Raw MultiIndex)
        energy_raw = results.loc["Energy"].loc["Raw"]
        print("Energy Raw Results:")
        print(energy_raw.groupby(level=0).sum())
