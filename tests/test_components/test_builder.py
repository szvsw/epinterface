"""Test the builder."""

from prisma import Prisma

from epinterface.data import DefaultEPWZipPath
from epinterface.geometry import ShoeboxGeometry
from epinterface.sbem.builder import (
    ZONE_TIMESTEP_WHOLE_BUILDING_METERS,
    AtticAssumptions,
    BasementAssumptions,
    Model,
    build_output_meter_requests,
)
from epinterface.sbem.prisma.client import deep_fetcher


def test_builder(preseeded_readonly_db: Prisma):
    """Test the builder."""
    _, zone = deep_fetcher.Zone.get_deep_object("default_zone", preseeded_readonly_db)

    model = Model(
        Weather=DefaultEPWZipPath,
        Zone=zone,
        Basement=BasementAssumptions(
            Conditioned=False,
            UseFraction=None,
        ),
        Attic=AtticAssumptions(
            Conditioned=False,
            UseFraction=None,
        ),
        geometry=ShoeboxGeometry(
            x=0,
            y=0,
            w=10,
            d=10,
            h=3,
            wwr=0.2,
            num_stories=2,
            basement=False,
            zoning="by_storey",
            roof_height=None,
        ),
    )

    _r = model.run()


def test_build_output_meter_requests_includes_whole_building_meter_at_zone_timestep():
    requests = build_output_meter_requests(
        ep_version_major=24,
        include_zone_timestep_meters=True,
    )

    zone_timestep_meters = {
        request["Key_Name"]
        for request in requests
        if request["key"] == "OUTPUT:METER"
        and request["Reporting_Frequency"] == "Zone Timestep"
    }

    assert set(ZONE_TIMESTEP_WHOLE_BUILDING_METERS).issubset(zone_timestep_meters)


# TODO: add parameterized tests for different attic/basement configurations
# and check almost all individual parameters in the returned idf model.
