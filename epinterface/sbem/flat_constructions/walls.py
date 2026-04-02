"""Wall construction objects for SBEM assemblies."""

import json
import warnings
from abc import ABC, abstractmethod
from typing import Literal, get_args

from pydantic import BaseModel, Field

from epinterface.sbem.components.envelope import (
    ConstructionAssemblyComponent,
    ConstructionLayerComponent,
)
from epinterface.sbem.components.materials import ConstructionMaterialComponent
from epinterface.sbem.flat_constructions.base import (
    CavityInsulationMaterialName,
    ContinuousInsulationMaterialName,
    FinishTemplate,
    FramingMaterialName,
    MonolithicFramingMaterialName,
    MonolithicInfillMaterialName,
    SheathingMaterialName,
    get_cavity_insulation_material,
    get_continuous_insulation_material,
    get_framing_material,
    get_monolithic_framing_material,
    get_monolithic_infill_material,
    get_sheathing_material,
)
from epinterface.sbem.flat_constructions.materials import MATERIALS_BY_NAME

WallInteriorFinishName = Literal[
    "none",
    "drywall",
    "plaster",
    "cement_plaster",
    "wood_panel",
]
WallExteriorFinishName = Literal[
    "brick_veneer",
    "stucco",
    "fiber_cement",
    "metal_panel",
    "vinyl_siding",
    "wood_siding",
    "stone_veneer",
    "none",
]


INTERIOR_FINISHES: dict[WallInteriorFinishName, FinishTemplate | None] = {
    "drywall": FinishTemplate(
        material_name="GypsumBoard",
        thickness_m=0.0127,
    ),
    "plaster": FinishTemplate(
        material_name="GypsumPlaster",
        thickness_m=0.013,
    ),
    "cement_plaster": FinishTemplate(
        material_name="CementMortar",
        thickness_m=0.015,
    ),
    "wood_panel": FinishTemplate(
        material_name="SoftwoodGeneral",
        thickness_m=0.012,
    ),
}

EXTERIOR_FINISHES: dict[WallExteriorFinishName, FinishTemplate | None] = {
    "brick_veneer": FinishTemplate(
        material_name="ClayBrick",
        thickness_m=0.090,
    ),
    "stucco": FinishTemplate(
        material_name="CementMortar",
        thickness_m=0.020,
    ),
    "fiber_cement": FinishTemplate(
        material_name="FiberCementBoard",
        thickness_m=0.012,
    ),
    "metal_panel": FinishTemplate(
        material_name="SteelPanel",
        thickness_m=0.001,
    ),
    "vinyl_siding": FinishTemplate(
        material_name="VinylSiding",
        thickness_m=0.0015,
    ),
    "wood_siding": FinishTemplate(
        material_name="SoftwoodGeneral",
        thickness_m=0.018,
    ),
    "stone_veneer": FinishTemplate(
        material_name="NaturalStone",
        thickness_m=0.025,
    ),
}


class FlatWallConstruction(ABC, BaseModel):
    """A base class for flat wall construction objects."""

    @abstractmethod
    def to_construction_assembly(
        self,
        *,
        cav_insul_name: CavityInsulationMaterialName | Literal["None"],
        ext_insul_name: ContinuousInsulationMaterialName | Literal["None"],
        int_insul_name: ContinuousInsulationMaterialName | Literal["None"],
        cav_insul_rval: float,
        ext_insul_rval: float,
        int_insul_rval: float,
        int_finish: WallInteriorFinishName,
        ext_finish: WallExteriorFinishName,
    ) -> ConstructionAssemblyComponent:
        """Translate the flat wall construction object into an EnergyPlus construction assembly."""


