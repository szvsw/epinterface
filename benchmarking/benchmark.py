"""Benchmark the flat model's runtime for different number of floors and with/without overheating calculation."""

import csv
from pathlib import Path
from time import perf_counter

from epinterface.analysis.overheating import (
    CountFailureCriterion,
    ExceedanceCriterion,
    HeatIndexCriteria,
    IntegratedStreakCriterion,
    OverheatingAnalysisConfig,
    StreakCriterion,
    ThermalComfortAssumptions,
    ThresholdWithCriteria,
)
from epinterface.sbem.flat_model import FlatModel
from epinterface.weather import WeatherUrl


def benchmark() -> None:
    """Benchmark the flat model's runtime for different number of floors and with/without overheating calculation."""
    base_parameters = FlatModel(
        F2FHeight=3.25,
        Width=40,
        Depth=40,
        Rotation=45,
        WWR=0.3,
        NFloors=2,
        FacadeStructuralSystem="cmu",
        FacadeCavityInsulationRValue=1.2,
        FacadeExteriorInsulationRValue=1.0,
        FacadeInteriorInsulationRValue=0.0,
        FacadeInteriorFinish="drywall",
        FacadeExteriorFinish="brick_veneer",
        RoofStructuralSystem="poured_concrete",
        RoofCavityInsulationRValue=0.0,
        RoofExteriorInsulationRValue=2.5,
        RoofInteriorInsulationRValue=0.2,
        RoofInteriorFinish="gypsum_board",
        RoofExteriorFinish="epdm_membrane",
        SlabStructuralSystem="slab_on_grade",
        SlabUnderInsulationRValue=2.2,
        SlabAboveInsulationRValue=0.0,
        SlabCavityInsulationRValue=0.0,
        SlabInteriorFinish="tile",
        SlabExteriorFinish="none",
        WindowUValue=3.0,
        WindowSHGF=0.7,
        WindowTVis=0.5,
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
        # HSPRegularWeekdayWorkhours=21,
        # HSPRegularWeekdayNight=21,
        # HSPSummerWeekdayWorkhours=21,
        # HSPSummerWeekdayNight=21,
        # HSPWeekendWorkhours=21,
        # HSPWeekendNight=21,
        # CSPRegularWeekdayWorkhours=23,
        # CSPRegularWeekdayNight=23,
        # CSPSummerWeekdayWorkhours=23,
        # CSPSummerWeekdayNight=23,
        # CSPWeekendWorkhours=23,
        # CSPWeekendNight=23,
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
        EPWURI=WeatherUrl(  # pyright: ignore [reportCallIssue]
            "https://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/USA_United_States_of_America/MA_Massachusetts/USA_MA_Bedford-Hanscom.Field.AP.744900_TMYx.2009-2023.zip"
        ),
    )

    print("Benchmarking flat model runtime")
    print("NFloors\tcalculate_overheating\telapsed_s")

    results: list[tuple[int, bool, float]] = []

    for num_floors in [1, 2, 4, 8, 16, 32]:
        for calculate_overheating in (False, True):
            flat_model = base_parameters.model_copy(update={"NFloors": num_floors})

            start = perf_counter()
            flat_model.simulate(
                overheating_config=OverheatingAnalysisConfig(
                    heat_thresholds=(
                        ThresholdWithCriteria(
                            threshold=26.0,
                            count_failure=CountFailureCriterion(max_hours=50),
                            streak_failure=StreakCriterion(
                                min_streak_length_hours=50, max_count=0
                            ),
                            integrated_streak_failure=IntegratedStreakCriterion(
                                min_streak_length_hours=50, max_integral=0
                            ),
                            exceedance_failure=ExceedanceCriterion(max_deg_hours=50),
                        ),
                        ThresholdWithCriteria(
                            threshold=30.0,
                            count_failure=CountFailureCriterion(max_hours=50),
                            streak_failure=StreakCriterion(
                                min_streak_length_hours=50, max_count=0
                            ),
                            integrated_streak_failure=IntegratedStreakCriterion(
                                min_streak_length_hours=50, max_integral=0
                            ),
                            exceedance_failure=ExceedanceCriterion(max_deg_hours=50),
                        ),
                        ThresholdWithCriteria(
                            threshold=35.0,
                            count_failure=CountFailureCriterion(max_hours=50),
                            streak_failure=StreakCriterion(
                                min_streak_length_hours=50, max_count=0
                            ),
                            integrated_streak_failure=IntegratedStreakCriterion(
                                min_streak_length_hours=50, max_integral=0
                            ),
                            exceedance_failure=ExceedanceCriterion(max_deg_hours=50),
                        ),
                    ),
                    cold_thresholds=(
                        ThresholdWithCriteria(
                            threshold=10.0,
                            count_failure=CountFailureCriterion(max_hours=50),
                            streak_failure=StreakCriterion(
                                min_streak_length_hours=50, max_count=0
                            ),
                            integrated_streak_failure=IntegratedStreakCriterion(
                                min_streak_length_hours=50, max_integral=0
                            ),
                            exceedance_failure=ExceedanceCriterion(max_deg_hours=50),
                        ),
                        ThresholdWithCriteria(
                            threshold=5.0,
                            count_failure=CountFailureCriterion(max_hours=50),
                            streak_failure=StreakCriterion(
                                min_streak_length_hours=50, max_count=0
                            ),
                            integrated_streak_failure=IntegratedStreakCriterion(
                                min_streak_length_hours=50, max_integral=0
                            ),
                            exceedance_failure=ExceedanceCriterion(max_deg_hours=50),
                        ),
                    ),
                    heat_index_criteria=HeatIndexCriteria(
                        caution_or_worse_hours=4000,
                    ),
                    thermal_comfort=ThermalComfortAssumptions(
                        met=1.1,
                        clo=0.5,
                        v=0.1,
                    ),
                )
            )
            elapsed = perf_counter() - start

            results.append((num_floors, calculate_overheating, elapsed))
            print(f"{num_floors}\t{calculate_overheating}\t{elapsed:.2f}")

    # Write CSV results next to this script.
    csv_path = Path(__file__).with_suffix(".csv")
    with csv_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["NFloors", "calculate_overheating", "elapsed_s"])
        writer.writerows(results)
    print(f"Wrote benchmark results to {csv_path}")

    # Generate plots if matplotlib is available.
    try:
        import matplotlib.pyplot as plt  # type: ignore[import-untyped]
    except ImportError:
        print("matplotlib not installed; skipping plot generation.")
        return

    floors = sorted({n for n, _, _ in results})
    times_no_oh: list[float] = []
    times_with_oh: list[float] = []

    for n in floors:
        # There should be exactly one entry per (NFloors, flag).
        elapsed_no = next(e for nf, co, e in results if nf == n and co is False)
        elapsed_yes = next(e for nf, co, e in results if nf == n and co is True)
        times_no_oh.append(elapsed_no)
        times_with_oh.append(elapsed_yes)

    fig, ax = plt.subplots()
    ax.plot(floors, times_no_oh, marker="o", label="No overheating")
    ax.plot(floors, times_with_oh, marker="o", label="With overheating")
    ax.set_xlabel("Number of floors")
    ax.set_ylabel("Elapsed time [s]")
    ax.set_title("Flat model runtime vs number of floors")
    ax.legend()
    fig.tight_layout()

    plot_path = Path(__file__).with_suffix(".png")
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)
    print(f"Saved plot to {plot_path}")


if __name__ == "__main__":
    benchmark()
