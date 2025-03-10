"""Test for the prisma database."""

import tempfile
from pathlib import Path
from typing import Literal

import pytest
from prisma import Prisma
from prisma.errors import RecordNotFoundError

from epinterface.sbem.prisma.client import PrismaSettings, deep_fetcher
from epinterface.sbem.prisma.seed_fns import create_schedule


@pytest.mark.parametrize("exists", ["raise", "overwrite", "migrate", "ignore"])
def test_create_db_without_conflicts(
    exists: Literal["raise", "overwrite", "migrate", "ignore"],
):
    """Test creating a database with the given exists argument but no existing database."""
    with tempfile.TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "test.db"
        assert not database_path.exists()
        settings = PrismaSettings.New(
            database_path=database_path, if_exists=exists, auto_register=False
        )
        assert database_path.exists()
        with settings.db:
            assert settings.db.year.find_many() == []


@pytest.mark.parametrize("exists", ["raise", "overwrite", "migrate", "ignore"])
def test_create_db_with_conflicts(
    exists: Literal["raise", "overwrite", "migrate", "ignore"],
):
    """Test creating a database with the given exists argument but an existing database."""
    with tempfile.TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "test.db"
        settings_og = PrismaSettings.New(
            database_path=database_path, if_exists="raise", auto_register=False
        )
        with settings_og.db:
            create_schedule(settings_og.db, "Test")

        if exists == "raise":
            with pytest.raises(FileExistsError, match="Database file"):
                settings = PrismaSettings.New(
                    database_path=database_path, if_exists=exists, auto_register=False
                )
        elif exists == "overwrite":
            settings = PrismaSettings.New(
                database_path=database_path, if_exists=exists, auto_register=False
            )
            assert database_path.exists()
            assert database_path.with_suffix(".db.bak").exists()
            with settings.db:
                assert len(settings.db.year.find_many()) == 0
        elif exists == "migrate":
            settings = PrismaSettings.New(
                database_path=database_path, if_exists=exists, auto_register=False
            )
            assert database_path.exists()
            assert database_path.with_suffix(".db.bak").exists()
            with settings.db:
                assert len(settings.db.year.find_many()) == 1
        elif exists == "ignore":
            settings = PrismaSettings.New(
                database_path=database_path, if_exists=exists, auto_register=False
            )
            assert database_path.exists()
            assert not database_path.with_suffix(".db.bak").exists()
            with settings.db:
                assert len(settings.db.year.find_many()) == 1


def test_deep_fetch_lighting(preseeded_readonly_db: Prisma):
    """Test the deep fetch of a lighting object."""
    lighting, lighting_comp = deep_fetcher.Lighting.get_deep_object("new_cold_office")
    assert lighting_comp.PowerDensity == lighting.PowerDensity
    assert lighting_comp.Schedule.Name == lighting.Schedule.Name
    with pytest.raises(RecordNotFoundError):
        deep_fetcher.Lighting.get_deep_object("new_cold_office_does_not_exist")


def test_deep_fetch_equipment(preseeded_readonly_db: Prisma):
    """Test the deep fetch of an equipment object."""
    equipment, equipment_comp = deep_fetcher.Equipment.get_deep_object("new_office")
    assert equipment_comp.PowerDensity == equipment.PowerDensity
    assert equipment_comp.Schedule.Name == equipment.Schedule.Name
    with pytest.raises(RecordNotFoundError):
        deep_fetcher.Equipment.get_deep_object("new_cold_office_does_not_exist")


def test_deep_fetch_thermostat(preseeded_readonly_db: Prisma):
    """Test the deep fetch of a thermostat object."""
    thermostat, thermostat_comp = deep_fetcher.Thermostat.get_deep_object("cold_office")
    assert thermostat_comp.HeatingSchedule.Name == thermostat.HeatingSchedule.Name
    assert thermostat_comp.CoolingSchedule.Name == thermostat.CoolingSchedule.Name


