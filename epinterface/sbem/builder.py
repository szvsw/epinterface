"""A module for building the energy model using the SBEM template library approach."""

import asyncio
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Literal, cast
from uuid import uuid4

import pandas as pd
from archetypal.idfclass import IDF
from archetypal.idfclass.sql import Sql
from pydantic import BaseModel, Field, model_validator
from shapely import Polygon

from epinterface.constants import assumed_constants, physical_constants
from epinterface.data import EnergyPlusArtifactDir
from epinterface.ddy_injector_bayes import DDYSizingSpec
from epinterface.geometry import ShoeboxGeometry
from epinterface.interface import (
    SiteGroundTemperature,
    ZoneList,
    add_default_schedules,
    add_default_sim_controls,
)
from epinterface.sbem.components import (
    ConstructionAssemblyComponent,
    EnvelopeAssemblyComponent,
    GlazingConstructionSimpleComponent,
    InfiltrationComponent,
    ZoneEnvelopeComponent,
    ZoneOperationsComponent,
)
from epinterface.sbem.exceptions import (
    NotImplementedParameter,
    SBEMBuilderNotImplementedError,
)
from epinterface.sbem.interface import ComponentLibrary
from epinterface.weather import BaseWeather


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
    surface_group: Literal["glazing", "opaque"]

    def assign_srfs(
        self, idf: IDF, lib: ComponentLibrary, construction_name: str
    ) -> IDF:
        """Adds a construction (and its materials) to an IDF and assigns it to matching surfaces.

        Args:
            idf (IDF): The IDF model to add the construction to.
            lib (ClimateStudioLibraryV2): The library of constructions.
            construction_name (str): The name of the construction to add.
        """
        raise NotImplementedError
        srf_key = (
            "FENESTRATIONSURFACE:DETAILED"
            if self.surface_group == "glazing"
            else "BUILDINGSURFACE:DETAILED"
        )
        if self.boundary_condition is not None and self.surface_group == "glazing":
            raise NotImplementedParameter(
                "BoundaryCondition", self.surface_group, "Glazing"
            )

        srfs = [srf for srf in idf.idfobjects[srf_key] if self.check_srf(srf)]
        construction_lib = (
            lib.OpaqueConstructions
            if self.surface_group != "glazing"
            else lib.GlazingConstructionSimple
        )
        if construction_name not in construction_lib:
            raise KeyError(
                f"MISSING_CONSTRUCTION:{construction_name}:TARGET={self.__repr__()}"
            )
        construction = construction_lib[construction_name]
        idf = (
            construction.add_to_idf(idf)
            if isinstance(construction, GlazingConstructionSimpleComponent)
            else construction.add_to_idf(idf, lib.ConstructionMaterial)
        )
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

        return cls(
            Roof=roof_handler,
            Facade=facade_handler,
            Slab=slab_handler,
            Ceiling=ceiling_handler,
            Partition=partition_handler,
            GroundSlab=ground_slab_handler,
            GroundWall=ground_wall_handler,
            Window=window_handler,
        )

    def handle_envelope(
        self,
        idf: IDF,
        lib: ComponentLibrary,
        constructions: EnvelopeAssemblyComponent,
        window: GlazingConstructionSimpleComponent | None,
    ):
        """Assign the envelope to the IDF model.

        Note that this will add a "reversed" construction for the floorsystem slab/ceiling

        Args:
            idf (IDF): The IDF model to add the envelope to.
            lib (ClimateStudioLibraryV2): The library of constructions.
            constructions (ZoneConstruction): The construction names for the envelope.
            window (GlazingConstructionSimpleComponent | None): The window definition.

        Returns:
            idf (IDF): The updated IDF model.
        """

        # outside walls are the ones with outdoor boundary condition and vertical orientation
        def make_reversed(const: ConstructionAssemblyComponent):
            new_const = const.model_copy(deep=True)
            new_const.Layers = new_const.Layers[::-1]
            new_const.Name = f"{const.Name}_Reversed"
            return new_const

        raise NotImplementedError

        def reverse_construction(const_name: str, lib: ComponentLibrary):
            const = lib.ConstructionAssembly[const_name]
            new_const = make_reversed(const)
            return new_const

        slab_reversed = reverse_construction(constructions.SlabAssembly, lib)
        lib.ConstructionAssembly[slab_reversed.Name] = slab_reversed

        idf = self.Roof.assign_srfs(
            idf=idf, lib=lib, construction_name=constructions.RoofAssembly
        )
        idf = self.Facade.assign_srfs(
            idf=idf, lib=lib, construction_name=constructions.FacadeAssembly
        )
        idf = self.Partition.assign_srfs(
            idf=idf, lib=lib, construction_name=constructions.PartitionAssembly
        )
        idf = self.Slab.assign_srfs(
            idf=idf, lib=lib, construction_name=slab_reversed.Name
        )
        idf = self.Ceiling.assign_srfs(
            idf=idf, lib=lib, construction_name=constructions.SlabAssembly
        )
        idf = self.GroundSlab.assign_srfs(
            idf=idf, lib=lib, construction_name=constructions.GroundSlabAssembly
        )
        idf = self.GroundWall.assign_srfs(
            idf=idf, lib=lib, construction_name=constructions.GroundWallAssembly
        )
        if window:
            idf = self.Window.assign_srfs(
                idf=idf, lib=lib, construction_name=window.Name
            )
        return idf