class FramedWallConstruction(FlatWallConstruction):
    """A framed wall construction object."""

    framing_material: FramingMaterialName
    framing_fraction: float = Field(
        ...,
        ge=0,
        le=1,
        description="The fraction of the wall that is the framing material.",
    )
    cavity_depth_m: float = Field(
        ..., ge=0, description="The depth of the cavity in the wall."
    )
    cavity_airgap_strategy: Literal[
        "fit-to-insulation-r",
        "gap-then-clip",  # standard studs + insulation
        "gap-gap-then-clip",  # two layers of cmu against each other
        "gap-gap-gap-then-clip",  # three layers of cmu against or each other or double stud wall
    ]
    framing_path_r_value_override: float | None = Field(
        default=None,
        description="The R-value of the framing path in the wall if the material + thickness should be ignored..",
    )
    sheathing_material: SheathingMaterialName | Literal["None"]
    sheathing_material_thickness_m: float = Field(
        ...,
        ge=0,
        description="The thickness of the sheathing material in the wall.",
    )

    def to_construction_assembly(  # noqa: C901
        self,
        *,
        cav_insul_name: CavityInsulationMaterialName | Literal["None"],
        ext_insul_name: ContinuousInsulationMaterialName | Literal["None"],
        int_insul_name: ContinuousInsulationMaterialName | Literal["None"],
        cav_insul_rval: float,
        ext_insul_rval: float,
        int_insul_rval: float,
        int_finish: WallInteriorFinishName,
        ext_finish: WallExteriorFinishName,
    ) -> ConstructionAssemblyComponent:
        """Translate the woodframed wall construction object into an EnergyPlus construction assembly."""
        layers: list[ConstructionLayerComponent] = []
        layer_order = 0

        ####### HANDLE EXTERIOR FINISH LAYER #######
        if exterior_finish_template := EXTERIOR_FINISHES[ext_finish]:
            exterior_layer = ConstructionLayerComponent(
                ConstructionMaterial=MATERIALS_BY_NAME[
                    exterior_finish_template.material_name
                ],
                Thickness=exterior_finish_template.thickness_m,
                LayerOrder=layer_order,
            )
            layers.append(exterior_layer)
            layer_order += 1

        ####### HANDLE EXTERIOR INSULATION LAYER #######
        if ext_insul_rval > 0 and ext_insul_name != "None":
            thickened_insul = get_continuous_insulation_material(
                ext_insul_name, ext_insul_rval
            )
            layers.append(
                ConstructionLayerComponent(
                    ConstructionMaterial=thickened_insul.material,
                    Thickness=thickened_insul.thickness_m,
                    LayerOrder=layer_order,
                )
            )
            layer_order += 1

        if self.sheathing_material != "None":
            sheathing_material = get_sheathing_material(self.sheathing_material)
            layers.append(
                ConstructionLayerComponent(
                    ConstructionMaterial=sheathing_material,
                    Thickness=self.sheathing_material_thickness_m,
                    LayerOrder=layer_order,
                )
            )
            layer_order += 1

        ####### HANDLE FRAMED CAVITY LAYER #######
        # TODO:
        # 13 mm (0.5 in) Air Space: Approx. RSI 0.16-0.18
        # 25 mm (1 in) Air Space: Approx. RSI 0.30-0.34
        # 100 mm (4 in) Air Space: Approx. RSI 0.35-0.40
        if cav_insul_rval > 0 and cav_insul_name != "None":
            thickend_cav_insul = get_cavity_insulation_material(
                cav_insul_name, cav_insul_rval
            )
            cavity_insulation_mat = thickend_cav_insul.material
            required_thickness_m = thickend_cav_insul.thickness_m
            difference = self.cavity_depth_m - required_thickness_m
            if self.cavity_airgap_strategy == "gap-then-clip":
                # TODO: airgap only starts having an effect if > 13mm
                gap_r = 0.17 if difference > 0 else 0
            elif self.cavity_airgap_strategy == "gap-gap-then-clip":
                gap_r = (
                    (0.17 * 2)
                    if difference > self.cavity_depth_m * 0.5
                    else 0.17
                    if difference > 0
                    else 0
                )
            elif self.cavity_airgap_strategy == "gap-gap-gap-then-clip":
                gap_r = (
                    (
                        (0.17 * 2)
                        if difference > self.cavity_depth_m * 0.5
                        else 0.17
                        if difference > 0
                        else 0
                    )
                    + 0.17
                )  # additional gap between the two layers of cmu/double stud walls
            elif self.cavity_airgap_strategy == "fit-to-insulation-r":
                gap_r = 0
            else:
                raise NotImplementedError(
                    f"Unsupported cavity airgap strategy: {self.cavity_airgap_strategy}"
                )

            cavity_insul_thickness_m = (
                required_thickness_m
                if difference > 0
                else (
                    self.cavity_depth_m
                    if self.cavity_airgap_strategy != "fit-to-insulation-r"
                    else required_thickness_m
                )
            )

            effective_r_from_insul = (
                cavity_insul_thickness_m / cavity_insulation_mat.Conductivity
            )
            cavity_effective_r = effective_r_from_insul + gap_r

            framing_mat = get_framing_material(self.framing_material)
            framing_thickness_m = (
                self.cavity_depth_m
                if self.cavity_airgap_strategy != "fit-to-insulation-r"
                else cavity_insul_thickness_m
            )
            framing_r = (
                self.framing_path_r_value_override
                if self.framing_path_r_value_override is not None
                else (framing_thickness_m / framing_mat.Conductivity)
            )
            framing_effective_k = framing_thickness_m / framing_r

            framing_frac = self.framing_fraction
            cavity_frac = 1 - self.framing_fraction
            cavity_effective_k = framing_thickness_m / cavity_effective_r
            equivalent_k = (
                framing_frac * framing_effective_k + cavity_frac * cavity_effective_k
            )
            # equivalent_r = 1 / (
            #     framing_frac / framing_r + cavity_frac / cavity_effective_r
            # )
            # equivalent_k_alt = framing_thickness_m / equivalent_r
            # assert equivalent_k == pytest.approx(equivalent_k_alt, rel=1e-6)

            framing_mass_per_m2 = self.cavity_depth_m * framing_mat.Density
            cavity_mass_per_m2 = (
                cavity_insul_thickness_m * cavity_insulation_mat.Density
            )
            # TODO: ignoring mass of air in the cavity
            cavity_mixed_mass_per_m2 = cavity_mass_per_m2 * cavity_frac
            framing_mixed_mass_per_m2 = framing_mass_per_m2 * framing_frac
            total_mass_per_m2 = cavity_mixed_mass_per_m2 + framing_mixed_mass_per_m2
            equivalent_rho = total_mass_per_m2 / self.cavity_depth_m

            cavity_mass_frac = cavity_mixed_mass_per_m2 / total_mass_per_m2
            framing_mass_frac = framing_mixed_mass_per_m2 / total_mass_per_m2

            equivalent_cp = (
                framing_mass_frac * framing_mat.SpecificHeat
                + cavity_mass_frac * cavity_insulation_mat.SpecificHeat
            )

            layers.append(
                ConstructionLayerComponent(
                    ConstructionMaterial=ConstructionMaterialComponent(
                        Name=f"FramedWallConstructionCavity_{self.framing_material}_{self.framing_fraction:.3f}_{cav_insul_name}_R{cav_insul_rval:.3f}_{hash(self.model_dump_json())}",
                        Conductivity=equivalent_k,
                        Density=equivalent_rho,
                        SpecificHeat=equivalent_cp,
                        ThermalAbsorptance=0.9,
                        SolarAbsorptance=0.6,
                        VisibleAbsorptance=0.6,
                        TemperatureCoefficientThermalConductivity=0.0,
                        Roughness="MediumRough",
                        Type="Other",
                    ),
                    Thickness=framing_thickness_m,
                    LayerOrder=layer_order,
                )
            )
            layer_order += 1
        else:
            # TODO: deal with different thicknesses of air
            gap_r = (
                0.17
                if self.cavity_airgap_strategy == "gap-then-clip"
                else (
                    (0.17 * 2)
                    if self.cavity_airgap_strategy == "gap-gap-then-clip"
                    else (
                        (0.17 * 3)
                        if self.cavity_airgap_strategy == "gap-gap-gap-then-clip"
                        else None
                    )
                )
            )
            if gap_r is None:
                msg = "`fit-to-insulation-r` air gap strategy requires incompatible with no insulation.."
                raise ValueError(msg)
            framing_mat = get_framing_material(self.framing_material)
            framing_thickness_m = self.cavity_depth_m
            framing_r = framing_thickness_m / framing_mat.Conductivity
            framing_frac = self.framing_fraction
            gap_frac = 1 - framing_frac
            effective_r = 1 / (framing_frac / framing_r + gap_frac / gap_r)
            effective_k = framing_thickness_m / effective_r
            framing_mass_per_m2 = framing_mat.Density * framing_thickness_m
            air_mass_per_m2 = 0  # TODO: approximation, air has *some* mass
            framing_mixed_mass_per_m2 = framing_mass_per_m2 * framing_frac
            air_mixed_mass_per_m2 = air_mass_per_m2 * gap_frac
            total_mass_per_m2 = framing_mixed_mass_per_m2 + air_mixed_mass_per_m2
            equivalent_rho = total_mass_per_m2 / framing_thickness_m
            framing_mass_frac = framing_mixed_mass_per_m2 / total_mass_per_m2
            air_mass_frac = air_mixed_mass_per_m2 / total_mass_per_m2
            equivalent_cp = (
                framing_mass_frac * framing_mat.SpecificHeat
                + air_mass_frac * 0  # TODO: approximation, air has *some* mass
            )

            layers.append(
                ConstructionLayerComponent(
                    ConstructionMaterial=ConstructionMaterialComponent(
                        Name=f"FramedWallConstructionCavity_{self.framing_material}_{self.framing_fraction:.3f}_{cav_insul_name}_R{cav_insul_rval:.3f}_{hash(self.model_dump_json())}",
                        Conductivity=effective_k,
                        Density=equivalent_rho,
                        SpecificHeat=equivalent_cp,
                        ThermalAbsorptance=0.9,
                        SolarAbsorptance=0.6,
                        VisibleAbsorptance=0.6,
                        TemperatureCoefficientThermalConductivity=0.0,
                        Roughness="MediumRough",
                        Type="Other",
                    ),
                    Thickness=framing_thickness_m,
                    LayerOrder=layer_order,
                )
            )
            layer_order += 1

        if self.sheathing_material != "None":
            sheathing_material = get_sheathing_material(self.sheathing_material)
            layers.append(
                ConstructionLayerComponent(
                    ConstructionMaterial=sheathing_material,
                    Thickness=self.sheathing_material_thickness_m,
                    LayerOrder=layer_order,
                )
            )
            layer_order += 1

        ####### HANDLE INTERIOR INSULATION LAYER #######
        if int_insul_rval > 0 and int_insul_name != "None":
            thickened_int_insul = get_continuous_insulation_material(
                int_insul_name, int_insul_rval
            )
            layers.append(
                ConstructionLayerComponent(
                    ConstructionMaterial=thickened_int_insul.material,
                    Thickness=thickened_int_insul.thickness_m,
                    LayerOrder=layer_order,
                )
            )
            layer_order += 1

        ####### HANDLE INTERIOR FINISH LAYER #######
        if interior_finish_template := INTERIOR_FINISHES[int_finish]:
            layers.append(
                ConstructionLayerComponent(
                    ConstructionMaterial=MATERIALS_BY_NAME[
                        interior_finish_template.material_name
                    ],
                    Thickness=interior_finish_template.thickness_m,
                    LayerOrder=layer_order,
                )
            )
            layer_order += 1
        return ConstructionAssemblyComponent(
            Name=f"FramedWallConstruction_{hash(json.dumps([layer.model_dump(mode='json') for layer in layers]))}",
            Type="Facade",
            Layers=layers,
        )


