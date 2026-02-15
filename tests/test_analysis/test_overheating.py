"""Unit tests for the overheating analysis module using synthetic data with known expected values."""

from typing import cast

import numpy as np
import pandas as pd
import pytest

from epinterface.analysis.overheating import (
    CountFailureCriterion,
    ExceedanceCriterion,
    HeatIndexCriteria,
    IntegratedStreakCriterion,
    OverheatingAnalysisConfig,
    OverheatingAnalysisResults,
    StreakCriterion,
    ThermalComfortAssumptions,
    ThresholdWithCriteria,
    _consecutive_run_lengths_looped,
    _consecutive_run_lengths_vectorized,
    calculate_basic_overheating_stats,
    calculate_consecutive_hours_above_threshold,
    calculate_edh,
    calculate_hi_categories,
    check_timeseries_shape,
    compute_zone_at_risk,
)

# ---------------------------------------------------------------------------
# Constants and fixtures
# ---------------------------------------------------------------------------

N_TIMESTEPS = 8760
HOURS_PER_MONTH = 744  # 31 days in Jan, etc. - use 744 for simplicity

# Default thresholds (heating = overheat, cooling = underheat)
DEFAULT_HEATING_THRESHOLDS = (
    ThresholdWithCriteria(threshold=26.0),
    ThresholdWithCriteria(threshold=30.0),
    ThresholdWithCriteria(threshold=35.0),
)
DEFAULT_COOLING_THRESHOLDS = (
    ThresholdWithCriteria(threshold=10.0),
    ThresholdWithCriteria(threshold=5.0),
)
THERMAL_COMFORT = ThermalComfortAssumptions(met=1.1, clo=0.5, v=0.1)


def synthetic_constant(n_zones: int, value: float) -> np.ndarray:
    """Create (n_zones, 8760) array with constant value."""
    return np.full((n_zones, N_TIMESTEPS), value, dtype=np.float64)


def synthetic_sawtooth(
    n_zones: int,
    base: float,
    period: int,
    step: float,
) -> np.ndarray:
    """Create sawtooth: T[i] = base + (i % period) * step."""
    t = np.arange(N_TIMESTEPS, dtype=np.float64)
    arr = base + (t % period) * step
    return np.broadcast_to(arr, (n_zones, N_TIMESTEPS)).copy()


def synthetic_step_monthly(
    n_zones: int,
    monthly_values: list[float],
) -> np.ndarray:
    """Create step pattern: each month (744h) at a constant value."""
    assert len(monthly_values) == 12
    arr = np.empty((n_zones, N_TIMESTEPS), dtype=np.float64)
    for m, val in enumerate(monthly_values):
        start = m * HOURS_PER_MONTH
        end = start + HOURS_PER_MONTH
        arr[:, start:end] = val
    return arr


# ---------------------------------------------------------------------------
# check_timeseries_shape
# ---------------------------------------------------------------------------


class TestCheckTimeseriesShape:
    """Tests for check_timeseries_shape validation."""

    def test_valid_2d_shape(self):
        """Valid (zones, 8760) array raises no error."""
        ts = np.zeros((3, N_TIMESTEPS))
        check_timeseries_shape(ts, expected_zones=3)

    def test_wrong_ndim_1d(self):
        """1D array raises ValueError."""
        ts = np.zeros(N_TIMESTEPS)
        with pytest.raises(ValueError, match="2D array"):
            check_timeseries_shape(ts)

    def test_wrong_ndim_3d(self):
        """3D array raises ValueError."""
        ts = np.zeros((2, 3, N_TIMESTEPS))
        with pytest.raises(ValueError, match="2D array"):
            check_timeseries_shape(ts)

    def test_wrong_zones_count(self):
        """Wrong number of zones raises ValueError."""
        ts = np.zeros((2, N_TIMESTEPS))
        with pytest.raises(ValueError, match="3 zones"):
            check_timeseries_shape(ts, expected_zones=3)

    def test_wrong_timesteps(self):
        """Wrong number of timesteps raises ValueError."""
        ts = np.zeros((2, 8761))
        with pytest.raises(ValueError, match="8760 timesteps"):
            check_timeseries_shape(ts, expected_zones=2)

    def test_expected_zones_none(self):
        """When expected_zones=None, only timesteps are checked."""
        ts = np.zeros((5, N_TIMESTEPS))
        check_timeseries_shape(ts, expected_zones=None)


# ---------------------------------------------------------------------------
# calculate_hi_categories
# ---------------------------------------------------------------------------


