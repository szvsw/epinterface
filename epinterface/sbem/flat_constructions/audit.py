"""Physical-sanity audit checks for semi-flat constructions."""

from dataclasses import dataclass
from typing import Literal

from epinterface.sbem.flat_constructions.materials import MATERIALS_BY_NAME
from epinterface.sbem.flat_constructions.roofs import (
    STRUCTURAL_TEMPLATES as ROOF_STRUCTURAL_TEMPLATES,
)
from epinterface.sbem.flat_constructions.roofs import (
    SemiFlatRoofConstruction,
    build_roof_assembly,
)
from epinterface.sbem.flat_constructions.slabs import (
    STRUCTURAL_TEMPLATES as SLAB_STRUCTURAL_TEMPLATES,
)
from epinterface.sbem.flat_constructions.slabs import (
    SemiFlatSlabConstruction,
    build_slab_assembly,
)
from epinterface.sbem.flat_constructions.walls import (
    STRUCTURAL_TEMPLATES as WALL_STRUCTURAL_TEMPLATES,
)
from epinterface.sbem.flat_constructions.walls import (
    SemiFlatWallConstruction,
    build_facade_assembly,
)

AuditSeverity = Literal["error", "warning"]


@dataclass(frozen=True)
class AuditIssue:
    """A physical-sanity issue found by the audit."""

    severity: AuditSeverity
    scope: str
    message: str


_CONDUCTIVITY_RANGES = {
    "Insulation": (0.02, 0.08),
    "Concrete": (0.4, 2.5),
    "Timber": (0.08, 0.25),
    "Masonry": (0.3, 1.6),
    "Metal": (10.0, 70.0),
    "Boards": (0.04, 0.25),
    "Other": (0.2, 1.5),
    "Plaster": (0.2, 1.0),
    "Finishes": (0.04, 1.5),
    "Siding": (0.1, 0.8),
    "Sealing": (0.1, 0.3),
}

_DENSITY_RANGES = {
    "Insulation": (8, 100),
    "Concrete": (800, 2600),
    "Timber": (300, 900),
    "Masonry": (900, 2400),
    "Metal": (6500, 8500),
    "Boards": (100, 1200),
    "Other": (500, 2600),
    "Plaster": (600, 1800),
    "Finishes": (80, 2600),
    "Siding": (600, 2000),
    "Sealing": (700, 1800),
}


def audit_materials() -> list[AuditIssue]:
    """Audit base material properties for physically sensible ranges."""
    issues: list[AuditIssue] = []
    for name, mat in MATERIALS_BY_NAME.items():
        conductivity_bounds = _CONDUCTIVITY_RANGES.get(mat.Type)
        if conductivity_bounds is not None:
            low, high = conductivity_bounds
            if not (low <= mat.Conductivity <= high):
                issues.append(
                    AuditIssue(
                        severity="error",
                        scope=f"material:{name}",
                        message=(
                            f"Conductivity {mat.Conductivity} W/mK is outside expected "
                            f"range [{low}, {high}] for type {mat.Type}."
                        ),
                    )
                )

        density_bounds = _DENSITY_RANGES.get(mat.Type)
        if density_bounds is not None:
            low, high = density_bounds
            if not (low <= mat.Density <= high):
                issues.append(
                    AuditIssue(
                        severity="error",
                        scope=f"material:{name}",
                        message=(
                            f"Density {mat.Density} kg/m³ is outside expected "
                            f"range [{low}, {high}] for type {mat.Type}."
                        ),
                    )
                )

    return issues


def _check_assembly_bounds(
    *,
    scope: str,
    thickness_m: float,
    r_value: float,
    min_thickness_m: float,
    max_thickness_m: float,
    min_r_value: float,
    max_r_value: float,
) -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    if not (min_thickness_m <= thickness_m <= max_thickness_m):
        issues.append(
            AuditIssue(
                severity="error",
                scope=scope,
                message=(
                    f"Total thickness {thickness_m:.3f} m is outside expected range "
                    f"[{min_thickness_m:.3f}, {max_thickness_m:.3f}] m."
                ),
            )
        )
    if not (min_r_value <= r_value <= max_r_value):
        issues.append(
            AuditIssue(
                severity="error",
                scope=scope,
                message=(
                    f"Total R-value {r_value:.3f} m²K/W is outside expected range "
                    f"[{min_r_value:.3f}, {max_r_value:.3f}] m²K/W."
                ),
            )
        )
    return issues


