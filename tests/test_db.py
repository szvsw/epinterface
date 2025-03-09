"""Test for the prisma database."""

import tempfile
from pathlib import Path
from typing import Literal

import pytest
from prisma import Prisma
from prisma.models import Day
from prisma.types import DayCreateInput, WeekCreateInput

from epinterface.sbem.prisma.client import PrismaSettings, deep_fetcher


def create_schedule(db: Prisma, name_prefix: str):
    """Create a schedule for the given name prefix."""
    with db.tx() as tx:
        day_create_input: DayCreateInput = {
            "Name": f"{name_prefix} Monday",
            "Type": "Fraction",
            "Hour_00": 0,
            "Hour_01": 0,
            "Hour_02": 0,
            "Hour_03": 0,
            "Hour_04": 0,
            "Hour_05": 0,
            "Hour_06": 0,
            "Hour_07": 0,
            "Hour_08": 0,
            "Hour_09": 0,
            "Hour_10": 0,
            "Hour_11": 0,
            "Hour_12": 0,
            "Hour_13": 0,
            "Hour_14": 0,
            "Hour_15": 0,
            "Hour_16": 0,
            "Hour_17": 0,
            "Hour_18": 0,
            "Hour_19": 0,
            "Hour_20": 0,
            "Hour_21": 0,
            "Hour_22": 0,
            "Hour_23": 0,
        }
        day_creations_for_whole_week = {
            "Monday": day_create_input,
            "Tuesday": day_create_input,
            "Wednesday": day_create_input,
            "Thursday": day_create_input,
            "Friday": day_create_input,
            "Saturday": day_create_input,
            "Sunday": day_create_input,
        }
        created_days: dict[str, Day] = {}
        for day_name, day_create_input in day_creations_for_whole_week.items():
            day_create_input["Name"] = f"{name_prefix}_{day_name}"
            day = tx.day.create(data=day_create_input)
            created_days[day_name] = day

        week_a_create_input: WeekCreateInput = {
            "Name": f"{name_prefix}_RegularWeek",
            "Monday": {"connect": {"id": created_days["Monday"].id}},
            "Tuesday": {"connect": {"id": created_days["Tuesday"].id}},
            "Wednesday": {"connect": {"id": created_days["Wednesday"].id}},
            "Thursday": {"connect": {"id": created_days["Thursday"].id}},
            "Friday": {"connect": {"id": created_days["Friday"].id}},
            "Saturday": {"connect": {"id": created_days["Saturday"].id}},
            "Sunday": {"connect": {"id": created_days["Sunday"].id}},
        }
        week_a = tx.week.create(data=week_a_create_input)
        week_b_create_input: WeekCreateInput = {
            "Name": f"{name_prefix}_All_Monday",
            "Monday": {"connect": {"id": created_days["Monday"].id}},
            "Tuesday": {"connect": {"id": created_days["Monday"].id}},
            "Wednesday": {"connect": {"id": created_days["Monday"].id}},
            "Thursday": {"connect": {"id": created_days["Monday"].id}},
            "Friday": {"connect": {"id": created_days["Monday"].id}},
            "Saturday": {"connect": {"id": created_days["Monday"].id}},
            "Sunday": {"connect": {"id": created_days["Monday"].id}},
        }
        week_b = tx.week.create(data=week_b_create_input)
        tx.year.create(
            data={
                "Name": f"{name_prefix}_Year",
                "Type": "Fraction",
                "Weeks": {
                    "create": [
                        {
                            "Week": {"connect": {"id": week_a.id}},  # pyright: ignore [reportArgumentType]
                            "StartDay": 1,
                            "StartMonth": 1,
                            "EndDay": 30,
                            "EndMonth": 6,
                        },
                        {
                            "Week": {"connect": {"id": week_b.id}},
                            "StartDay": 1,
                            "StartMonth": 7,
                            "EndDay": 31,
                            "EndMonth": 12,
                        },
                    ]
                },
            }
        )


def create_schedules(db: Prisma):
    """Create schedules for the given database for the typical uses."""
    create_schedule(db, "Lights")
    create_schedule(db, "Equipment")
    create_schedule(db, "Occupancy")
    create_schedule(db, "WaterUse")
    create_schedule(db, "Heating")
    create_schedule(db, "Cooling")
    create_schedule(db, "Ventilation")


def create_space_use_children(db: Prisma):
    """Create space use children objects for the given database for the typical uses."""
    typologies = ["office", "residential"]
    ages = ["new", "old"]
    locations = ["cold", "warm"]
    for typology in typologies:
        epd = 10 if typology == "office" else 20
        for age in ages:
            epd = epd * 0.83 if age == "new" else epd
            db.equipment.create(
                data={
                    "Name": f"{age}_{typology}",
                    "Schedule": {"connect": {"Name": "Equipment_Year"}},
                    "PowerDensity": epd,
                    "IsOn": True,
                }
            )

    for typology in typologies:
        lpd = 10 if typology == "office" else 20
        for age in ages:
            lpd = lpd * 0.8 if age == "old" else lpd
            for loc in locations:
                lpd = lpd * 1.23 if loc == "cold" else lpd
                db.lighting.create(
                    data={
                        "Name": f"{age}_{loc}_{typology}",
                        "Schedule": {"connect": {"Name": "Lights_Year"}},
                        "PowerDensity": lpd,
                        "DimmingType": "Stepped" if typology == "office" else "Off",
                        "IsOn": True,
                    }
                )

    for typology in typologies:
        for loc in locations:
            db.thermostat.create(
                data={
                    "Name": f"{loc}_{typology}",
                    "HeatingSchedule": {"connect": {"Name": "Heating_Year"}},
                    "CoolingSchedule": {"connect": {"Name": "Cooling_Year"}},
                    "IsOn": True,
                    "HeatingSetpoint": 20 if loc == "cold" else 23,
                    "CoolingSetpoint": 24 if typology == "office" else 23,
                }
            )

    for typology in typologies:
        db.occupancy.create(
            data={
                "Name": typology,
                "Schedule": {"connect": {"Name": "Occupancy_Year"}},
                "PeopleDensity": 0.05 if typology == "office" else 0.01,
                "IsOn": True,
                "MetabolicRate": 1.2,
            }
        )


@pytest.fixture(scope="module")
def db_with_schedules_and_space_use_children():
    """Create a database with schedules and space use children to be used in other tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "test.db"
        settings = PrismaSettings.New(database_path=database_path, if_exists="raise")
        with settings.db:
            create_schedules(settings.db)
            create_space_use_children(settings.db)
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


def test_deep_fetch(db_with_schedules_and_space_use_children: Prisma):
    """Test the deep fetch of a lighting object."""
    lighting, lighting_comp = deep_fetcher.Lighting.get_deep_object("new_cold_office")
    assert lighting_comp.PowerDensity == lighting.PowerDensity
    assert lighting_comp.Schedule.Name == lighting.Schedule.Name


# def test_db_path_does_not_exist():
#     prisma_settings.database_path = Path("does_not_exist.db")
#     db = prisma_settings.db
#     with db:
#         assert db.year.find_many() == []
