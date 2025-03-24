"""A module for building the energy model using the SBEM template library approach."""

import asyncio
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
from pydantic import BaseModel, Field, model_validator

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
from epinterface.sbem.exceptions import (
    NotImplementedParameter,
    SBEMBuilderNotImplementedError,
)
from epinterface.weather import BaseWeather

DESIRED_METERS = (
    "InteriorEquipment:Electricity",
    "InteriorLights:Electricity",
    "Heating:DistrictHeating",
    "Cooling:DistrictCooling",
    "WaterSystems:DistrictHeating",
)


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


AtticInsulationSurfaceOption = Literal["roof", "floor", None]
BasementInsulationSurfaceOption = Literal["walls", "ceiling", None]


class SurfaceHandler(BaseModel):
    """A handler for filtering and adding surfaces to a model."""

    boundary_condition: str | None
    original_construction_name: str | None
    original_surface_type: str | None
    surface_group: Literal["glazing", "opaque", "internal_mass"]

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


class SurfaceHandlers(BaseModel):
    """A collection of surface handlers for different surface types."""

    Roof: SurfaceHandler
    Facade: SurfaceHandler
    Slab: SurfaceHandler
    Ceiling: SurfaceHandler
    Partition: SurfaceHandler
    InternalMass: SurfaceHandler
    GroundSlab: SurfaceHandler
    GroundWall: SurfaceHandler
    Window: SurfaceHandler

    @classmethod
    def Default(cls):
        """Get the default surface handlers."""
        roof_handler = SurfaceHandler(
            boundary_condition="outdoors",
            original_construction_name=None,
            original_surface_type="roof",
            surface_group="opaque",
        )
        facade_handler = SurfaceHandler(
            boundary_condition="outdoors",
            original_construction_name=None,
            original_surface_type="wall",
            surface_group="opaque",
        )
        partition_handler = SurfaceHandler(
            boundary_condition="surface",
            original_construction_name=None,
            original_surface_type="wall",
            surface_group="opaque",
        )
        ground_wall_handler = SurfaceHandler(
            boundary_condition="ground",
            original_construction_name=None,
            original_surface_type="wall",
            surface_group="opaque",
        )
        slab_handler = SurfaceHandler(
            boundary_condition="surface",
            original_construction_name=None,
            original_surface_type="floor",
            surface_group="opaque",
        )
        ceiling_handler = SurfaceHandler(
            boundary_condition="surface",
            original_construction_name=None,
            original_surface_type="ceiling",
            surface_group="opaque",
        )
        ground_slab_handler = SurfaceHandler(
            boundary_condition="ground",
            original_construction_name=None,
            original_surface_type="floor",
            surface_group="opaque",
        )
        window_handler = SurfaceHandler(
            boundary_condition=None,
            original_construction_name=None,
            original_surface_type=None,
            surface_group="glazing",
        )

        internal_mass_handler = SurfaceHandler(
            boundary_condition=None,
            original_construction_name=None,
            original_surface_type=None,
            surface_group="internal_mass",
        )

        return cls(
            Roof=roof_handler,
            Facade=facade_handler,
            Slab=slab_handler,
            Ceiling=ceiling_handler,
            Partition=partition_handler,
            InternalMass=internal_mass_handler,
            GroundSlab=ground_slab_handler,
            GroundWall=ground_wall_handler,
            Window=window_handler,
        )

    def handle_envelope(
        self,
        idf: IDF,
        constructions: EnvelopeAssemblyComponent,
        window: GlazingConstructionSimpleComponent | None,
    ):
        """Assign the envelope to the IDF model.

        Note that this will add a "reversed" construction for the floorsystem slab/ceiling

        Args:
            idf (IDF): The IDF model to add the envelope to.
            constructions (ZoneConstruction): The construction names for the envelope.
            window (GlazingConstructionSimpleComponent | None): The window definition.

        Returns:
            idf (IDF): The updated IDF model.
        """
        # outside walls are the ones with outdoor boundary condition and vertical orientation
        # def make_reversed(const: ConstructionAssemblyComponent):
        #     new_const = const.model_copy(deep=True)
        #     sorted_layers = sorted(new_const.Layers, key=lambda x: x.LayerOrder)
        #     for i, layer in enumerate(sorted_layers[::-1]):
        #         layer.LayerOrder = i
        #     resorted_layers = sorted(sorted_layers, key=lambda x: x.LayerOrder)
        #     new_const.Layers = resorted_layers
        #     new_const.Name = f"{const.Name}_Reversed"
        #     return new_const

        slab_reversed = constructions.SlabAssembly.reversed

        idf = self.Roof.assign_constructions_to_objs(
            idf=idf, construction=constructions.RoofAssembly
        )
        idf = self.Facade.assign_constructions_to_objs(
            idf=idf, construction=constructions.FacadeAssembly
        )
        idf = self.Partition.assign_constructions_to_objs(
            idf=idf, construction=constructions.PartitionAssembly
        )
        idf = self.Slab.assign_constructions_to_objs(
            idf=idf, construction=slab_reversed
        )
        idf = self.Ceiling.assign_constructions_to_objs(
            idf=idf, construction=constructions.SlabAssembly
        )
        idf = self.GroundSlab.assign_constructions_to_objs(
            idf=idf, construction=constructions.GroundSlabAssembly
        )
        idf = self.GroundWall.assign_constructions_to_objs(
            idf=idf, construction=constructions.GroundWallAssembly
        )
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


