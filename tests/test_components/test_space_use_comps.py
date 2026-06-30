"""Test the space use components."""

import pytest
from archetypal.idfclass.idf import IDF
from prisma import Prisma

from epinterface.data import DefaultEPWPath, DefaultMinimalIDFPath
from epinterface.geometry import ShoeboxGeometry
from epinterface.interface import ZoneList
from epinterface.sbem.components.schedules import (
    DayComponent,
    WeekComponent,
    YearComponent,
)
from epinterface.sbem.components.space_use import (
    DimmingTypeType,
    EquipmentComponent,
    LightingComponent,
    OccupancyComponent,
    ThermostatComponent,
    WaterUseComponent,
    ZoneSpaceUseComponent,
)
from epinterface.sbem.exceptions import NotImplementedParameter
from epinterface.sbem.prisma.client import deep_fetcher
from epinterface.settings import energyplus_settings


@pytest.fixture(scope="function")
def schedule(preseeded_readonly_db: Prisma):
    """Get the schedule name for the default zone."""
    year, year_comp = deep_fetcher.Year.get_deep_object(
        "Lights_Year", preseeded_readonly_db
    )
    return year_comp


@pytest.fixture(scope="function")
def simple_fraction_schedule():
    """Build a small in-memory lighting schedule without using Prisma."""
    day = DayComponent(
        Name="AlwaysOnDay",
        Type="Fraction",
        **{f"Hour_{hour:02d}": 1.0 for hour in range(24)},
    )
    week = WeekComponent(
        Name="AlwaysOnWeek",
        Monday=day,
        Tuesday=day,
        Wednesday=day,
        Thursday=day,
        Friday=day,
        Saturday=day,
        Sunday=day,
    )
    return YearComponent(
        Name="AlwaysOnYear",
        Type="Lighting",
        January=week,
        February=week,
        March=week,
        April=week,
        May=week,
        June=week,
        July=week,
        August=week,
        September=week,
        October=week,
        November=week,
        December=week,
    )


@pytest.fixture(scope="function")
def daylighting_idf():
    """Create an IDF for daylighting unit tests without writing to temp files."""
    return IDF(
        DefaultMinimalIDFPath.as_posix(),
        epw=DefaultEPWPath.as_posix(),
        as_version=energyplus_settings.energyplus_version,
        file_version=energyplus_settings.energyplus_version,
    )


@pytest.mark.parametrize("is_on", [True, False])
def test_add_lighting_to_idf_zone(idf: IDF, schedule: YearComponent, is_on: bool):
    """Test the add_lighting_to_idf_zone method."""
    component_name = "new_office"
    schedule_name = schedule.Name
    zone_name = "some_zone"
    expected_idf_obj_name = f"{zone_name}_{component_name}_LIGHTS"
    # expected_schedule_name = f"{expected_idf_obj_name}_YEAR_{schedule_name}"
    expected_schedule_name = schedule_name

    lighting = LightingComponent(
        Name=component_name,
        PowerDensity=10,
        Schedule=schedule,
        IsOn=is_on,
        DimmingType="Off",
    )
    assert not idf.idfobjects["LIGHTS"]
    assert not idf.idfobjects["SCHEDULE:YEAR"]
    idf = lighting.add_lights_to_idf_zone(idf, zone_name)
    if is_on:
        assert idf.idfobjects["LIGHTS"]
        assert idf.idfobjects["LIGHTS"][0].Name == expected_idf_obj_name
        assert idf.idfobjects["LIGHTS"][0].Schedule_Name == expected_schedule_name
        assert (
            idf.idfobjects["LIGHTS"][0].Zone_or_ZoneList_or_Space_or_SpaceList_Name
            == zone_name
        )
        assert idf.idfobjects["SCHEDULE:YEAR"]
        assert idf.idfobjects["SCHEDULE:YEAR"][0].Name == expected_schedule_name
    else:
        assert not idf.idfobjects["LIGHTS"]
        assert not idf.idfobjects["SCHEDULE:YEAR"]


@pytest.mark.parametrize("dimming_type", ["Stepped", "ContinuousOff"])
def test_add_lighting_to_idf_zone_rejects_unsupported_dimming_type(
    daylighting_idf: IDF,
    simple_fraction_schedule: YearComponent,
    dimming_type: DimmingTypeType,
):
    """Test stored dimming values can deserialize but unsupported modes fail."""
    lighting = LightingComponent(
        Name="new_office",
        PowerDensity=10,
        Schedule=simple_fraction_schedule,
        IsOn=True,
        DimmingType=dimming_type,
    )

    # Stepped and ContinuousOff can exist in source data, but are not implemented.
    with pytest.raises(NotImplementedParameter):
        lighting.add_lights_to_idf_zone(daylighting_idf, "default_zone")


