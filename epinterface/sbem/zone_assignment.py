"""Zone name parsing and sparse overrides merged into ZoneParams."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from epinterface.geometry import ShoeboxGeometry
from epinterface.sbem.zone_params import ZoneParams


class ZoneRole(StrEnum):
    """Thermal-zone role within a storey (matches geomeppy shoebox naming)."""

    core = "core"
    perim_1 = "perim_1"
    perim_2 = "perim_2"
    perim_3 = "perim_3"
    perim_4 = "perim_4"
    floor = "floor"
    attic = "attic"


@dataclass(frozen=True)
class ParsedZoneKey:
    """Parsed EP zone name -> assignment indices."""

    storey_index: int
    role: ZoneRole
    category: Literal["main", "attic", "basement"]


_STOREY_RE = re.compile(r"Storey\s+(-?\d+)\s*$", re.IGNORECASE)
_PERIM_RE = re.compile(r"Perimeter_Zone_(\d+)", re.IGNORECASE)


def parse_zone_key(zone_name: str, geometry: ShoeboxGeometry) -> ParsedZoneKey:
    """Map EnergyPlus zone name to storey index and role."""
    zn = zone_name.strip()
    low = zn.lower()
    if "attic" in low:
        return ParsedZoneKey(storey_index=-1, role=ZoneRole.attic, category="attic")

    m = _STOREY_RE.search(zn)
    if not m:
        msg = f"cannot parse storey index from zone name: {zone_name!r}"
        raise ValueError(msg)
    storey_index = int(m.group(1))

    if geometry.basement:
        if geometry.zoning == "by_storey":
            category: Literal["main", "attic", "basement"] = (
                "basement" if storey_index == -1 else "main"
            )
        else:
            category = "basement" if storey_index == 0 else "main"
    else:
        category = "main"

    if geometry.zoning == "by_storey":
        return ParsedZoneKey(
            storey_index=storey_index, role=ZoneRole.floor, category=category
        )

    if "core_zone" in low:
        return ParsedZoneKey(
            storey_index=storey_index, role=ZoneRole.core, category=category
        )

    pm = _PERIM_RE.search(zn)
    if pm:
        idx = int(pm.group(1))
        if idx not in range(1, 5):
            msg = f"unexpected perimeter index {idx} in {zone_name!r}"
            raise ValueError(msg)
        role = ZoneRole(f"perim_{idx}")
        return ParsedZoneKey(storey_index=storey_index, role=role, category=category)

    msg = f"cannot classify core/perimeter zone name: {zone_name!r}"
    raise ValueError(msg)


class ZoneAssignmentTable(BaseModel):
    """Building defaults plus sparse (storey, role) patches."""

    defaults: ZoneParams
    overrides: dict[int, dict[str, dict[str, Any]]] = Field(default_factory=dict)

    def merged_patch(self, storey_index: int, role: ZoneRole) -> dict[str, Any]:
        """Return override dict for one zone key."""
        return dict(self.overrides.get(storey_index, {}).get(role.value, {}))

    def resolve_base_params(self, key: ParsedZoneKey) -> ZoneParams:
        """Apply YAML-style overrides only (no attic/basement occupancy scaling)."""
        data = self.defaults.model_dump()
        patch = self.merged_patch(key.storey_index, key.role)
        data.update({k: v for k, v in patch.items() if v is not None})
        return ZoneParams.model_validate(data)

    def resolve(
        self,
        key: ParsedZoneKey,
        *,
        attic_use_fraction: float | None,
        attic_conditioned: bool,
        basement_use_fraction: float | None,
        basement_conditioned: bool,
        geometry: ShoeboxGeometry,
    ) -> ZoneParams:
        """Resolve patch plus attic/basement behaviour matching legacy Model.build."""
        params = self.resolve_base_params(key)

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
