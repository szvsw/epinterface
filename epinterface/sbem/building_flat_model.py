"""Building-level flat model with typed per-floor configuration."""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pandas as pd
from archetypal import IDF
from pydantic import BaseModel, Field
from pydantic.functional_validators import model_validator

from epinterface.analysis.overheating import OverheatingAnalysisConfig
from epinterface.geometry import ShoeboxGeometry, ZoningType
from epinterface.sbem.builder import (
    AtticAssumptions,
    BasementAssumptions,
    Model,
    ModelRunResults,
    SimulationPathConfig,
)
from epinterface.sbem.zone_assignment import (
    FloorBand,
    PartialZoneTemplate,
    ZoneAssignmentResolver,
    ZoneTemplate,
    roles_for_zoning,
)
from epinterface.weather import WeatherUrl


class BuildingShell(BaseModel, extra="forbid"):
    """Building-only inputs shared by all floor templates."""

    EPWURI: WeatherUrl | Path
    zoning: ZoningType = "core/perim"
    Width: float = Field(gt=0)
    Depth: float = Field(gt=0)
    F2FHeight: float = Field(gt=0)
    NFloors: int = Field(ge=1)
    Rotation: float = 0.0
    RoofHeight: float | None = Field(default=None, ge=0)
    Basement: bool = False
    ExposedBasementFraction: float = Field(default=0.0, ge=0, lt=1)

    def to_geometry(self, *, default_wwr: float) -> ShoeboxGeometry:
        """Create shoebox geometry; per-floor WWR is applied after geometry creation."""
        return ShoeboxGeometry(
            x=0,
            y=0,
            w=self.Width,
            d=self.Depth,
            h=self.F2FHeight,
            num_stories=self.NFloors,
            zoning=self.zoning,
            roof_height=self.RoofHeight,
            wwr=default_wwr,
            basement=self.Basement,
            exposed_basement_frac=self.ExposedBasementFraction,
        )


