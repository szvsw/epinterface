"""Test for the prisma database."""

import tempfile
from pathlib import Path
from typing import Literal

import pytest
from prisma import Prisma
from prisma.errors import RecordNotFoundError

from epinterface.sbem.prisma.client import PrismaSettings, deep_fetcher
from epinterface.sbem.prisma.seed_fns import (
    create_dhw_systems,
    create_hvac_systems,
    create_operations,
    create_schedule,
    create_schedules,
    create_space_use_children,
)


@pytest.fixture(scope="module")
def db_with_schedules_and_space_use_children():
    """Create a database with schedules and space use children to be used in other tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "test.db"
        settings = PrismaSettings.New(database_path=database_path, if_exists="raise")
        with settings.db:
            create_schedules(settings.db)
            last_space_use_name = create_space_use_children(settings.db)
            last_hvac_name = create_hvac_systems(settings.db)
            last_dhw_name = create_dhw_systems(settings.db)
            _last_ops_name = create_operations(
                settings.db, last_space_use_name, last_hvac_name, last_dhw_name
            )

            yield settings.db


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


def test_deep_fetch_lighting(db_with_schedules_and_space_use_children: Prisma):
    """Test the deep fetch of a lighting object."""
    lighting, lighting_comp = deep_fetcher.Lighting.get_deep_object("new_cold_office")
    assert lighting_comp.PowerDensity == lighting.PowerDensity
    assert lighting_comp.Schedule.Name == lighting.Schedule.Name
    with pytest.raises(RecordNotFoundError):
        deep_fetcher.Lighting.get_deep_object("new_cold_office_does_not_exist")


def test_deep_fetch_ventilation(db_with_schedules_and_space_use_children: Prisma):
    """Test the deep fetch of a ventilation object."""
    hvac, hvac_comp = deep_fetcher.HVAC.get_deep_object("cold_office")
    assert hvac_comp.ConditioningSystems.Heating is not None
    assert hvac_comp.ConditioningSystems.Cooling is not None
    assert (
        hvac_comp.Ventilation.Schedule.Weeks[0].Week.Name == "Ventilation_RegularWeek"
    )


def test_deep_fetch_operations(db_with_schedules_and_space_use_children: Prisma):
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


@pytest.mark.skip(reason="not implemented")
def test_fetch_schedules_ordering(db_with_schedules_and_space_use_children: Prisma):
    """Test the ordering of schedules."""
    pass


@pytest.mark.skip(reason="not implemented")
def test_fetch_construction_assembly_ordering(
    db_with_schedules_and_space_use_children: Prisma,
):
    """Test the ordering of construction assemblies."""
    pass


# def test_db_path_does_not_exist():
#     prisma_settings.database_path = Path("does_not_exist.db")
#     db = prisma_settings.db
#     with db:
#         assert db.year.find_many() == []
