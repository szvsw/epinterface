"""Fixtures for the tests."""

import tempfile
from pathlib import Path

import pytest

from epinterface.sbem.prisma.client import PrismaSettings
from epinterface.sbem.prisma.seed_fns import (
    create_dhw_systems,
    create_hvac_systems,
    create_operations,
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