def test_deep_fetch_occupancy(preseeded_readonly_db: Prisma):
    """Test the deep fetch of an occupancy object."""
    occupancy, occupancy_comp = deep_fetcher.Occupancy.get_deep_object("office")
    assert occupancy_comp.Schedule.Name == occupancy.Schedule.Name
    with pytest.raises(RecordNotFoundError):
        deep_fetcher.Occupancy.get_deep_object("new_cold_office_does_not_exist")


def test_deep_fetch_water_use(preseeded_readonly_db: Prisma):
    """Test the deep fetch of a water use object."""
    water_use, water_use_comp = deep_fetcher.WaterUse.get_deep_object("office")
    assert water_use_comp.Schedule.Name == water_use.Schedule.Name
    with pytest.raises(RecordNotFoundError):
        deep_fetcher.WaterUse.get_deep_object("new_cold_office_does_not_exist")


def test_deep_fetch_space_use(preseeded_readonly_db: Prisma):
    """Test the deep fetch of a space use object."""
    space_use, space_use_comp = deep_fetcher.SpaceUse.get_deep_object("default")
    assert space_use_comp.Lighting.Name == space_use.Lighting.Name
    assert space_use_comp.Equipment.Name == space_use.Equipment.Name
    assert space_use_comp.Occupancy.Name == space_use.Occupancy.Name
    assert space_use_comp.WaterUse.Name == space_use.WaterUse.Name
    assert space_use_comp.Thermostat.Name == space_use.Thermostat.Name


def test_deep_fetch_ventilation(preseeded_readonly_db: Prisma):
    """Test the deep fetch of a ventilation object."""
    hvac, hvac_comp = deep_fetcher.HVAC.get_deep_object("cold_office")
    assert hvac_comp.ConditioningSystems.Heating is not None
    assert hvac_comp.ConditioningSystems.Cooling is not None
    assert (
        hvac_comp.Ventilation.Schedule.Weeks[0].Week.Name == "Ventilation_RegularWeek"
    )


def test_deep_fetch_thermal_system(preseeded_readonly_db: Prisma):
    """Test the deep fetch of a thermal system object."""
    thermal_system, thermal_system_comp = deep_fetcher.ThermalSystem.get_deep_object(
        "Heating_cold_office"
    )
    assert thermal_system_comp.DistributionCOP == thermal_system.DistributionCOP
    assert thermal_system_comp.SystemCOP == thermal_system.SystemCOP
    assert thermal_system_comp.Fuel == thermal_system.Fuel
    assert thermal_system_comp.ConditioningType == thermal_system.ConditioningType
    with pytest.raises(RecordNotFoundError):
        deep_fetcher.ThermalSystem.get_deep_object("new_cold_office_does_not_exist")


def test_deep_fetch_dhw_system(preseeded_readonly_db: Prisma):
    """Test the deep fetch of a dhw system object."""
    dhw_system, dhw_system_comp = deep_fetcher.DHW.get_deep_object("good")
    assert dhw_system_comp.FuelType == dhw_system.FuelType
    assert dhw_system_comp.SystemCOP == dhw_system.SystemCOP
    assert dhw_system_comp.DistributionCOP == dhw_system.DistributionCOP
    assert dhw_system_comp.WaterTemperatureInlet == dhw_system.WaterTemperatureInlet
    assert dhw_system_comp.WaterSupplyTemperature == dhw_system.WaterSupplyTemperature
    assert dhw_system_comp.IsOn == dhw_system.IsOn
    with pytest.raises(RecordNotFoundError):
        deep_fetcher.DHW.get_deep_object("new_cold_office_does_not_exist")


