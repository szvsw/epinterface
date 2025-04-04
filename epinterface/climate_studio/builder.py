"""A module for building the energy model using the Climate Studio API."""

import asyncio
import gc
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import cast
from uuid import uuid4

import pandas as pd
from archetypal.idfclass import IDF
from archetypal.idfclass.sql import Sql
from pydantic import BaseModel, Field
from shapely import Polygon

from epinterface.climate_studio.interface import (
    ClimateStudioLibraryV2,
    SurfaceHandlers,
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
    SiteGroundTemperature,
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
    conditioned_basement: bool = False
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

    @property
    def total_conditioned_area(self) -> float:
        """The total conditioned area of the model.

        Returns:
            float: The total conditioned area of the model.
        """
        return self.geometry.total_living_area + (
            self.geometry.footprint_area
            if self.geometry.basement and self.conditioned_basement
            else 0
        )

    @property
    def total_people(self) -> float:
        """The total number of people in the model.

        Returns:
            ppl (float): The total number of people in the model

        """
        ppl_per_m2 = (
            self.space_use.Loads.PeopleDensity if self.space_use.Loads.PeopleIsOn else 0
        )
        total_area = self.total_conditioned_area
        total_ppl = ppl_per_m2 * total_area
        return total_ppl

    def compute_dhw(self) -> float:
        """Compute the domestic hot water energy demand.

        Returns:
            energy (float): The domestic hot water energy demand (kWh/m2)
        """
        # TODO: this should be computed from the DHW schedule
        if not self.space_use.HotWater.IsOn:
            return 0
        flow_rate_per_person = self.space_use.HotWater.FlowRatePerPerson  # m3/hr/person
        temperature_rise = (
            self.space_use.HotWater.WaterSupplyTemperature
            - self.space_use.HotWater.WaterTemperatureInlet
        )  # K
        water_density = 1000  # kg/m3
        c = 4186  # J/kg.K
        total_flow_rate = flow_rate_per_person * self.total_people  # m3/hr
        total_volume = total_flow_rate * 8760  # m3 / yr
        total_energy = total_volume * temperature_rise * water_density * c  # J / yr
        total_energy_kWh = total_energy / 3600000  # kWh / yr
        total_energy_kWh_per_m2 = (
            total_energy_kWh / self.total_conditioned_area
        )  # kWh/m2 / yr
        return total_energy_kWh_per_m2

    def build(self, config: SimulationPathConfig) -> IDF:
        """Build the energy model using the Climate Studio API.

        Args:
            config (SimulationConfig): The configuration for the simulation.

        Returns:
            IDF: The built energy model.
        """
        if (not self.geometry.basement) and self.conditioned_basement:
            raise ValueError("CONDITIONEDBASEMENT:TRUE:BASEMENT:FALSE")

        if self.geometry.roof_height:
            raise ClimateStudioBuilderNotImplementedError("roof_height")
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
        self.lib.Schedules.update(scheds)

        idf = SiteGroundTemperature.FromValues([
            18.3,
            18.2,
            18.3,
            18.4,
            20.1,
            22.0,
            22.3,
            22.5,
            22.5,
            20.7,
            18.9,
            18.5,
            # 18,
            # 18,
            # 18,
            # 18,
            # 18,
            # 18,
            # 18,
            # 18,
            # 18,
            # 18,
            # 18,
            # 18,
            # 7.9,
            # 6.05,
            # 5.65,
            # 6.21,
            # 8.98,
            # 11.97,
            # 14.71,
            # 16.62,
            # 17.06,
            # 15.98,
            # 13.61,
            # 10.71,
            # 1.11,
            # 0.1,
            # 1.89,
            # 4.69,
            # 12.02,
            # 17.68,
            # 21.5,
            # 22.66,
            # 20.68,
            # 16.29,
            # 10.42,
            # 4.97,
        ]).add(idf)

        idf = self.geometry.add(idf)

        # construct zone lists
        idf, conditioned_zone_list, all_zones_list = self.add_zone_lists(idf)

        # TODO: Handle separately ventilated attic/basement?
        idf = self.add_space_use(idf, self.space_use, conditioned_zone_list)
        idf = self.add_envelope(idf, self.envelope, all_zones_list)

        return idf

    def add_hot_water_to_zone_list(
        self, idf: IDF, space_use: ZoneUse, zone_list: ZoneList
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

    def add_hot_water_to_zone(
        self, idf: IDF, space_use: ZoneUse, zone_name: str
    ) -> IDF:
        """Add the hot water to the zone.

        Args:
            idf (IDF): The IDF model to add the hot water to.
            space_use (ZoneUse): The zone use template.
            zone_name (str): The name of the zone to add the hot water to.

        Returns:
            idf (IDF): The IDF model with the added hot water.
        """
        zone = next(filter(lambda x: x.Name == zone_name, idf.idfobjects["ZONE"]), None)
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
        ppl_density = space_use.Loads.PeopleDensity
        total_ppl = ppl_density * area
        idf = space_use.HotWater.add_water_to_idf_zone(idf, zone.Name, total_ppl)
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

        handlers = SurfaceHandlers.Default()
        idf = handlers.handle_envelope(idf, self.lib, constructions, window_def)

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
        conditioned_zone_names = [
            zone.Name
            for zone in idf.idfobjects["ZONE"]
            if "attic" not in zone.Name.lower()
            and (
                not zone.Name.lower().endswith(self.geometry.basement_suffix.lower())
                if ((not self.conditioned_basement) and self.geometry.basement)
                else True
            )
        ]

        conditioned_storey_count = self.geometry.num_stories + (
            1 if self.conditioned_basement else 0
        )
        zones_per_storey = 1 if self.geometry.zoning == "by_storey" else 5
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

    def add_infiltration(
        self, idf: IDF, infiltration: ZoneInfiltration, zone_list: ZoneList
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
        idf = self.add_hot_water_to_zone_list(idf, space_use, zone_list)
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
        gc.collect()
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
            heat_cop = self.space_use.Conditioning.HeatingCOP
            cool_cop = self.space_use.Conditioning.CoolingCOP
            dhw_cop = self.space_use.HotWater.DomHotWaterCOP
            heat_fuel = self.space_use.Conditioning.HeatingFuelType
            cool_fuel = self.space_use.Conditioning.CoolingFuelType
            dhw_fuel = self.space_use.HotWater.HotWaterFuelType
            heat_energy = res_series["District Heating"] / heat_cop
            cool_energy = res_series["District Cooling"] / cool_cop
            dhw_energy = res_series["Domestic Hot Water"] / dhw_cop
            if heat_fuel not in res_series.index:
                res_series[heat_fuel] = 0
            if cool_fuel not in res_series.index:
                res_series[cool_fuel] = 0
            if dhw_fuel not in res_series.index:
                res_series[dhw_fuel] = 0
            res_series[heat_fuel] += heat_energy
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


# TODO: move to interface?
if __name__ == "__main__":
    import asyncio
    import json

    # import tempfile
    from pydantic import AnyUrl

    with open("notebooks/everett_lib.json") as f:
        lib_data = json.load(f)
    lib = ClimateStudioLibraryV2.model_validate(lib_data)
    for env in lib.Envelopes.values():
        if env.WindowDefinition is None:
            msg = f"Envelope {env.Name} has no window definition"
            raise ValueError(msg)
        env.WindowDefinition.Construction = "Template_post_2003"

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
            basement=False,
            zoning="by_storey",
            roof_height=None,
        ),
    )

    idf, results, err_text = model.run(move_energy=False)
    print(results)
