"""A module for computing and analyzing metrics related to overheating, such as heat index, exceedance hours, etc."""

from dataclasses import dataclass
from typing import cast

import numpy as np
import pandas as pd
from archetypal.idfclass.sql import Sql
from numpy.typing import NDArray


def calculate_hi_categories(
    dbt_mat: NDArray[np.float64],
    rh_mat: NDArray[np.float64],
    zone_names: list[str] | None = None,
    zone_weights: NDArray[np.float64] | None = None,
) -> pd.DataFrame:
    """Computes heat index per hour across all zones and bins into 5 categories (sum = 8760), then takes the most common category for each timestep and the worst category for each timestep.

    Uses Rothfusz regression and NOAA categories:
      - Extreme Danger: ≥130°F
      - Danger: 105 to 129°F
      - Extreme Caution: 90 to 104°F
      - Caution: 80 to 89°F
      - Normal: <80°F

    Args:
        dbt_mat (np.ndarray): The dry bulb temperature matrix (zones x timesteps).
        rh_mat (np.ndarray): The relative humidity matrix (zones x timesteps).
        zone_names (list[str] | None): The names of the zones. If None, the zones will be named "Zone 001", "Zone 002", etc.
        zone_weights (NDArray[np.float64] | None): The weights of the zones. If None, the zones will be weighted equally when summing the heat index.

    Returns:
        cat_counts (pd.DataFrame): A dataframe with the count of timesteps that the building is in each category, using various aggregation methods.

    """
    zone_names_ = (
        [f"Zone {i:03d}" for i in range(dbt_mat.shape[0])]
        if zone_names is None
        else zone_names
    )
    zone_weights_ = (
        zone_weights if zone_weights is not None else np.ones(dbt_mat.shape[0])
    )
    if len(zone_names_) != len(zone_weights_):
        msg = f"Zone names and zone weights must have the same length. Got {len(zone_names_)} zone names and {len(zone_weights_)} zone weights."
        raise ValueError(msg)
    normalized_zone_weights: NDArray[np.float64] = zone_weights_ / zone_weights_.sum()
    n_zones = len(zone_weights_)
    check_timeseries_shape(dbt_mat, expected_zones=n_zones, expected_timesteps=8760)
    check_timeseries_shape(rh_mat, expected_zones=n_zones, expected_timesteps=8760)
    # we use an index map to solve ties and guarantee the "worst" category in the event of a tie is always chosen.
    cat_index_map = {
        "Extreme Danger": 4,
        "Danger": 3,
        "Extreme Caution": 2,
        "Caution": 1,
        "Normal": 0,
    }

    def compute_hi(temp_c, rh):
        # Convert to Fahrenheit
        temp_f = temp_c * 9 / 5 + 32
        hi_f = (
            -42.379
            + 2.04901523 * temp_f
            + 10.14333127 * rh
            - 0.22475541 * temp_f * rh
            - 6.83783e-3 * temp_f**2
            - 5.481717e-2 * rh**2
            + 1.22874e-3 * temp_f**2 * rh
            + 8.5282e-4 * temp_f * rh**2
            - 1.99e-6 * temp_f**2 * rh**2
        )
        return hi_f

    def compute_category(hi_f):
        return np.where(
            hi_f >= 130,
            cat_index_map["Extreme Danger"],
            np.where(
                hi_f >= 105,
                cat_index_map["Danger"],
                np.where(
                    hi_f >= 90,
                    cat_index_map["Extreme Caution"],
                    np.where(
                        hi_f >= 80, cat_index_map["Caution"], cat_index_map["Normal"]
                    ),
                ),
            ),
        )

    heat_index_mat = compute_hi(dbt_mat, rh_mat)
    zone_weighted_heat_index = heat_index_mat * normalized_zone_weights.reshape(-1, 1)
    aggregated_heat_index = zone_weighted_heat_index.sum(axis=0)

    bins_by_hour_and_zone = compute_category(heat_index_mat)
    bins_by_hour_building = compute_category(aggregated_heat_index)

    df = pd.DataFrame(
        bins_by_hour_and_zone,
        index=zone_names_,
        columns=pd.RangeIndex(0, 8760),
    )

    val_counts_by_timestep = [df.loc[zone].value_counts() for zone in zone_names_]
    cat_counts_by_zone = (
        pd.concat(val_counts_by_timestep, axis=1, keys=zone_names_, names=["Group"])
        .fillna(0)
        .sort_index()
    )
    cat_counts_by_zone = cat_counts_by_zone.rename(
        index={ix: val for val, ix in cat_index_map.items()}
    )
    cat_counts_by_zone.index.name = "Heat Index Category"

    modes_by_timestep: pd.DataFrame | pd.Series = cast(
        pd.DataFrame | pd.Series, df.mode(axis=0)
    )

    worst_by_timestep = df.max(axis=0)

    # since some timesteps may have multiple modes, we choose the mode with the highest count.
    if isinstance(modes_by_timestep, pd.Series):
        modes = modes_by_timestep
    else:
        modes = modes_by_timestep.max(axis=0)

    val_count_modes = modes.value_counts()
    val_count_modes = val_count_modes.rename(
        index={ix: val for val, ix in cat_index_map.items()}
    )

    val_count_worst = worst_by_timestep.value_counts()
    val_count_worst = val_count_worst.rename(
        index={ix: val for val, ix in cat_index_map.items()}
    )

    val_counts_building = pd.Series(
        bins_by_hour_building, name="Building"
    ).value_counts()
    val_counts_building = val_counts_building.rename(
        index={ix: val for val, ix in cat_index_map.items()}
    )

    for cat in cat_index_map:
        if cat not in val_count_modes.index:
            val_count_modes[cat] = 0
        if cat not in val_count_worst.index:
            val_count_worst[cat] = 0
        if cat not in val_counts_building.index:
            val_counts_building[cat] = 0

    building_counts = pd.concat(
        [val_count_modes, val_count_worst, val_counts_building],
        axis=1,
        keys=["Modal per Timestep", "Worst per Timestep", "Zone Weighted"],
    ).loc[list(cat_index_map.keys())]
    building_counts.index.name = "Heat Index Category"
    building_counts.columns.name = "Group"

    return pd.concat(
        [building_counts.T, cat_counts_by_zone.T],
        axis=0,
        names=["Aggregation Unit"],
        keys=["Building", "Zone"],
    ).rename(columns={c: f"{c} [hr]" for c in cat_index_map})


