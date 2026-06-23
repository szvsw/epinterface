"""Tests for zone and floor energy aggregation."""

from typing import Any, cast

import pandas as pd
import pytest

from epinterface.analysis import zone_energy
from epinterface.analysis.zone_energy import (
    floor_energy_summary,
    merge_assignment_and_energy,
    zone_energy_summary,
)


class _FakeZone:
    """Small stand-in for an EnergyPlus ZONE object."""

    def __init__(self, name: str) -> None:
        """Store the generated zone name."""
        self.Name = name


class _FakeIDF:
    """Small stand-in exposing the idfobjects mapping used by zone_energy."""

    def __init__(self, zone_names: list[str]) -> None:
        """Create fake ZONE objects."""
        self.idfobjects = {"ZONE": [_FakeZone(name) for name in zone_names]}


class _FakeSql:
    """Fake Sql object returning prepared hourly DataFrames by variable name."""

    def __init__(self, data: dict[str, pd.DataFrame]) -> None:
        """Store variable-name keyed DataFrames."""
        self.data = data

    def timeseries_by_name(self, names: list[str], reporting_frequency: str):
        """Return the fake hourly timeseries for the requested variable."""
        assert reporting_frequency == "Hourly"
        return self.data[names[0]]


def _hourly_df(variable_name: str, key_value: str, values: list[float]) -> pd.DataFrame:
    """Create an archetypal-like hourly variable DataFrame."""
    columns = pd.MultiIndex.from_tuples(
        [("Zone", key_value, variable_name)],
        names=["IndexGroup", "KeyValue", "Name"],
    )
    return pd.DataFrame(values, columns=columns)


def test_zone_energy_summary_returns_raw_and_normalized_kwh(monkeypatch) -> None:
    """Zone energy summary converts Joules to kWh and normalizes by zone area."""
    zone_name = "Block shoebox Storey 0"
    idf = _FakeIDF([zone_name])
    sql = _FakeSql({
        "Zone Lights Electricity Energy": _hourly_df(
            "Zone Lights Electricity Energy", zone_name, [3_600_000, 3_600_000]
        ),
        "Zone Electric Equipment Electricity Energy": _hourly_df(
            "Zone Electric Equipment Electricity Energy", zone_name, [3_600_000]
        ),
        "Zone Ideal Loads Zone Total Heating Energy": pd.DataFrame(),
        "Zone Ideal Loads Zone Total Cooling Energy": pd.DataFrame(),
    })
    monkeypatch.setattr(zone_energy, "get_zone_floor_area", lambda _idf, _zone: 10.0)

    result = zone_energy_summary(cast(Any, sql), cast(Any, idf))

    assert result.loc[0, "sim_lighting_site_kwh"] == pytest.approx(2.0)
    assert result.loc[0, "sim_lighting_site_kwh_per_m2"] == pytest.approx(0.2)
    assert result.loc[0, "sim_equipment_site_kwh"] == pytest.approx(1.0)
    assert result.loc[0, "sim_total_included_kwh"] == pytest.approx(3.0)


def test_zone_energy_summary_maps_ideal_loads_system_keys(monkeypatch) -> None:
    """Ideal-loads output keys ending in system suffix map back to zone names."""
    zone_name = "Block shoebox Storey 0"
    idf = _FakeIDF([zone_name])
    sql = _FakeSql({
        "Zone Lights Electricity Energy": pd.DataFrame(),
        "Zone Electric Equipment Electricity Energy": pd.DataFrame(),
        "Zone Ideal Loads Zone Total Heating Energy": _hourly_df(
            "Zone Ideal Loads Zone Total Heating Energy",
            f"{zone_name} Ideal Loads Air System",
            [7_200_000],
        ),
        "Zone Ideal Loads Zone Total Cooling Energy": pd.DataFrame(),
    })
    monkeypatch.setattr(zone_energy, "get_zone_floor_area", lambda _idf, _zone: 20.0)

    result = zone_energy_summary(cast(Any, sql), cast(Any, idf))

    assert result.loc[0, "sim_heating_delivered_kwh"] == pytest.approx(2.0)
    assert result.loc[0, "sim_heating_delivered_kwh_per_m2"] == pytest.approx(0.1)


def _two_floor_zone_df() -> pd.DataFrame:
    """A small zone-energy table spanning two above-grade floors."""
    return pd.DataFrame({
        "ep_zone_name": ["z0", "z1", "z2"],
        "category": ["main", "main", "main"],
        "floor_index": [0, 0, 1],
        "floor_area_m2": [10.0, 30.0, 20.0],
        "sim_lighting_site_kwh": [10.0, 90.0, 20.0],
        "sim_equipment_site_kwh": [0.0, 0.0, 0.0],
        "sim_heating_delivered_kwh": [0.0, 0.0, 0.0],
        "sim_cooling_delivered_kwh": [0.0, 0.0, 0.0],
        "sim_total_included_kwh": [10.0, 90.0, 20.0],
    })


