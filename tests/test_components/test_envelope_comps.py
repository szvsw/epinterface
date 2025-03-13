"""Tests for adding envelope components to an IDF."""

import pytest
from archetypal.idfclass import IDF

from epinterface.interface import InfDesignFlowRateCalculationMethodType
from epinterface.sbem.components.envelope import InfiltrationComponent


@pytest.mark.parametrize(
    "is_on,rates,calculation_method_main,calculation_method_attic",
    [
        (True, (0.5, 0.0002), "Flow/ExteriorArea", "AirChanges/Hour"),
        (False, (0.25, 0.0001), "AirChanges/Hour", "Flow/ExteriorArea"),
    ],
)
def test_infiltration_comp(
    idf: IDF,
    is_on: bool,
    rates: tuple[float, float],
    calculation_method_main: InfDesignFlowRateCalculationMethodType,
    calculation_method_attic: InfDesignFlowRateCalculationMethodType,
):
    """Test the infiltration component."""
    inf_name = "Test_Infiltration"
    main_zone_name = "Test_Zone"
    attic_zone_name = "Test_Zone_Attic"
    main_ach, main_flow_rate = rates
    attic_ach, attic_flow_rate = main_ach * 2, main_flow_rate * 2
    expected_main_inf_name = f"{main_zone_name}_{inf_name}_INFILTRATION"
    expected_attic_inf_name = f"{attic_zone_name}_{inf_name}_INFILTRATION"
    infiltration = InfiltrationComponent(
        Name=inf_name,
        AirChangesPerHour=main_ach,
        FlowPerExteriorSurfaceArea=main_flow_rate,
        CalculationMethod=calculation_method_main,
        IsOn=is_on,
        ConstantCoefficient=0.606,
        TemperatureCoefficient=3.6359996e-2,
        WindVelocityCoefficient=0.117765,
        WindVelocitySquaredCoefficient=0,
        AFNAirMassFlowCoefficientCrack=0,
    )
    assert not idf.getobject("ZONEINFILTRATION:DESIGNFLOWRATE", expected_main_inf_name)
    assert not idf.getobject("ZONEINFILTRATION:DESIGNFLOWRATE", expected_attic_inf_name)
    attic_infiltration = infiltration.model_copy(
        deep=True,
        update={
            "Name": f"{infiltration.Name}_Attic",
            "AirChangesPerHour": attic_ach,
            "FlowPerExteriorSurfaceArea": attic_flow_rate,
            "CalculationMethod": calculation_method_attic,
        },
    )
    idf = infiltration.add_infiltration_to_idf_zone(idf, main_zone_name)
    idf = attic_infiltration.add_infiltration_to_idf_zone(idf, attic_zone_name)

    main_inf = idf.getobject("ZONEINFILTRATION:DESIGNFLOWRATE", expected_main_inf_name)
    attic_inf = idf.getobject(
        "ZONEINFILTRATION:DESIGNFLOWRATE", expected_attic_inf_name
    )
    if is_on:
        assert main_inf is not None
        assert main_inf.Air_Changes_per_Hour == main_ach
        assert main_inf.Flow_Rate_per_Exterior_Surface_Area == main_flow_rate
        assert main_inf.Calculation_Method == calculation_method_main
        assert attic_inf is not None
        assert attic_inf.Flow_Rate_per_Exterior_Surface_Area == attic_flow_rate
        assert attic_inf.Air_Changes_per_Hour == attic_ach
        assert attic_inf.Calculation_Method == calculation_method_attic
    else:
        assert main_inf is None
        assert attic_inf is None
