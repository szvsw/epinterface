"""Fixtures for floor-aware SBEM tests."""

import pytest

from epinterface.sbem.zone_assignment import ZoneTemplate


@pytest.fixture
def base_zone_template() -> ZoneTemplate:
    """Return a simple valid zone template for floor-assignment tests."""
    return ZoneTemplate(
        FacadeRValue=3.0,
        RoofRValue=3.0,
        SlabRValue=3.0,
        WindowUValue=3.0,
        WindowSHGF=0.7,
        WindowTVis=0.5,
        WWR=0.2,
        InfiltrationACH=0.5,
        VentFlowRatePerArea=0.001,
        VentFlowRatePerPerson=0.0085,
        VentProvider="Mechanical",
        VentHRV="NoHRV",
        VentEconomizer="NoEconomizer",
        VentDCV="NoDCV",
        DHWFlowRatePerPerson=0.010,
        DHWFuel="Electricity",
        DHWSystemCOP=1.0,
        DHWDistributionCOP=1.0,
        EquipmentPowerDensity=25,
        LightingPowerDensity=10,
        OccupantDensity=0.01,
        EquipmentBase=0.4,
        EquipmentAMInterp=0.5,
        EquipmentLunchInterp=0.8,
        EquipmentPMInterp=0.5,
        EquipmentWeekendPeakInterp=0.25,
        EquipmentSummerPeakInterp=0.5,
        LightingBase=0.3,
        LightingAMInterp=0.75,
        LightingLunchInterp=0.75,
        LightingPMInterp=0.9,
        LightingWeekendPeakInterp=0.75,
        LightingSummerPeakInterp=0.9,
        OccupancyBase=0.05,
        OccupancyAMInterp=0.25,
        OccupancyLunchInterp=0.9,
        OccupancyPMInterp=0.5,
        OccupancyWeekendPeakInterp=0.15,
        OccupancySummerPeakInterp=0.85,
        HeatingSetpointBase=21,
        SetpointDeadband=2,
        HeatingSetpointSetback=2,
        CoolingSetpointSetback=2,
        NightSetback=0.5,
        WeekendSetback=0.5,
        SummerSetback=0.5,
        HeatingFuel="Electricity",
        CoolingFuel="Electricity",
        HeatingSystemCOP=1.0,
        CoolingSystemCOP=1.0,
        HeatingDistributionCOP=1.0,
        CoolingDistributionCOP=1.0,
    )
