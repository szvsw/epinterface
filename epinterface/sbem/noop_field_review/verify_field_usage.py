"""Verification script: grep for each field's usage in energy model construction path.

Run from repo root: python -m epinterface.sbem.noop_field_review.verify_field_usage
"""

import re
import sys
from pathlib import Path

# Search paths for energy model construction (exclude tests, notebooks, prisma migrations)
SEARCH_PATHS = [
    "epinterface/sbem",
    "epinterface/interface.py",
    "epinterface/geometry.py",
    "epinterface/analysis",
    "epinterface/constants",
]
EXCLUDE_PATTERNS = ["test_", "__pycache__", ".pyc", "migrations", "schema.prisma"]


def grep_field(field_name: str, search_dirs: list[Path]) -> list[str]:
    """Search for field usage in Python files. Returns matching file:line content."""
    pattern = re.compile(rf"\b{re.escape(field_name)}\b")
    matches: list[str] = []
    for search_path in search_dirs:
        if not search_path.exists():
            continue
        files_to_search: list[Path] = (
            [search_path] if search_path.is_file() else list(search_path.rglob("*.py"))
        )
        for py_file in files_to_search:
            if py_file.suffix != ".py":
                continue
            if any(ex in str(py_file) for ex in EXCLUDE_PATTERNS):
                continue
            try:
                text = py_file.read_text(encoding="utf-8", errors="ignore")
                for i, line in enumerate(text.splitlines(), 1):
                    if pattern.search(line):
                        matches.append(f"{py_file}:{i}:{line.strip()}")
            except OSError:
                pass
    return matches[:20]  # Limit to 20 per field


def main() -> None:
    """Main function to verify field usage."""
    from epinterface.sbem.noop_field_review.field_inventory import FIELD_INVENTORY

    repo_root = Path(__file__).resolve().parents[3]
    search_dirs = [repo_root / p for p in SEARCH_PATHS if (repo_root / p).exists()]

    print("Field usage verification (epinterface construction path)\n")
    print("=" * 60)

    for component, fields in FIELD_INVENTORY.items():
        print(f"\n{component}:")
        for field in fields:
            matches = grep_field(field, search_dirs)
            status = "USED" if matches else "NO MATCH"
            print(f"  {field}: {status} ({len(matches)} refs)")
            if matches and len(matches) <= 5:
                for m in matches[:5]:
                    print(f"    -> {m}")


if __name__ == "__main__":
    main()
    sys.exit(0)
