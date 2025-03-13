"""Fixtures for the tests."""

import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from archetypal.idfclass import IDF

from epinterface.data import EnergyPlusArtifactDir
from epinterface.sbem.prisma.client import PrismaSettings
from epinterface.sbem.prisma.seed_fns import (
    create_dhw_systems,
    create_envelope,
    create_hvac_systems,
    create_operations,
    create_schedules,
    create_space_use_children,
    create_zone,
)


@pytest.fixture(scope="package")
def preseeded_readonly_db():
    """Create a database with schedules and space use children to be used in other tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "test.db"
        settings = PrismaSettings.New(
            database_path=database_path, if_exists="raise", auto_register=False
        )
        with settings.db:
            create_schedules(settings.db)
            last_space_use_name = create_space_use_children(settings.db)
            last_hvac_name = create_hvac_systems(settings.db)
            last_dhw_name = create_dhw_systems(settings.db)
            _last_ops_name = create_operations(
                settings.db, last_space_use_name, last_hvac_name, last_dhw_name
            )

            create_envelope(settings.db)
            create_zone(settings.db)

            yield settings.db


@pytest.fixture(scope="function")
def idf() -> Generator[IDF, None, None]:
    """Create a new IDF object."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base_filepath = EnergyPlusArtifactDir / "Minimal.idf"
        target_base_filepath = Path(temp_dir) / "Minimal.idf"
        shutil.copy(base_filepath, target_base_filepath)
        idf = IDF(
            target_base_filepath.as_posix(),
            as_version=None,  # pyright: ignore [reportArgumentType]
            prep_outputs=True,
            output_directory=temp_dir,
        )
        yield idf