class BuildingFlatModel(BaseModel, extra="forbid"):
    """A floor-first flat model for heterogeneous shoebox buildings."""

    shell: BuildingShell
    defaults: ZoneTemplate
    floor_bands: list[FloorBand] = Field(default_factory=list)
    attic: AtticAssumptions = Field(
        default_factory=lambda: AtticAssumptions(UseFraction=None, Conditioned=False)
    )
    basement: BasementAssumptions = Field(
        default_factory=lambda: BasementAssumptions(UseFraction=None, Conditioned=False)
    )

    @model_validator(mode="after")
    def validate_roles(self) -> BuildingFlatModel:
        """Reject role overrides that do not exist for the shell zoning strategy."""
        valid_roles = roles_for_zoning(self.shell.zoning)
        for band in self.floor_bands:
            invalid = set(band.role_overrides).difference(valid_roles)
            if invalid:
                msg = (
                    f"Invalid role override(s) for zoning {self.shell.zoning!r}: "
                    f"{sorted(role.value for role in invalid)}."
                )
                raise ValueError(msg)
        return self

    def assignment_resolver(self) -> ZoneAssignmentResolver:
        """Return a resolver for this building's floor bands."""
        return ZoneAssignmentResolver(
            defaults=self.defaults,
            n_floors=self.shell.NFloors,
            floor_bands=self.floor_bands,
        )

    def to_model(self) -> tuple[Model, Callable[[IDF], IDF]]:
        """Return a runnable Model plus post-geometry rotation callback."""
        geometry = self.shell.to_geometry(default_wwr=self.defaults.WWR)
        rotation = self.shell.Rotation

        def post_geometry_callback(idf: IDF) -> IDF:
            idf.rotate(rotation)
            return idf

        return (
            Model(
                geometry=geometry,
                Zone=None,
                zone_assignments=self.assignment_resolver(),
                Attic=self.attic,
                Basement=self.basement,
                Weather=self.shell.EPWURI,
            ),
            post_geometry_callback,
        )

    def build_idf(
        self,
        *,
        output_dir: Path | None = None,
        weather_dir: Path | None = None,
    ) -> IDF:
        """Build an IDF without running EnergyPlus."""
        model, callback = self.to_model()
        out = (
            Path(tempfile.mkdtemp(prefix="epinterface_floor_build_"))
            if output_dir is None
            else Path(output_dir)
        )
        out.mkdir(parents=True, exist_ok=True)
        config = (
            SimulationPathConfig(output_dir=out, weather_dir=weather_dir)
            if weather_dir is not None
            else SimulationPathConfig(output_dir=out)
        )
        return model.build(config, post_geometry_callback=callback)

    def zone_assignment_summary(self, idf: IDF | None = None) -> pd.DataFrame:
        """Resolved per-zone inputs, including per-floor WWR and area."""
        model, _ = self.to_model()
        idf_built = idf or self.build_idf()
        rows = []
        for resolved in self.assignment_resolver().resolved_zone_table(
            idf_built,
            model.geometry,
            attic_use_fraction=self.attic.UseFraction,
            attic_conditioned=self.attic.Conditioned,
            basement_use_fraction=self.basement.UseFraction,
            basement_conditioned=self.basement.Conditioned,
        ):
            params = resolved.params
            rows.append({
                "ep_zone_name": resolved.ep_zone_name,
                "ep_storey_index": resolved.ep_storey_index,
                "floor_index": resolved.floor_index,
                "role": resolved.role.value,
                "category": resolved.category,
                "floor_area_m2": resolved.floor_area_m2,
                "LightingPowerDensity": params.LightingPowerDensity,
                "EquipmentPowerDensity": params.EquipmentPowerDensity,
                "OccupantDensity": params.OccupantDensity,
                "HeatingSetpointBase": params.HeatingSetpointBase,
                "SetpointDeadband": params.SetpointDeadband,
                "InfiltrationACH": params.InfiltrationACH,
                "FacadeRValue": params.FacadeRValue,
                "WindowUValue": params.WindowUValue,
                "WindowSHGF": params.WindowSHGF,
                "WindowTVis": params.WindowTVis,
                "WWR": params.WWR,
                "HeatingFuel": params.HeatingFuel,
                "CoolingFuel": params.CoolingFuel,
                "HeatingSystemCOP": params.HeatingSystemCOP,
                "CoolingSystemCOP": params.CoolingSystemCOP,
                "DHWFlowRatePerPerson": params.DHWFlowRatePerPerson,
                "DHWFuel": params.DHWFuel,
            })
        return pd.DataFrame(rows)

    def floor_assignment_summary(self, idf: IDF | None = None) -> pd.DataFrame:
        """Area-weighted input summary with exactly NFloors main rows."""
        zone_summary = self.zone_assignment_summary(idf=idf)
        main = zone_summary[zone_summary["category"] == "main"].copy()
        if main.empty:
            return pd.DataFrame()

        numeric_cols = [
            "LightingPowerDensity",
            "EquipmentPowerDensity",
            "OccupantDensity",
            "InfiltrationACH",
            "FacadeRValue",
            "WindowUValue",
            "WindowSHGF",
            "WindowTVis",
            "WWR",
        ]
        rows = []
        for floor_index, group in main.groupby("floor_index", dropna=False):
            area = group["floor_area_m2"].astype(float)
            total_area = float(area.sum())
            floor_index_int = int(cast(int, floor_index))
            row = {"floor_index": floor_index_int, "floor_area_m2": total_area}
            for col in numeric_cols:
                vals = group[col].astype(float)
                row[col] = float((vals * area).sum() / total_area)
            rows.append(row)
        return pd.DataFrame(rows).sort_values("floor_index").reset_index(drop=True)

    def zone_simulation_summary(self, results: ModelRunResults) -> pd.DataFrame:
        """Assignment summary joined with simulated zone energy."""
        from epinterface.analysis.zone_energy import (
            merge_assignment_and_energy,
            zone_energy_summary,
        )

        assignment = self.zone_assignment_summary(idf=results.idf)
        energy = zone_energy_summary(results.sql, results.idf, model=self)
        return merge_assignment_and_energy(assignment, energy)

    def simulate(
        self,
        overheating_config: OverheatingAnalysisConfig | None = None,
        eplus_parent_dir: Path | None = None,
    ) -> ModelRunResults:
        """Run EnergyPlus and return standard plus floor/zone results."""
        model, callback = self.to_model()
        return model.run(
            post_geometry_callback=callback,
            eplus_parent_dir=eplus_parent_dir,
            overheating_config=overheating_config,
        )

    @classmethod
    def from_uniform_flat_model(
        cls,
        flat_model,
        *,
        zoning: ZoningType = "core/perim",
    ) -> BuildingFlatModel:
        """Create a BuildingFlatModel from an existing uniform FlatModel."""
        template = flat_model.zone_template()
        shell = BuildingShell(
            EPWURI=flat_model.EPWURI,
            zoning=zoning,
            Width=flat_model.Width,
            Depth=flat_model.Depth,
            F2FHeight=flat_model.F2FHeight,
            NFloors=flat_model.NFloors,
            Rotation=flat_model.Rotation,
        )
        return cls(shell=shell, defaults=template)


__all__ = [
    "BuildingFlatModel",
    "BuildingShell",
    "FloorBand",
    "PartialZoneTemplate",
    "ZoneTemplate",
]
