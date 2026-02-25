"""Physical-sanity audit tests for semi-flat construction defaults."""

import pytest

from epinterface.sbem.flat_constructions.audit import run_physical_sanity_audit
from epinterface.sbem.flat_constructions.roofs import (
    SemiFlatRoofConstruction,
    build_roof_assembly,
)
from epinterface.sbem.flat_constructions.walls import (
    SemiFlatWallConstruction,
    build_facade_assembly,
)


def test_physical_sanity_audit_has_no_errors() -> None:
    """Material properties and default layups should stay in plausible ranges."""
    issues = run_physical_sanity_audit()
    errors = [issue for issue in issues if issue.severity == "error"]
    assert not errors, "\n".join([
        f"[{issue.scope}] {issue.message}" for issue in errors
    ])


def test_audit_with_excessive_cavity_r_override_produces_valid_assemblies() -> None:
    """When cavity R is overridden to max, assemblies should still pass audit bounds."""
    # Excessive cavity R triggers override; audit bounds should still be satisfied
    with pytest.warns(UserWarning, match="cavity-depth-compatible limit"):
        wall = SemiFlatWallConstruction(
            structural_system="woodframe",
            nominal_cavity_insulation_r=10.0,
        )
        roof = SemiFlatRoofConstruction(
            structural_system="deep_wood_truss",
            nominal_cavity_insulation_r=10.0,
        )

    wall_assembly = build_facade_assembly(wall)
    roof_assembly = build_roof_assembly(roof)

    wall_thickness = sum(layer.Thickness for layer in wall_assembly.sorted_layers)
    roof_thickness = sum(layer.Thickness for layer in roof_assembly.sorted_layers)

    assert 0.04 <= wall_thickness <= 0.80
    assert 0.20 <= wall_assembly.r_value <= 12.0
    assert 0.04 <= roof_thickness <= 1.00
    assert 0.20 <= roof_assembly.r_value <= 14.0