class MonolithicWallConstruction(FlatWallConstruction):
    """A wall with no cavity, e.g. poured concrete, masonry, etc.

    Includes support for blended materials, e.g. rc frame + masonry infill.

    For a completely monolithic wall, set the structural fraction to 1.0
    """

    structural_material: MonolithicFramingMaterialName
    infill_material: MonolithicInfillMaterialName
    structural_fraction: float = Field(
        default=...,
        ge=0,
        le=1,
        description="The fraction of the wall that is the structural material.",
    )
    thickness_m: float = Field(
        default=...,
        ge=0,
        description="The thickness of the wall in meters.",
    )

    def to_construction_assembly(
        self,
        *,
        ext_insul_name: ContinuousInsulationMaterialName | Literal["None"],
        int_insul_name: ContinuousInsulationMaterialName | Literal["None"],
        cav_insul_name: CavityInsulationMaterialName | Literal["None"],
        ext_insul_rval: float,
        int_insul_rval: float,
        cav_insul_rval: float,
        int_finish: WallInteriorFinishName,
        ext_finish: WallExteriorFinishName,
    ) -> ConstructionAssemblyComponent:
        """Translate the monolithic wall construction object into an EnergyPlus construction assembly."""
        layers: list[ConstructionLayerComponent] = []
        layer_order = 0

        ####### HANDLE EXTERIOR FINISH LAYER #######
        if exterior_finish_template := EXTERIOR_FINISHES[ext_finish]:
            layers.append(
                ConstructionLayerComponent(
                    ConstructionMaterial=MATERIALS_BY_NAME[
                        exterior_finish_template.material_name
                    ],
                    Thickness=exterior_finish_template.thickness_m,
                    LayerOrder=layer_order,
                )
            )
            layer_order += 1

        ####### HANDLE EXTERIOR INSULATION LAYER #######
        if ext_insul_rval > 0 and ext_insul_name != "None":
            thickened_ext_insul = get_continuous_insulation_material(
                ext_insul_name, ext_insul_rval
            )
            layers.append(
                ConstructionLayerComponent(
                    ConstructionMaterial=thickened_ext_insul.material,
                    Thickness=thickened_ext_insul.thickness_m,
                    LayerOrder=layer_order,
                )
            )
            layer_order += 1

        ####### HANDLE STRUCTURAL MATERIAL LAYER #######
        structural_mat = get_monolithic_framing_material(self.structural_material)
        infill_mat = get_monolithic_infill_material(self.infill_material)
        blended_material_k = (
            structural_mat.Conductivity * self.structural_fraction
            + infill_mat.Conductivity * (1 - self.structural_fraction)
        )
        structural_mat_mass_per_m2 = structural_mat.Density * self.structural_fraction
        infill_mat_mass_per_m2 = infill_mat.Density * (1 - self.structural_fraction)
        total_mass_per_m2 = structural_mat_mass_per_m2 + infill_mat_mass_per_m2
        structural_mass_frac = structural_mat_mass_per_m2 / total_mass_per_m2
        infill_mass_frac = infill_mat_mass_per_m2 / total_mass_per_m2
        blended_material_rho = (
            structural_mass_frac * structural_mat.Density
            + infill_mass_frac * infill_mat.Density
        )
        blended_material_cp = (
            structural_mass_frac * structural_mat.SpecificHeat
            + infill_mass_frac * infill_mat.SpecificHeat
        )
        blended_material = ConstructionMaterialComponent(
            Name=f"MonolithicWallConstruction_{self.structural_material}_{self.infill_material}_{self.structural_fraction:.3f}_{hash(self.model_dump_json())}",
            Conductivity=blended_material_k,
            Density=blended_material_rho,
            SpecificHeat=blended_material_cp,
            ThermalAbsorptance=0.9,
            SolarAbsorptance=0.6,
            VisibleAbsorptance=0.6,
            Roughness="MediumRough",
            Type="Other",
            TemperatureCoefficientThermalConductivity=0.0,  # TODO: verify that 0.0 is okay
        )

        layers.append(
            ConstructionLayerComponent(
                ConstructionMaterial=blended_material,
                Thickness=self.thickness_m,
                LayerOrder=layer_order,
            )
        )
        layer_order += 1
        if cav_insul_rval > 0 and cav_insul_name != "None":
            warnings.warn(
                "Cavity insulation is not supported for monolithic walls, ignoring cavity insulation.",
                stacklevel=2,
            )

        ####### HANDLE INTERIOR INSULATION LAYER #######
        if int_insul_rval > 0 and int_insul_name != "None":
            thickened_int_insul = get_continuous_insulation_material(
                int_insul_name, int_insul_rval
            )
            layers.append(
                ConstructionLayerComponent(
                    ConstructionMaterial=thickened_int_insul.material,
                    Thickness=thickened_int_insul.thickness_m,
                    LayerOrder=layer_order,
                )
            )
            layer_order += 1

        ####### HANDLE INTERIOR FINISH LAYER #######
        if interior_finish_template := INTERIOR_FINISHES[int_finish]:
            layers.append(
                ConstructionLayerComponent(
                    ConstructionMaterial=MATERIALS_BY_NAME[
                        interior_finish_template.material_name
                    ],
                    Thickness=interior_finish_template.thickness_m,
                    LayerOrder=layer_order,
                )
            )
            layer_order += 1
        return ConstructionAssemblyComponent(
            Name=f"MonolithicWallConstruction_{hash(json.dumps([layer.model_dump(mode='json') for layer in layers]))}",
            Type="Facade",
            Layers=layers,
        )


