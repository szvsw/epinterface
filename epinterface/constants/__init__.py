"""This module contains physical constants used in the epinterface project."""

from pydantic import BaseModel, Field


class PhysicalConstants(BaseModel, frozen=True):
    """Physical constants used in the epinterface project."""

    kWh_per_GJ: float = Field(default=277.778, ge=0, frozen=True)
    WaterDensity_kg_per_m3: float = Field(default=998.2, ge=0, frozen=True)
    WaterSpecificHeat_J_per_kg_degK: float = Field(default=4186, ge=0, frozen=True)
    HoursPerYear: float = Field(default=8760, ge=0, frozen=True)
    J_to_kWh: float = Field(default=3600000, ge=0, frozen=True)

    ConversionFactor_W_per_kg: float = Field(default=1.162, ge=0, frozen=True)


physical_constants = PhysicalConstants()


class AssumedConstants(BaseModel, frozen=True):
    """Assumed constants used as boundary conditions in various EnergyPlus components."""

    AvgHumanWeight_kg: float = Field(default=80, ge=0, frozen=True)
    FractionRadiantPeople: float = Field(default=0.3, ge=0, le=1)

    FractionRadiantLights: float = Field(default=0.42, ge=0, le=1)
    FractionVisibleLights: float = Field(default=0.18, ge=0, le=1)
    FractionReplaceableLights: float = Field(default=1, ge=0, le=1)
    ReturnAirFractionLights: float = Field(default=0, ge=1, le=1)

    FractionLatentEquipment: float = Field(default=0.00, ge=0, le=1)
    FractionRadiantEquipment: float = Field(default=0.2, ge=0, le=1)
    FractionLostEquipment: float = Field(default=0, ge=0, le=1)

    MetabolicRate_met: float = Field(default=1.2, ge=0, frozen=True)
    SiteGroundTemperature_degC: list[float] = Field(
        default=[
            18.3,
            18.2,
            18.3,
            18.4,
            20.1,
            22.0,
            22.3,
            22.5,
            22.5,
            20.7,
            18.9,
            18.5,
        ],
        frozen=True,
    )
    Sensible_Heat_Recovery_Effectiveness: float = Field(
        default=0.70, ge=0, le=1, frozen=True
    )
    Latent_Heat_Recovery_Effectiveness: float = Field(
        default=0.65, ge=0, le=1, frozen=True
    )
    Minimum_Outdoor_Temperature: float = Field(default=18, ge=0, frozen=True)

    Maximum_Outdoor_Temperature: float = Field(default=25, ge=0, frozen=True)
    Basement_Infiltration_Air_Changes_Per_Hour: float = Field(
        default=0.0, ge=0, frozen=True
    )
    Basement_Infiltration_Flow_Per_Exterior_Surface_Area: float = Field(
        default=0.0, ge=0, frozen=True
    )


assumed_constants = AssumedConstants()

__all__ = ["assumed_constants", "physical_constants"]
