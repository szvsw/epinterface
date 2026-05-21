"""matplotlib plots comparing resolved zone-assignment scalars and sim energy."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import pandas as pd

if TYPE_CHECKING:
    from epinterface.sbem.builder import ModelRunResults

DEFAULT_ASSIGNMENT_METRICS: tuple[str, ...] = (
    "LightingPowerDensity",
    "EquipmentPowerDensity",
    "FacadeRValue",
)

DEFAULT_SIM_ENERGY_METRICS: tuple[str, ...] = (
    "sim_lighting_kwh_per_m2",
    "sim_equipment_kwh_per_m2",
    "sim_heating_kwh_per_m2",
    "sim_cooling_kwh_per_m2",
    "sim_total_kwh_per_m2",
)


def _import_plt():
    try:
        import matplotlib.pyplot as plt
        from matplotlib.axes import Axes
        from matplotlib.figure import Figure
    except ImportError as exc:
        msg = "matplotlib is required for plotting (install dev deps: uv sync --group dev)"
        raise ImportError(msg) from exc
    return plt, Axes, Figure


def _plot_label_column(
    df: pd.DataFrame, groupby: Literal["zone", "storey_role"]
) -> pd.Series:
    if groupby == "zone":
        return df["ep_zone_name"].astype(str)
    return "S" + df["storey_index"].astype(str) + " / " + df["role"].astype(str)


def _horizontal_metric_bars(
    df: pd.DataFrame,
    metrics: tuple[str, ...],
    *,
    groupby: Literal["zone", "storey_role"],
    title_prefix: str = "",
    ax=None,
):
    plt, Axes, Figure = _import_plt()
    plot_df = df.copy()
    plot_df["_plot_label"] = _plot_label_column(plot_df, groupby)

    present = [m for m in metrics if m in plot_df.columns]
    if not present:
        msg = f"none of the metrics {metrics!r} appear in columns {list(plot_df.columns)!r}"
        raise ValueError(msg)

    roles = (
        sorted(plot_df["role"].astype(str).unique())
        if "role" in plot_df.columns
        else ["all"]
    )
    cmap = plt.colormaps["tab10"]
    role_color = {r: cmap(i % 10) for i, r in enumerate(roles)}

    if ax is not None:
        if len(present) > 1:
            msg = "pass a single metric when ax is provided"
            raise ValueError(msg)
        metric = present[0]
        if not isinstance(ax, Axes):
            msg = "ax must be a matplotlib Axes when provided"
            raise TypeError(msg)
        sub = plot_df.sort_values(["storey_index", "role", "_plot_label"])
        colors = [role_color.get(str(r), cmap(0)) for r in sub.get("role", sub.index)]
        ax.barh(sub["_plot_label"], sub[metric], color=colors)
        ax.set_xlabel(metric)
        ax.set_title(f"{title_prefix}{metric}".strip())
        return ax.figure

    fig_h = max(3.0, 2.0 * len(present))
    fig, axes = plt.subplots(len(present), 1, figsize=(9, fig_h), squeeze=False)
    for axi, metric in zip(axes.flatten(), present, strict=True):
        sub = plot_df.sort_values(["storey_index", "role", "_plot_label"])
        colors = [role_color.get(str(r), cmap(0)) for r in sub.get("role", sub.index)]
        axi.barh(sub["_plot_label"], sub[metric], color=colors)
        axi.set_xlabel(metric)
        axi.set_title(f"{title_prefix}{metric}".strip())
    fig.tight_layout()
    if not isinstance(fig, Figure):
        msg = "expected matplotlib Figure"
        raise TypeError(msg)
    return fig


def plot_zone_comparison(
    summary: pd.DataFrame,
    metrics: tuple[str, ...] = DEFAULT_ASSIGNMENT_METRICS,
    *,
    groupby: Literal["zone", "storey_role"] = "zone",
    ax=None,
):
    """Horizontal bars for resolved assignment scalars (inputs)."""
    return _horizontal_metric_bars(summary, metrics, groupby=groupby, ax=ax)


def plot_zone_energy_comparison(
    summary: pd.DataFrame,
    metrics: tuple[str, ...] = DEFAULT_SIM_ENERGY_METRICS,
    *,
    groupby: Literal["zone", "storey_role"] = "zone",
    ax=None,
    results: ModelRunResults | None = None,
):
    """Horizontal bars of simulated annual site energy (kWh/m2) per zone."""
    if results is not None:
        from epinterface.analysis.zone_energy import (
            merge_assignment_and_energy,
            zone_energy_summary,
        )

        energy = zone_energy_summary(results.sql, results.idf)
        summary = merge_assignment_and_energy(summary, energy)
    present = tuple(m for m in metrics if m in summary.columns)
    return _horizontal_metric_bars(
        summary,
        present or DEFAULT_SIM_ENERGY_METRICS,
        groupby=groupby,
        title_prefix="sim: ",
        ax=ax,
    )


def plot_assignment_and_energy(
    summary: pd.DataFrame,
    *,
    results: ModelRunResults,
    groupby: Literal["zone", "storey_role"] = "zone",
):
    """Return (assignment_figure, energy_figure, merged_summary)."""
    from epinterface.analysis.zone_energy import (
        merge_assignment_and_energy,
        zone_energy_summary,
    )

    energy = zone_energy_summary(results.sql, results.idf)
    merged = merge_assignment_and_energy(summary, energy)
    assign_metrics = tuple(m for m in DEFAULT_ASSIGNMENT_METRICS if m in merged.columns)
    sim_metrics = tuple(m for m in DEFAULT_SIM_ENERGY_METRICS if m in merged.columns)
    assign_fig = _horizontal_metric_bars(
        merged, assign_metrics, groupby=groupby, title_prefix="assigned: "
    )
    energy_fig = _horizontal_metric_bars(
        merged, sim_metrics, groupby=groupby, title_prefix="sim: "
    )
    return assign_fig, energy_fig, merged
