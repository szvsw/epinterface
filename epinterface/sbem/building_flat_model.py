"""Building-level flat model with per-floor zone role assignments."""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from epinterface.sbem.builder import ModelRunResults

import pandas as pd
from archetypal import IDF
from pydantic import BaseModel, Field, field_validator, model_validator

from epinterface.analysis.overheating import OverheatingAnalysisConfig
from epinterface.geometry import ShoeboxGeometry, ZoningType
from epinterface.sbem.builder import (
    AtticAssumptions,
    BasementAssumptions,
    Model,
    SimulationPathConfig,
)
from epinterface.sbem.flat_model import (
    FlatModel,
    _eppy_lights_watts_per_area,
    _eppy_lights_zone_name,
)
from epinterface.sbem.zone_assignment import (
    ParsedZoneKey,
    ZoneAssignmentTable,
    ZoneRole,
    parse_zone_key,
)
from epinterface.sbem.zone_params import ZoneParams
from epinterface.weather import WeatherUrl

_GEOMETRY_SHELL_FIELDS = ("Width", "Depth", "F2FHeight", "NFloors", "WWR", "Rotation")


def roles_for_zoning(zoning: ZoningType) -> frozenset[str]:
    """Valid zone role keys for a zoning strategy."""
    if zoning == "by_storey":
        return frozenset({ZoneRole.floor.value})
    return frozenset({
        ZoneRole.core.value,
        ZoneRole.perim_1.value,
        ZoneRole.perim_2.value,
        ZoneRole.perim_3.value,
        ZoneRole.perim_4.value,
    })


class BuildingShellParams(BaseModel):
    """Building-only inputs: geometry shell, weather, and zoning."""

    EPWURI: WeatherUrl | Path
    zoning: ZoningType = Field(default="core/perim")
    Width: float
    Depth: float
    F2FHeight: float
    NFloors: int = Field(ge=1)
    WWR: float = Field(ge=0, le=1)
    Rotation: float = 0.0

    @classmethod
    def from_defaults(
        cls,
        defaults: ZoneParams,
        *,
        EPWURI: WeatherUrl | Path,
        zoning: ZoningType = "core/perim",
    ) -> BuildingShellParams:
        """Build shell params from zone defaults plus weather and zoning."""
        return cls(
            EPWURI=EPWURI,
            zoning=zoning,
            **{name: getattr(defaults, name) for name in _GEOMETRY_SHELL_FIELDS},
        )


class FloorFlatModel(BaseModel):
    """Per-storey zone role patches applied on top of building defaults."""

    storey_index: int = Field(ge=0)
    zones: dict[str, dict[str, Any]] = Field(default_factory=dict)