def check_timeseries_shape(
    ts: np.ndarray, expected_zones: int | None = None, expected_timesteps: int = 8760
) -> None:
    """Checks if the timeseries is a 2D array with shape (zones, timesteps).

    Args:
        ts (np.ndarray): The timeseries to check.
        expected_zones (int | None): The expected number of zones. If None, the number of zones will not be checked.
        expected_timesteps (int): The expected number of timesteps.

    Raises:
        ValueError: If the timeseries is not a 2D array with shape (zones, timesteps).
        ValueError: If the timeseries has a different number of zones than the expected number of zones.
        ValueError: If the timeseries has a different number of timesteps than the expected number of timesteps.

    Returns:
        None
    """
    if ts.ndim != 2:
        msg = f"Timeseries must be a 2D array with shape (zones, timesteps). Got shape {ts.shape}."
        raise ValueError(msg)
    if ts.shape[0] != expected_zones and expected_zones is not None:
        msg = f"Timeseries must have {expected_zones} zones. Got {ts.shape[0]} zones."
        raise ValueError(msg)
    if ts.shape[1] != expected_timesteps:
        msg = f"Timeseries must have {expected_timesteps} timesteps. Got {ts.shape[1]} timesteps."
        raise ValueError(msg)


def calculate_edh(
    dbt_mat: NDArray[np.float64],
    rh_mat: NDArray[np.float64],
    mrt_mat: NDArray[np.float64],
    met: float = 1.1,
    clo: float = 0.5,
    v: float = 0.1,
    comfort_bounds: tuple[float, float] = (22, 27),
    zone_names: list[str] | None = None,
    zone_weights: NDArray[np.float64] | None = None,
) -> pd.DataFrame:
    """Calculates Exceedance Degree Hours (EDH) using fixed comfort bounds and separates hot and cold contributions.

    When aggregating at the building scale, we compute a few variants:
        - Zone Weighted: The weighted average of the EDHs for all zones.
        - Worst Zone: The EDH for the zone with the worst EDH.

    Parameters:
        dry_bulb_temperature_mat (np.ndarray): The dry bulb temperature matrix (zones x timesteps).
        relative_humidity_mat (np.ndarray): The relative humidity matrix (zones x timesteps).
        mean_radiant_temperature_mat (np.ndarray): The mean radiant temperature matrix (zones x timesteps).
        met (float): The metabolic rate in metabolic equivalents (MET).
        clo (float): The clothing insulation in clo.
        v (float): The air speed in meters per second.
        comfort_bounds (tuple[float, float]): The comfort bounds in degrees Celsius considered comfortable.
        zone_names (list[str] | None): The names of the zones. If None, the zones will be named "Zone 001", "Zone 002", etc.
        zone_weights (NDArray[np.float64] | None): The weights of the zones. If None, the zones will be weighted equally when summing the EDHs.

    Returns:
        building_edhs (pd.DataFrame): A dataframe with the building weighted EDHs.
        zone_edhs (pd.DataFrame): A dataframe with the EDHs for each zone.
    """
    from pythermalcomfort.models import set_tmp

    _zone_weights = (
        zone_weights if zone_weights is not None else np.ones(dbt_mat.shape[0])
    )
    _zone_names = (
        [f"Zone {i:03d}" for i in range(dbt_mat.shape[0])]
        if zone_names is None
        else zone_names
    )

    zone_names_len = len(_zone_names)
    if zone_names_len != len(_zone_weights):
        msg = f"Zone names and zone weights must have the same length. Got {zone_names_len} zone names and {len(_zone_weights)} zone weights."
        raise ValueError(msg)

    check_timeseries_shape(
        dbt_mat, expected_zones=zone_names_len, expected_timesteps=8760
    )
    check_timeseries_shape(
        mrt_mat,
        expected_zones=zone_names_len,
        expected_timesteps=8760,
    )
    check_timeseries_shape(
        rh_mat, expected_zones=zone_names_len, expected_timesteps=8760
    )

    SETs = np.stack(
        [
            set_tmp(
                tdb=dbt_row,
                tr=mrt_row,
                rh=relative_humidity_row,
                met=met,
                clo=clo,
                v=v,
                limit_inputs=False,  # TODO: remove this, or set it and handle NaN cases appropriately.
            )["set"]
            for dbt_row, mrt_row, relative_humidity_row in zip(
                dbt_mat,
                mrt_mat,
                rh_mat,
                strict=False,
            )
        ],
        axis=0,
    )
    low, high = np.sort(comfort_bounds)
    hot_edh = np.maximum(0, SETs - high)
    cold_edh = np.maximum(0, low - SETs)
    total_edh = hot_edh + cold_edh

    edhs_by_zone: NDArray[np.float64] = np.stack(
        [total_edh, hot_edh, cold_edh], axis=2
    ).sum(axis=1)
    edhs = pd.DataFrame(
        edhs_by_zone,
        index=_zone_names,
        columns=["Total", "Heat Exceedance", "Cold Exceedance"],
        dtype=np.float64,
    )
    edhs.index.name = "Zone"
    edhs.columns.name = "EDH Type"

    normalized_zone_weights: NDArray[np.float64] = _zone_weights / _zone_weights.sum()
    # weighted_edhs_by_zone: NDArray[np.float64] = (
    #     edhs_by_zone * normalized_zone_weights.reshape(-1, 1)
    # )
    weighted_edhs_by_zone = edhs.mul(normalized_zone_weights, axis=0)

    aggregated_edhs = weighted_edhs_by_zone.sum(axis=0)
    worst_edh = edhs.max(axis=0)

    building_edhs = pd.concat(
        [aggregated_edhs, worst_edh], axis=1, keys=["Zone Weighted", "Worst Zone"]
    ).T
    final = pd.concat(
        [building_edhs, edhs],
        axis=0,
        names=["Aggregation Unit", "Group"],
        keys=["Building", "Zone"],
    )
    return final.rename(columns={c: f"{c} [degC-hr]" for c in final.columns})