def test_deep_fetch_conditioning_system(preseeded_readonly_db: Prisma):
    """Test the deep fetch of a conditioning system object."""
    conditioning_system, conditioning_system_comp = (
        deep_fetcher.ConditioningSystems.get_deep_object("cold_office")
    )
    if (
        conditioning_system_comp.Heating is None
        or conditioning_system_comp.Cooling is None
    ):
        pytest.fail(
            reason="No heating or cooling system found in the conditioning comp, which is unexpected."
        )
    if conditioning_system.Heating is None or conditioning_system.Cooling is None:
        pytest.fail(
            reason="No heating or cooling system found in the conditioning system, which is unexpected."
        )
    assert conditioning_system_comp.Heating.Name == conditioning_system.Heating.Name
    assert conditioning_system_comp.Cooling.Name == conditioning_system.Cooling.Name
    with pytest.raises(RecordNotFoundError):
        deep_fetcher.ConditioningSystems.get_deep_object(
            "new_cold_office_does_not_exist"
        )


def test_deep_fetch_hvac(preseeded_readonly_db: Prisma):
    """Test the deep fetch of a hvac object."""
    hvac, hvac_comp = deep_fetcher.HVAC.get_deep_object("cold_office")
    assert hvac_comp.ConditioningSystems.Name == hvac.ConditioningSystems.Name
    assert hvac_comp.Ventilation.Name == hvac.Ventilation.Name
    with pytest.raises(RecordNotFoundError):
        deep_fetcher.HVAC.get_deep_object("new_cold_office_does_not_exist")


def test_deep_fetch_operations(preseeded_readonly_db: Prisma):
    """Test the deep fetch of an operations object."""
    operations, operations_comp = deep_fetcher.Operations.get_deep_object("default_ops")
    assert operations_comp.SpaceUse.Name == operations.SpaceUse.Name
    assert operations_comp.SpaceUse.Equipment.Name == operations.SpaceUse.Equipment.Name
    assert operations_comp.SpaceUse.Lighting.Name == operations.SpaceUse.Lighting.Name
    assert (
        operations_comp.SpaceUse.Thermostat.Name == operations.SpaceUse.Thermostat.Name
    )
    assert operations_comp.SpaceUse.Occupancy.Name == operations.SpaceUse.Occupancy.Name
    assert operations_comp.SpaceUse.WaterUse.Name == operations.SpaceUse.WaterUse.Name
    assert operations_comp.HVAC.Name == operations.HVAC.Name
    assert operations_comp.DHW.Name == operations.DHW.Name
    with pytest.raises(RecordNotFoundError):
        deep_fetcher.Operations.get_deep_object("new_cold_office_does_not_exist")


@pytest.mark.skip(reason="not implemented")
def test_fetch_schedules_ordering(preseeded_readonly_db: Prisma):
    """Test the ordering of schedules, specifically that the repeated weeks are in correct order sorted by starting month then starting day."""
    pass


def test_deep_fetch_construction_assembly_ordering(preseeded_readonly_db: Prisma):
    """Test the ordering of construction assemblies."""
    construction_assembly, construction_assembly_comp = (
        deep_fetcher.ConstructionAssembly.get_deep_object("Roof")
    )
    layer_order = [layer.LayerOrder for layer in construction_assembly.Layers]
    # TODO: this is relying on the fact that they are out of order in the db write;
    # this should be done with a newly created construction assembly wihtin this test to
    # make sure if the seed_fn changes that this test is no longer invalid.
    assert layer_order == [0, 1, 2, 3]
    layer_order_comp = [layer.LayerOrder for layer in construction_assembly_comp.Layers]
    assert layer_order_comp == [0, 1, 2, 3]
    for i in range(4):
        assert (
            construction_assembly_comp.Layers[i].ConstructionMaterial.Name
            == construction_assembly.Layers[i].ConstructionMaterial.Name
        )


