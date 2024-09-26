"""A simple model for automatically constructing a shoebox building energy model."""

import logging
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Annotated

import httpx
import pandas as pd
from archetypal.idfclass import IDF
from archetypal.schedule import Schedule
from archetypal.schedule import ScheduleTypeLimits as AScheduleTypeLimits
from pydantic import AfterValidator, AnyUrl, BaseModel, Field, UrlConstraints

from epinterface.ddy_injector_bayes import DDYSizingSpec
from epinterface.geometry import ZoneDimensions
from epinterface.interface import (
    Construction,
    DefaultMaterialLibrary,
    ElectricEquipment,
    HVACTemplateThermostat,
    HVACTemplateZoneIdealLoadsAirSystem,
    Lights,
    People,
    RunPeriod,
    SimpleGlazingMaterial,
    SimulationControl,
    Timestep,
    ZoneInfiltrationDesignFlowRate,
    ZoneList,
)

logger = logging.getLogger(__name__)


class NotAZipError(ValueError):
    """Raised when a URL does not end with a .zip extension."""

    def __init__(self) -> None:
        """Initialize the error."""
        super().__init__("The URL provided does not end with a .zip extension.")


def check_path_ends_with_zip(url: AnyUrl):
    """Check that the path of the URL ends with a .zip extension.

    Args:
        url (AnyUrl): The URL to check.

    Raises:
        NotAZipError: If the URL does not end with a .zip extension.

    Returns:
        AnyUrl: The URL.
    """
    if not url.path:
        raise NotAZipError()
    if not url.path.endswith(".zip"):
        raise NotAZipError()
    return url


WeatherUrl = Annotated[
    Annotated[AnyUrl, UrlConstraints(allowed_schemes=["s3", "https", "http", "file"])],
    AfterValidator(check_path_ends_with_zip),
]


class BaseWeather(BaseModel):
    """A base class for fetching weather files.

    Responsible for fetching weather files from a URL and extracting the .epw and .ddy files.

    Also takes care of caching the weather files in a directory.
    """

    Weather: WeatherUrl = Field(
        default="https://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/USA_United_States_of_America/MA_Massachusetts/USA_MA_Boston-Logan.Intl.AP.725090_TMYx.2009-2023.zip"
    )

    async def fetch_weather(self, cache_dir: Path | str):
        """Fetch the weather file from the URL and extract the .epw and .ddy files.

        Args:
            cache_dir (Path | str): The directory to cache the weather files.

        Returns:
            Tuple[Path, Path]: The path to the .epw and .ddy files.
        """
        if isinstance(cache_dir, str):
            cache_dir = Path(cache_dir)

        if not self.Weather.path or not self.Weather.path.endswith(".zip"):
            raise NotAZipError()

        weather_path = Path(self.Weather.path).relative_to("/")
        weather_dir = cache_dir / weather_path.with_suffix("")
        epw_path = weather_dir / weather_path.with_suffix(".epw").name
        ddy_path = weather_dir / weather_path.with_suffix(".ddy").name
        weather_dir.mkdir(parents=True, exist_ok=True)
        if not epw_path.exists() or not ddy_path.exists():
            logger.info(f"Fetching weather file from {self.Weather}")
            # fetch the .zip file, unzip it, and extract the .epw and .ddy files
            client = httpx.AsyncClient()
            response = await client.get(str(self.Weather))
            with tempfile.TemporaryFile() as f:
                f.write(response.content)
                f.seek(0)
                with zipfile.ZipFile(f, "r") as z:
                    # z.extractall(weather_dir)
                    z.extract(epw_path.name, weather_dir)
                    z.extract(ddy_path.name, weather_dir)
            await client.aclose()
        else:
            logger.info(f"Using cached weather file from {weather_dir}")
        return epw_path, ddy_path