def test_add_lighting_to_idf_zone_with_continuous_dimming(
    daylighting_idf: IDF, simple_fraction_schedule: YearComponent
):
    """Test continuous dimming adds lights and daylighting controls."""
    geom = ShoeboxGeometry(
        x=0,
        y=0,
        w=10,
        d=10,
        h=3.5,
        num_stories=1,
        zoning="by_storey",
        basement=False,
        wwr=0.15,
        roof_height=None,
    )
    idf = geom.add(daylighting_idf)
    zone_name = idf.idfobjects["ZONE"][0].Name

    lighting = LightingComponent(
        Name="new_office",
        PowerDensity=10,
        Schedule=simple_fraction_schedule,
        IsOn=True,
        DimmingType="Continuous",
    )

    idf = lighting.add_lights_to_idf_zone(idf, zone_name)

    lights = idf.idfobjects["LIGHTS"]
    reference_points = idf.idfobjects["DAYLIGHTING:REFERENCEPOINT"]
    controls = idf.idfobjects["DAYLIGHTING:CONTROLS"]

    assert len(lights) == 1
    assert len(reference_points) == 1
    assert len(controls) == 1

    light = lights[0]
    reference_point = reference_points[0]
    control = controls[0]
    name_prefix = f"{zone_name}_new_office_LIGHTS"

    assert light.Name == name_prefix
    assert light.Zone_or_ZoneList_or_Space_or_SpaceList_Name == zone_name

    # Daylighting currently assumes one center-point sensor for one real zone.
    assert reference_point.Name == f"{name_prefix}_DaylightRefPt"
    assert reference_point.Zone_or_Space_Name == zone_name
    assert control.Name == f"{name_prefix}_DaylightControls"
    assert control.Zone_or_Space_Name == zone_name
    assert control.Lighting_Control_Type == "Continuous"
    assert control.Daylighting_Reference_Point_1_Name == reference_point.Name

    # The current daylighting implementation uses one fixed 300 lux setpoint.
    assert control.Fraction_of_Lights_Controlled_by_Reference_Point_1 == 1.0
    assert control.Illuminance_Setpoint_at_Reference_Point_1 == 300
    assert (
        control.Minimum_Input_Power_Fraction_for_Continuous_or_ContinuousOff_Dimming_Control
        == 0.3
    )
    assert (
        control.Minimum_Light_Output_Fraction_for_Continuous_or_ContinuousOff_Dimming_Control
        == 0.2
    )

    # Eppy pre-fills unused extensible fields; the wrapper trims after ref point 1.
    last_idx = control.fieldnames.index("Illuminance_Setpoint_at_Reference_Point_1")
    assert len(control.obj) == last_idx + 1
    assert control.fieldnames.index("Daylighting_Reference_Point_2_Name") >= len(
        control.obj
    )


def test_add_lighting_to_idf_zone_with_continuous_dimming_rejects_zone_list(
    daylighting_idf: IDF, simple_fraction_schedule: YearComponent
):
    """Test daylighting dimming rejects zone lists."""
    geom = ShoeboxGeometry(
        x=0,
        y=0,
        w=10,
        d=10,
        h=3.5,
        num_stories=1,
        zoning="by_storey",
        basement=False,
        wwr=0.15,
        roof_height=None,
    )
    idf = geom.add(daylighting_idf)
    zone_name = idf.idfobjects["ZONE"][0].Name
    zone_list = ZoneList(Name="Test_Zone_List", Names=[zone_name])
    idf = zone_list.add(idf)

    lighting = LightingComponent(
        Name="new_office",
        PowerDensity=10,
        Schedule=simple_fraction_schedule,
        IsOn=True,
        DimmingType="Continuous",
    )

    # Daylighting:Controls targets a single zone in this implementation, not a list.
    with pytest.raises(ValueError, match="zone list"):
        lighting.add_lights_to_idf_zone(idf, zone_list.Name)