class TestCalculateHiCategories:
    """Tests for calculate_hi_categories."""

    def test_constant_normal(self):
        """1 zone, 25°C/40% RH all hours -> 8760 in Normal."""
        dbt = synthetic_constant(1, 25.0)
        rh = synthetic_constant(1, 40.0)
        result = calculate_hi_categories(dbt, rh)
        # Building Zone Weighted: all hours in Normal
        building = cast(pd.DataFrame, result.loc["Building"])
        assert building.loc["Zone Weighted", "Normal [hr]"] == 8760
        other_cats = [
            "Caution [hr]",
            "Extreme Caution [hr]",
            "Danger [hr]",
            "Extreme Danger [hr]",
        ]
        assert bool((building.loc["Zone Weighted", other_cats] == 0).all())  # pyright: ignore [reportArgumentType

    def test_constant_caution(self):
        """28°C/60% RH -> 8760 in Caution (HI 80-89°F)."""
        dbt = synthetic_constant(1, 28.0)
        rh = synthetic_constant(1, 60.0)
        result = calculate_hi_categories(dbt, rh)
        building = result.loc["Building"]
        assert building.loc["Zone Weighted", "Caution [hr]"] == 8760

    def test_constant_extreme_caution(self):
        """32°C/70% RH -> Extreme Caution (HI 90-104°F)."""
        dbt = synthetic_constant(1, 32.0)
        rh = synthetic_constant(1, 70.0)
        result = calculate_hi_categories(dbt, rh)
        building = result.loc["Building"]
        assert building.loc["Zone Weighted", "Extreme Caution [hr]"] == 8760

    def test_constant_danger(self):
        """35°C/80% RH -> Danger (HI 105-129°F)."""
        dbt = synthetic_constant(1, 35.0)
        rh = synthetic_constant(1, 67.0)
        result = calculate_hi_categories(dbt, rh)
        building = result.loc["Building"]
        assert building.loc["Zone Weighted", "Danger [hr]"] == 8760

    def test_constant_extreme_danger(self):
        """38°C/90% RH -> Extreme Danger (HI ≥130°F)."""
        dbt = synthetic_constant(1, 38.0)
        rh = synthetic_constant(1, 90.0)
        result = calculate_hi_categories(dbt, rh)
        building = result.loc["Building"]
        assert building.loc["Zone Weighted", "Extreme Danger [hr]"] == 8760

    def test_mixed_categories(self):
        """Make sure that a single zone can have multiple categories with the right number of hours in each."""
        zone_names = ["Zone 000", "Zone 001"]
        zone_weights = np.array([0.5, 0.5])
        dbt = np.array([
            np.full(N_TIMESTEPS, 25.0),
            np.full(N_TIMESTEPS, 28.0),
        ])
        rh = np.array([
            np.full(N_TIMESTEPS, 50.0),
            np.full(N_TIMESTEPS, 60.0),
        ])

        # Zone 00, Normal for 1/4 of the year
        dbt[0, : int(8760 / 4)] = 25
        rh[0, : int(8760 / 4)] = 40
        # Zone 00, Caution for 1/4 of the year
        dbt[0, int(8760 / 4) : int(8760 * 2 / 4)] = 28.0
        rh[0, int(8760 / 4) : int(8760 * 2 / 4)] = 60.0
        # Zone 00, Extreme Caution for 1/4 of the year
        dbt[0, int(8760 * 2 / 4) : int(8760 * 3 / 4)] = 32.0
        rh[0, int(8760 * 2 / 4) : int(8760 * 3 / 4)] = 70.0
        # Zone 00, Danger for 1/4 of the year
        dbt[0, int(8760 * 3 / 4) :] = 35.0
        rh[0, int(8760 * 3 / 4) :] = 67.0

        # Zone 01, Extreme Danger for 1/4 of the year
        dbt[1, : int(8760 / 4)] = 38.0
        rh[1, : int(8760 / 4)] = 90.0
        # Zone 01, Danger for 1/4 of the year
        dbt[1, int(8760 / 4) : int(8760 * 2 / 4)] = 35.0
        rh[1, int(8760 / 4) : int(8760 * 2 / 4)] = 67.0
        # Zone 01, Extreme Caution for 1/4 of the year
        dbt[1, int(8760 * 2 / 4) : int(8760 * 3 / 4)] = 32.0
        rh[1, int(8760 * 2 / 4) : int(8760 * 3 / 4)] = 70.0
        # Zone 01, Caution for 1/4 of the year
        dbt[1, int(8760 * 3 / 4) :] = 28.0
        rh[1, int(8760 * 3 / 4) :] = 60.0

        result = calculate_hi_categories(
            dbt, rh, zone_names=zone_names, zone_weights=zone_weights
        )
        zones = result.loc["Zone"]
        assert zones.loc["Zone 000", "Normal [hr]"] == int(8760 / 4)
        assert zones.loc["Zone 000", "Caution [hr]"] == int(8760 / 4)
        assert zones.loc["Zone 000", "Extreme Caution [hr]"] == int(8760 / 4)
        assert zones.loc["Zone 000", "Danger [hr]"] == int(8760 / 4)
        assert zones.loc["Zone 000", "Extreme Danger [hr]"] == 0

        assert zones.loc["Zone 001", "Normal [hr]"] == 0
        assert zones.loc["Zone 001", "Caution [hr]"] == int(8760 / 4)
        assert zones.loc["Zone 001", "Extreme Caution [hr]"] == int(8760 / 4)
        assert zones.loc["Zone 001", "Danger [hr]"] == int(8760 / 4)
        assert zones.loc["Zone 001", "Extreme Danger [hr]"] == int(8760 / 4)

    def test_zone_weights_aggregation(self):
        """2 zones with different weights; verify weighted aggregation."""
        zone_names = ["Zone A", "Zone B"]
        zone_weights = np.array([0.7, 0.3])
        # Zone A: 25°C (Normal), Zone B: 32°C (Extreme Caution)
        dbt = np.array([
            np.full(N_TIMESTEPS, 25.0),
            np.full(N_TIMESTEPS, 32.0),
        ])
        rh = synthetic_constant(2, 50.0)
        result = calculate_hi_categories(
            dbt, rh, zone_names=zone_names, zone_weights=zone_weights
        )
        # Zone Weighted row: category hours sum to 8760
        building = result.loc["Building"]
        assert bool(building.loc["Zone Weighted"].sum() == 8760)

    def test_zone_names_weights_length_mismatch(self):
        """Zone names and weights length mismatch raises ValueError."""
        dbt = synthetic_constant(2, 25.0)
        rh = synthetic_constant(2, 50.0)
        with pytest.raises(ValueError, match="same length"):
            calculate_hi_categories(
                dbt, rh, zone_names=["A", "B"], zone_weights=np.array([1.0])
            )

    def test_output_structure(self):
        """Output has Building-level and Zone-level rows, columns sum to 8760."""
        dbt = synthetic_constant(2, 25.0)
        rh = synthetic_constant(2, 50.0)
        result = calculate_hi_categories(dbt, rh)
        assert "Building" in result.index.get_level_values(0)
        assert "Zone" in result.index.get_level_values(0)
        cat_cols = [c for c in result.columns if " [hr]" in str(c)]
        for agg in ["Modal per Timestep", "Worst per Timestep", "Zone Weighted"]:
            row = cast(pd.Series, result.loc[("Building", agg)])
            assert row[cat_cols].sum() == 8760