class SimpleResidentialModel(BaseWeather, extra="allow"):
    """A simple model for automatically constructing a shoebox building energy model."""

    EPD: float = 9.0
    LPD: float = 4.0
    WWR: float = 0.15
    WindowU: float = 2.7
    WindowSHGC: float = 0.763
    HeatingSetpoint: float = 19
    CoolingSetpoint: float = 24
    PeopleDensity: float = 0.05
    Infiltration: float = 0.1
    timestep: int = 6

    async def build(
        self, output_dir: Path | str, weather_cache_dir: Path | str | None = None
    ) -> IDF:
        """Build the energy model.

        Args:
            output_dir (Path | str): The directory to save the IDF file.
            weather_cache_dir (Path | str | None): The directory to cache the weather files.

        Returns:
            IDF: The constructed IDF model.
        """
        if isinstance(output_dir, str):
            output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        material_lib = DefaultMaterialLibrary()
        weather_cache_dir = Path(weather_cache_dir) if weather_cache_dir else output_dir
        epw_path, ddy_path = await self.fetch_weather(weather_cache_dir)
        schedules = pd.read_parquet(
            Path(__file__).parent / "data" / "res_schedules.parquet"
        )

        shutil.copy(
            Path(__file__).parent / "data" / "Minimal.idf",
            output_dir / "Minimal.idf",
        )
        idf = IDF(
            (output_dir / "Minimal.idf").as_posix(),
            epw=(epw_path.as_posix()),
            output_directory=output_dir.as_posix(),
            prep_outputs=True,
        )  # pyright: ignore [reportArgumentType]
        ddy = IDF(
            (ddy_path.as_posix()),
            as_version="9.2.0",
            file_version="9.2.0",
            prep_outputs=False,
        )
        ddyspec = DDYSizingSpec(match=True)
        ddyspec.inject_ddy(idf, ddy)

        # Configure simulation
        sim_control = SimulationControl(
            Do_Zone_Sizing_Calculation="Yes",
            Do_System_Sizing_Calculation="Yes",
            Do_Plant_Sizing_Calculation="Yes",
            Run_Simulation_for_Sizing_Periods="Yes",
            Run_Simulation_for_Weather_File_Run_Periods="Yes",
            Do_HVAC_Sizing_Simulation_for_Sizing_Periods="Yes",
        )
        sim_control.add(idf)

        # Configure run period
        run_period = RunPeriod(
            Name="Year",
            Use_Weather_File_Daylight_Saving_Period="No",
            Use_Weather_File_Rain_Indicators="No",
            Use_Weather_File_Snow_Indicators="No",
            Use_Weather_File_Holidays_and_Special_Days="No",
            Begin_Month=1,
            Begin_Day_of_Month=1,
            End_Month=12,
            End_Day_of_Month=31,
            Day_of_Week_for_Start_Day="Sunday",
        )
        run_period.add(idf)

        # configure timestep
        timestep = Timestep(
            Number_of_Timesteps_per_Hour=self.timestep,
        )
        timestep.add(idf)

        # create constant scheds
        always_on_schedule = Schedule.constant_schedule(Name="Always_On", value=1)
        always_off_schedule = Schedule.constant_schedule(Name="Always_Off", value=0)
        year, *_ = always_on_schedule.to_year_week_day()
        year.to_epbunch(idf)
        year, *_ = always_off_schedule.to_year_week_day()
        year.to_epbunch(idf)

        always_on_schedule = Schedule.constant_schedule(Name="Always On", value=1)
        always_off_schedule = Schedule.constant_schedule(Name="Always Off", value=0)
        year, *_ = always_on_schedule.to_year_week_day()
        year.to_epbunch(idf)
        year, *_ = always_off_schedule.to_year_week_day()
        year.to_epbunch(idf)

        always_on_schedule = Schedule.constant_schedule(Name="On", value=1)
        always_off_schedule = Schedule.constant_schedule(Name="Off", value=0)
        year, *_ = always_on_schedule.to_year_week_day()
        year.to_epbunch(idf)
        year, *_ = always_off_schedule.to_year_week_day()
        year.to_epbunch(idf)

        # Handle Geometry
        zone_dims = ZoneDimensions(
            x=0,
            y=0,
            w=10,
            d=10,
            h=3,
            num_stories=3,
            roof_height=2.5,  # zoning='core/perim'
        )
        idf = zone_dims.add(idf)
        idf.set_default_constructions()
        idf.intersect_match()

        # Handle Windows
        window_walls = [
            w
            for w in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
            if w.Outside_Boundary_Condition.lower() == "outdoors"
            and "attic" not in w.Zone_Name.lower()
            and w.Surface_Type.lower() == "wall"
        ]
        idf.set_wwr(
            wwr=self.WWR,
            construction="Project External Window",
            force=True,
            surfaces=window_walls,
        )
        window_construction = Construction(
            name="Project External Window",
            layers=[
                SimpleGlazingMaterial(
                    Name="DefaultGlazing",
                    Solar_Heat_Gain_Coefficient=self.WindowSHGC,
                    UFactor=self.WindowU,
                    Visible_Transmittance=0.7,
                )
            ],
        )
        window_construction.add(idf)

        # Handle Wall Constructions
        wall_construction = Construction(
            name="Project Wall",  # NB/TODO: this is the name set by geomeppy
            layers=[
                material_lib.stucco.as_layer(thickness=0.03),
                material_lib.insulation.as_layer(thickness=0.15),
                material_lib.gypsum.as_layer(thickness=0.02),
            ],
        )
        wall_construction.add(idf)

        # Handle Roof Constructions
        # roof_construction = Construction(
        #     name="Project Flat Roof",
        #     layers=[
        #         material_lib.stucco.as_layer(thickness=0.03),
        #         material_lib.insulation.as_layer(thickness=0.15),
        #         material_lib.gypsum.as_layer(thickness=0.02),
        #     ],
        # )
        # roof_construction.add(idf)

        # TODO: handle other constructions.

        # Handle Zone List
        zone_names = [
            zone.Name
            for zone in idf.idfobjects["ZONE"]
            if "attic" not in zone.Name.lower()
        ]
        zone_list = ZoneList(Name="Conditioned_Zones", Names=zone_names)
        zone_list.add(idf)

        # Handle HVAC
        thermostat = HVACTemplateThermostat(
            Name="Thermostat",
            Constant_Heating_Setpoint=self.HeatingSetpoint,
            Constant_Cooling_Setpoint=self.CoolingSetpoint,
        )
        thermostat.add(idf)
        for zone in idf.idfobjects["ZONE"]:
            zone_name = zone.Name
            if "attic" in zone_name.lower():
                continue
            hvac_template = HVACTemplateZoneIdealLoadsAirSystem(
                Zone_Name=zone_name,
                Template_Thermostat_Name=thermostat.Name,
            )
            idf = hvac_template.add(idf)

        # Handle People
        occ_sched, *_ = Schedule.from_values(
            "Occupancy_sch",
            Values=schedules.Occupancy.values.tolist(),
            Type="fraction",
        ).to_year_week_day()
        any_number_lim = AScheduleTypeLimits(
            Name="any number", LowerLimit=None, UpperLimit=None
        )
        any_number_lim.to_epbunch(idf)
        acti_year, *_ = Schedule.constant_schedule(
            value=117.28,  # pyright: ignore [reportArgumentType]
            Name="Activity_Schedule",
            Type="any number",
        ).to_year_week_day()
        occ_sched.to_epbunch(idf)
        acti_year.to_epbunch(idf)
        people = People(
            Name="People",
            Zone_or_ZoneList_Name=zone_list.Name,
            Number_of_People_Schedule_Name=occ_sched.Name,
            Activity_Level_Schedule_Name=acti_year.Name,
            Number_of_People_Calculation_Method="People/Area",
            People_per_Floor_Area=self.PeopleDensity,
        )
        people.add(idf)

        # Handle Infiltration
        infiltration = ZoneInfiltrationDesignFlowRate(
            Name="Infiltration",
            Zone_or_ZoneList_Name=zone_list.Name,
            Schedule_Name=always_on_schedule.Name,
            Design_Flow_Rate_Calculation_Method="AirChanges/Hour",
            Flow_Rate_per_Exterior_Surface_Area=self.Infiltration,
        )
        infiltration.add(idf)

        # Handle Equipment
        equip_sched, *_ = Schedule.from_values(
            "Equipment_sch",
            Values=schedules.Equipment.values.tolist(),
            Type="fraction",
        ).to_year_week_day()
        equip_sched.to_epbunch(idf)
        equipment = ElectricEquipment(
            Name="Equipment",
            Zone_or_ZoneList_Name=zone_list.Name,
            Schedule_Name=equip_sched.Name,
            Design_Level_Calculation_Method="Watts/Area",
            Watts_per_Zone_Floor_Area=self.EPD,
        )
        equipment.add(idf)

        # Handle Lights
        lights_sched, *_ = Schedule.from_values(
            "Lights_sch",
            Values=schedules.Lights.values.tolist(),
            Type="fraction",
        ).to_year_week_day()
        lights_sched.to_epbunch(idf)
        lights = Lights(
            Name="Lights",
            Zone_or_ZoneList_Name=zone_list.Name,
            Schedule_Name=lights_sched.Name,
            Design_Level_Calculation_Method="Watts/Area",
            Watts_per_Zone_Floor_Area=self.LPD,
        )
        lights.add(idf)

        # Handle Water
        # TODO: energy only changes with flow rate because no heater is provided.
        # water_flow_sch, *_ = Schedule.constant_schedule(Name="Water_Flow", value=0.1).to_year_week_day()
        # water_flow_sch.to_epbunch(idf)
        # target_temp_sch, *_ = Schedule.constant_schedule(Name="Target_Temperature", value=10, Type="Temperature").to_year_week_day()
        # target_temp_sch.to_epbunch(idf)
        # water = WaterUseEquipment(
        #     Name="DHW",
        #     Peak_Flow_Rate=0.0001,
        #     Flow_Rate_Fraction_Schedule_Name=water_flow_sch.Name,
        #     Hot_Water_Supply_Temperature_Schedule_Name=target_temp_sch.Name,
        #     # Zone_Name=
        #     # Latent_Fraction_Schedule_Name=
        #     # Sensible_Fraction_Schedule_Name=
        # )
        # water.add(idf)

        # TODO: should we be using a slab processor?

        return idf
