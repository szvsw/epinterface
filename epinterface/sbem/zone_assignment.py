"""Typed floor and zone assignment models for shoebox SBEM runs."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from epinterface.geometry import ShoeboxGeometry, ZoningType, get_zone_floor_area
from epinterface.sbem.components.systems import (
    DCVMethod,
    DHWFuelType,
    EconomizerMethod,
    FuelType,
    HRVMethod,
    VentilationProvider,
)

ZoneCategory = Literal["main", "attic", "basement"]


class ZoneRole(StrEnum):
    """Thermal-zone role within a storey."""

    core = "core"
    perim_1 = "perim_1"
    perim_2 = "perim_2"
    perim_3 = "perim_3"
    perim_4 = "perim_4"
    floor = "floor"
    attic = "attic"
    basement = "basement"


class ZoneTemplate(BaseModel, extra="forbid"):
    """Shell-free zone/floor inputs used to construct a ZoneComponent."""

    EquipmentBase: float = Field(ge=0, le=1)
    EquipmentAMInterp: float = Field(ge=0, le=1)
    EquipmentLunchInterp: float = Field(ge=0, le=1)
    EquipmentPMInterp: float = Field(ge=0, le=1)
    EquipmentWeekendPeakInterp: float = Field(ge=0, le=1)
    EquipmentSummerPeakInterp: float = Field(ge=0, le=1)

    LightingBase: float = Field(ge=0, le=1)
    LightingAMInterp: float = Field(ge=0, le=1)
    LightingLunchInterp: float = Field(ge=0, le=1)
    LightingPMInterp: float = Field(ge=0, le=1)
    LightingWeekendPeakInterp: float = Field(ge=0, le=1)
    LightingSummerPeakInterp: float = Field(ge=0, le=1)

    OccupancyBase: float = Field(ge=0, le=1)
    OccupancyAMInterp: float = Field(ge=0, le=1)
    OccupancyLunchInterp: float = Field(ge=0, le=1)
    OccupancyPMInterp: float = Field(ge=0, le=1)
    OccupancyWeekendPeakInterp: float = Field(ge=0, le=1)
    OccupancySummerPeakInterp: float = Field(ge=0, le=1)

    HeatingSetpointBase: float = Field(ge=0, le=23)
    SetpointDeadband: float = Field(ge=0, le=10)
    HeatingSetpointSetback: float = Field(ge=0, le=10)
    CoolingSetpointSetback: float = Field(ge=0, le=10)
    NightSetback: float = Field(ge=0, le=1)
    WeekendSetback: float = Field(ge=0, le=1)
    SummerSetback: float = Field(ge=0, le=1)

    HeatingFuel: FuelType
    CoolingFuel: FuelType
    HeatingSystemCOP: float = Field(ge=0)
    CoolingSystemCOP: float = Field(ge=0)
    HeatingDistributionCOP: float = Field(ge=0)
    CoolingDistributionCOP: float = Field(ge=0)

    EquipmentPowerDensity: float = Field(ge=0, le=200)
    LightingPowerDensity: float = Field(ge=0, le=100)
    OccupantDensity: float = Field(ge=0, le=50)

    VentFlowRatePerPerson: float = Field(ge=0)
    VentFlowRatePerArea: float = Field(ge=0)
    VentProvider: VentilationProvider
    VentHRV: HRVMethod
    VentEconomizer: EconomizerMethod
    VentDCV: DCVMethod

    DHWFlowRatePerPerson: float = Field(ge=0)
    DHWFuel: DHWFuelType
    DHWSystemCOP: float = Field(ge=0)
    DHWDistributionCOP: float = Field(ge=0)

    InfiltrationACH: float = Field(ge=0)

    WindowUValue: float = Field(ge=0)
    WindowSHGF: float = Field(ge=0, le=1)
    WindowTVis: float = Field(ge=0, le=1)

    FacadeRValue: float = Field(gt=0)
    RoofRValue: float = Field(gt=0)
    SlabRValue: float = Field(gt=0)
    WWR: float = Field(ge=0, le=1)

    IdealLoadsHeatingOn: bool = True
    IdealLoadsCoolingOn: bool = True


class PartialZoneTemplate(BaseModel, extra="forbid"):
    """Sparse patch for a floor or role template."""

    EquipmentBase: float | None = Field(default=None, ge=0, le=1)
    EquipmentAMInterp: float | None = Field(default=None, ge=0, le=1)
    EquipmentLunchInterp: float | None = Field(default=None, ge=0, le=1)
    EquipmentPMInterp: float | None = Field(default=None, ge=0, le=1)
    EquipmentWeekendPeakInterp: float | None = Field(default=None, ge=0, le=1)
    EquipmentSummerPeakInterp: float | None = Field(default=None, ge=0, le=1)

    LightingBase: float | None = Field(default=None, ge=0, le=1)
    LightingAMInterp: float | None = Field(default=None, ge=0, le=1)
    LightingLunchInterp: float | None = Field(default=None, ge=0, le=1)
    LightingPMInterp: float | None = Field(default=None, ge=0, le=1)
    LightingWeekendPeakInterp: float | None = Field(default=None, ge=0, le=1)
    LightingSummerPeakInterp: float | None = Field(default=None, ge=0, le=1)

    OccupancyBase: float | None = Field(default=None, ge=0, le=1)
    OccupancyAMInterp: float | None = Field(default=None, ge=0, le=1)
    OccupancyLunchInterp: float | None = Field(default=None, ge=0, le=1)
    OccupancyPMInterp: float | None = Field(default=None, ge=0, le=1)
    OccupancyWeekendPeakInterp: float | None = Field(default=None, ge=0, le=1)
    OccupancySummerPeakInterp: float | None = Field(default=None, ge=0, le=1)

    HeatingSetpointBase: float | None = Field(default=None, ge=0, le=23)
    SetpointDeadband: float | None = Field(default=None, ge=0, le=10)
    HeatingSetpointSetback: float | None = Field(default=None, ge=0, le=10)
    CoolingSetpointSetback: float | None = Field(default=None, ge=0, le=10)
    NightSetback: float | None = Field(default=None, ge=0, le=1)
    WeekendSetback: float | None = Field(default=None, ge=0, le=1)
    SummerSetback: float | None = Field(default=None, ge=0, le=1)

    HeatingFuel: FuelType | None = None
    CoolingFuel: FuelType | None = None
    HeatingSystemCOP: float | None = Field(default=None, ge=0)
    CoolingSystemCOP: float | None = Field(default=None, ge=0)
    HeatingDistributionCOP: float | None = Field(default=None, ge=0)
    CoolingDistributionCOP: float | None = Field(default=None, ge=0)

    EquipmentPowerDensity: float | None = Field(default=None, ge=0, le=200)
    LightingPowerDensity: float | None = Field(default=None, ge=0, le=100)
    OccupantDensity: float | None = Field(default=None, ge=0, le=50)

    VentFlowRatePerPerson: float | None = Field(default=None, ge=0)
    VentFlowRatePerArea: float | None = Field(default=None, ge=0)
    VentProvider: VentilationProvider | None = None
    VentHRV: HRVMethod | None = None
    VentEconomizer: EconomizerMethod | None = None
    VentDCV: DCVMethod | None = None

    DHWFlowRatePerPerson: float | None = Field(default=None, ge=0)
    DHWFuel: DHWFuelType | None = None
    DHWSystemCOP: float | None = Field(default=None, ge=0)
    DHWDistributionCOP: float | None = Field(default=None, ge=0)

    InfiltrationACH: float | None = Field(default=None, ge=0)

    WindowUValue: float | None = Field(default=None, ge=0)
    WindowSHGF: float | None = Field(default=None, ge=0, le=1)
    WindowTVis: float | None = Field(default=None, ge=0, le=1)

    FacadeRValue: float | None = Field(default=None, gt=0)
    RoofRValue: float | None = Field(default=None, gt=0)
    SlabRValue: float | None = Field(default=None, gt=0)
    WWR: float | None = Field(default=None, ge=0, le=1)

    IdealLoadsHeatingOn: bool | None = None
    IdealLoadsCoolingOn: bool | None = None


class FloorBand(BaseModel, extra="forbid"):
    """A half-open range of above-grade floors with optional role overrides."""

    start: int = Field(ge=0)
    stop: int = Field(gt=0)
    template: PartialZoneTemplate | ZoneTemplate | None = None
    role_overrides: dict[ZoneRole, PartialZoneTemplate | ZoneTemplate] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_range(self) -> FloorBand:
        """Require a non-empty half-open floor range."""
        if self.stop <= self.start:
            msg = f"FloorBand stop ({self.stop}) must be greater than start ({self.start})."
            raise ValueError(msg)
        return self

    def contains(self, floor_index: int) -> bool:
        """Return True if this band applies to the above-grade floor index."""
        return self.start <= floor_index < self.stop


class ParsedZoneKey(BaseModel, frozen=True):
    """Semantic identity parsed from a generated EnergyPlus zone name."""

    ep_zone_name: str
    ep_storey_index: int | None
    floor_index: int | None
    role: ZoneRole
    category: ZoneCategory


class ResolvedZone(BaseModel, arbitrary_types_allowed=True):
    """A resolved EnergyPlus zone plus floor metadata and final parameters."""

    ep_zone_name: str
    ep_storey_index: int | None
    floor_index: int | None
    role: ZoneRole
    category: ZoneCategory
    params: ZoneTemplate
    floor_area_m2: float | None = None


_STOREY_RE = re.compile(r"Storey\s+(-?\d+)\s*$", re.IGNORECASE)
_PERIM_RE = re.compile(r"Perimeter_Zone_(\d+)", re.IGNORECASE)


def roles_for_zoning(zoning: ZoningType) -> frozenset[ZoneRole]:
    """Return the valid above-grade roles for a zoning strategy."""
    if zoning == "by_storey":
        return frozenset({ZoneRole.floor})
    return frozenset({
        ZoneRole.core,
        ZoneRole.perim_1,
        ZoneRole.perim_2,
        ZoneRole.perim_3,
        ZoneRole.perim_4,
    })


def parse_zone_key(zone_name: str, geometry: ShoeboxGeometry) -> ParsedZoneKey:  # noqa: C901
    """Map a generated EnergyPlus zone name to semantic floor/role metadata."""
    normalized = zone_name.strip()
    low = normalized.lower()
    if "attic" in low:
        return ParsedZoneKey(
            ep_zone_name=zone_name,
            ep_storey_index=None,
            floor_index=None,
            role=ZoneRole.attic,
            category="attic",
        )

    match = _STOREY_RE.search(normalized)
    if not match:
        msg = f"Cannot parse storey index from zone name: {zone_name!r}."
        raise ValueError(msg)
    ep_storey_index = int(match.group(1))

    category: ZoneCategory = "main"
    if geometry.basement:
        is_basement = (
            ep_storey_index == -1
            if geometry.zoning == "by_storey"
            else ep_storey_index == 0
        )
        if is_basement:
            category = "basement"

    if category == "basement":
        floor_index = None
    elif geometry.basement and geometry.zoning == "core/perim":
        floor_index = ep_storey_index - 1
    else:
        floor_index = ep_storey_index

    if geometry.zoning == "by_storey":
        role = ZoneRole.basement if category == "basement" else ZoneRole.floor
    elif "core_zone" in low:
        role = ZoneRole.core
    else:
        perim_match = _PERIM_RE.search(normalized)
        if not perim_match:
            msg = f"Cannot classify core/perimeter zone name: {zone_name!r}."
            raise ValueError(msg)
        perim_index = int(perim_match.group(1))
        if perim_index not in range(1, 5):
            msg = f"Unexpected perimeter index {perim_index} in {zone_name!r}."
            raise ValueError(msg)
        role = ZoneRole(f"perim_{perim_index}")

    return ParsedZoneKey(
        ep_zone_name=zone_name,
        ep_storey_index=ep_storey_index,
        floor_index=floor_index,
        role=role,
        category=category,
    )


def safe_zone_tag(zone_name: str) -> str:
    """Create an EnergyPlus-object-safe suffix from a zone name."""
    return "".join(char if char.isalnum() else "_" for char in zone_name)


class ZoneAssignmentResolver(BaseModel, extra="forbid"):
    """Resolve defaults, floor bands, and role overrides for generated zones."""

    defaults: ZoneTemplate
    n_floors: int = Field(ge=1)
    floor_bands: list[FloorBand] = Field(default_factory=list)

    @field_validator("floor_bands")
    @classmethod
    def sort_floor_bands(cls, value: list[FloorBand]) -> list[FloorBand]:
        """Keep floor bands deterministic."""
        return sorted(value, key=lambda band: (band.start, band.stop))

    @model_validator(mode="after")
    def validate_floor_bands(self) -> ZoneAssignmentResolver:
        """Reject overlapping or out-of-range floor bands."""
        covered: set[int] = set()
        for band in self.floor_bands:
            if band.stop > self.n_floors:
                msg = (
                    f"FloorBand {band.start}:{band.stop} extends beyond "
                    f"n_floors={self.n_floors}."
                )
                raise ValueError(msg)
            floors = set(range(band.start, band.stop))
            overlap = covered.intersection(floors)
            if overlap:
                msg = f"Overlapping floor bands for floor(s): {sorted(overlap)}."
                raise ValueError(msg)
            covered.update(floors)
        return self

    def floor_band_for(self, floor_index: int) -> FloorBand | None:
        """Return the floor band for a zero-based above-grade floor index."""
        for band in self.floor_bands:
            if band.contains(floor_index):
                return band
        return None

    @staticmethod
    def _patch_dict(template: PartialZoneTemplate | ZoneTemplate | None) -> dict:
        """Return non-null values from a partial or full template."""
        if template is None:
            return {}
        return template.model_dump(exclude_none=True)

    def resolve_key(
        self,
        key: ParsedZoneKey,
        *,
        attic_use_fraction: float | None = None,
        attic_conditioned: bool = False,
        basement_use_fraction: float | None = None,
        basement_conditioned: bool = False,
    ) -> ZoneTemplate:
        """Resolve final zone parameters for a parsed generated zone key."""
        data = self.defaults.model_dump()

        if key.category == "main":
            if key.floor_index is None:
                msg = f"Main zone {key.ep_zone_name!r} has no floor_index."
                raise ValueError(msg)
            if not 0 <= key.floor_index < self.n_floors:
                msg = (
                    f"Zone {key.ep_zone_name!r} resolved to floor_index "
                    f"{key.floor_index}, outside 0..{self.n_floors - 1}."
                )
                raise ValueError(msg)

            band = self.floor_band_for(key.floor_index)
            if band is not None:
                data.update(self._patch_dict(band.template))
                data.update(self._patch_dict(band.role_overrides.get(key.role)))

        params = ZoneTemplate.model_validate(data)

        if key.category == "attic":
            frac = attic_use_fraction or 0
            params = params.model_copy(
                update={
                    "EquipmentPowerDensity": frac * params.EquipmentPowerDensity,
                    "LightingPowerDensity": frac * params.LightingPowerDensity,
                    "OccupantDensity": frac * params.OccupantDensity,
                }
            )
            if not attic_conditioned:
                params = params.model_copy(
                    update={
                        "VentProvider": "None",
                        "IdealLoadsHeatingOn": False,
                        "IdealLoadsCoolingOn": False,
                    }
                )
            return params

        if key.category == "basement":
            frac = basement_use_fraction or 0
            params = params.model_copy(
                update={
                    "EquipmentPowerDensity": frac * params.EquipmentPowerDensity,
                    "LightingPowerDensity": frac * params.LightingPowerDensity,
                    "OccupantDensity": frac * params.OccupantDensity,
                }
            )
            if not basement_conditioned:
                params = params.model_copy(
                    update={
                        "VentProvider": "None",
                        "IdealLoadsHeatingOn": False,
                        "IdealLoadsCoolingOn": False,
                    }
                )
            else:
                params = params.model_copy(update={"IdealLoadsCoolingOn": False})
            return params

        return params

    def resolve_zone(
        self,
        zone_name: str,
        geometry: ShoeboxGeometry,
        *,
        attic_use_fraction: float | None = None,
        attic_conditioned: bool = False,
        basement_use_fraction: float | None = None,
        basement_conditioned: bool = False,
        floor_area_m2: float | None = None,
    ) -> ResolvedZone:
        """Resolve one generated EnergyPlus zone name."""
        key = parse_zone_key(zone_name, geometry)
        params = self.resolve_key(
            key,
            attic_use_fraction=attic_use_fraction,
            attic_conditioned=attic_conditioned,
            basement_use_fraction=basement_use_fraction,
            basement_conditioned=basement_conditioned,
        )
        return ResolvedZone(
            ep_zone_name=zone_name,
            ep_storey_index=key.ep_storey_index,
            floor_index=key.floor_index,
            role=key.role,
            category=key.category,
            params=params,
            floor_area_m2=floor_area_m2,
        )

    def resolved_zone_table(
        self,
        idf,
        geometry: ShoeboxGeometry,
        *,
        attic_use_fraction: float | None = None,
        attic_conditioned: bool = False,
        basement_use_fraction: float | None = None,
        basement_conditioned: bool = False,
    ) -> list[ResolvedZone]:
        """Resolve every generated zone in an IDF and include floor area where possible."""
        resolved: list[ResolvedZone] = []
        for zone in idf.idfobjects["ZONE"]:
            try:
                area = float(get_zone_floor_area(idf, zone.Name))
            except ValueError:
                area = None
            resolved.append(
                self.resolve_zone(
                    zone.Name,
                    geometry,
                    attic_use_fraction=attic_use_fraction,
                    attic_conditioned=attic_conditioned,
                    basement_use_fraction=basement_use_fraction,
                    basement_conditioned=basement_conditioned,
                    floor_area_m2=area,
                )
            )
        return resolved