def test_deep_fetch_envelope_assembly(preseeded_readonly_db: Prisma):
    """Test the deep fetch of an envelope assembly object."""
    envelope_assembly, envelope_assembly_comp = (
        deep_fetcher.EnvelopeAssembly.get_deep_object("default")
    )
    assert (
        envelope_assembly_comp.RoofAssembly.Name == envelope_assembly.RoofAssembly.Name
    )
    assert (
        envelope_assembly_comp.RoofAssembly.Layers[0].ConstructionMaterial.Name
        == envelope_assembly.RoofAssembly.Layers[0].ConstructionMaterial.Name
    )


def test_deep_fetch_glazing_construction(preseeded_readonly_db: Prisma):
    """Test the deep fetch of a glazing construction object."""
    glazing_construction, glazing_construction_comp = (
        deep_fetcher.GlazingConstructionSimple.get_deep_object("single")
    )
    assert glazing_construction_comp.Name == glazing_construction.Name
    assert glazing_construction_comp.UValue == glazing_construction.UValue
    assert glazing_construction_comp.SHGF == glazing_construction.SHGF
    assert glazing_construction_comp.TVis == glazing_construction.TVis
    assert glazing_construction_comp.Type == glazing_construction.Type


def test_deep_fetch_infiltration(preseeded_readonly_db: Prisma):
    """Test the deep fetch of an infiltration object."""
    infiltration, infiltration_comp = deep_fetcher.Infiltration.get_deep_object(
        "office_unweatherized"
    )
    assert infiltration_comp.Name == infiltration.Name
    assert infiltration_comp.IsOn == infiltration.IsOn
    assert infiltration_comp.AirChangesPerHour == infiltration.AirChangesPerHour
    assert infiltration_comp.CalculationMethod == infiltration.CalculationMethod


def test_deep_fetch_envelope(preseeded_readonly_db: Prisma):
    """Test the deep fetch of an envelope object."""
    envelope, envelope_comp = deep_fetcher.Envelope.get_deep_object("default_env")
    assert envelope_comp.Name == envelope.Name

    _expected_assemblies, expected_assemblies_comp = (
        deep_fetcher.EnvelopeAssembly.get_deep_object("default")
    )
    _expected_infiltration, expected_infiltration_comp = (
        deep_fetcher.Infiltration.get_deep_object("office_unweatherized")
    )
    _expected_window, expected_window_comp = (
        deep_fetcher.GlazingConstructionSimple.get_deep_object("single")
    )

    assert envelope_comp.Assemblies == expected_assemblies_comp
    assert envelope_comp.Infiltration == expected_infiltration_comp
    assert envelope_comp.Window == expected_window_comp


def test_deep_fetch_zone(preseeded_readonly_db: Prisma):
    """Test the deep fetch of a zone object."""
    zone, zone_comp = deep_fetcher.Zone.get_deep_object("default_zone")
    assert zone_comp.Name == zone.Name
    assert zone_comp.Envelope.Name == zone.Envelope.Name
    assert zone_comp.Operations.Name == zone.Operations.Name

    _expected_envelope, expected_envelope_comp = deep_fetcher.Envelope.get_deep_object(
        "default_env"
    )
    _expected_operations, expected_operations_comp = (
        deep_fetcher.Operations.get_deep_object("default_ops")
    )

    assert zone_comp.Envelope == expected_envelope_comp
    assert zone_comp.Operations == expected_operations_comp


def test_deep_fetch_zone_with_second_db(preseeded_readonly_db: Prisma):
    """Test the deep fetch of a zone object with a second database does not conflict with the  first.."""
    assert preseeded_readonly_db.is_registered()

    ds = preseeded_readonly_db._datasource
    assert ds is not None
    url = ds["url"]
    fp = url.split("file:")[-1]
    new_db = PrismaSettings.New(
        database_path=Path(fp), if_exists="ignore", auto_register=False
    ).db
    with new_db:
        zone, zone_comp = deep_fetcher.Zone.get_deep_object("default_zone", db=new_db)
        assert zone_comp.Name == zone.Name
        assert zone_comp.Envelope.Name == zone.Envelope.Name
        assert zone_comp.Operations.Name == zone.Operations.Name
