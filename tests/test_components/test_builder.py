"""Test the builder."""

from prisma import Prisma
from pydantic import AnyUrl

from epinterface.geometry import ShoeboxGeometry
from epinterface.sbem.builder import Model
from epinterface.sbem.prisma.client import deep_fetcher


def test_builder(preseeded_readonly_db: Prisma):
    """Test the builder."""
    _, zone = deep_fetcher.Zone.get_deep_object("default_zone", preseeded_readonly_db)

    model = Model(
        Weather=AnyUrl(
            "https://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/USA_United_States_of_America/MA_Massachusetts/USA_MA_Boston-Logan.Intl.AP.725090_TMYx.2009-2023.zip"
        ),
        Zone=zone,
        basement_insulation_surface=None,
        conditioned_basement=False,
        basement_use_fraction=None,
        attic_insulation_surface=None,
        conditioned_attic=False,
        attic_use_fraction=None,
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

    _idf, results, _err_text = model.run(move_energy=False)


# TODO: add parameterized tests for different attic/basement configurations
# and check almost all individual parameters in the returned idf model.