# ---------------------------------------------------------------------------
# calculate_basic_overheating_stats
# ---------------------------------------------------------------------------


class TestCalculateBasicOverheatingStats:
    """Tests for calculate_basic_overheating_stats."""

    def test_constant_28c_overheat(self):
        """Constant 28°C: above 26°C=8760, above 30°C=0, above 35°C=0."""
        dbt = synthetic_constant(1, 28.0)
        result = calculate_basic_overheating_stats(
            dbt,
            heating_thresholds=DEFAULT_HEATING_THRESHOLDS,
            cooling_thresholds=DEFAULT_COOLING_THRESHOLDS,
        )
        # Overheat, 26°C, Zone, Zone 000
        val_26 = result.loc[("Overheat", 26.0, "Zone", "Zone 000"), "Total Hours [hr]"]
        val_30 = result.loc[("Overheat", 30.0, "Zone", "Zone 000"), "Total Hours [hr]"]
        val_35 = result.loc[("Overheat", 35.0, "Zone", "Zone 000"), "Total Hours [hr]"]
        assert val_26 == 8760
        assert val_30 == 0
        assert val_35 == 0

    def test_constant_5c_underheat(self):
        """Constant 5°C: below 10°C=8760, below 5°C=0."""
        dbt = synthetic_constant(1, 5.0)
        result = calculate_basic_overheating_stats(
            dbt,
            heating_thresholds=DEFAULT_HEATING_THRESHOLDS,
            cooling_thresholds=DEFAULT_COOLING_THRESHOLDS,
        )
        val_10 = result.loc[("Underheat", 10.0, "Zone", "Zone 000"), "Total Hours [hr]"]
        val_5 = result.loc[("Underheat", 5.0, "Zone", "Zone 000"), "Total Hours [hr]"]
        assert val_10 == 8760
        assert val_5 == 0

    def test_two_zones_different_temps(self):
        """Zone A 28°C, Zone B 24°C → verify Any Zone, Zone Weighted, Worst Zone."""
        zone_names = ["Zone A", "Zone B"]
        dbt = np.array([
            np.full(N_TIMESTEPS, 28.0),
            np.full(N_TIMESTEPS, 24.0),
        ])
        result = calculate_basic_overheating_stats(
            dbt,
            zone_names=zone_names,
            zone_weights=np.ones(2),
            heating_thresholds=DEFAULT_HEATING_THRESHOLDS,
            cooling_thresholds=DEFAULT_COOLING_THRESHOLDS,
        )
        # Above 26°C: Zone A=8760, Zone B=0
        # Any Zone: 8760 (at least one zone above)
        # Worst Zone: 8760
        # Zone Weighted: 0.5*8760 + 0.5*0 = 4380
        # Equally Weighted: 4380
        any_zone = result.loc[
            ("Overheat", 26.0, "Building", "Any Zone"), "Total Hours [hr]"
        ]
        worst_zone = result.loc[
            ("Overheat", 26.0, "Building", "Worst Zone"), "Total Hours [hr]"
        ]
        zone_weighted = result.loc[
            ("Overheat", 26.0, "Building", "Zone Weighted"), "Total Hours [hr]"
        ]
        assert any_zone == 8760
        assert worst_zone == 8760
        assert zone_weighted == 4380

    def test_output_structure(self):
        """Output has MultiIndex and Total Hours [hr] column."""
        dbt = synthetic_constant(1, 25.0)
        result = calculate_basic_overheating_stats(
            dbt,
            heating_thresholds=DEFAULT_HEATING_THRESHOLDS,
            cooling_thresholds=DEFAULT_COOLING_THRESHOLDS,
        )
        assert result.index.names == [
            "Polarity",
            "Threshold [degC]",
            "Aggregation Unit",
            "Group",
        ]
        assert "Total Hours [hr]" in result.columns


# ---------------------------------------------------------------------------
# calculate_consecutive_hours_above_threshold
# ---------------------------------------------------------------------------