class BuildingFlatModel(BaseModel):
    """Flat building model: shell, building-wide defaults, and per-floor zone patches."""

    shell: BuildingShellParams
    defaults: ZoneParams
    floors: list[FloorFlatModel] = Field(default_factory=list)
    attic: AtticAssumptions = Field(
        default_factory=lambda: AtticAssumptions(UseFraction=None, Conditioned=False)
    )
    basement: BasementAssumptions = Field(
        default_factory=lambda: BasementAssumptions(UseFraction=None, Conditioned=False)
    )

    @model_validator(mode="after")
    def validate_shell_matches_defaults(self) -> BuildingFlatModel:
        """Ensure shell geometry fields match building defaults."""
        for name in _GEOMETRY_SHELL_FIELDS:
            shell_val = getattr(self.shell, name)
            default_val = getattr(self.defaults, name)
            if shell_val != default_val:
                msg = (
                    f"shell.{name} ({shell_val!r}) must match "
                    f"defaults.{name} ({default_val!r})"
                )
                raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_floors(self) -> BuildingFlatModel:
        """Validate floor indices and zone roles for the shell zoning."""
        seen: set[int] = set()
        valid_roles = roles_for_zoning(self.shell.zoning)
        for floor in self.floors:
            if floor.storey_index in seen:
                msg = f"duplicate floor storey_index: {floor.storey_index}"
                raise ValueError(msg)
            seen.add(floor.storey_index)
            if floor.storey_index >= self.shell.NFloors:
                msg = (
                    f"floor storey_index {floor.storey_index} must be "
                    f"< NFloors ({self.shell.NFloors})"
                )
                raise ValueError(msg)
            for role in floor.zones:
                if role not in valid_roles:
                    msg = f"invalid role {role!r} for zoning {self.shell.zoning!r}"
                    raise ValueError(msg)
        return self

    @field_validator("floors")
    @classmethod
    def sort_floors(cls, floors: list[FloorFlatModel]) -> list[FloorFlatModel]:
        """Keep floors ordered by storey index."""
        return sorted(floors, key=lambda f: f.storey_index)

    def zone_overrides(self) -> dict[int, dict[str, dict[str, Any]]]:
        """Compile floor zone patches into legacy override dict shape."""
        out: dict[int, dict[str, dict[str, Any]]] = {}
        for floor in self.floors:
            if floor.zones:
                out[floor.storey_index] = {
                    role: dict(patch) for role, patch in floor.zones.items()
                }
        return out

    def zone_assignment_table(self) -> ZoneAssignmentTable:
        """Building defaults plus sparse per-floor zone role overrides."""
        return ZoneAssignmentTable(
            defaults=self.defaults,
            overrides=self.zone_overrides(),
        )

    def resolve_params(
        self,
        key: ParsedZoneKey,
        *,
        geometry: ShoeboxGeometry,
        attic_use_fraction: float | None = None,
        attic_conditioned: bool = False,
        basement_use_fraction: float | None = None,
        basement_conditioned: bool = False,
    ) -> ZoneParams:
        """Merge building defaults and floor zone patches for one zone key."""
        return self.zone_assignment_table().resolve(
            key,
            attic_use_fraction=attic_use_fraction,
            attic_conditioned=attic_conditioned,
            basement_use_fraction=basement_use_fraction,
            basement_conditioned=basement_conditioned,
            geometry=geometry,
        )

    def to_model(self) -> tuple[Model, Callable[[IDF], IDF]]:
        """Return runnable Model and post-geometry rotation callback."""
        geometry = ShoeboxGeometry(
            x=0,
            y=0,
            w=self.shell.Width,
            d=self.shell.Depth,
            h=self.shell.F2FHeight,
            num_stories=self.shell.NFloors,
            zoning=self.shell.zoning,
            roof_height=None,
            wwr=self.shell.WWR,
            basement=False,
        )
        rotation = self.shell.Rotation

        def post_geometry_callback(idf: IDF) -> IDF:
            idf.rotate(rotation)
            return idf

        return (
            Model(
                geometry=geometry,
                Zone=None,
                zone_assignments=self.zone_assignment_table(),
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
        model, cb = self.to_model()
        out = (
            Path(tempfile.mkdtemp(prefix="flat_build_"))
            if output_dir is None
            else Path(output_dir)
        )
        out.mkdir(parents=True, exist_ok=True)
        cfg = (
            SimulationPathConfig(output_dir=out, weather_dir=weather_dir)
            if weather_dir is not None
            else SimulationPathConfig(output_dir=out)
        )
        return model.build(cfg, post_geometry_callback=cb)

    def zone_assignment_summary(self, idf: IDF | None = None) -> pd.DataFrame:
        """Resolved zone params plus optional cross-check against built IDF."""
        model, _ = self.to_model()
        geom = model.geometry
        tbl = self.zone_assignment_table()
        idf_built = idf or self.build_idf()
        lights_by_zone: dict[str, float] = {}
        for lg in idf_built.idfobjects["LIGHTS"]:
            zn = _eppy_lights_zone_name(lg)
            lights_by_zone[zn] = _eppy_lights_watts_per_area(lg)

        facade_by_zone: dict[str, str] = {}
        for srf in idf_built.idfobjects["BUILDINGSURFACE:DETAILED"]:
            if (
                str(srf.Surface_Type).lower() == "wall"
                and str(srf.Outside_Boundary_Condition).lower() == "outdoors"
            ):
                zn = str(srf.Zone_Name)
                facade_by_zone.setdefault(zn, str(srf.Construction_Name))

        rows = []
        for z in idf_built.idfobjects["ZONE"]:
            zn = z.Name
            key = parse_zone_key(zn, geom)
            params = tbl.resolve(
                key,
                attic_use_fraction=model.Attic.UseFraction,
                attic_conditioned=model.Attic.Conditioned,
                basement_use_fraction=model.Basement.UseFraction,
                basement_conditioned=model.Basement.Conditioned,
                geometry=geom,
            )
            rows.append({
                "ep_zone_name": zn,
                "storey_index": key.storey_index,
                "role": key.role.value,
                "category": key.category,
                "LightingPowerDensity": params.LightingPowerDensity,
                "EquipmentPowerDensity": params.EquipmentPowerDensity,
                "FacadeRValue": params.FacadeRValue,
                "idf_lighting_w_per_m2": lights_by_zone.get(zn),
                "idf_facade_construction": facade_by_zone.get(zn),
            })
        return pd.DataFrame(rows)

    def zone_simulation_summary(self, results: ModelRunResults) -> pd.DataFrame:
        """Assignment summary joined with per-zone simulated energy from a model run."""
        from epinterface.analysis.zone_energy import (
            merge_assignment_and_energy,
            zone_energy_summary,
        )

        assign = self.zone_assignment_summary(idf=results.idf)
        energy = zone_energy_summary(results.sql, results.idf)
        return merge_assignment_and_energy(assign, energy)

    def simulate(
        self,
        overheating_config: OverheatingAnalysisConfig | None = None,
        eplus_parent_dir: Path | None = None,
    ):
        """Simulate the model and return run results."""
        model, cb = self.to_model()
        return model.run(
            post_geometry_callback=cb,
            eplus_parent_dir=eplus_parent_dir,
            overheating_config=overheating_config,
        )

    def to_flat_model(self) -> FlatModel:
        """Convert to legacy FlatModel with compiled zone_overrides."""
        data = self.defaults.model_dump()
        data.update({
            "EPWURI": self.shell.EPWURI,
            "zoning": self.shell.zoning,
            "zone_overrides": self.zone_overrides(),
        })
        return FlatModel.model_validate(data)

    @classmethod
    def from_flat_model(cls, flat: FlatModel) -> BuildingFlatModel:
        """Build structured model from legacy FlatModel."""
        defaults = flat.zone_params_defaults()
        shell = BuildingShellParams.from_defaults(
            defaults,
            EPWURI=flat.EPWURI,
            zoning=flat.zoning,
        )
        floors = [
            FloorFlatModel(storey_index=storey, zones=roles)
            for storey, roles in sorted(flat.zone_overrides.items())
        ]
        return cls(
            shell=shell,
            defaults=defaults,
            floors=floors,
        )

    @classmethod
    def example_with_zone_overrides(cls) -> BuildingFlatModel:
        """Two-storey core/perim shoebox with contrasting zone overrides."""
        lp = 10.0
        defaults = ZoneParams(
            F2FHeight=3.25,
            Width=12,
            Depth=12,
            Rotation=0,
            WWR=0.2,
            NFloors=2,
            FacadeRValue=3.0,
            RoofRValue=3.0,
            SlabRValue=3.0,
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
            LightingPowerDensity=lp,
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
            IdealLoadsHeatingOn=True,
            IdealLoadsCoolingOn=True,
        )
        shell = BuildingShellParams.from_defaults(
            defaults,
            EPWURI=WeatherUrl(  # pyright: ignore[reportCallIssue]
                "https://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/USA_United_States_of_America/MA_Massachusetts/USA_MA_Bedford-Hanscom.Field.AP.744900_TMYx.2009-2023.zip"
            ),
            zoning="core/perim",
        )
        return cls(
            shell=shell,
            defaults=defaults,
            floors=[
                FloorFlatModel(
                    storey_index=0,
                    zones={
                        "perim_1": {"LightingPowerDensity": lp * 1.5},
                        "perim_2": {"LightingPowerDensity": lp * 1.5},
                        "perim_3": {"LightingPowerDensity": lp * 1.5},
                        "perim_4": {"LightingPowerDensity": lp * 1.5},
                    },
                ),
                FloorFlatModel(
                    storey_index=1,
                    zones={
                        "core": {"LightingPowerDensity": lp * 0.5, "FacadeRValue": 6.0}
                    },
                ),
            ],
        )
