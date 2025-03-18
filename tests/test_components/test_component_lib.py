"""Test ingesting an excel spreadsheet into a database."""

import tempfile
from pathlib import Path

import pytest
from prisma import Prisma

from epinterface.sbem.interface import add_excel_to_db
from epinterface.sbem.prisma.client import PrismaSettings


@pytest.fixture(scope="module")
def writeable_db():
    """Create a database with schedules and space use children to be used in other tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "test.db"
        settings = PrismaSettings.New(
            database_path=database_path, if_exists="raise", auto_register=False
        )
        with settings.db:
            yield settings.db


def test_add_excel_to_db(writeable_db: Prisma):
    """Test that adding an excel file to the database works."""
    path_to_excel = Path("tests/data/0318_Template_MAWebApp.xlsx")
    add_excel_to_db(path_to_excel, writeable_db, erase_db=True)
    assert writeable_db.year.count() > 0
    assert writeable_db.week.count() > 0
    assert writeable_db.day.count() > 0
    assert writeable_db.occupancy.count() > 0
    assert writeable_db.lighting.count() > 0
    assert writeable_db.equipment.count() > 0
    assert writeable_db.thermostat.count() > 0
    assert writeable_db.wateruse.count() > 0
    assert writeable_db.spaceuse.count() > 0
    assert writeable_db.thermalsystem.count() > 0
    assert writeable_db.conditioningsystems.count() > 0
    assert writeable_db.ventilation.count() > 0
    assert writeable_db.hvac.count() > 0
    assert writeable_db.dhw.count() > 0
    assert writeable_db.infiltration.count() > 0
    assert writeable_db.glazingconstructionsimple.count() > 0
    assert writeable_db.constructionmaterial.count() > 0
    assert writeable_db.envelopeassembly.count() > 0
    assert writeable_db.constructionassembly.count() > 0
    assert writeable_db.envelope.count() > 0

    assert writeable_db.zone.count() == 0
    assert writeable_db.operations.count() == 0


# TODO: test erase_db behavior