# TODO: confined masonry walls, double leaf walls, AAC walls, rammed earth walls, adobe, wattle and daub walls, engineered timber panel walls (clt, glulam, etc.), informal settlement styles, etc.


# TODO: should we use a higher framing fraction to acount for doors, headers etc
TwoByFour16OCCWoodframeWallConstruction = FramedWallConstruction(
    framing_material="SoftwoodGeneral",
    framing_fraction=1.5 / 16,
    cavity_depth_m=0.090,
    sheathing_material="Plywood",
    sheathing_material_thickness_m=0.012,
    cavity_airgap_strategy="gap-then-clip",
)


TwoByFour24OCCWoodframeWallConstruction = FramedWallConstruction(
    framing_material="SoftwoodGeneral",
    framing_fraction=1.5 / 24,
    cavity_depth_m=0.090,  # 3.54in (90mm) stud
    sheathing_material="Plywood",
    sheathing_material_thickness_m=0.012,  # 1/2in (12.7mm) plywood
    cavity_airgap_strategy="gap-then-clip",
)

TwoBySix16OCCWoodframeWallConstruction = FramedWallConstruction(
    framing_material="SoftwoodGeneral",
    framing_fraction=1.5 / 16,
    cavity_depth_m=0.140,  # 5.5in (140mm) stud
    sheathing_material="Plywood",
    sheathing_material_thickness_m=0.012,  # 1/2in (12.7mm) plywood
    cavity_airgap_strategy="gap-then-clip",
)

