"""Configuration settings for epinterface, loaded from environment variables."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_energyplus_version(value: str) -> str:
    """Normalize EnergyPlus version string to X.Y.Z format.

    Accepts formats like "22.2.0", "22.2", "22-2-0", "22-2".
    """
    # Replace hyphens with dots for formats like "22-2-0"
    normalized = value.strip().replace("-", ".")
    # Ensure we have at least X.Y format
    parts = normalized.split(".")
    if len(parts) == 2:
        return f"{parts[0]}.{parts[1]}.0"
    return ".".join(parts[:3])  # Take at most major.minor.patch


class EnergyPlusSettings(BaseSettings):
    """Settings for EnergyPlus version and configuration.

    The EnergyPlus version is used when creating IDF objects via archetypal.idfclass.IDF.
    It determines which EnergyPlus schema/IDD version is used for parsing and validation.
    """

    model_config = SettingsConfigDict(
        env_prefix="EPINTERFACE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    energyplus_version: str = "22.2.0"

    @field_validator("energyplus_version", mode="before")
    @classmethod
    def normalize_version(cls, v: str) -> str:
        """Normalize version string from env (e.g. 22-2-0 -> 22.2.0)."""
        if not isinstance(v, str) or not v.strip():
            return "22.2.0"
        return _normalize_energyplus_version(v)


# Singleton instance for application-wide use
energyplus_settings = EnergyPlusSettings()