def test_floor_energy_summary_sums_raw_energy_then_normalizes() -> None:
    """Floor aggregation sums raw zone kWh before dividing by total floor area."""
    floor_df = floor_energy_summary(_two_floor_zone_df())

    assert floor_df.shape[0] == 2
    assert floor_df.loc[0, "floor_area_m2"] == 40.0
    assert floor_df.loc[0, "sim_lighting_site_kwh"] == 100.0
    assert floor_df.loc[0, "sim_lighting_site_kwh_per_m2"] == 2.5


def test_floor_energy_summary_excludes_basement_and_attic() -> None:
    """Only 'main' zones contribute, so basement/attic rows are excluded."""
    zone_df = _two_floor_zone_df()
    extra = pd.DataFrame({
        "ep_zone_name": ["bsmt", "attic"],
        "category": ["basement", "attic"],
        "floor_index": [None, None],
        "floor_area_m2": [50.0, 50.0],
        "sim_lighting_site_kwh": [5.0, 5.0],
        "sim_equipment_site_kwh": [0.0, 0.0],
        "sim_heating_delivered_kwh": [0.0, 0.0],
        "sim_cooling_delivered_kwh": [0.0, 0.0],
        "sim_total_included_kwh": [5.0, 5.0],
    })
    combined = pd.concat([zone_df, extra], ignore_index=True)

    floor_df = floor_energy_summary(combined, n_floors=2)

    assert set(floor_df["floor_index"]) == {0, 1}


def test_floor_energy_summary_validates_n_floors() -> None:
    """A missing floor row is a hard error when n_floors is supplied."""
    # Only floors 0 and 1 are present; asserting 3 floors must fail.
    with pytest.raises(ValueError, match="floor"):
        floor_energy_summary(_two_floor_zone_df(), n_floors=3)


def test_floor_energy_summary_passes_when_n_floors_matches() -> None:
    """Two floors present and n_floors=2 validates cleanly."""
    floor_df = floor_energy_summary(_two_floor_zone_df(), n_floors=2)
    assert set(floor_df["floor_index"]) == {0, 1}


def test_merge_assignment_and_energy_has_no_suffixed_metadata() -> None:
    """Merging assignment + energy must not create *_x / *_y duplicate columns."""
    assignment = pd.DataFrame({
        "ep_zone_name": ["z0", "z1"],
        "floor_index": [0, 1],
        "role": ["floor", "floor"],
        "category": ["main", "main"],
        "floor_area_m2": [10.0, 20.0],
        "LightingPowerDensity": [5.0, 15.0],
    })
    energy = pd.DataFrame({
        "ep_zone_name": ["z0", "z1"],
        "floor_index": [0, 1],
        "role": ["floor", "floor"],
        "category": ["main", "main"],
        "ep_storey_index": [0, 1],
        "floor_area_m2": [10.0, 20.0],
        "sim_lighting_site_kwh": [50.0, 300.0],
        "sim_total_included_kwh": [50.0, 300.0],
    })

    merged = merge_assignment_and_energy(assignment, energy)

    assert not any(c.endswith(("_x", "_y")) for c in merged.columns)
    # Metadata columns appear exactly once, energy columns are joined in.
    assert list(merged["floor_index"]) == [0, 1]
    assert merged.loc[0, "sim_lighting_site_kwh"] == 50.0
    assert merged.loc[1, "LightingPowerDensity"] == 15.0


def test_zone_energy_summary_missing_variables_are_none(monkeypatch) -> None:
    """Missing SQL variables yield None columns rather than crashing."""
    zone_name = "Block shoebox Storey 0"
    idf = _FakeIDF([zone_name])
    sql = _FakeSql({
        "Zone Lights Electricity Energy": pd.DataFrame(),
        "Zone Electric Equipment Electricity Energy": pd.DataFrame(),
        "Zone Ideal Loads Zone Total Heating Energy": pd.DataFrame(),
        "Zone Ideal Loads Zone Total Cooling Energy": pd.DataFrame(),
    })
    monkeypatch.setattr(zone_energy, "get_zone_floor_area", lambda _idf, _zone: 10.0)

    result = zone_energy_summary(cast(Any, sql), cast(Any, idf))

    assert result.loc[0, "sim_lighting_site_kwh"] is None
    assert result.loc[0, "sim_total_included_kwh"] is None