TwoBySix24OCCWoodframeWallConstruction = FramedWallConstruction(
    framing_material="SoftwoodGeneral",
    framing_fraction=1.5 / 24,
    cavity_depth_m=0.140,  # 5.5in (140mm) stud
    sheathing_material="Plywood",
    sheathing_material_thickness_m=0.012,  # 1/2in (12.7mm) plywood
    cavity_airgap_strategy="gap-then-clip",
)

TwoByEight16OCCWoodframeWallConstruction = FramedWallConstruction(
    framing_material="SoftwoodGeneral",
    framing_fraction=1.5 / 16,
    cavity_depth_m=0.180,  # 7in (180mm) stud
    sheathing_material="Plywood",
    sheathing_material_thickness_m=0.012,  # 1/2in (12.7mm) plywood
    cavity_airgap_strategy="gap-then-clip",
)

TwoByEight24OCCWoodframeWallConstruction = FramedWallConstruction(
    framing_material="SoftwoodGeneral",
    framing_fraction=1.5 / 24,
    cavity_depth_m=0.180,  # 7in (180mm) stud
    sheathing_material="Plywood",
    sheathing_material_thickness_m=0.012,  # 1/2in (12.7mm) plywood
    cavity_airgap_strategy="gap-then-clip",
)
# TODO: double layer wall consructions using the gap-gap-gap-then-clip strategy

