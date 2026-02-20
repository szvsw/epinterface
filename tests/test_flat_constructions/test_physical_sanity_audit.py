"""Physical-sanity audit tests for semi-flat construction defaults."""

from epinterface.sbem.flat_constructions.audit import run_physical_sanity_audit


def test_physical_sanity_audit_has_no_errors() -> None:
    """Material properties and default layups should stay in plausible ranges."""
    issues = run_physical_sanity_audit()
    errors = [issue for issue in issues if issue.severity == "error"]
    assert not errors, "\n".join([
        f"[{issue.scope}] {issue.message}" for issue in errors
    ])
