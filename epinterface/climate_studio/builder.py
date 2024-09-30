"""A module for building the energy model using the Climate Studio API."""

import shutil
import tempfile
from pathlib import Path
from typing import Literal, cast
from uuid import uuid4

import pandas as pd
from archetypal.idfclass import IDF
from archetypal.idfclass.sql import Sql
from pydantic import BaseModel, Field

from epinterface.climate_studio.interface import (
    ClimateStudioLibraryV2,
    GlazingConstructionSimple,
    OpaqueConstruction,
    WindowDefinition,
    ZoneConstruction,
    ZoneEnvelope,
    ZoneInfiltration,
    ZoneUse,
)
from epinterface.data import EnergyPlusArtifactDir
from epinterface.ddy_injector_bayes import DDYSizingSpec
from epinterface.geometry import ShoeboxGeometry
from epinterface.interface import (
    ZoneList,
    add_default_schedules,
    add_default_sim_controls,
)
from epinterface.weather import BaseWeather


class ClimateStudioBuilderNotImplementedError(NotImplementedError):
    """Raised when a parameter is not yet implemented in the climate studio shoebox builder."""

    def __init__(self, parameter: str):
        """Initialize the error.

        Args:
            parameter (str): The parameter that is not yet implemented.
        """
        self.parameter = parameter
        super().__init__(
            f"Parameter {parameter} is not yet implemented in the climate studio shoebox builder."
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


class Model(BaseWeather, validate_assignment=True):
    """A simple model constructor for the IDF model.

    Creates geometry as well as zone definitions.
    """

    geometry: ShoeboxGeometry
    space_use_name: str
    envelope_name: str
    lib: ClimateStudioLibraryV2

    @property
    def space_use(self) -> ZoneUse:
        """The space use definition for the model."""
        if self.space_use_name not in self.lib.SpaceUses:
            raise KeyError(f"MISSING:SPACE_USE:{self.space_use_name}")
        return self.lib.SpaceUses[self.space_use_name]

    @property
    def envelope(self) -> ZoneEnvelope:
        """The envelope definition for the model."""
        if self.envelope_name not in self.lib.Envelopes:
            raise KeyError(f"MISSING:ENVELOPE:{self.envelope_name}")

        return self.lib.Envelopes[self.envelope_name]

    async def build(self, config: SimulationPathConfig) -> IDF:
        """Build the energy model using the Climate Studio API.

        Args:
            config (SimulationConfig): The configuration for the simulation.

        Returns:
            IDF: The built energy model.
        """
        if self.geometry.basement_depth:
            raise ClimateStudioBuilderNotImplementedError("basement_depth")

        if self.geometry.roof_height:
            raise ClimateStudioBuilderNotImplementedError("roof_height")

        config.output_dir.mkdir(parents=True, exist_ok=True)
        base_filepath = EnergyPlusArtifactDir / "Minimal.idf"
        target_base_filepath = config.output_dir / "Minimal.idf"
        shutil.copy(base_filepath, target_base_filepath)
        epw_path, ddy_path = await self.fetch_weather(config.weather_dir)
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
        idf = add_default_schedules(idf)

        idf = self.geometry.add(idf)

        # construct zone lists
        idf, conditioned_zone_list, all_zones_list = self.add_zone_lists(idf)

        # TODO: Handle separately ventilated attic/basement?
        idf = self.add_space_use(idf, self.space_use, conditioned_zone_list)
        idf = self.add_envelope(idf, self.envelope, all_zones_list)

        return idf

    def add_envelope(
        self, idf: IDF, envelope: ZoneEnvelope, inf_zone_list: ZoneList
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
        constructions = envelope.Constructions
        infiltration = envelope.Infiltration
        window_def = envelope.WindowDefinition
        _other_settings = envelope.OtherSettings
        _foundation_settings = envelope.Foundation
        # TODO: other settings

        self.add_srf_constructions(idf, constructions, window_def)
        self.add_infiltration(idf, infiltration, inf_zone_list)

        sch_names = self.envelope.schedule_names
        idf = self.add_schedules_by_name(idf, sch_names)

        return idf

    def add_srf_constructions(
        self,
        idf: IDF,
        constructions: ZoneConstruction,
        window_def: WindowDefinition | None,
    ) -> IDF:
        """Assigns the constructions to the surfaces in the model.

        Args:
            idf (IDF): The IDF model to select the surfaces from.
            constructions (ZoneConstruction): The construction template.
            window_def (WindowDefinition): The window definition template.

        Returns:
            IDF: The IDF model with the selected surfaces.
        """
        if self.geometry.basement_depth:
            raise ClimateStudioBuilderNotImplementedError("basement_depth")

        if self.geometry.roof_height:
            raise ClimateStudioBuilderNotImplementedError("roof_height")

        if (
            constructions.FacadeIsAdiabatic
            or constructions.RoofIsAdiabatic
            or constructions.GroundIsAdiabatic
            or constructions.PartitionIsAdiabatic
            or constructions.SlabIsAdiabatic
        ):
            raise ClimateStudioBuilderNotImplementedError("_IsAdiabatic")

        if constructions.InternalMassIsOn:
            raise ClimateStudioBuilderNotImplementedError("InternalMassIsOn")

        # outside walls are the ones with outdoor boundary condition and vertical orientation
        def make_reversed(const: OpaqueConstruction):
            new_const = const.model_copy(deep=True)
            new_const.Layers = new_const.Layers[::-1]
            new_const.Name = f"{const.Name}_Reversed"
            return new_const

        def reverse_construction(const_name: str, lib: ClimateStudioLibraryV2):
            const = lib.OpaqueConstructions[const_name]
            new_const = make_reversed(const)
            return new_const

        slab_reversed = reverse_construction(constructions.SlabConstruction, self.lib)
        lib.OpaqueConstructions[slab_reversed.Name] = slab_reversed

        actions = [
            (
                constructions.FacadeConstruction,
                SurfaceHandler(
                    boundary_condition="outdoors",
                    original_construction_name="Project Wall",
                    surface_type="opaque",
                ),
            ),
            (
                constructions.RoofConstruction,
                SurfaceHandler(
                    boundary_condition="outdoors",
                    original_construction_name="Project Flat Roof",
                    surface_type="opaque",
                ),
            ),
            (
                constructions.PartitionConstruction,
                SurfaceHandler(
                    boundary_condition="surface",
                    original_construction_name="Project Partition",
                    surface_type="opaque",
                ),
            ),
            (
                slab_reversed.Name,
                SurfaceHandler(
                    boundary_condition="surface",
                    original_construction_name="Project Floor",
                    surface_type="opaque",
                ),
            ),
            (
                constructions.SlabConstruction,
                SurfaceHandler(
                    boundary_condition="surface",
                    original_construction_name="Project Ceiling",
                    surface_type="opaque",
                ),
            ),
            (
                constructions.GroundSlabConstruction,
                SurfaceHandler(
                    boundary_condition="ground",
                    original_construction_name="Project Floor",
                    surface_type="opaque",
                ),
            ),
        ]

        # TODO: External floors, basements, etc

        if window_def:
            actions.append((
                window_def.Construction,
                SurfaceHandler(
                    boundary_condition=None,
                    original_construction_name="Project External Window",
                    surface_type="glazing",
                ),
            ))

        for const_name, action in actions:
            idf = action.asssign_srfs(idf, self.lib, const_name)

        return idf

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
        all_zone_names = [zone.Name for zone in idf.idfobjects["ZONE"]]
        all_zones_list = ZoneList(Name="All_Zones", Names=all_zone_names)
        zone_names = [
            zone.Name
            for zone in idf.idfobjects["ZONE"]
            if "attic" not in zone.Name.lower() and not zone.Name.endswith("-1")
        ]

        expected_zone_count = self.geometry.num_stories * (
            1 if self.geometry.zoning == "by_storey" else 5
        )
        if len(zone_names) != expected_zone_count:
            msg = f"Expected {expected_zone_count} zones, but found {len(zone_names)}."
            raise ValueError(msg)

        conditioned_zone_list = ZoneList(Name="Conditioned_Zones", Names=zone_names)
        idf = conditioned_zone_list.add(idf)
        idf = all_zones_list.add(idf)
        return idf, conditioned_zone_list, all_zones_list

    def add_infiltration(
        self, idf: IDF, infiltration: ZoneInfiltration, zone_list: ZoneList
    ):
        """Add the infiltration to the IDF model.

        Args:
            idf (IDF): The IDF model to add the infiltration to.
            infiltration: The infiltration object.
            zone_list (ZoneList): The list of zones to add the infiltration to.

        Returns:
            IDF: The IDF model with the added infiltration.
        """
        idf = infiltration.add_infiltration_to_idf_zone(idf, zone_list.Name)
        # idf = self.add_schedules_by_name(idf, infiltration.schedule_names)
        return idf

    def add_space_use(self, idf: IDF, space_use: ZoneUse, zone_list: ZoneList) -> IDF:
        """Add the space use to the IDF model.

        Args:
            idf (IDF): The IDF model to add the space use to.
            space_use (ZoneUse): The zone use template.
            zone_list (ZoneList): The list of zones to add the space use to.

        Returns:
            IDF: The IDF model with the added space use.
        """
        idf = space_use.add_space_use_to_idf_zone(idf, zone_list)
        idf = self.add_schedules_by_name(idf, space_use.schedule_names)
        return idf

    def add_schedules_by_name(self, idf: IDF, schedule_names: set[str]) -> IDF:
        """Add schedules to the IDF model by name.

        Args:
            idf (IDF): The IDF model to add the schedules to.
            schedule_names (set[str]): The names of the schedules to add.

        Returns:
            IDF: The IDF model with the added schedules.
        """
        schedules = [self.lib.Schedules[s] for s in schedule_names]
        for schedule in schedules:
            yr_sch, *_ = schedule.to_year_week_day()
            yr_sch.to_epbunch(idf)
        return idf

    async def simulate(self, config: SimulationPathConfig) -> tuple[IDF, Sql]:
        """Build and simualte the idf model.

        Args:
           config (SimulationConfig): The configuration for the simulation.

        Returns:
            tuple[IDF, Sql]: The built energy model and the sql file.
        """
        idf = await self.build(config)
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
        res_series = (
            res_df[
                [
                    "Electricity",
                    "District Cooling",
                    "District Heating",
                ]
            ].droplevel(-1, axis=1)
            * kWh_per_GJ
        ).loc["Total End Uses"] / self.geometry.total_living_area

        res_series.name = "kWh/m2"

        if move_energy:
            heat_cop = self.space_use.Conditioning.HeatingCOP
            cool_cop = self.space_use.Conditioning.CoolingCOP
            heat_fuel = self.space_use.Conditioning.HeatingFuelType
            cool_fuel = self.space_use.Conditioning.CoolingFuelType
            heat_energy = res_series["District Heating"] / heat_cop
            cool_energy = res_series["District Cooling"] / cool_cop
            if heat_fuel not in res_series.index:
                res_series[heat_fuel] = 0
            if cool_fuel not in res_series.index:
                res_series[cool_fuel] = 0
            res_series[heat_fuel] += heat_energy
            res_series[cool_fuel] += cool_energy
            res_series = res_series.drop(["District Cooling", "District Heating"])

        return cast(pd.Series, res_series)

    async def run(self, move_energy: bool) -> tuple[IDF, pd.Series, str]:
        """Build and simualte the idf model.

        Args:
            move_energy (bool): Whether to move the energy to fuels based off of the CoP/Fuel Types.

        Returns:
            idf (IDF): The built energy model.
            results (pd.Series): The postprocessed results.
            err_text (str): The warning text.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            config = SimulationPathConfig(output_dir=output_dir)
            idf, sql = await self.simulate(config)
            results = self.standard_results_postprocess(sql, move_energy=move_energy)
            err_text = self.get_warnings(idf)
            return idf, results, err_text


# TODO: move to interface?
class SurfaceHandler(BaseModel):
    """A handler for filtering and adding surfaces to a model."""

    boundary_condition: str | None
    original_construction_name: str | None
    surface_type: Literal["glazing", "opaque"]

    def asssign_srfs(
        self, idf: IDF, lib: ClimateStudioLibraryV2, construction_name: str
    ) -> IDF:
        """Adds a construction (and its materials) to an IDF and assigns it to matching surfaces.

        Args:
            idf (IDF): The IDF model to add the construction to.
            lib (ClimateStudioLibraryV2): The library of constructions.
            construction_name (str): The name of the construction to add.
        """
        srf_key = (
            "FENESTRATIONSURFACE:DETAILED"
            if self.surface_type == "glazing"
            else "BUILDINGSURFACE:DETAILED"
        )
        if self.boundary_condition is not None and self.surface_type == "glazing":
            raise ClimateStudioBuilderNotImplementedError(
                f"{self.surface_type}:BOUNDARY_CONDITON:{self.boundary_condition}"
            )

        srfs = [
            srf
            for srf in idf.idfobjects[srf_key]
            if self.check_boundary(srf) and self.check_construction_name(srf)
        ]
        construction_lib = (
            lib.OpaqueConstructions
            if self.surface_type != "glazing"
            else lib.GlazingConstructions
        )
        if construction_name not in construction_lib:
            raise KeyError(
                f"MISSING_CONSTRUCTION:{construction_name}:TARGET={self.__repr__()}"
            )
        construction = construction_lib[construction_name]
        idf = (
            construction.add_to_idf(idf)
            if isinstance(construction, GlazingConstructionSimple)
            else construction.add_to_idf(idf, lib.OpaqueMaterials)
        )
        for srf in srfs:
            srf.Construction_Name = construction.Name
        return idf

    def check_boundary(self, srf):
        """Check if the surface matches the boundary condition.

        Args:
            srf: The surface to check.

        Returns:
            bool: True if the surface matches the boundary condition.
        """
        if self.surface_type == "glazing":
            # Ignore the bc filter check for windows
            return True
        if self.boundary_condition is None:
            # Ignore the bc filter when filter not provided
            return True
        # Check the boundary condition
        return srf.Outside_Boundary_Condition == self.boundary_condition

    def check_construction_name(self, srf):
        """Check if the surface matches the original construction name.

        Args:
            srf: The surface to check.

        Returns:
            bool: True if the surface matches the original construction name.
        """
        if self.original_construction_name is None:
            # Ignore the original construction name check when filter not provided
            return True
        # Check the original construction name
        return srf.Construction_Name == self.original_construction_name


if __name__ == "__main__":
    import asyncio
    import json

    # import tempfile
    from pydantic import AnyUrl

    from epinterface.climate_studio.interface import (
        ClimateStudioLibraryV1,
        OpaqueConstruction,
        OpaqueMaterial,
        extract_sch,
    )

    lib = ClimateStudioLibraryV2(
        SpaceUses={},
        Schedules={},
        Envelopes={},
        GlazingConstructions={},
        OpaqueConstructions={},
        OpaqueMaterials={},
    )
    base_path = Path("D:/climatestudio/default")
    merge_path = Path("C:/users/szvsw/Downloads")
    opaque_mats = ClimateStudioLibraryV1.LoadObjects(
        merge_path, OpaqueMaterial, pluralize=True
    )
    opaque_mats_2 = ClimateStudioLibraryV1.LoadObjects(
        base_path, OpaqueMaterial, pluralize=True
    )
    opaque_mats.update(opaque_mats_2)
    lib.OpaqueMaterials = opaque_mats
    opaque_constructions = ClimateStudioLibraryV1.LoadObjects(
        base_path, OpaqueConstruction, pluralize=True
    )
    opaque_constructions_2 = ClimateStudioLibraryV1.LoadObjects(
        merge_path,
        OpaqueConstruction,
        pluralize=True,
    )
    opaque_constructions.update(opaque_constructions_2)
    lib.OpaqueConstructions = opaque_constructions

    year_schs = pd.read_csv(base_path / "YearSchedules.csv", dtype=str)
    sch_names = year_schs.columns
    schedules_list = [extract_sch(year_schs, sch_name) for sch_name in sch_names]
    schedules = {sch.Name: sch for sch in schedules_list}
    if len(schedules) != len(schedules_list):
        raise ValueError("Schedules")
    lib.Schedules = schedules

    with open("notebooks/data/test_outputs_construction.json") as f:
        const_data = json.load(f)

    with open("notebooks/data/v1_CS_output_space_use_MA.json") as f:
        su_data = list(json.load(f).values())

    for val in su_data:
        zu = ZoneUse(**val)
        if zu.Name in lib.SpaceUses:
            raise ValueError(f"DUPLICATE_SPACE_USE_NAME:{zu.Name}")
        lib.SpaceUses[zu.Name] = zu

    for val in const_data:
        ze = ZoneEnvelope(**val)
        if ze.Name in lib.Envelopes:
            raise ValueError(f"DUPLICATE_ENVELOPE_NAME:{ze.Name}")
        lib.Envelopes[ze.Name] = ze

    model = Model(
        Weather=AnyUrl(
            "https://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/USA_United_States_of_America/MA_Massachusetts/USA_MA_Boston-Logan.Intl.AP.725090_TMYx.2009-2023.zip"
        ),
        lib=lib,
        space_use_name=next(iter(lib.SpaceUses)),
        envelope_name=next(iter(lib.Envelopes)),
        geometry=ShoeboxGeometry(
            x=0,
            y=0,
            w=10,
            d=10,
            h=3,
            wwr=0.2,
            num_stories=2,
            basement_depth=None,
            zoning="by_storey",
            roof_height=None,
        ),
    )
    model.space_use.Conditioning.HeatingSetpoint = 18
    model.space_use.Conditioning.CoolingSetpoint = 23
    model.space_use.Loads.LightingPowerDensity = 10
    model.space_use.Loads.EquipmentPowerDensity = 10
    model.envelope.Infiltration.InfiltrationAch = 0.4
    idf, results, err_text = asyncio.run(model.run(move_energy=False))
    import json

    with open("notebooks/lib_demo.json", "w") as f:
        json.dump(lib.model_dump(mode="json"), f, indent=2)
    with open("notebooks/lib_demo.json") as f:
        lib = ClimateStudioLibraryV2.model_validate(json.load(f))

    model.lib = lib
    idf, results_2, err_text = asyncio.run(model.run(move_energy=False))

    print(results)
    print(results_2)