def audit_layups() -> list[AuditIssue]:
    """Audit default layups for sensible thickness and thermal bounds."""
    issues: list[AuditIssue] = []

    for structural_system, template in WALL_STRUCTURAL_TEMPLATES.items():
        wall = SemiFlatWallConstruction(
            structural_system=structural_system,
            nominal_cavity_insulation_r=(
                2.0 if template.supports_cavity_insulation else 0.0
            ),
            nominal_exterior_insulation_r=1.0,
            nominal_interior_insulation_r=0.2,
            interior_finish="drywall",
            exterior_finish="fiber_cement",
        )
        assembly = build_facade_assembly(wall)
        total_thickness = sum(layer.Thickness for layer in assembly.sorted_layers)
        issues.extend(
            _check_assembly_bounds(
                scope=f"wall:{structural_system}",
                thickness_m=total_thickness,
                r_value=assembly.r_value,
                min_thickness_m=0.04,
                max_thickness_m=0.80,
                min_r_value=0.20,
                max_r_value=12.0,
            )
        )
        if template.framing_fraction is not None:
            has_consolidated_cavity = any(
                layer.ConstructionMaterial.Name.startswith(
                    f"ConsolidatedCavity_{structural_system}"
                )
                for layer in assembly.sorted_layers
            )
            if not has_consolidated_cavity:
                issues.append(
                    AuditIssue(
                        severity="error",
                        scope=f"wall:{structural_system}",
                        message=(
                            "Expected consolidated framed cavity layer for a framed wall "
                            "system but did not find one."
                        ),
                    )
                )

    for structural_system, template in ROOF_STRUCTURAL_TEMPLATES.items():
        roof = SemiFlatRoofConstruction(
            structural_system=structural_system,
            nominal_cavity_insulation_r=(
                2.5 if template.supports_cavity_insulation else 0.0
            ),
            nominal_exterior_insulation_r=2.0,
            nominal_interior_insulation_r=0.2,
            interior_finish="gypsum_board",
            exterior_finish="epdm_membrane",
        )
        assembly = build_roof_assembly(roof)
        total_thickness = sum(layer.Thickness for layer in assembly.sorted_layers)
        issues.extend(
            _check_assembly_bounds(
                scope=f"roof:{structural_system}",
                thickness_m=total_thickness,
                r_value=assembly.r_value,
                min_thickness_m=0.04,
                max_thickness_m=1.00,
                min_r_value=0.20,
                max_r_value=14.0,
            )
        )
        if template.framing_fraction is not None:
            has_consolidated_cavity = any(
                layer.ConstructionMaterial.Name.startswith(
                    f"ConsolidatedCavity_{structural_system}"
                )
                for layer in assembly.sorted_layers
            )
            if not has_consolidated_cavity:
                issues.append(
                    AuditIssue(
                        severity="error",
                        scope=f"roof:{structural_system}",
                        message=(
                            "Expected consolidated framed cavity layer for a framed roof "
                            "system but did not find one."
                        ),
                    )
                )

    for structural_system in SLAB_STRUCTURAL_TEMPLATES:
        slab = SemiFlatSlabConstruction(
            structural_system=structural_system,
            nominal_insulation_r=1.5,
            insulation_placement="auto",
            interior_finish="tile",
            exterior_finish="none",
        )
        assembly = build_slab_assembly(slab)
        total_thickness = sum(layer.Thickness for layer in assembly.sorted_layers)
        issues.extend(
            _check_assembly_bounds(
                scope=f"slab:{structural_system}",
                thickness_m=total_thickness,
                r_value=assembly.r_value,
                min_thickness_m=0.04,
                max_thickness_m=1.00,
                min_r_value=0.15,
                max_r_value=12.0,
            )
        )

    return issues


def run_physical_sanity_audit() -> list[AuditIssue]:
    """Run all physical-sanity checks for semi-flat constructions."""
    return [*audit_materials(), *audit_layups()]
