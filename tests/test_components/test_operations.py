"""A module for testing the operations component."""

import pytest
from archetypal.idfclass import IDF
from prisma import Prisma

from epinterface.sbem.prisma.client import deep_fetcher


@pytest.mark.skip(reason="Not yet implmented")
@pytest.mark.parametrize(
    "is_on,supply_temp,inlet_temp,flow_rate_per_person",
    [(False, 10, 55, 0.1), (True, 10, 55, 0.1)],
)
def test_operations_add_hot_water_to_idf(
    idf: IDF,
    preseeded_readonly_db: Prisma,
    is_on: bool,
    supply_temp: float,
    inlet_temp: float,
    flow_rate_per_person: float,
):
    """Testing adding hot water to the idf."""
    _zone_record, zone = deep_fetcher.Zone.get_deep_object(
        "default_zone", preseeded_readonly_db
    )
    # idf = geometry.add(idf)
    # zone.Operations.DHW.IsOn = is_on
    # zone.Operations.DHW.WaterSupplyTemperature = supply_temp
    # zone.Operations.DHW.WaterTemperatureInlet = inlet_temp
    # zone.Operations.SpaceUse.WaterUse.FlowRatePerPerson = flow_rate_per_person

    # for idf_zone in idf.idfobjects["ZONE"]:
    #     zone_name = idf_zone.Name
    #     expected_water_name = f"{zone_name}_{zone.Operations.SpaceUse.WaterUse.safe_name}_{zone.Operations.DHW.safe_name}_WATER"
    #     assert not idf.getobject("WATERUSE:EQUIPMENT", expected_water_name)
    #     idf = zone.Operations.add_water_use_to_idf_zone(idf, zone_name)
    #     water_use = idf.getobject("WATERUSE:EQUIPMENT", expected_water_name)
    #     if is_on:
    #         assert water_use
    #     TODO: complit explicitly expected flow rates using prior knowledge of fixture zone areas.
    #         zone_area = 100 if idf_zone.Floor_Area == 0 else idf_zone.Floor_Area
    #         assert water_use.Peak_Flow_Rate == flow_rate_per_person * zone_area *
    #     else:
    #         assert not water_use
