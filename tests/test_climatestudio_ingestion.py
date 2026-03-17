"""End-to-end test for ClimateStudio JSON ingestion and downstream usage."""

import tempfile
from pathlib import Path

import pytest

from epinterface.sbem.builder import (
    construct_zone_def,
)
from epinterface.sbem.components.zones import ZoneComponent
from epinterface.sbem.ingestion import add_climatestudio_to_db
from epinterface.sbem.prisma.client import PrismaSettings


@pytest.fixture(scope="module")
def climatestudio_db_and_map():
    """Create DB from ClimateStudio template and minimal component map."""
    template_path = Path(__file__).parent / "data" / "climatestudio" / "template.json"
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "climatestudio.db"
        component_map_path = Path(temp_dir) / "component-map.yaml"

        settings = PrismaSettings.New(
            database_path=db_path, if_exists="raise", auto_register=False
        )
        with settings.db:
            add_climatestudio_to_db(
                template_path, settings.db, erase_db=True, template_name="TestTemplate"
            )

        component_map_path.write_text(
            "selector:\n  source_fields: [zone_name]\n",
            encoding="utf-8",
        )

        yield db_path, component_map_path


def test_climatestudio_ingestion_construct_zone_def(
    climatestudio_db_and_map: tuple[Path, Path],
):
    """construct_zone_def returns valid ZoneComponent from ClimateStudio-ingested db."""
    db_path, component_map_path = climatestudio_db_and_map

    zone = construct_zone_def(
        component_map_path=component_map_path,
        db_path=db_path,
        semantic_field_context={"zone_name": "Zone_0"},
    )

    assert isinstance(zone, ZoneComponent)
    assert zone.Name == "Zone_0"
    assert zone.Envelope is not None
    assert zone.Operations is not None
    assert zone.Operations.SpaceUse is not None
    assert zone.Operations.HVAC is not None
    assert zone.Operations.DHW is not None
