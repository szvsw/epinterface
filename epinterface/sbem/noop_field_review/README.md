# SBEM No-Op Field Review

This package contains the results and tools for the exhaustive review of SBEM component fields that have no effect on energy model construction.

## Contents

- **NOOP_FIELD_REPORT.md** – Full report with field classifications, detailed findings, and recommendations
- **field_inventory.py** – Catalog of all component fields
- **verify_field_usage.py** – Verification script that searches for field references

## Usage

Run the verification script from the repository root:

```bash
python -m epinterface.sbem.noop_field_review.verify_field_usage
```

Note: The script reports all references (definitions, Prisma, interface). Manual trace-through of the construction path is required to confirm no-op status. See NOOP_FIELD_REPORT.md for the authoritative classification.
