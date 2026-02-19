"""Tests for construct_zone_def."""

import tempfile
from pathlib import Path

import pytest

from epinterface.sbem.builder import construct_zone_def
from epinterface.sbem.components.zones import ZoneComponent
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


@pytest.fixture(scope="module")
def preseeded_db_path_and_component_map():
    """Create a preseeded database and minimal component map for construct_zone_def tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        component_map_path = Path(temp_dir) / "component-map.yaml"

        settings = PrismaSettings.New(
            database_path=db_path, if_exists="raise", auto_register=False
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

        component_map_path.write_text(
            "selector:\n  source_fields: [basic]\n",
            encoding="utf-8",
        )

        yield db_path, component_map_path


def test_construct_zone_def_returns_zone_component(
    preseeded_db_path_and_component_map: tuple[Path, Path],
):
    """Test that construct_zone_def returns a valid ZoneComponent from the preseeded db."""
    db_path, component_map_path = preseeded_db_path_and_component_map

    zone = construct_zone_def(
        component_map_path=component_map_path,
        db_path=db_path,
        semantic_field_context={"basic": "default_zone"},
    )

    assert isinstance(zone, ZoneComponent)
    assert zone.Name == "default_zone"
    assert zone.Envelope is not None
    assert zone.Operations is not None
    assert zone.Envelope.Name == "default_env"
    assert zone.Operations.Name == "default_ops"