class Model(BaseWeather, validate_assignment=True):
    """A simple model constructor for the IDF model.

    Creates geometry as well as zone definitions.
    """

    geometry: ShoeboxGeometry
    attic_insulation_surface: AtticInsulationSurfaceOption
    conditioned_attic: bool
    attic_use_fraction: float | None = Field(..., ge=0, le=1)
    operations: ZoneOperationsComponent
    envelope: ZoneEnvelopeComponent
    basement_use_fraction: float | None = Field(..., ge=0, le=1)
    conditioned_basement: bool
    basement_insulation_surface: BasementInsulationSurfaceOption
    lib: ComponentLibrary

    @property
    def total_conditioned_area(self) -> float:
        """The total conditioned area of the model.

        Returns:
            float: The total conditioned area of the model.
        """
        return self.geometry.total_living_area + (
            self.geometry.footprint_area
            if (self.geometry.basement and self.conditioned_basement)
            | (self.conditioned_attic)
            else 0
        )

    @property
    def total_people(self) -> float:
        """The total number of people in the model.

        Returns:
            ppl (float): The total number of people in the model

        """
        ppl_per_m2 = (
            self.operations.SpaceUse.Occupancy.OccupancyDensity
            if self.operations.SpaceUse.Occupancy.PeopleIsOn
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
    ):
        """Add the zone lists to the IDF model.

        Note that this attempts to automatically determine
        the zones from the IDF model which are conditioned
        as well as a separate list for all zones.

        Args:
            idf (IDF): The IDF model to add the zone lists to.

        Returns:
            idf (IDF): The IDF model with the added zone lists
            conditioned_zone_list (ZoneList): The list of conditioned zones
            all_zones_list (ZoneList): The list of all zones
        """
        raise NotImplementedError
        all_zone_names = [zone.Name for zone in idf.idfobjects["ZONE"]]
        all_zones_list = ZoneList(Name="All_Zones", Names=all_zone_names)
        conditioned_zone_names = [
            zone.Name
            for zone in idf.idfobjects["ZONE"]
            if "attic" not in zone.Name.lower()  # attic considered
            and (
                not zone.Name.lower().endswith(self.geometry.basement_suffix.lower())
                if ((not self.conditioned_basement) and self.geometry.basement)
                else True
            )
        ]

        conditioned_storey_count = self.geometry.num_stories + (
            1 if self.conditioned_basement else 0
        )
        zones_per_storey = self.geometry.zones_per_storey
        expected_zone_count = conditioned_storey_count * zones_per_storey
        if len(conditioned_zone_names) != expected_zone_count:
            msg = f"Expected {expected_zone_count} zones, but found {len(conditioned_zone_names)}."
            raise ValueError(msg)

        conditioned_zone_list = ZoneList(
            Name="Conditioned_Zones", Names=conditioned_zone_names
        )
        idf = conditioned_zone_list.add(idf)
        idf = all_zones_list.add(idf)
        return idf, conditioned_zone_list, all_zones_list

    # part of the HVAC/conditioning system
    def compute_dhw(self) -> float:
        """Compute the domestic hot water energy demand.

        Returns:
            energy (float): The domestic hot water energy demand (kWh/m2)
        """
        raise NotImplementedError
        # TODO: this should be computed from the DHW schedule
        if not self.space_use.DHW.IsOn:
            return 0
        flow_rate_per_person = self.space_use.DHW.FlowRatePerPerson  # m3/hr/person
        temperature_rise = (
            self.space_use.DHW.WaterSupplyTemperature
            - self.space_use.DHW.WaterTemperatureInlet
        )  # K
        water_density = physical_constants["water_density"]  # kg/m3
        c = physical_constants["water_specific_heat"]  # J/kg.K
        total_flow_rate = flow_rate_per_person * self.total_people  # m3/hr
        total_volume = (
            total_flow_rate * physical_constants["flow_rate_to_volume_conversion"]
        )  # m3 / yr
        total_energy = total_volume * temperature_rise * water_density * c  # J / yr
        total_energy_kWh = total_energy / physical_constants["J_to_kWh"]  # kWh / yr
        total_energy_kWh_per_m2 = (
            total_energy_kWh / self.total_conditioned_area
        )  # kWh/m2 / yr
        return total_energy_kWh_per_m2

    def add_hot_water_to_zone(
        self, idf: IDF, space_use: ZoneOperationsComponent, zone_name: str
    ) -> IDF:
        """Add the hot water to the zone.

        Args:
            idf (IDF): The IDF model to add the hot water to.
            space_use (ZoneUse): The zone use template.
            zone_name (str): The name of the zone to add the hot water to.

        Returns:
            idf (IDF): The IDF model with the added hot water.
        """
        raise NotImplementedError
        zone = next((x for x in idf.idfobjects["ZONE"] if x.Name == zone_name), None)
        if zone is None:
            raise ValueError(f"NO_ZONE:{zone_name}")
        area = 0
        area_ct = 0
        for srf in idf.idfobjects["BUILDINGSURFACE:DETAILED"]:
            if srf.Zone_Name == zone.Name and srf.Surface_Type.lower() == "floor":
                poly = Polygon(srf.coords)
                area += poly.area
                area_ct += 1
        if area_ct > 1:
            raise ValueError(f"TOO_MANY_FLOORS:{zone.Name}")
        if area == 0 or area_ct == 0:
            raise ValueError(f"NO_AREA:{zone.Name}")
        ppl_density = space_use.SpaceUse.OccupancyDensity
        total_ppl = ppl_density * area
        idf = space_use.DHW.add_water_to_idf_zone(idf, zone.Name, total_ppl)
        return idf

    def add_hot_water_to_zone_list(
        self, idf: IDF, space_use: ZoneOperationsComponent, zone_list: ZoneList
    ) -> IDF:
        """Add the hot water to the zone list.

        Args:
            idf (IDF): The IDF model to add the hot water to.
            space_use (ZoneUse): The zone use template.
            zone_list (ZoneList): The list of zones to add the hot water to.

        Returns:
            idf (IDF): The IDF model with the added hot water.
        """
        for zone_name in zone_list.Names:
            idf = self.add_hot_water_to_zone(idf, space_use, zone_name)
        return idf

    def add_space_use(
        self, idf: IDF, space_use: ZoneOperationsComponent, zone_list: ZoneList
    ) -> IDF:
        """Add the space use to the IDF model.

        Args:
            idf (IDF): The IDF model to add the space use to.
            space_use (ZoneUse): The zone use template.
            zone_list (ZoneList): The list of zones to add the space use to.

        Returns:
            IDF: The IDF model with the added space use.
        """
        raise NotImplementedError
        idf = space_use.add_space_use_to_idf_zone(idf, zone_list)
        idf = self.add_hot_water_to_zone_list(idf, space_use, zone_list)
        idf = self.add_schedules_by_name(
            idf, space_use.schedule_names
        )  # TODO: Add schedules methodology
        return idf

    def add_envelope(
        self, idf: IDF, envelope: ZoneEnvelopeComponent, inf_zone_list: ZoneList
    ) -> IDF:
        """Add the envelope to the IDF model.

        Takes care of both the constructions and infiltration and windows.

        Args:
            idf (IDF): The IDF model to add the envelope to.
            envelope (ZoneEnvelope): The envelope template.
            inf_zone_list (ZoneList): The list of zones to add the infiltration to.


        Returns:
            IDF: The IDF model with the added envelope.
        """
        constructions = envelope.Assemblies
        infiltration = envelope.Infiltration
        window_def = envelope.Window
        # _other_settings = envelope.OtherSettings
        # _foundation_settings = envelope.Foundation
        # TODO: other settings

        self.add_srf_constructions(idf, constructions, window_def)
        self.add_infiltration(idf, infiltration, inf_zone_list)

        # TODO: consider natvent/operable windows etc
        # sch_names = self.envelope.schedule_names
        # idf = self.add_schedules_by_name(idf, sch_names)

        return idf

    def add_srf_constructions(
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
            IDF: The IDF model with the selected surfaces.
        """
        if self.geometry.roof_height:
            raise SBEMBuilderNotImplementedError("roof_height")

        if (
            constructions.FacadeIsAdiabatic
            or constructions.RoofIsAdiabatic
            or constructions.GroundIsAdiabatic
            or constructions.PartitionIsAdiabatic
            or constructions.SlabIsAdiabatic
        ):
            raise SBEMBuilderNotImplementedError("_IsAdiabatic")

        if constructions.InternalMassIsOn:
            raise SBEMBuilderNotImplementedError("InternalMassIsOn")

        handlers = SurfaceHandlers.Default()
        idf = handlers.handle_envelope(idf, self.lib, constructions, window_def)

        return idf

    def add_infiltration(
        self, idf: IDF, infiltration: InfiltrationComponent, zone_list: ZoneList
    ):
        """Add the infiltration to the IDF model.

        Args:
            idf (IDF): The IDF model to add the infiltration to.
            infiltration: The infiltration object.
            zone_list (ZoneList): The list of zones to add the infiltration to.

        Returns:
            idf (IDF): The IDF model with the added infiltration.
        """
        idf = infiltration.add_infiltration_to_idf_zone(idf, zone_list.Name)
        # idf = self.add_schedules_by_name(idf, infiltration.schedule_names)
        return idf

    def build(self, config: SimulationPathConfig) -> IDF:
        """Build the energy model using the Climate Studio API.

        Args:
            config (SimulationConfig): The configuration for the simulation.

        Returns:
            IDF: The built energy model.
        """
        raise NotImplementedError
        if (not self.geometry.basement) and self.conditioned_basement:
            raise ValueError("CONDITIONEDBASEMENT:TRUE:BASEMENT:FALSE")

        if self.geometry.roof_height:
            raise SBEMBuilderNotImplementedError("roof_height")
        config.output_dir.mkdir(parents=True, exist_ok=True)
        base_filepath = EnergyPlusArtifactDir / "Minimal.idf"
        target_base_filepath = config.output_dir / "Minimal.idf"
        shutil.copy(base_filepath, target_base_filepath)
        epw_path, ddy_path = asyncio.run(self.fetch_weather(config.weather_dir))
        idf = IDF(
            target_base_filepath.as_posix(),
            as_version=None,  # pyright: ignore [reportArgumentType]
            prep_outputs=True,
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
        self.lib.Schedule.update(scheds)

        idf = SiteGroundTemperature.FromValues(
            assumed_constants.SiteGroundTemperature_degC
        ).add(idf)

        idf = self.geometry.add(idf)

        # construct zone lists
        idf, conditioned_zone_list, all_zones_list = self.add_zone_lists(idf)

        # TODO: Handle separately ventilated attic/basement?
        idf = self.add_space_use(idf, self.space_use, conditioned_zone_list)
        idf = self.add_envelope(idf, self.envelope, all_zones_list)

        return idf

    # add schedules definition

    # base simulation information
    def simulate(
        self,
        config: SimulationPathConfig,
        post_build_callback: Callable[[IDF], IDF] | None = None,
    ) -> tuple[IDF, Sql]:
        """Build and simualte the idf model.

        Args:
            config (SimulationConfig): The configuration for the simulation.
            post_build_callback (Callable[[IDF],IDF] | None): A callback to run after the model is built.

        Returns:
            tuple[IDF, Sql]: The built energy model and the sql file.
        """
        idf = self.build(config)
        if post_build_callback is not None:
            idf = post_build_callback(idf)
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

    def standard_results_postprocess(self, sql: Sql, move_energy: bool) -> pd.Series:
        """Postprocess the sql file to get the standard results.

        Args:
            sql (Sql): The sql file to postprocess.
            move_energy (bool): Whether to move the energy to fuels based off of the CoP/Fuel Types.

        Returns:
            pd.DataFrame: The postprocessed results.
        """
        res_df = sql.tabular_data_by_name(
            "AnnualBuildingUtilityPerformanceSummary", "End Uses"
        )
        kWh_per_GJ = 277.778
        res_df = (
            res_df[
                [
                    "Electricity",
                    "District Cooling",
                    "District Heating",
                ]
            ].droplevel(-1, axis=1)
            * kWh_per_GJ
        ) / self.total_conditioned_area
        res_series_hot_water = res_df.loc["Water Systems"]
        res_series = res_df.loc["Total End Uses"] - res_series_hot_water
        res_series["Domestic Hot Water"] = res_series_hot_water.sum()

        res_series.name = "kWh/m2"

        if move_energy:
            if self.operations.HVAC.ConditioningSystems.Heating is not None:
                heat_cop = self.operations.HVAC.ConditioningSystems.Heating.effective_system_cop
                heat_fuel = self.operations.HVAC.ConditioningSystems.Heating.Fuel
                heat_energy = res_series["District Heating"] / heat_cop
                if heat_fuel not in res_series.index:
                    res_series[heat_fuel] = 0
                res_series[heat_fuel] += heat_energy

            raise NotImplementedError
            cool_cop = (
                self.operations.HVAC.ConditioningSystems.Cooling.effective_system_cop
            )
            dhw_cop = self.operations.DHW.SystemCOP
            cool_fuel = self.space_use.Conditioning.CoolingFuelType
            dhw_fuel = self.space_use.HotWater.HotWaterFuelType
            cool_energy = res_series["District Cooling"] / cool_cop
            dhw_energy = res_series["Domestic Hot Water"] / dhw_cop
            if cool_fuel not in res_series.index:
                res_series[cool_fuel] = 0
            if dhw_fuel not in res_series.index:
                res_series[dhw_fuel] = 0
            res_series[cool_fuel] += cool_energy
            res_series[dhw_fuel] += dhw_energy
            res_series = res_series.drop([
                "District Cooling",
                "District Heating",
                "Domestic Hot Water",
            ])

        return cast(pd.Series, res_series)

    def run(
        self,
        weather_dir: Path | None = None,
        post_build_callback: Callable[[IDF], IDF] | None = None,
        move_energy: bool = False,
    ) -> tuple[IDF, pd.Series, str]:
        """Build and simualte the idf model.

        Args:
            weather_dir (Path): The directory to store the weather files.
            post_build_callback (Callable[[IDF],IDF] | None): A callback to run after the model is built.
            move_energy (bool): Whether to move the energy to fuels based off of the CoP/Fuel Types.

        Returns:
            idf (IDF): The built energy model.
            results (pd.Series): The postprocessed results.
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
                post_build_callback=post_build_callback,
            )
            results = self.standard_results_postprocess(sql, move_energy=move_energy)
            err_text = self.get_warnings(idf)
            return idf, results, err_text


if __name__ == "__main__":
    import asyncio
    import json

    # import tempfile
    from pydantic import AnyUrl

    raise NotImplementedError
    with open("notebooks/everett_lib.json") as f:
        lib_data = json.load(f)
    lib = ComponentLibrary.model_validate(lib_data)
    for env in lib.Envelope.values():
        if env.WindowDefinition is None:
            msg = f"Envelope {env.Name} has no window definition"
            raise ValueError(msg)
        env.WindowDefinition.GlazingConstruction = "Template_post_2003"

    model = Model(
        Weather=AnyUrl(
            "https://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/USA_United_States_of_America/MA_Massachusetts/USA_MA_Boston-Logan.Intl.AP.725090_TMYx.2009-2023.zip"
        ),
        lib=lib,
        space_use_name=next(iter(lib.Operations)),
        envelope_name=next(iter(lib.Envelope)),
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

    idf, results, err_text = model.run(move_energy=False)
    print(results)