def calculate_basic_overheating_stats(
    dbt_mat: NDArray[np.float64],
    zone_names: list[str] | None = None,
    zone_weights: NDArray[np.float64] | None = None,
    overheating_thresholds: tuple[float, ...] = (26, 30, 35),
    undercooling_thresholds: tuple[float, ...] = (10, 5),
) -> pd.DataFrame:
    """Calculates basic overheating hours by zone and for the whole building.

    When aggregating at the building scale, we compute a few variants:
        - Any Zone: The number of timesteps that the threshold is violated for any zone in the whole building.
        - Zone Weighted: The number of timesteps that the threshold is violated for the weighted average of all zones.
        - Worst Zone: The number of timesteps that the threshold is violated for the zone with the worst number of violations.

    Args:
        dbt_mat (NDArray[np.float64]): The dry bulb temperature matrix (zones x timesteps).
        zone_names (list[str] | None): The names of the zones. If None, the zones will be named "Zone 001", "Zone 002", etc.
        zone_weights (NDArray[np.float64] | None): The weights of the zones. If None, the zones will be weighted equally when summing the overheating hours.
        overheating_thresholds (tuple[float, ...]): The thresholds for overheating.
        undercooling_thresholds (tuple[float, ...]): The thresholds for undercooling.

    Returns:
        hours (pd.DataFrame): A dataframe with the overheating and undercooling hours by threshold for the whole building and by zone and threshold for each zone.

    """
    zone_names_ = (
        [f"Zone {i:03d}" for i in range(dbt_mat.shape[0])]
        if zone_names is None
        else zone_names
    )
    zone_weights_ = (
        zone_weights if zone_weights is not None else np.ones(dbt_mat.shape[0])
    )
    if len(zone_names_) != len(zone_weights_):
        msg = f"Zone names and zone weights must have the same length. Got {len(zone_names_)} zone names and {len(zone_weights_)} zone weights."
        raise ValueError(msg)
    normalized_zone_weights: NDArray[np.float64] = zone_weights_ / zone_weights_.sum()
    n_zones = len(zone_weights_)
    check_timeseries_shape(dbt_mat, expected_zones=n_zones, expected_timesteps=8760)

    overheat_thresholds = np.array(overheating_thresholds)
    undercool_thresholds = np.array(undercooling_thresholds)

    # threshold comparisons have shape (n_thresholds, n_zones, n_timesteps)
    over_thresh_by_zone = dbt_mat > overheat_thresholds.reshape(-1, 1, 1)
    under_thresh_by_zone = dbt_mat < undercool_thresholds.reshape(-1, 1, 1)
    # max returns true if any of the zones are above the threshold
    # thresh_any has shape (n_thresholds, n_timesteps)
    over_thresh_any: NDArray[np.bool_] = over_thresh_by_zone.max(
        axis=1
    )  # max returns true if threshold is exceeded for any zone
    under_thresh_any: NDArray[np.bool_] = under_thresh_by_zone.max(axis=1)

    # sum returns the number of timesteps that the threshold is exceeded for each zone
    # hours_by_zone has shape (n_thresholds, n_zones)
    over_hours_by_zone = over_thresh_by_zone.sum(axis=-1)
    under_hours_by_zone = under_thresh_by_zone.sum(axis=-1)

    over_hours_by_zone = pd.DataFrame(
        over_hours_by_zone,
        columns=pd.Index(zone_names_, name="Zone"),
        index=pd.Index(overheat_thresholds, name="Threshold [degC]"),
        dtype=np.float64,
    )
    under_hours_by_zone = pd.DataFrame(
        under_hours_by_zone,
        columns=pd.Index(zone_names_, name="Zone"),
        index=pd.Index(undercool_thresholds, name="Threshold [degC]"),
        dtype=np.float64,
    )

    worst_overhours_by_threshold = over_hours_by_zone.max(axis=1)
    worst_underhours_by_threshold = under_hours_by_zone.max(axis=1)

    weighted_overhours_by_threshold = over_hours_by_zone.mul(
        normalized_zone_weights
    ).sum(axis=1)
    weighted_underhours_by_threshold = under_hours_by_zone.mul(
        normalized_zone_weights
    ).sum(axis=1)

    over_hours_by_zone["Any Zone"] = over_thresh_any.sum(axis=1)
    under_hours_by_zone["Any Zone"] = under_thresh_any.sum(axis=1)
    over_hours_by_zone["Zone Weighted"] = weighted_overhours_by_threshold
    under_hours_by_zone["Zone Weighted"] = weighted_underhours_by_threshold
    over_hours_by_zone["Worst Zone"] = worst_overhours_by_threshold
    under_hours_by_zone["Worst Zone"] = worst_underhours_by_threshold
    over_hours_by_zone["Equally Weighted"] = over_hours_by_zone.mean(axis=1)
    under_hours_by_zone["Equally Weighted"] = under_hours_by_zone.mean(axis=1)

    over_whole_bldg = over_hours_by_zone[
        ["Any Zone", "Zone Weighted", "Worst Zone", "Equally Weighted"]
    ]
    under_whole_bldg = under_hours_by_zone[
        ["Any Zone", "Zone Weighted", "Worst Zone", "Equally Weighted"]
    ]
    over_hours_by_zone = over_hours_by_zone.drop(
        columns=["Any Zone", "Zone Weighted", "Worst Zone", "Equally Weighted"]
    )
    under_hours_by_zone = under_hours_by_zone.drop(
        columns=["Any Zone", "Zone Weighted", "Worst Zone", "Equally Weighted"]
    )

    ouh_counts_by_zone_and_threshold = pd.concat(
        [over_hours_by_zone, under_hours_by_zone],
        axis=0,
        keys=["Overheat", "Underheat"],
        names=["Metric", "Threshold [degC]"],
    )

    ouh_counts_by_building_and_threshold = pd.concat(
        [over_whole_bldg, under_whole_bldg],
        axis=0,
        keys=["Overheat", "Underheat"],
        names=["Metric", "Threshold [degC]"],
    )

    combined = pd.concat(
        [ouh_counts_by_building_and_threshold, ouh_counts_by_zone_and_threshold],
        axis=1,
        names=["Aggregation Unit", "Group"],
        keys=["Building", "Zone"],
    ).T
    combined.columns.names = ["Polarity", "Threshold [degC]"]
    combined = (
        cast(pd.Series, cast(pd.DataFrame, combined.stack()).stack())
        .rename("Total Hours [hr]")
        .dropna()
        .to_frame()
        .reorder_levels(
            ["Polarity", "Threshold [degC]", "Aggregation Unit", "Group"], axis=0
        )
    )

    return combined