@pytest.mark.parametrize("is_on,density", [(True, 10), (False, 0)])
def test_add_people_to_idf_zone(
    idf: IDF, schedule: YearComponent, is_on: bool, density: float
):
    """Test the add_people_to_idf_zone method."""
    component_name = "new_office"
    schedule.Name = "some_people_schedule"
    schedule_name = schedule.Name
    zone_name = "default_zone"
    expected_idf_obj_name = f"{zone_name}_{component_name}_PEOPLE"
    # expected_schedule_name = f"{expected_idf_obj_name}_YEAR_{schedule_name}"
    expected_schedule_name = schedule_name
    expected_activity_schedule_name = f"{expected_idf_obj_name}_Activity_Schedule"

    occupancy = OccupancyComponent(
        Name=component_name,
        PeopleDensity=density,
        Schedule=schedule,
        IsOn=is_on,
        MetabolicRate=1.3,
    )

    assert not idf.idfobjects["PEOPLE"]
    assert not idf.idfobjects["SCHEDULE:YEAR"]
    idf = occupancy.add_people_to_idf_zone(idf, zone_name)
    if is_on:
        assert idf.idfobjects["PEOPLE"]
        assert idf.idfobjects["PEOPLE"][0].Name == expected_idf_obj_name
        assert idf.idfobjects["PEOPLE"][0].People_per_Floor_Area == density
        assert (
            idf.idfobjects["PEOPLE"][0].Number_of_People_Schedule_Name
            == expected_schedule_name
        )
        assert (
            idf.idfobjects["PEOPLE"][0].Zone_or_ZoneList_or_Space_or_SpaceList_Name
            == zone_name
        )
        assert idf.idfobjects["SCHEDULE:YEAR"]
        assert (
            idf.getobject("SCHEDULE:YEAR", expected_activity_schedule_name) is not None
        )
        assert idf.getobject("SCHEDULE:YEAR", expected_schedule_name) is not None
    else:
        assert not idf.idfobjects["PEOPLE"]


@pytest.mark.parametrize("is_on", [True, False])
def test_add_equipment_to_idf_zone(idf: IDF, schedule: YearComponent, is_on: bool):
    """Test the add_equipment_to_idf_zone method."""
    component_name = "new_office"
    schedule.Name = "some_equip_schedule"
    schedule_name = schedule.Name
    zone_name = "default_zone"
    expected_idf_obj_name = f"{zone_name}_{component_name}_EQUIPMENT"
    # expected_schedule_name = f"{expected_idf_obj_name}_YEAR_{schedule_name}"
    expected_schedule_name = schedule_name
    equipment = EquipmentComponent(
        Name=component_name,
        PowerDensity=10,
        Schedule=schedule,
        IsOn=is_on,
    )
    assert not idf.idfobjects["ELECTRICEQUIPMENT"]
    assert not idf.idfobjects["SCHEDULE:YEAR"]
    idf = equipment.add_equipment_to_idf_zone(idf, zone_name)
    if is_on:
        assert idf.idfobjects["ELECTRICEQUIPMENT"]
        assert idf.idfobjects["ELECTRICEQUIPMENT"][0].Name == expected_idf_obj_name
        assert (
            idf.idfobjects["ELECTRICEQUIPMENT"][0].Schedule_Name
            == expected_schedule_name
        )
        print(idf.idfobjects["ELECTRICEQUIPMENT"][0].__dict__)
        assert (
            idf.idfobjects["ELECTRICEQUIPMENT"][
                0
            ].Zone_or_ZoneList_or_Space_or_SpaceList_Name
            == zone_name
        )
        assert idf.idfobjects["SCHEDULE:YEAR"]
        assert idf.idfobjects["SCHEDULE:YEAR"][0].Name == expected_schedule_name
    else:
        assert not idf.idfobjects["ELECTRICEQUIPMENT"]


@pytest.mark.skip(reason="Not implemented")
def test_add_thermostat_to_idf_zone(idf: IDF):
    """Test the add_thermostat_to_idf_zone method."""
    pass


@pytest.mark.skip(reason="Not implemented")
def test_add_water_to_idf_zone(idf: IDF):
    """Test the add_water_to_idf_zone method."""
    pass


