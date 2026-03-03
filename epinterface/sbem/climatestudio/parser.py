"""Helpers for loading ClimateStudio template JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_climatestudio_template(path: Path | str) -> dict[str, Any]:
    """Load a ClimateStudio template JSON file into a dictionary."""
    template_path = Path(path)
    with template_path.open("r", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return data


def get_library(template: dict[str, Any]) -> dict[str, Any]:
    """Return the `Library` section of the template."""
    library = template.get("Library")
    if not isinstance(library, dict):
        msg = "template Library section is missing or invalid"
        raise TypeError(msg)
    return library


def get_settings(template: dict[str, Any]) -> dict[str, Any]:
    """Return the top-level `Settings` section of the template."""
    settings = template.get("Settings")
    if not isinstance(settings, dict):
        msg = "template Settings section is missing or invalid"
        raise TypeError(msg)
    return settings


def get_zones(template: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the list of zones from the template."""
    zones = template.get("Zones") or []
    if not isinstance(zones, list):
        msg = "template Zones section is invalid"
        raise TypeError(msg)
    return [z for z in zones if isinstance(z, dict)]