# Face Shell: 1-1.25in (25.4mm - 31.75mm)
# End Shell: 1-1.25in (25.4mm - 31.75mm)
# Web: 1in (25.4mm)
# Standard dimensions: 8in (203.2mm) x 8in (203.2mm) x 16in (406.4mm)
# Framing fraction: (end + web + end) / total_length
# Sheathing thickness: face shell
# cavity_depth: total_depth - (face shell + face shell)
# for construction like:
#    outside
#       |
#       v
#   ---------------
#   |      |      |
#   ---------------
#       ^
#       |
#    inside
SingleLayerCMUWallConstruction = FramedWallConstruction(
    framing_material="ConcreteMC_Light",
    framing_fraction=(0.028 + 0.254 + 0.028)
    / 0.406,  # (end + web + end) / total_length
    cavity_depth_m=0.406 - (0.028 + 0.028),  # total_depth - (end + end)
    sheathing_material="ConcreteMC_Light",
    sheathing_material_thickness_m=0.028,  # face shell
    cavity_airgap_strategy="gap-then-clip",
)
# TODO: make sure that the air gap still gets added correctly since the max
DoubleLayerCMUWallConstruction = FramedWallConstruction(
    framing_material="ConcreteMC_Light",
    framing_fraction=(0.028 + 0.254 + 0.028)
    / 0.406,  # (end + web + end) / total_length
    cavity_depth_m=2 * (0.406 - (0.028 + 0.028)),  # total_depth - (end + end)
    sheathing_material="ConcreteMC_Light",
    sheathing_material_thickness_m=2 * 0.028,  # face shell
    cavity_airgap_strategy="gap-gap-then-clip",
)


