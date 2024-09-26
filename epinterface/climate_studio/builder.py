"""A module for building the energy model using the Climate Studio API."""

import shutil
from pathlib import Path
from typing import cast
from uuid import uuid4

import pandas as pd
from archetypal.idfclass import IDF
from archetypal.idfclass.sql import Sql
from pydantic import BaseModel, Field

from epinterface.climate_studio.interface import ClimateStudioLibrary, ZoneDefinition
from epinterface.data import EnergyPlusArtifactDir
from epinterface.ddy_injector_bayes import DDYSizingSpec
from epinterface.geometry import ShoeboxGeometry
from epinterface.interface import (
    ZoneList,
    add_default_schedules,
    add_default_sim_controls,
)


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
    epw_path: Path = Field(..., description="The path to the EPW file.")
    ddy_path: Path = Field(..., description="The path to the DDY file.")


class Model(BaseModel):
    """A simple model constructor for the IDF model.

    Creates geometry as well as zone definitions.
    """

    geometry: ShoeboxGeometry
    zone_name: str
    library: ClimateStudioLibrary

    def build(self, config: SimulationPathConfig) -> IDF:
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
        idf = IDF(
            target_base_filepath.as_posix(),
            as_version=None,  # pyright: ignore [reportArgumentType]
            prep_outputs=True,
            epw=config.epw_path,
            output_directory=config.output_dir,
        )
        ddy = IDF(
            config.ddy_path.as_posix(),
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
        idf, conditioned_zone_list, _all_zones_list = self.add_zone_lists(idf)

        # Acquire the template
        zone_template = self.library.ZoneDefinition[self.zone_name]

        # TODO: assign window types

        idf = self.add_srf_constructions(idf, zone_template)
        idf = self.add_loads(idf, zone_template, conditioned_zone_list)
        # TODO: Handle separately ventilated attic/basement?
        idf = self.add_infiltration(idf, zone_template, conditioned_zone_list)
        idf = self.add_conditioning(idf, zone_template, conditioned_zone_list)

        return idf

    def add_srf_constructions(self, idf: IDF, zone_template: ZoneDefinition) -> IDF:
        """Assigns the constructions to the surfaces in the model.

        Args:
            idf (IDF): The IDF model to select the surfaces from.
            zone_template (ZoneDefinition): The zone definition template.

        Returns:
            IDF: The IDF model with the selected surfaces.
        """
        if self.geometry.basement_depth:
            raise ClimateStudioBuilderNotImplementedError("basement_depth")

        if self.geometry.roof_height:
            raise ClimateStudioBuilderNotImplementedError("roof_height")

        zone_constructions_def = self.library.ZoneConstruction[
            zone_template.Constructions
        ]

        if (
            zone_constructions_def.FacadeIsAdiabatic
            or zone_constructions_def.RoofIsAdiabatic
            or zone_constructions_def.GroundIsAdiabatic
            or zone_constructions_def.PartitionIsAdiabatic
            or zone_constructions_def.SlabIsAdiabatic
        ):
            raise ClimateStudioBuilderNotImplementedError("_IsAdiabatic")

        if zone_constructions_def.InternalMassIsOn:
            raise ClimateStudioBuilderNotImplementedError("InternalMassIsOn")

        def handle_srfs_for_filter(
            idf: IDF,
            construction_name: str,
            boundary_condition: str,
            original_construction_name: str,
        ) -> IDF:
            srfs = [
                srf
                for srf in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
                if srf.Outside_Boundary_Condition == boundary_condition
                and srf.Construction_Name == original_construction_name
            ]
            construction = self.library.OpaqueConstructions[construction_name]
            idf = construction.add_to_idf(idf, self.library.OpaqueMaterials)
            for srf in srfs:
                srf.Construction_Name = construction.Name
            return idf

        # outside walls are the ones with outdoor boundary condition and vertical orientation
        actions = [
            (zone_constructions_def.FacadeConstruction, "outdoors", "Project Wall"),
            (zone_constructions_def.RoofConstruction, "outdoors", "Project Flat Roof"),
            (
                zone_constructions_def.PartitionConstruction,
                "surface",
                "Project Partition",
            ),
            (
                zone_constructions_def.SlabConstruction,
                "surface",
                "Project Ceiling",
            ),
            (zone_constructions_def.SlabConstruction, "surface", "Project Floor"),
            (zone_constructions_def.GroundSlabConstruction, "ground", "Project Floor"),
        ]
        for action in actions:
            idf = handle_srfs_for_filter(idf, *action)

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
        self, idf: IDF, zone_template: ZoneDefinition, zone_list: ZoneList
    ):
        """Add the infiltration to the IDF model.

        Args:
            idf (IDF): The IDF model to add the infiltration to.
            zone_template (ZoneInfiltration): The zone infiltration template.
            zone_list (ZoneList): The list of zones to add the infiltration to.

        Returns:
            IDF: The IDF model with the added infiltration.
        """
        infiltration_name = zone_template.Infiltration
        infiltration = self.library.ZoneInfiltration[infiltration_name]
        idf = infiltration.add_infiltration_to_idf_zone(idf, zone_list.Name)
        # idf = self.add_schedules_by_name(idf, infiltration.schedule_names)
        return idf

    def add_loads(
        self, idf: IDF, zone_template: ZoneDefinition, zone_list: ZoneList
    ) -> IDF:
        """Add the loads to the IDF model.

        Args:
            idf (IDF): The IDF model to add the loads to.
            zone_template (ZoneLoads): The zone loads template.
            zone_list (ZoneList): The list of zones to add the loads to.

        Returns:
            IDF: The IDF model with the added loads.
        """
        zone_load_name = zone_template.Loads
        zone_load = self.library.ZoneLoad[zone_load_name]
        idf = zone_load.add_loads_to_idf_zone(idf, zone_list.Name)
        idf = self.add_schedules_by_name(idf, zone_load.schedule_names)
        return idf

    def add_conditioning(
        self, idf: IDF, zone_template: ZoneDefinition, zone_list: ZoneList
    ) -> IDF:
        """Add the conditioning to the IDF model.

        Args:
            idf (IDF): The IDF model to add the conditioning to.
            zone_template (ZoneConditioning): The zone conditioning template.
            zone_list (ZoneList): The list of zones to add the conditioning to.

        Returns:
            IDF: The IDF model with the added conditioning.
        """
        hvac_name = zone_template.Conditioning
        hvac = self.library.ZoneConditioning[hvac_name]
        for zone in zone_list.Names:
            idf = hvac.add_conditioning_to_idf_zone(idf, zone)
        idf = self.add_schedules_by_name(idf, hvac.schedule_names)
        return idf

    def add_schedules_by_name(self, idf: IDF, schedule_names: set[str]) -> IDF:
        """Add schedules to the IDF model by name.

        Args:
            idf (IDF): The IDF model to add the schedules to.
            schedule_names (set[str]): The names of the schedules to add.

        Returns:
            IDF: The IDF model with the added schedules.
        """
        schedules = [self.library.Schedules[s] for s in schedule_names]
        for schedule in schedules:
            yr_sch, *_ = schedule.to_year_week_day()
            yr_sch.to_epbunch(idf)
        return idf

    def simulate(self, config: SimulationPathConfig) -> tuple[IDF, Sql]:
        """Build and simualte the idf model.

        Args:
           config (SimulationConfig): The configuration for the simulation.

        Returns:
            tuple[IDF, Sql]: The built energy model and the sql file.
        """
        idf = self.build(config)
        idf.simulate()
        sql = Sql(idf.sql_file)
        return idf, sql

    def standard_results_postprocess(self, sql: Sql) -> pd.Series:
        """Postprocess the sql file to get the standard results.

        Args:
            sql (Sql): The sql file to postprocess.

        Returns:
            pd.DataFrame: The postprocessed results.
        """
        res_df = sql.tabular_data_by_name(
            "AnnualBuildingUtilityPerformanceSummary", "End Uses"
        )
        kWh_per_GJ = 277.778
        res_series = (
            res_df[
                ["Electricity", "Natural Gas", "District Cooling", "District Heating"]
            ].droplevel(-1, axis=1)
            * kWh_per_GJ
        ).loc["Total End Uses"] / self.geometry.total_living_area

        res_series.name = "kWh/m2"

        return cast(pd.Series, res_series)


if __name__ == "__main__":
    import tempfile

    from epinterface.data import DefaultDDYPath, DefaultEPWPath

    lib_base_path = Path("D:/climatestudio/Default")
    lib = ClimateStudioLibrary.Load(lib_base_path)

    # the default library has some errors in its export which
    # need to be fixed
    for zone_def in lib.ZoneDefinition.values():
        zone_def.Infiltration = "Residential"
        zone_def.Constructions = "UVal_0.4_Light"

    model = Model(
        geometry=ShoeboxGeometry(
            x=0,
            y=0,
            w=10,
            d=10,
            h=6,
            num_stories=2,
            basement_depth=None,
            zoning="core/perim",
            roof_height=None,
        ),
        zone_name="Residential",
        library=lib,
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        epw_path = DefaultEPWPath
        ddy_path = DefaultDDYPath
        config = SimulationPathConfig(
            output_dir=output_dir, epw_path=epw_path, ddy_path=ddy_path
        )
        idf, sql = model.simulate(config)
        results = model.standard_results_postprocess(sql)
        err_files = filter(
            lambda x: x.suffix == ".err",
            [idf.output_directory / Path(f) for f in idf.simulation_files],
        )
        for file in err_files:
            print(file.read_text())
        print(results)