class Model(BaseWeather, validate_assignment=True):
    """A simple model constructor for the IDF model.

    Creates geometry as well as zone definitions.
    """

    geometry: ShoeboxGeometry
    attic_insulation_surface: AtticInsulationSurfaceOption
    # TODO: should we have another field for whether or not the attic is ventilated, i.e. high infiltration?
    conditioned_attic: bool
    attic_use_fraction: float | None = Field(..., ge=0, le=1)
    basement_use_fraction: float | None = Field(..., ge=0, le=1)
    conditioned_basement: bool
    basement_insulation_surface: BasementInsulationSurfaceOption
    Zone: ZoneComponent

    @property
    def total_conditioned_area(self) -> float:
        """The total conditioned area of the model.

        Returns:
            area (float): The total conditioned area of the model.
        """
        conditioned_area = self.geometry.total_living_area
        if self.geometry.basement and self.conditioned_basement:
            conditioned_area += self.geometry.footprint_area
        if self.geometry.roof_height and self.conditioned_attic:
            conditioned_area += self.geometry.footprint_area
        return conditioned_area

    @property
    def total_people(self) -> float:
        """The total number of people in the model.

        Returns:
            ppl (float): The total number of people in the model

        """
        ppl_per_m2 = (
            self.Zone.Operations.SpaceUse.Occupancy.PeopleDensity
            if self.Zone.Operations.SpaceUse.Occupancy.IsOn
            else 0
        )
        total_area = self.total_conditioned_area
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
        if (
            self.attic_insulation_surface == "roof"
            and self.geometry.roof_height is None
        ):
            msg = "Cannot have roof-surface insulation if there is no roof height."
            raise ValueError(msg)

        if self.conditioned_attic and self.geometry.roof_height is None:
            msg = "Cannot have a conditioned attic if there is no roof height."
            raise ValueError(msg)

        if self.attic_use_fraction and self.geometry.roof_height is None:
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
        if self.basement_insulation_surface is not None and not self.geometry.basement:
            msg = "Cannot have basement walls/ceiling insulated if there is no basement in self.geometry."
            raise ValueError(msg)

        if self.conditioned_basement and not self.geometry.basement:
            msg = "Cannot have a conditioned basement if there is no basement in self.geometry."
            raise ValueError(msg)

        if self.basement_use_fraction and not self.geometry.basement:
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
                (is_attic and self.conditioned_attic)
                or (is_basement and self.conditioned_basement)
                or is_normal_zone
            )
            should_be_occupied = (
                (is_attic and self.attic_use_fraction is not None)
                or (is_basement and self.basement_use_fraction is not None)
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
            1 if self.conditioned_basement else 0
        )
        zones_per_storey = self.geometry.zones_per_storey
        expected_zone_count = conditioned_storey_count * zones_per_storey + (
            1 if self.conditioned_attic else 0
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
        if self.geometry.roof_height:
            raise SBEMBuilderNotImplementedError("roof_height")
        if self.geometry.basement:
            raise SBEMBuilderNotImplementedError("basement")

        if (
            constructions.FacadeIsAdiabatic
            or constructions.RoofIsAdiabatic
            or constructions.GroundIsAdiabatic
            or constructions.PartitionIsAdiabatic
            or constructions.SlabIsAdiabatic
        ):
            raise SBEMBuilderNotImplementedError("_IsAdiabatic")

        # if constructions.InternalMassAssembly is not None:
        #     raise SBEMBuilderNotImplementedError("InternalMassAssembly")

        handlers = SurfaceHandlers.Default()
        idf = handlers.handle_envelope(idf, constructions, window_def)

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
        if self.geometry.roof_height:
            raise SBEMBuilderNotImplementedError("roof_height")
        config.output_dir.mkdir(parents=True, exist_ok=True)
        base_filepath = EnergyPlusArtifactDir / "Minimal.idf"
        target_base_filepath = config.output_dir / "Minimal.idf"
        shutil.copy(base_filepath, target_base_filepath)
        epw_path, ddy_path = asyncio.run(self.fetch_weather(config.weather_dir))
        output_meters = [
            {"key": "OUTPUT:METER", "Key_Name": meter, "Reporting_Frequency": "Monthly"}
            for meter in DESIRED_METERS
        ]
        idf = IDF(
            target_base_filepath.as_posix(),
            as_version=None,  # pyright: ignore [reportArgumentType]
            prep_outputs=output_meters,  # pyright: ignore [reportArgumentType]
            epw=epw_path.as_posix(),
            output_directory=config.output_dir.as_posix(),
        )
        ddy = IDF(
            ddy_path.as_posix(),
            as_version="9.2.0",
            file_version="9.2.0",
            prep_outputs=False,
        )
        ddy_spec = DDYSizingSpec(
            match=False, conditions_types=["Summer Extreme", "Winter Extreme"]
        )
        ddy_spec.inject_ddy(idf, ddy)

        idf = add_default_sim_controls(idf)
        idf, scheds = add_default_schedules(idf)

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

        # TODO: Handle Basements:
        # TODO: Handle Attic:

        idf = self.add_constructions(
            idf, self.Zone.Envelope.Assemblies, self.Zone.Envelope.Window
        )
        # self.add_infiltration(idf, infiltration, inf_zone_list)

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

    def standard_results_postprocess(self, sql: Sql) -> pd.Series:
        """Postprocess the sql file to get the standard results.

        This will return a series with two levels:
        - Aggregation: "Raw", "End Uses", "Utilities"
        - Meter: ["Electricity", "Cooling", "Heating", "Domestic Hot Water"], ["Electricity", "Propane", ...]

        Args:
            sql (Sql): The sql file to postprocess.

        Returns:
            series (pd.Series): The postprocessed results.
        """
        raw_monthly = sql.timeseries_by_name(DESIRED_METERS, "Monthly")
        # TODO: get peaks
        raw_df = sql.tabular_data_by_name(
            "AnnualBuildingUtilityPerformanceSummary", "End Uses"
        )
        kWh_per_GJ = 277.778
        GJ_per_J = 1e-9
        normalizing_floor_area = self.total_conditioned_area

        raw_df = (
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
            columns=["Electricity", "District Cooling", "District Heating"]
        )
        print(raw_df_others.sum())
        print(raw_df_others)

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

        raw_series_hot_water = raw_df.loc["Water Systems"]
        raw_series = raw_df.loc["Total End Uses"] - raw_series_hot_water
        raw_series["Domestic Hot Water"] = raw_series_hot_water.sum()
        if not np.allclose(raw_series.sum(), raw_monthly.sum().sum()):
            msg = "Raw series and raw monthly do not match"
            raise ValueError(msg)

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

        dfs = pd.concat(
            [raw_monthly, end_use_df, utilities_df],
            axis=1,
            keys=["Raw", "End Uses", "Utilities"],
            names=["Aggregation", "Meter"],
        ).unstack()

        return cast(pd.Series, dfs.fillna(0)).rename("kWh/m2")

    def run(
        self,
        weather_dir: Path | None = None,
        post_geometry_callback: Callable[[IDF], IDF] | None = None,
    ) -> tuple[IDF, pd.Series, str]:
        """Build and simualte the idf model.

        Args:
            weather_dir (Path): The directory to store the weather files.
            post_geometry_callback (Callable[[IDF],IDF] | None): A callback to run after the geometry is added.

        Returns:
            idf (IDF): The built energy model.
            results (dict[str, pd.Series]): The postprocessed results.
            err_text (str): The warning text.
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
            results = self.standard_results_postprocess(sql)
            err_text = self.get_warnings(idf)
            return idf, results, err_text


if __name__ == "__main__":
    from epinterface.sbem.prisma.client import PrismaSettings, deep_fetcher
    from epinterface.sbem.prisma.seed_fns import (
        create_dhw_systems,
        create_envelope,
        create_hvac_systems,
        create_operations,
        create_schedules,
        create_space_use_children,
        create_zone,
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "test.db"
        settings = PrismaSettings.New(
            database_path=database_path, if_exists="raise", auto_register=False
        )
        with settings.db:
            create_schedules(settings.db)
            last_space_use_name = create_space_use_children(settings.db)
            last_hvac_name = create_hvac_systems(settings.db)
            last_dhw_name = create_dhw_systems(settings.db)
            _last_ops_name = create_operations(
                settings.db, last_space_use_name, last_hvac_name, last_dhw_name
            )

            create_envelope(settings.db)
            create_zone(settings.db)

            _, zone = deep_fetcher.Zone.get_deep_object("default_zone", settings.db)

            model = Model(
                Weather=(
                    "https://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/USA_United_States_of_America/MA_Massachusetts/USA_MA_Boston-Logan.Intl.AP.725090_TMYx.2009-2023.zip"
                ),  # pyright: ignore [reportArgumentType]
                Zone=zone,
                basement_insulation_surface=None,
                conditioned_basement=False,
                basement_use_fraction=None,
                attic_insulation_surface=None,
                conditioned_attic=False,
                attic_use_fraction=None,
                geometry=ShoeboxGeometry(
                    x=0,
                    y=0,
                    w=10,
                    d=10,
                    h=3,
                    wwr=0.2,
                    num_stories=2,
                    basement=False,
                    zoning="by_storey",
                    roof_height=None,
                ),
            )

            _idf, results, _err_text = model.run()
            print(_err_text)
            print(results)