def _consecutive_run_lengths_vectorized(
    M_diff: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Compute lengths and integrals of consecutive runs where M_diff > 0, along the last axis.

    M_diff has shape (..., n_timesteps). For each (..., :) slice, identifies runs where
    M_diff > 0 and returns:
      - lengths: (n_slices, max_runs) count of timesteps per run, NaN-padded.
      - integrals: (n_slices, max_runs) sum of M_diff over each run (degree-hours), NaN-padded.

    Uses run_id + bincount (and bincount with weights for integrals) so no Python loops
    over rows or timesteps.
    """
    M = M_diff > 0
    orig_shape = M.shape
    n_timesteps = orig_shape[-1]
    n_slices = int(np.prod(orig_shape[:-1]))
    M_2d = M.reshape(n_slices, n_timesteps)
    M_diff_2d = M_diff.reshape(n_slices, n_timesteps)

    # Run starts: True where a new run of True begins
    run_start = np.empty_like(M_2d)
    run_start[:, 0] = M_2d[:, 0]
    run_start[:, 1:] = M_2d[:, 1:] & ~M_2d[:, :-1]

    # Run id: 0 where False, 1,2,3,... for each run of True
    run_id = np.where(M_2d, np.cumsum(run_start, axis=1), 0)

    max_run_id = int(run_id.max())
    if max_run_id == 0:
        nan_out = np.full((n_slices, 1), np.nan, dtype=np.float64)
        return nan_out, nan_out.copy()

    # Linear index for (row, run_id); run_id is 1..max_run_id
    flat_row = np.repeat(np.arange(n_slices, dtype=np.intp), n_timesteps)
    flat_run = run_id.ravel()
    mask = flat_run > 0
    flat_row = flat_row[mask]
    flat_run = flat_run[mask]
    flat_diff = M_diff_2d.ravel()[mask]

    idx = flat_row * max_run_id + (flat_run - 1)
    counts_flat = np.bincount(idx, minlength=n_slices * max_run_id)
    counts = counts_flat.reshape(n_slices, max_run_id).astype(np.float64)
    counts[counts == 0] = np.nan

    integrals_flat = np.bincount(
        idx, weights=flat_diff, minlength=n_slices * max_run_id
    )
    integrals = integrals_flat.reshape(n_slices, max_run_id).astype(np.float64)
    integrals[np.isnan(counts)] = np.nan
    return counts, integrals


def calculate_consecutive_hours_above_threshold(
    dbt_mat: NDArray[np.float64],
    overheating_thresholds: list[float] | tuple[float, ...] = (26, 30, 35),
    underheating_thresholds: list[float] | tuple[float, ...] = (10, 5),
    zone_names: list[str] | None = None,
) -> pd.DataFrame:
    """Calculates consecutive hours above (overheating) or below (underheating) thresholds per zone.

    For each overheating threshold and each zone, computes the lengths of every run of
    consecutive hours above that threshold. For each underheating threshold and each zone,
    computes the lengths of every run of consecutive hours below that threshold. Uses
    vectorized operations across thresholds and zones; only the time dimension is
    processed with run-length logic.

    Args:
        dbt_mat (NDArray[np.float64]): The dry bulb temperature matrix (zones x timesteps).
        overheating_thresholds (list[float] | tuple[float, ...]): Thresholds for consecutive hours *above*. If None, uses (26, 30, 35).
        underheating_thresholds (list[float] | tuple[float, ...]): Thresholds for consecutive hours *below*. If None, uses (10, 5).
        zone_names (list[str] | None): The names of the zones. If None, zones are named "Zone 001", "Zone 002", etc.

    Returns:
        pd.DataFrame: MultiIndex (Metric, Threshold [degC], Zone). Columns "Streak 001", ... (run lengths, NaN-padded) and "Integral 001", ... (sum of excess/deficit per run, degree-hours, NaN-padded).
    """
    n_zones, _ = dbt_mat.shape
    zone_names_ = (
        [f"Zone {i + 1:03d}" for i in range(n_zones)]
        if zone_names is None
        else zone_names
    )

    over_arr = np.asarray(overheating_thresholds, dtype=np.float64)
    under_arr = np.asarray(underheating_thresholds, dtype=np.float64)

    check_timeseries_shape(dbt_mat, expected_zones=n_zones, expected_timesteps=8760)

    # Excess/deficit for integrals: (n_thresholds, n_zones, n_timesteps)
    over_diff = dbt_mat - over_arr.reshape(-1, 1, 1)
    under_diff = under_arr.reshape(-1, 1, 1) - dbt_mat

    # Compute run lengths and integrals for all (threshold, zone) slices in one go per metric
    if over_arr.size > 0:
        over_lengths, over_integrals = _consecutive_run_lengths_vectorized(over_diff)
    else:
        over_lengths = over_integrals = np.empty((0, 0), dtype=np.float64)
    if under_arr.size > 0:
        under_lengths, under_integrals = _consecutive_run_lengths_vectorized(under_diff)
    else:
        under_lengths = under_integrals = np.empty((0, 0), dtype=np.float64)

    def build_df(
        lengths: NDArray[np.float64],
        integrals: NDArray[np.float64],
        thresholds: NDArray[np.float64],
        metric: str,
    ) -> pd.DataFrame:
        if lengths.size == 0:
            return pd.DataFrame()
        n_runs = lengths.shape[1]
        index = pd.MultiIndex.from_product(
            [
                [metric],
                list(thresholds),
                zone_names_,
            ],
            names=["Polarity", "Threshold [degC]", "Zone"],
        )
        streak_cols = [f"{i:05d}" for i in range(n_runs)]
        integral_cols = [f"{i:05d}" for i in range(n_runs)]
        length_df = pd.DataFrame(
            lengths,
            index=index,
            columns=streak_cols,
            dtype=np.float64,
        )
        integral_df = pd.DataFrame(
            integrals,
            index=index,
            columns=integral_cols,
            dtype=np.float64,
        )
        return pd.concat(
            [length_df, integral_df],
            axis=1,
            keys=["Streak [hr]", "Integral [deg-hr]"],
            names=["Metric", "Streak Index"],
        )

    over_df = build_df(over_lengths, over_integrals, over_arr, "Overheat")
    under_df = build_df(under_lengths, under_integrals, under_arr, "Underheat")

    if over_df.size == 0 and under_df.size == 0:
        return pd.DataFrame(
            index=pd.MultiIndex.from_tuples(
                [], names=["Metric", "Threshold [degC]", "Zone"]
            ),
        )

    if over_df.size == 0:
        return under_df
    if under_df.size == 0:
        return over_df
    return cast(
        pd.DataFrame,
        (
            pd.concat([over_df, under_df], axis=0)
            .stack(level="Streak Index", future_stack=True)
            .dropna()
        ),
    )


def _consecutive_run_lengths_looped(
    M_diff: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Compute lengths of consecutive True runs along the last axis, for all leading dimensions.

    M has shape (..., n_timesteps). For each (..., :) slice, returns run lengths in a padded
    2D array of shape (n_slices, max_runs), with NaN padding.
    """
    # TODO: use this method in a test to validate the vectorized version.
    M = M_diff > 0
    orig_shape = M.shape
    n_timesteps = orig_shape[-1]
    n_slices = int(np.prod(orig_shape[:-1]))

    M_2d = M.reshape(n_slices, n_timesteps)
    M_diff_2d = M_diff.reshape(n_slices, n_timesteps)

    slice_streaks = []
    slice_streak_integrals = []
    for slice_ix in range(n_slices):
        slice_data = M_2d[slice_ix, :]
        is_streaking = False
        streak_len = 0
        streak_integral = 0
        streaks = []
        streak_integrals = []
        for i in range(n_timesteps):
            flag = slice_data[i]
            diff = M_diff_2d[slice_ix, i]
            if flag and not is_streaking:
                is_streaking = True
                streak_len = 1
                streak_integral = diff
            elif flag and is_streaking:
                streak_len += 1
                streak_integral += diff
            elif not flag and is_streaking:
                streaks.append(streak_len)
                streak_integrals.append(streak_integral)
                is_streaking = False
                streak_len = 0
                streak_integral = 0
            else:
                streak_len = 0
                streak_integral = 0
        if is_streaking:
            streaks.append(streak_len)
            streak_integrals.append(streak_integral)
        slice_streaks.append(streaks)
        slice_streak_integrals.append(streak_integrals)
    most_streaks = max(len(streaks) for streaks in slice_streaks)
    most_streak_integrals = max(
        len(streak_integrals) for streak_integrals in slice_streak_integrals
    )
    padded_streaks = np.full((n_slices, most_streaks), np.nan, dtype=np.float64)
    padded_streak_integrals = np.full(
        (n_slices, most_streak_integrals), np.nan, dtype=np.float64
    )
    for slice_ix in range(n_slices):
        padded_streaks[slice_ix, : len(slice_streaks[slice_ix])] = slice_streaks[
            slice_ix
        ]
        padded_streak_integrals[slice_ix, : len(slice_streak_integrals[slice_ix])] = (
            slice_streak_integrals[slice_ix]
        )
    reshaped_streaks = padded_streaks.reshape((
        *orig_shape[:-1],
        most_streaks,
    ))
    reshaped_streak_integrals = padded_streak_integrals.reshape((
        *orig_shape[:-1],
        most_streak_integrals,
    ))
    return reshaped_streaks, reshaped_streak_integrals


def overheating_results_postprocess(
    sql: Sql,
    zone_weights: NDArray[np.float64],
    zone_names: list[str],
):
    """Postprocess the sql file to get the temperature results.

    Args:
        sql (Sql): The sql file to postprocess.
        zone_weights (NDArray[np.float64]): The weights of the zones.
        zone_names (list[str]): The names of the zones.
    """
    # TODO: compare the single request flamegraph to splitting it out as multiple requests
    hourly = sql.timeseries_by_name(
        [
            "Zone Mean Air Temperature",
            "Zone Air Relative Humidity",
            "Zone Mean Radiant Temperature",
        ],
        "Hourly",
    )
    hourly.index.names = ["Timestep"]
    hourly.columns.names = ["_", "Zone", "Meter"]

    hourly: pd.DataFrame = cast(
        pd.DataFrame,
        hourly.droplevel("_", axis=1)
        .stack(level="Zone", future_stack=True)
        .unstack(level="Timestep"),
    )

    rh = hourly.xs("Zone Air Relative Humidity", level="Meter", axis=1)
    dbt = hourly.xs("Zone Mean Air Temperature", level="Meter", axis=1)
    radiant = hourly.xs("Zone Mean Radiant Temperature", level="Meter", axis=1)

    zone_names_: list[str] = dbt.index.tolist()
    zone_names__: list[str] = radiant.index.tolist()
    zone_names___: list[str] = rh.index.tolist()
    if (
        {z.lower() for z in zone_names} != {z.lower() for z in zone_names_}
        or {z.lower() for z in zone_names} != {z.lower() for z in zone_names__}
        or {z.lower() for z in zone_names} != {z.lower() for z in zone_names___}
    ):
        msg = f"Zone names do not match! Expected: {zone_names}, Found: {zone_names_}, {zone_names__}, {zone_names___}."
        raise ValueError(msg)
    if zone_names_ != zone_names__ or zone_names_ != zone_names___:
        msg = f"Dataframe zone names are not in the same order as each other! Expected: {zone_names_}, but got {zone_names__}, {zone_names___}."
        raise ValueError(msg)

    # reorder the zone weights to match the zone names.
    zone_weights_to_use = np.array([
        zone_weights[[z.lower() for z in zone_names].index(zone.lower())]
        for zone in zone_names_
    ])
    zone_names_to_use = zone_names_

    dbt_mat = dbt.to_numpy()
    rh_mat = rh.to_numpy()
    radiant_mat = radiant.to_numpy()

    hi = calculate_hi_categories(
        dbt_mat=dbt_mat,
        rh_mat=rh_mat,
        zone_names=zone_names_to_use,
        zone_weights=zone_weights_to_use,
    )

    edh = calculate_edh(
        dbt_mat=dbt_mat,
        rh_mat=rh_mat,
        mrt_mat=radiant_mat,
        zone_names=zone_names_to_use,
        zone_weights=zone_weights_to_use,
    )

    consecutive_e_zone = calculate_consecutive_hours_above_threshold(
        dbt_mat=dbt_mat,
        zone_names=zone_names_to_use,
    )

    basic_oh = calculate_basic_overheating_stats(
        dbt_mat=dbt_mat,
        zone_names=zone_names_to_use,
        zone_weights=zone_weights_to_use,
    )
    return OverheatingAnalysisResults(
        hi=hi, edh=edh, basic_oh=basic_oh, consecutive_e_zone=consecutive_e_zone
    )


@dataclass
class OverheatingAnalysisResults:
    """The results of a overheating analysis."""

    hi: pd.DataFrame
    edh: pd.DataFrame
    basic_oh: pd.DataFrame
    consecutive_e_zone: pd.DataFrame


if __name__ == "__main__":
    # Timesteps should be along the columns
    # Zones should be along the rows
    _n_timesteps = 8760
    _n_zones = 10
    _temperature_matrix = np.random.rand(_n_zones, _n_timesteps) * 30 + 10
    _relative_humidity_matrix = np.random.rand(_n_zones, _n_timesteps) * 50 + 50
    # _mean_radiant_temperature_matrix = np.random.rand(_n_zones, _n_timesteps) * 40 - 10
    _mean_radiant_temperature_matrix = (
        _temperature_matrix + np.random.randn(_n_zones, _n_timesteps) * 1
    )
    r = calculate_hi_categories(_temperature_matrix, _relative_humidity_matrix)

    edh = calculate_edh(
        _temperature_matrix,
        _relative_humidity_matrix,
        _mean_radiant_temperature_matrix,
    )

    basic_oh_stats = calculate_basic_overheating_stats(_temperature_matrix)

    consecutive_hours = calculate_consecutive_hours_above_threshold(
        np.array(
            [
                [
                    np.sin(i / _n_timesteps * 2 * np.pi) * 30 + 5
                    for i in range(_n_timesteps)
                ],
                [
                    np.cos(i / _n_timesteps * 2 * np.pi) * 30 + 5
                    for i in range(_n_timesteps)
                ],
                [
                    np.cos(2 * i / _n_timesteps * 2 * np.pi) * 30 + 5
                    for i in range(_n_timesteps)
                ],
                [
                    np.sin(2 * i / _n_timesteps * 2 * np.pi) * 30 + 5
                    for i in range(_n_timesteps)
                ],
            ],
        ),
    )

    print("---- Heat Index ----")
    print("\n")
    print(r)
    print("--- EDH ----")
    print("\n")
    print(edh)
    print("--- Basic Overheating Stats ----")
    print("\n")
    print(basic_oh_stats)
    print("--- Consecutive Hours ----")
    print("\n")
    print(consecutive_hours)