# SIPs
StructuralInsulatedPanelWallConstruction = FramedWallConstruction(
    framing_material="SoftwoodGeneral",
    framing_fraction=0.03,  # 3% framing fraction, still some joints between panels
    sheathing_material="OSB",
    sheathing_material_thickness_m=0.012,
    cavity_airgap_strategy="fit-to-insulation-r",
    cavity_depth_m=0.180,
)

# Poured Concrete Wall Construction
PouredConcreteWallConstruction_6Inch = MonolithicWallConstruction(
    structural_material="ConcreteRC_Dense",
    infill_material="ConcreteRC_Dense",
    structural_fraction=1.0,
    thickness_m=0.15,  # 15cm (6in) thick wall
)

PouredConcreteWallConstruction_8Inch = MonolithicWallConstruction(
    structural_material="ConcreteRC_Dense",
    infill_material="ConcreteRC_Dense",
    structural_fraction=1.0,
    thickness_m=0.20,  # 20cm (8in) thick wall
)

PouredConcreteWallConstruction_10Inch = MonolithicWallConstruction(
    structural_material="ConcreteRC_Dense",
    infill_material="ConcreteRC_Dense",
    structural_fraction=1.0,
    thickness_m=0.25,  # 25cm (10in) thick wall
)

WallFramingSystemName = Literal[
    "2x4 16OCC Woodframe",
    "2x4 24OCC Woodframe",
    "2x6 16OCC Woodframe",
    "2x6 24OCC Woodframe",
    "2x8 16OCC Woodframe",
    "2x8 24OCC Woodframe",
    "SingleLayerCMU",
    "DoubleLayerCMU",
    "StructuralInsulatedPanel",
    "PouredConcrete_6In",
    "PouredConcrete_8In",
    "PouredConcrete_10In",
]

WallFramingSystems: dict[WallFramingSystemName, FlatWallConstruction] = {
    "2x4 16OCC Woodframe": TwoByFour16OCCWoodframeWallConstruction,
    "2x4 24OCC Woodframe": TwoByFour24OCCWoodframeWallConstruction,
    "2x6 16OCC Woodframe": TwoBySix16OCCWoodframeWallConstruction,
    "2x6 24OCC Woodframe": TwoBySix24OCCWoodframeWallConstruction,
    "2x8 16OCC Woodframe": TwoByEight16OCCWoodframeWallConstruction,
    "2x8 24OCC Woodframe": TwoByEight24OCCWoodframeWallConstruction,
    "SingleLayerCMU": SingleLayerCMUWallConstruction,
    "DoubleLayerCMU": DoubleLayerCMUWallConstruction,
    "StructuralInsulatedPanel": StructuralInsulatedPanelWallConstruction,
    "PouredConcrete_6In": PouredConcreteWallConstruction_6Inch,
    "PouredConcrete_8In": PouredConcreteWallConstruction_8Inch,
    "PouredConcrete_10In": PouredConcreteWallConstruction_10Inch,
}
for name in get_args(WallFramingSystemName):
    if name not in WallFramingSystems:
        msg = f"Wall framing system {name} not found in WallFramingSystems."
        raise ValueError(msg)