class TestCalculateConsecutiveHoursAboveThreshold:
    """Tests for calculate_consecutive_hours_above_threshold."""

    def test_single_744h_run(self):
        """Jan (744h) at 28°C, rest at 20°C, threshold 26°C -> one streak of 744h, integral = 744*2."""
        dbt = synthetic_constant(1, 20.0)
        dbt[:, :744] = 28.0  # Jan
        # Add cooling threshold with some cold hours so output is stacked (flat columns)
        dbt[:, 750:755] = 5.0  # 5h below 10°C for underheat streak
        result = calculate_consecutive_hours_above_threshold(
            dbt,
            heating_thresholds=(ThresholdWithCriteria(threshold=26.0),),
            cooling_thresholds=(ThresholdWithCriteria(threshold=10.0),),
        )
        # One overheat streak of 744h, integral = 744 * (28-26) = 1488
        subset = result.xs(("Overheat", 26.0), level=("Polarity", "Threshold [degC]"))
        overheat_rows = subset[subset["Streak [hr]"] == 744]
        assert len(overheat_rows) == 1
        assert overheat_rows["Integral [deg-hr]"].iloc[0] == 1488

    def test_integral_single_streak_100h(self):
        """100h at 28°C above 26°C threshold -> integral = 100 * 2 = 200 deg-hr."""
        dbt = synthetic_constant(1, 20.0)
        dbt[:, :100] = 28.0
        dbt[:, 756:761] = 5.0  # cooling for stacked output
        result = calculate_consecutive_hours_above_threshold(
            dbt,
            heating_thresholds=(ThresholdWithCriteria(threshold=26.0),),
            cooling_thresholds=(ThresholdWithCriteria(threshold=10.0),),
        )
        subset = result.xs(("Overheat", 26.0), level=("Polarity", "Threshold [degC]"))
        overheat_rows = subset[subset["Streak [hr]"] == 100]
        assert len(overheat_rows) == 1
        assert overheat_rows["Integral [deg-hr]"].iloc[0] == 200

    def test_integral_two_streaks_sum(self):
        """Two streaks: 50h at 28°C + 30h at 28°C -> integrals 100 + 60 = 160 deg-hr total."""
        dbt = synthetic_constant(1, 20.0)
        dbt[:, :50] = 28.0
        dbt[:, 50:80] = 20.0
        dbt[:, 80:110] = 28.0
        dbt[:, 756:761] = 5.0  # cooling for stacked output
        result = calculate_consecutive_hours_above_threshold(
            dbt,
            heating_thresholds=(ThresholdWithCriteria(threshold=26.0),),
            cooling_thresholds=(ThresholdWithCriteria(threshold=10.0),),
        )
        subset = result.xs(("Overheat", 26.0), level=("Polarity", "Threshold [degC]"))
        total_integral = subset["Integral [deg-hr]"].sum()
        assert total_integral == 50 * 2 + 30 * 2  # 100 + 60 = 160

    def test_sawtooth_12h_above_12h_below(self):
        """12h at 28°C, 12h at 20°C, repeat -> 365 streaks of 12h, integral = 365*12*2 = 8760."""
        dbt = synthetic_constant(1, 20.0)
        for i in range(N_TIMESTEPS):
            if (i // 12) % 2 == 0:
                dbt[0, i] = 28.0
            else:
                dbt[0, i] = 20.0
        # Add cooling in a 20°C block (756-767) to get stacked output without breaking overheat pattern
        dbt[:, 756:761] = 5.0
        result = calculate_consecutive_hours_above_threshold(
            dbt,
            heating_thresholds=(ThresholdWithCriteria(threshold=26.0),),
            cooling_thresholds=(ThresholdWithCriteria(threshold=10.0),),
        )
        subset = result.xs(("Overheat", 26.0), level=("Polarity", "Threshold [degC]"))
        assert len(subset) == 365
        assert subset["Streak [hr]"].iloc[0] == 12
        total_integral = subset["Integral [deg-hr]"].sum()
        assert total_integral == 365 * 12 * 2  # 8760 deg-hr

    def test_empty_heating_thresholds(self):
        """Empty heating thresholds returns only underheat."""
        dbt = synthetic_constant(1, 5.0)
        result = calculate_consecutive_hours_above_threshold(
            dbt,
            heating_thresholds=(),
            cooling_thresholds=DEFAULT_COOLING_THRESHOLDS,
        )
        assert "Underheat" in result.index.get_level_values("Polarity")
        assert "Overheat" not in result.index.get_level_values("Polarity")

    def test_empty_cooling_thresholds(self):
        """Empty cooling thresholds returns only overheat."""
        dbt = synthetic_constant(1, 28.0)
        result = calculate_consecutive_hours_above_threshold(
            dbt,
            heating_thresholds=DEFAULT_HEATING_THRESHOLDS,
            cooling_thresholds=(),
        )
        assert "Overheat" in result.index.get_level_values("Polarity")
        assert "Underheat" not in result.index.get_level_values("Polarity")

    def test_output_structure(self):
        """Output has Streak [hr] and Integral [deg-hr] columns."""
        dbt = synthetic_constant(1, 28.0)
        result = calculate_consecutive_hours_above_threshold(
            dbt,
            heating_thresholds=(ThresholdWithCriteria(threshold=26.0),),
            cooling_thresholds=(),
        )
        assert "Streak [hr]" in result.columns
        assert "Integral [deg-hr]" in result.columns


class TestConsecutiveRunLengthsVectorizedVsLooped:
    """Cross-validate _consecutive_run_lengths_vectorized vs _consecutive_run_lengths_looped."""

    def test_structured_m_diff(self):
        """Structured M_diff: 1,2,3,0,0,5,6,0 -> runs of 3 and 2."""
        M_diff = np.array([[1, 2, 3, 0, 0, 5, 6, 0]], dtype=np.float64)
        lengths_v, integrals_v = _consecutive_run_lengths_vectorized(M_diff)
        lengths_l, integrals_l = _consecutive_run_lengths_looped(M_diff)
        np.testing.assert_array_almost_equal(lengths_v, lengths_l)
        np.testing.assert_array_almost_equal(integrals_v, integrals_l)

    def test_random_m_diff(self):
        """Random M_diff: both implementations agree."""
        np.random.seed(42)
        M_diff = np.random.rand(4, 100) * 2 - 0.5  # mix of positive and negative
        lengths_v, integrals_v = _consecutive_run_lengths_vectorized(M_diff)
        lengths_l, integrals_l = _consecutive_run_lengths_looped(M_diff)
        np.testing.assert_array_almost_equal(lengths_v, lengths_l)
        np.testing.assert_array_almost_equal(integrals_v, integrals_l)

    def test_all_zero(self):
        """All zeros: no runs; both return NaN-filled arrays."""
        M_diff = np.zeros((2, 100))
        lengths_v, integrals_v = _consecutive_run_lengths_vectorized(M_diff)
        lengths_l, integrals_l = _consecutive_run_lengths_looped(M_diff)
        assert np.all(np.isnan(lengths_v))
        assert np.all(np.isnan(integrals_v))
        # Looped may return different shape (0 cols vs 1 col); both have all NaN
        assert np.all(np.isnan(lengths_l))
        assert np.all(np.isnan(integrals_l))


# ---------------------------------------------------------------------------
# calculate_edh
# ---------------------------------------------------------------------------


class TestCalculateEdh:
    """Tests for calculate_edh."""

    def test_constant_hot_edh(self):
        """Constant DBT=MRT=28°C, RH=50%: EDH = 8760 * max(0, SET - T) per threshold."""
        from pythermalcomfort.models import set_tmp

        dbt = synthetic_constant(1, 28.0)
        mrt = synthetic_constant(1, 28.0)
        rh = synthetic_constant(1, 50.0)
        out = set_tmp(
            tdb=dbt[0],
            tr=mrt[0],
            rh=rh[0],
            met=THERMAL_COMFORT.met,
            clo=THERMAL_COMFORT.clo,
            v=THERMAL_COMFORT.v,
            limit_inputs=False,
        )
        set_val = out["set"][0]
        result = calculate_edh(
            dbt,
            rh,
            mrt,
            heating_thresholds=DEFAULT_HEATING_THRESHOLDS,
            cooling_thresholds=DEFAULT_COOLING_THRESHOLDS,
            thermal_comfort=THERMAL_COMFORT,
        )
        for thresh in [26.0, 30.0, 35.0]:
            expected = N_TIMESTEPS * max(0, set_val - thresh)
            actual = float(
                result.loc[("Overheat", thresh, "Zone", "Zone 000"), "EDH [degC-hr]"]  # pyright: ignore [reportArgumentType
            )
            np.testing.assert_almost_equal(actual, expected, decimal=2)

    def test_constant_cold_edh(self):
        """Constant DBT=MRT=8°C: cold EDH = 8760 * max(0, 10 - SET) for 10°C threshold."""
        from pythermalcomfort.models import set_tmp

        dbt = synthetic_constant(1, 8.0)
        mrt = synthetic_constant(1, 8.0)
        rh = synthetic_constant(1, 50.0)
        out = set_tmp(
            tdb=dbt[0],
            tr=mrt[0],
            rh=rh[0],
            met=THERMAL_COMFORT.met,
            clo=THERMAL_COMFORT.clo,
            v=THERMAL_COMFORT.v,
            limit_inputs=False,
        )
        set_val = out["set"][0]
        result = calculate_edh(
            dbt,
            rh,
            mrt,
            heating_thresholds=DEFAULT_HEATING_THRESHOLDS,
            cooling_thresholds=DEFAULT_COOLING_THRESHOLDS,
            thermal_comfort=THERMAL_COMFORT,
        )
        expected_10 = N_TIMESTEPS * max(0, 10 - set_val)
        actual_10 = float(
            result.loc[("Underheat", 10.0, "Zone", "Zone 000"), "EDH [degC-hr]"]  # pyright: ignore [reportArgumentType
        )
        np.testing.assert_almost_equal(actual_10, expected_10, decimal=2)

    def test_zone_weighted_vs_worst_zone(self):
        """2 zones with different SET profiles; Zone Weighted and Worst Zone differ."""
        dbt = np.array([
            np.full(N_TIMESTEPS, 28.0),
            np.full(N_TIMESTEPS, 24.0),
        ])
        mrt = dbt.copy()
        rh = synthetic_constant(2, 50.0)
        result = calculate_edh(
            dbt,
            rh,
            mrt,
            zone_weights=np.array([0.5, 0.5]),
            heating_thresholds=DEFAULT_HEATING_THRESHOLDS,
            cooling_thresholds=DEFAULT_COOLING_THRESHOLDS,
            thermal_comfort=THERMAL_COMFORT,
        )
        edh_26 = result.loc[result.index.get_level_values("Threshold [degC]") == 26.0]
        zone_weighted = float(
            edh_26.loc[("Overheat", 26.0, "Building", "Zone Weighted"), "EDH [degC-hr]"]  # pyright: ignore [reportArgumentType
        )
        worst_zone = float(
            edh_26.loc[("Overheat", 26.0, "Building", "Worst Zone"), "EDH [degC-hr]"]  # pyright: ignore [reportArgumentType
        )
        assert worst_zone > zone_weighted

    def test_output_structure(self):
        """Output has correct MultiIndex and EDH [degC-hr] column."""
        dbt = synthetic_constant(1, 25.0)
        mrt = synthetic_constant(1, 25.0)
        rh = synthetic_constant(1, 50.0)
        result = calculate_edh(
            dbt,
            rh,
            mrt,
            heating_thresholds=DEFAULT_HEATING_THRESHOLDS,
            cooling_thresholds=DEFAULT_COOLING_THRESHOLDS,
            thermal_comfort=THERMAL_COMFORT,
        )
        assert result.index.names == [
            "Polarity",
            "Threshold [degC]",
            "Aggregation Unit",
            "Group",
        ]
        assert "EDH [degC-hr]" in result.columns


# ---------------------------------------------------------------------------
# compute_zone_at_risk
# ---------------------------------------------------------------------------


def _make_basic_oh_simple(
    zone_names: list[str], hours_above_26: dict[str, float]
) -> pd.DataFrame:
    """Simpler: only Overheat 26°C for zones."""
    rows = []
    for pol, thresh in [
        ("Overheat", 26.0),
        ("Overheat", 30.0),
        ("Overheat", 35.0),
        ("Underheat", 10.0),
        ("Underheat", 5.0),
    ]:
        for agg, groups in [
            (
                "Building",
                ["Any Zone", "Zone Weighted", "Worst Zone", "Equally Weighted"],
            ),
            ("Zone", zone_names),
        ]:
            for g in groups:
                if agg == "Zone" and pol == "Overheat" and thresh == 26.0:
                    val = hours_above_26.get(g, 0)
                elif agg == "Building":
                    if g == "Worst Zone":
                        val = (
                            max(hours_above_26.values())
                            if pol == "Overheat" and thresh == 26.0
                            else 0
                        )
                    elif g == "Zone Weighted" or g == "Equally Weighted":
                        val = (
                            sum(hours_above_26.values()) / len(zone_names)
                            if pol == "Overheat" and thresh == 26.0
                            else 0
                        )
                    elif g == "Any Zone":
                        val = (
                            8760
                            if any(h > 0 for h in hours_above_26.values())
                            and pol == "Overheat"
                            and thresh == 26.0
                            else 0
                        )
                    else:
                        val = 0
                else:
                    val = 0
                rows.append((pol, thresh, agg, g, val))
    idx = pd.MultiIndex.from_tuples(
        [(r[0], r[1], r[2], r[3]) for r in rows],
        names=["Polarity", "Threshold [degC]", "Aggregation Unit", "Group"],
    )
    return pd.DataFrame({"Total Hours [hr]": [r[4] for r in rows]}, index=idx)


def _make_edh_simple(
    zone_names: list[str], edh_overheat_26: dict[str, float]
) -> pd.DataFrame:
    """Simpler EDH for zone-at-risk: Overheat 26°C only."""
    rows = []
    for pol, thresh in [
        ("Overheat", 26.0),
        ("Overheat", 30.0),
        ("Overheat", 35.0),
        ("Underheat", 10.0),
        ("Underheat", 5.0),
    ]:
        for agg, groups in [
            ("Building", ["Zone Weighted", "Worst Zone"]),
            ("Zone", zone_names),
        ]:
            for g in groups:
                if agg == "Zone" and pol == "Overheat" and thresh == 26.0:
                    val = edh_overheat_26.get(g, 0)
                elif agg == "Building" and pol == "Overheat" and thresh == 26.0:
                    val = (
                        max(edh_overheat_26.values())
                        if g == "Worst Zone"
                        else sum(edh_overheat_26.values()) / len(zone_names)
                    )
                else:
                    val = 0
                rows.append((pol, thresh, agg, g, val))
    idx = pd.MultiIndex.from_tuples(
        [(r[0], r[1], r[2], r[3]) for r in rows],
        names=["Polarity", "Threshold [degC]", "Aggregation Unit", "Group"],
    )
    return pd.DataFrame({"EDH [degC-hr]": [r[4] for r in rows]}, index=idx)


def _make_hi_for_zone_at_risk(
    zone_names: list[str], caution_or_worse_by_zone: dict[str, float]
) -> pd.DataFrame:
    """HI DataFrame with Zone-level rows. Columns: Normal [hr], Caution [hr], etc."""
    total = sum(caution_or_worse_by_zone.values())
    building = pd.DataFrame(
        {
            "Normal [hr]": [8760 - total],
            "Caution [hr]": [total],
            "Extreme Caution [hr]": [0],
            "Danger [hr]": [0],
            "Extreme Danger [hr]": [0],
        },
        index=["Zone Weighted"],
    )
    zone_rows = []
    for z in zone_names:
        c = caution_or_worse_by_zone.get(z, 0)
        zone_rows.append({
            "Normal [hr]": 8760 - c,
            "Caution [hr]": c,
            "Extreme Caution [hr]": 0,
            "Danger [hr]": 0,
            "Extreme Danger [hr]": 0,
        })
    zone_df = pd.DataFrame(zone_rows, index=zone_names)
    return pd.concat([building, zone_df], keys=["Building", "Zone"])


class TestComputeZoneAtRisk:
    """Tests for compute_zone_at_risk."""

    def test_count_failure_at_risk(self):
        """Zone with 100h above 26°C, max_hours=50 -> at risk."""
        zone_names = ["Zone A"]
        dbt = synthetic_constant(1, 25.0)
        dbt[0, :100] = 28.0  # 100h above 26
        basic_oh = calculate_basic_overheating_stats(
            dbt,
            zone_names=zone_names,
            heating_thresholds=(
                ThresholdWithCriteria(
                    threshold=26.0, count_failure=CountFailureCriterion(max_hours=50)
                ),
            ),
            cooling_thresholds=(),
        )
        hi = _make_hi_for_zone_at_risk(zone_names, {"Zone A": 0})
        edh = _make_edh_simple(zone_names, {"Zone A": 0})
        consecutive = calculate_consecutive_hours_above_threshold(
            dbt,
            heating_thresholds=(ThresholdWithCriteria(threshold=26.0),),
            cooling_thresholds=(),
        )
        results = OverheatingAnalysisResults(
            hi=hi,
            edh=edh,
            basic_oh=basic_oh,
            consecutive_e_zone=consecutive,
            zone_at_risk=pd.DataFrame(),
        )
        config = OverheatingAnalysisConfig(
            heating_thresholds=(
                ThresholdWithCriteria(
                    threshold=26.0, count_failure=CountFailureCriterion(max_hours=50)
                ),
            ),
            cooling_thresholds=(),
        )
        out = compute_zone_at_risk(results, config, np.ones(1), zone_names)
        assert out.loc["Zone A", "at_risk"]

    def test_count_failure_pass(self):
        """30h above 26°C, max_hours=50 -> not at risk."""
        zone_names = ["Zone A"]
        dbt = synthetic_constant(1, 25.0)
        dbt[0, :30] = 28.0
        basic_oh = calculate_basic_overheating_stats(
            dbt,
            zone_names=zone_names,
            heating_thresholds=(
                ThresholdWithCriteria(
                    threshold=26.0, count_failure=CountFailureCriterion(max_hours=50)
                ),
            ),
            cooling_thresholds=(),
        )
        hi = _make_hi_for_zone_at_risk(zone_names, {"Zone A": 0})
        edh = _make_edh_simple(zone_names, {"Zone A": 0})
        consecutive = calculate_consecutive_hours_above_threshold(
            dbt,
            heating_thresholds=(ThresholdWithCriteria(threshold=26.0),),
            cooling_thresholds=(),
        )
        results = OverheatingAnalysisResults(
            hi=hi,
            edh=edh,
            basic_oh=basic_oh,
            consecutive_e_zone=consecutive,
            zone_at_risk=pd.DataFrame(),
        )
        config = OverheatingAnalysisConfig(
            heating_thresholds=(
                ThresholdWithCriteria(
                    threshold=26.0, count_failure=CountFailureCriterion(max_hours=50)
                ),
            ),
            cooling_thresholds=(),
        )
        out = compute_zone_at_risk(results, config, np.ones(1), zone_names)
        assert not out.loc["Zone A", "at_risk"]

    def test_exceedance_failure_at_risk(self):
        """EDH exceeds max_deg_hours -> at risk."""
        zone_names = ["Zone A"]
        basic_oh = calculate_basic_overheating_stats(
            synthetic_constant(1, 25.0),
            zone_names=zone_names,
            heating_thresholds=(ThresholdWithCriteria(threshold=26.0),),
            cooling_thresholds=(),
        )
        # Manually set EDH high for Zone A
        edh = _make_edh_simple(zone_names, {"Zone A": 10000})
        hi = _make_hi_for_zone_at_risk(zone_names, {"Zone A": 0})
        consecutive = calculate_consecutive_hours_above_threshold(
            synthetic_constant(1, 25.0),
            heating_thresholds=(ThresholdWithCriteria(threshold=26.0),),
            cooling_thresholds=(),
        )
        results = OverheatingAnalysisResults(
            hi=hi,
            edh=edh,
            basic_oh=basic_oh,
            consecutive_e_zone=consecutive,
            zone_at_risk=pd.DataFrame(),
        )
        config = OverheatingAnalysisConfig(
            heating_thresholds=(
                ThresholdWithCriteria(
                    threshold=26.0,
                    exceedance_failure=ExceedanceCriterion(max_deg_hours=5000),
                ),
            ),
            cooling_thresholds=(),
        )
        out = compute_zone_at_risk(results, config, np.ones(1), zone_names)
        assert out.loc["Zone A", "at_risk"]

    def test_streak_failure_at_risk(self):
        """Long streak count exceeds max_count -> at risk."""
        zone_names = ["Zone A"]
        dbt = synthetic_constant(1, 20.0)
        dbt[0, :100] = 28.0  # 100h streak above 26
        dbt[0, 756:761] = (
            5.0  # 5h below 10 for stacked consecutive output (in 20°C block)
        )
        basic_oh = calculate_basic_overheating_stats(
            dbt,
            zone_names=zone_names,
            heating_thresholds=(ThresholdWithCriteria(threshold=26.0),),
            cooling_thresholds=(),
        )
        edh = _make_edh_simple(zone_names, {"Zone A": 200})
        hi = _make_hi_for_zone_at_risk(zone_names, {"Zone A": 0})
        consecutive = calculate_consecutive_hours_above_threshold(
            dbt,
            zone_names=zone_names,
            heating_thresholds=(ThresholdWithCriteria(threshold=26.0),),
            cooling_thresholds=(ThresholdWithCriteria(threshold=10.0),),
        )
        results = OverheatingAnalysisResults(
            hi=hi,
            edh=edh,
            basic_oh=basic_oh,
            consecutive_e_zone=consecutive,
            zone_at_risk=pd.DataFrame(),
        )
        config = OverheatingAnalysisConfig(
            heating_thresholds=(
                ThresholdWithCriteria(
                    threshold=26.0,
                    streak_failure=StreakCriterion(
                        min_streak_length_hours=50, max_count=0
                    ),
                ),
            ),
            cooling_thresholds=(ThresholdWithCriteria(threshold=10.0),),
        )
        out = compute_zone_at_risk(results, config, np.ones(1), zone_names)
        assert out.loc["Zone A", "at_risk"]

    def test_integrated_streak_failure_at_risk(self):
        """Sum of integrals for long streaks exceeds max_integral -> at risk."""
        zone_names = ["Zone A"]
        dbt = synthetic_constant(1, 20.0)
        dbt[0, :100] = 28.0  # 100h at 28°C above 26°C -> integral = 200 deg-hr
        dbt[0, 756:761] = 5.0  # cooling for stacked output
        basic_oh = calculate_basic_overheating_stats(
            dbt,
            zone_names=zone_names,
            heating_thresholds=(ThresholdWithCriteria(threshold=26.0),),
            cooling_thresholds=(),
        )
        edh = _make_edh_simple(zone_names, {"Zone A": 200})
        hi = _make_hi_for_zone_at_risk(zone_names, {"Zone A": 0})
        consecutive = calculate_consecutive_hours_above_threshold(
            dbt,
            zone_names=zone_names,
            heating_thresholds=(ThresholdWithCriteria(threshold=26.0),),
            cooling_thresholds=(ThresholdWithCriteria(threshold=10.0),),
        )
        results = OverheatingAnalysisResults(
            hi=hi,
            edh=edh,
            basic_oh=basic_oh,
            consecutive_e_zone=consecutive,
            zone_at_risk=pd.DataFrame(),
        )
        config = OverheatingAnalysisConfig(
            heating_thresholds=(
                ThresholdWithCriteria(
                    threshold=26.0,
                    integrated_streak_failure=IntegratedStreakCriterion(
                        min_streak_length_hours=50, max_integral=150
                    ),
                ),
            ),
            cooling_thresholds=(ThresholdWithCriteria(threshold=10.0),),
        )
        out = compute_zone_at_risk(results, config, np.ones(1), zone_names)
        assert out.loc["Zone A", "at_risk"]

    def test_integrated_streak_failure_pass(self):
        """Sum of integrals for long streaks below max_integral -> not at risk."""
        zone_names = ["Zone A"]
        dbt = synthetic_constant(1, 20.0)
        dbt[0, :100] = 28.0  # 100h at 28°C above 26°C -> integral = 200 deg-hr
        dbt[0, 756:761] = 5.0  # cooling for stacked output
        basic_oh = calculate_basic_overheating_stats(
            dbt,
            zone_names=zone_names,
            heating_thresholds=(ThresholdWithCriteria(threshold=26.0),),
            cooling_thresholds=(),
        )
        edh = _make_edh_simple(zone_names, {"Zone A": 200})
        hi = _make_hi_for_zone_at_risk(zone_names, {"Zone A": 0})
        consecutive = calculate_consecutive_hours_above_threshold(
            dbt,
            zone_names=zone_names,
            heating_thresholds=(ThresholdWithCriteria(threshold=26.0),),
            cooling_thresholds=(ThresholdWithCriteria(threshold=10.0),),
        )
        results = OverheatingAnalysisResults(
            hi=hi,
            edh=edh,
            basic_oh=basic_oh,
            consecutive_e_zone=consecutive,
            zone_at_risk=pd.DataFrame(),
        )
        config = OverheatingAnalysisConfig(
            heating_thresholds=(
                ThresholdWithCriteria(
                    threshold=26.0,
                    integrated_streak_failure=IntegratedStreakCriterion(
                        min_streak_length_hours=50, max_integral=300
                    ),
                ),
            ),
            cooling_thresholds=(ThresholdWithCriteria(threshold=10.0),),
        )
        out = compute_zone_at_risk(results, config, np.ones(1), zone_names)
        assert not out.loc["Zone A", "at_risk"]

    def test_integrated_streak_ignores_short_streaks(self):
        """Only streaks longer than min_streak_length contribute to integral sum."""
        zone_names = ["Zone A"]
        dbt = synthetic_constant(1, 20.0)
        # Two short streaks of 20h each at 28°C -> 40 deg-hr each, total 80
        dbt[0, :20] = 28.0
        dbt[0, 20:40] = 20.0
        dbt[0, 40:60] = 28.0
        dbt[0, 756:761] = 5.0  # cooling for stacked output
        basic_oh = calculate_basic_overheating_stats(
            dbt,
            zone_names=zone_names,
            heating_thresholds=(ThresholdWithCriteria(threshold=26.0),),
            cooling_thresholds=(),
        )
        edh = _make_edh_simple(zone_names, {"Zone A": 80})
        hi = _make_hi_for_zone_at_risk(zone_names, {"Zone A": 0})
        consecutive = calculate_consecutive_hours_above_threshold(
            dbt,
            zone_names=zone_names,
            heating_thresholds=(ThresholdWithCriteria(threshold=26.0),),
            cooling_thresholds=(ThresholdWithCriteria(threshold=10.0),),
        )
        results = OverheatingAnalysisResults(
            hi=hi,
            edh=edh,
            basic_oh=basic_oh,
            consecutive_e_zone=consecutive,
            zone_at_risk=pd.DataFrame(),
        )
        # min_streak_length=30: no streaks qualify (both are 20h), so integral sum = 0
        config = OverheatingAnalysisConfig(
            heating_thresholds=(
                ThresholdWithCriteria(
                    threshold=26.0,
                    integrated_streak_failure=IntegratedStreakCriterion(
                        min_streak_length_hours=30, max_integral=50
                    ),
                ),
            ),
            cooling_thresholds=(ThresholdWithCriteria(threshold=10.0),),
        )
        out = compute_zone_at_risk(results, config, np.ones(1), zone_names)
        assert not out.loc["Zone A", "at_risk"]

    def test_heat_index_caution_or_worse(self):
        """HI caution_or_worse_hours exceeded -> at risk."""
        zone_names = ["Zone A"]
        hi = _make_hi_for_zone_at_risk(
            zone_names, {"Zone A": 5000}
        )  # 5000h in caution or worse
        basic_oh = calculate_basic_overheating_stats(
            synthetic_constant(1, 25.0),
            zone_names=zone_names,
            heating_thresholds=(ThresholdWithCriteria(threshold=26.0),),
            cooling_thresholds=(),
        )
        edh = _make_edh_simple(zone_names, {"Zone A": 0})
        consecutive = calculate_consecutive_hours_above_threshold(
            synthetic_constant(1, 25.0),
            heating_thresholds=(ThresholdWithCriteria(threshold=26.0),),
            cooling_thresholds=(),
        )
        results = OverheatingAnalysisResults(
            hi=hi,
            edh=edh,
            basic_oh=basic_oh,
            consecutive_e_zone=consecutive,
            zone_at_risk=pd.DataFrame(),
        )
        config = OverheatingAnalysisConfig(
            heating_thresholds=(ThresholdWithCriteria(threshold=26.0),),
            cooling_thresholds=(),
            heat_index_criteria=HeatIndexCriteria(caution_or_worse_hours=4000),
        )
        out = compute_zone_at_risk(results, config, np.ones(1), zone_names)
        assert out.loc["Zone A", "at_risk"]

    def test_output_structure(self):
        """Output has index=zone names, columns=weight, at_risk."""
        zone_names = ["Zone A", "Zone B"]
        dbt = synthetic_constant(2, 25.0)
        rh = synthetic_constant(2, 50.0)
        mrt = synthetic_constant(2, 25.0)
        hi = calculate_hi_categories(dbt, rh, zone_names=zone_names)
        basic_oh = calculate_basic_overheating_stats(
            dbt,
            zone_names=zone_names,
            heating_thresholds=DEFAULT_HEATING_THRESHOLDS,
            cooling_thresholds=DEFAULT_COOLING_THRESHOLDS,
        )
        edh = calculate_edh(
            dbt,
            rh,
            mrt,
            zone_names=zone_names,
            heating_thresholds=DEFAULT_HEATING_THRESHOLDS,
            cooling_thresholds=DEFAULT_COOLING_THRESHOLDS,
            thermal_comfort=THERMAL_COMFORT,
        )
        consecutive = calculate_consecutive_hours_above_threshold(
            dbt,
            zone_names=zone_names,
            heating_thresholds=DEFAULT_HEATING_THRESHOLDS,
            cooling_thresholds=DEFAULT_COOLING_THRESHOLDS,
        )
        results = OverheatingAnalysisResults(
            hi=hi,
            edh=edh,
            basic_oh=basic_oh,
            consecutive_e_zone=consecutive,
            zone_at_risk=pd.DataFrame(),
        )
        config = OverheatingAnalysisConfig()
        out = compute_zone_at_risk(results, config, np.ones(2), zone_names)
        assert out.index.tolist() == zone_names
        assert "weight" in out.columns
        assert "at_risk" in out.columns
        assert out["weight"].sum() == pytest.approx(1.0)