def test_add_space_use_to_idf_zone(idf: IDF, schedule: YearComponent):
    """Test the add_loads_to_idf_zone method."""
    zone_name = "default_zone"

    space_use_name = "new_dense_office_controlled"

    lighting_component_name = "new_office"
    equipment_component_name = "office"
    occupancy_component_name = "dense_office"
    thermostat_component_name = "new_office_controlled"
    water_component_name = "new_office"

    expected_equip_name = f"{zone_name}_{equipment_component_name}_EQUIPMENT"
    expected_lighting_name = f"{zone_name}_{lighting_component_name}_LIGHTS"
    expected_occupancy_name = f"{zone_name}_{occupancy_component_name}_PEOPLE"

    equip_schedule_name = "some_equip_schedule"
    lighting_schedule_name = "some_light_schedule"
    occupancy_schedule_name = "some_occupancy_schedule"
    water_schedule_name = "some_water_schedule"
    heating_schedule_name = "some_heating_schedule"
    cooling_schedule_name = "some_cooling_schedule"

    equip_schedule = schedule.model_copy(
        deep=True, update={"Name": equip_schedule_name}
    )
    light_schedule = schedule.model_copy(
        deep=True, update={"Name": lighting_schedule_name}
    )
    occupancy_schedule = schedule.model_copy(
        deep=True, update={"Name": occupancy_schedule_name}
    )
    heating_schedule = schedule.model_copy(
        deep=True, update={"Name": heating_schedule_name}
    )
    cooling_schedule = schedule.model_copy(
        deep=True, update={"Name": cooling_schedule_name}
    )
    water_schedule = schedule.model_copy(
        deep=True, update={"Name": water_schedule_name}
    )

    # expected_lighting_schedule_name = (
    #     f"{expected_lighting_name}_YEAR_{lighting_schedule_name}"
    # )
    # expected_equipment_schedule_name = (
    #     f"{expected_equip_name}_YEAR_{equip_schedule_name}"
    # )
    # expected_occupancy_schedule_name = (
    #     f"{expected_occupancy_name}_YEAR_{occupancy_schedule_name}"
    # )
    # _expected_heating_schedule_name = (
    #     f"{expected_thermostat_name}_YEAR_{heating_schedule_name}"
    # )
    # _expected_cooling_schedule_name = (
    #     f"{expected_thermostat_name}_YEAR_{cooling_schedule_name}"
    # )
    # _expected_water_schedule_name = f"{expected_water_name}_YEAR_{water_schedule_name}"
    expected_lighting_schedule_name = lighting_schedule_name
    expected_equipment_schedule_name = equip_schedule_name
    expected_occupancy_schedule_name = occupancy_schedule_name
    # expected_heating_schedule_name = heating_schedule_name
    # expected_cooling_schedule_name = cooling_schedule_name
    # expected_water_schedule_name = water_schedule_name

    lighting = LightingComponent(
        Name=lighting_component_name,
        PowerDensity=10,
        Schedule=light_schedule,
        IsOn=True,
        DimmingType="Off",
    )
    equipment = EquipmentComponent(
        Name=equipment_component_name,
        PowerDensity=10,
        Schedule=equip_schedule,
        IsOn=True,
    )
    occupancy = OccupancyComponent(
        Name=occupancy_component_name,
        PeopleDensity=10,
        Schedule=occupancy_schedule,
        IsOn=True,
        MetabolicRate=1.3,
    )
    thermostat = ThermostatComponent(
        Name=thermostat_component_name,
        HeatingSetpoint=20,
        CoolingSetpoint=25,
        HeatingSchedule=heating_schedule,
        CoolingSchedule=cooling_schedule,
        IsOn=True,
    )
    water = WaterUseComponent(
        Name=water_component_name,
        FlowRatePerPerson=0.001,
        Schedule=water_schedule,
    )
    space_use = ZoneSpaceUseComponent(
        Name=space_use_name,
        Lighting=lighting,
        Equipment=equipment,
        Occupancy=occupancy,
        Thermostat=thermostat,
        WaterUse=water,
    )

    assert not idf.idfobjects["LIGHTS"]
    assert not idf.idfobjects["ELECTRICEQUIPMENT"]
    assert not idf.idfobjects["PEOPLE"]
    assert not idf.idfobjects["HVACTEMPLATE:THERMOSTAT"]
    assert not idf.idfobjects["SCHEDULE:YEAR"]
    assert not idf.idfobjects["WATERUSE:EQUIPMENT"]

    idf = space_use.add_loads_to_idf_zone(idf, zone_name)

    assert idf.idfobjects["LIGHTS"]
    assert idf.idfobjects["ELECTRICEQUIPMENT"]
    assert idf.idfobjects["PEOPLE"]
    assert idf.idfobjects["SCHEDULE:YEAR"]

    lights_obj = idf.getobject("LIGHTS", expected_lighting_name)
    equip_obj = idf.getobject("ELECTRICEQUIPMENT", expected_equip_name)
    occupancy_obj = idf.getobject("PEOPLE", expected_occupancy_name)
    assert lights_obj is not None
    assert lights_obj.Name == expected_lighting_name
    assert lights_obj.Schedule_Name == expected_lighting_schedule_name
    assert equip_obj is not None
    assert equip_obj.Name == expected_equip_name
    assert equip_obj.Schedule_Name == expected_equipment_schedule_name
    assert occupancy_obj is not None
    assert occupancy_obj.Name == expected_occupancy_name
    assert (
        occupancy_obj.Number_of_People_Schedule_Name == expected_occupancy_schedule_name
    )

    assert idf.getobject("SCHEDULE:YEAR", expected_lighting_schedule_name) is not None
    assert idf.getobject("SCHEDULE:YEAR", expected_equipment_schedule_name) is not None
    assert idf.getobject("SCHEDULE:YEAR", expected_occupancy_schedule_name) is not None


# TODO: test with spaces/invalid chars in names
# TODO: test with incorrect schedule types
