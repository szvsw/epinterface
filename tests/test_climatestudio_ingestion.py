"""End-to-end test for ClimateStudio JSON ingestion and downstream usage."""

import tempfile
from pathlib import Path

import pytest

from epinterface.geometry import ShoeboxGeometry
from epinterface.sbem.builder import (
    AtticAssumptions,
    BasementAssumptions,
    Model,
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
            add_climatestudio_to_db(template_path, settings.db, erase_db=True)

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


@pytest.mark.skip(
    reason="requires network and weather download; run manually to verify full simulation"
)
def test_climatestudio_ingestion_model_run(
    climatestudio_db_and_map: tuple[Path, Path],
):
    """Model can run simulation using zone from ClimateStudio-ingested db."""
    db_path, component_map_path = climatestudio_db_and_map

    zone = construct_zone_def(
        component_map_path=component_map_path,
        db_path=db_path,
        semantic_field_context={"zone_name": "Zone_0"},
    )

    model = Model(
        Weather=(
            "https://climate.onebuilding.org/WMO_Region_6_Europe/GBR_United_Kingdom/ENG_England/GBR_ENG_London.Heathrow.037760_TMYx.2009-2023.zip"
        ),  # pyright: ignore [reportArgumentType]
        Zone=zone,
        geometry=ShoeboxGeometry(
            x=0,
            y=0,
            w=10,
            d=10,
            h=3,
            wwr=0.3,
            num_stories=1,
            zoning="by_storey",
            basement=False,
            roof_height=None,
            exposed_basement_frac=0.25,
        ),
        Attic=AtticAssumptions(Conditioned=False, UseFraction=None),
        Basement=BasementAssumptions(Conditioned=False, UseFraction=None),
    )

    results = model.run()
    assert results.idf is not None
    assert results.energy_and_peak is not None
    assert (
        "TotalSiteEnergy" in results.energy_and_peak.index
        or len(results.energy_and_peak) > 0
    )
