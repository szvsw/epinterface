"""Slab construction objects for SBEM assemblies."""

import json
from abc import ABC, abstractmethod
from typing import Literal, get_args

from pydantic import BaseModel

from epinterface.sbem.components.envelope import (
    ConstructionAssemblyComponent,
    ConstructionLayerComponent,
)
from epinterface.sbem.flat_constructions.base import (
    BasicGroundSlabMaterialName,
    ContinuousInsulationMaterialName,
    FinishTemplate,
    get_basic_ground_slab_material,
    get_continuous_insulation_material,
)
from epinterface.sbem.flat_constructions.materials import MATERIALS_BY_NAME

GroundSlabInteriorFinishName = Literal[
    "tile",
    "wood_floor",
    "carpet",
    "polished_concrete",
    "cement_screed",
    "none",
]

INTERIOR_FINISHES: dict[GroundSlabInteriorFinishName, FinishTemplate | None] = {
    "tile": FinishTemplate(
        material_name="CeramicTile",
        thickness_m=0.015,
    ),
    "wood_floor": FinishTemplate(
        material_name="SoftwoodGeneral",
        thickness_m=0.015,
    ),
    "carpet": FinishTemplate(
        material_name="UrethaneCarpet",
        thickness_m=0.012,
    ),
    "polished_concrete": FinishTemplate(
        material_name="CementMortar",
        thickness_m=0.015,
    ),
    "cement_screed": FinishTemplate(
        material_name="CementMortar",
        thickness_m=0.02,
    ),
    "none": None,
}


class FlatGroundSlabConstruction(ABC, BaseModel):
    """A base class for slab construction templates."""

    insulation_location: Literal["below", "above"]

    @abstractmethod
    def to_construction_assembly(
        self,
        *,
        insul_name: ContinuousInsulationMaterialName | Literal["None"],
        insul_rval: float,
        structural_thickness: float,
        interior_finish: GroundSlabInteriorFinishName,
    ) -> ConstructionAssemblyComponent:
        """Translate the slab construction object into an EnergyPlus construction assembly."""


class BasicGroundSlab(FlatGroundSlabConstruction):
    """A basic slab construction object."""

    slab_material: BasicGroundSlabMaterialName

    def to_construction_assembly(
        self,
        *,
        insul_name: ContinuousInsulationMaterialName | Literal["None"],
        insul_rval: float,
        structural_thickness: float,
        interior_finish: GroundSlabInteriorFinishName,
    ) -> ConstructionAssemblyComponent:
        """Translate the basic slab construction object into an EnergyPlus construction assembly."""
        layers: list[ConstructionLayerComponent] = []
        layer_order = 0

        ####### HANDLE INSULATION BELOW SLAB LAYER #######
        if (
            insul_rval > 0
            and insul_name != "None"
            and self.insulation_location == "below"
        ):
            thickened_insul = get_continuous_insulation_material(insul_name, insul_rval)
            layers.append(
                ConstructionLayerComponent(
                    ConstructionMaterial=thickened_insul.material,
                    Thickness=thickened_insul.thickness_m,
                    LayerOrder=layer_order,
                )
            )
            layer_order += 1

        ####### HANDLE STRUCTURAL MATERIAL LAYER #######
        structural_mat = get_basic_ground_slab_material(self.slab_material)
        layers.append(
            ConstructionLayerComponent(
                ConstructionMaterial=structural_mat,
                Thickness=structural_thickness,
                LayerOrder=layer_order,
            )
        )
        layer_order += 1

        ####### HANDLE INSULATION ABOVE SLAB LAYER #######
        if (
            insul_rval > 0
            and insul_name != "None"
            and self.insulation_location == "above"
        ):
            thickened_insul = get_continuous_insulation_material(insul_name, insul_rval)
            layers.append(
                ConstructionLayerComponent(
                    ConstructionMaterial=thickened_insul.material,
                    Thickness=thickened_insul.thickness_m,
                    LayerOrder=layer_order,
                )
            )
            layer_order += 1

        ####### HANDLE INTERIOR FINISH LAYER #######
        if interior_finish_template := INTERIOR_FINISHES[interior_finish]:
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
            Name=f"BasicGroundSlab_{self.slab_material}_{insul_name}_{
                self.insulation_location
            }_{insul_rval}_{structural_thickness}_{interior_finish}_{
                hash(json.dumps([layer.model_dump(mode='json') for layer in layers]))
            }",
            Layers=layers,
            Type="GroundSlab",
        )


BasicConcreteGroundSlab = BasicGroundSlab(
    slab_material="ConcreteMC_Light",
    insulation_location="below",
)

BasicRCGroundSlab = BasicGroundSlab(
    slab_material="ConcreteRC_Dense",
    insulation_location="below",
)

GroundSlabSystemName = Literal[
    "BasicConcrete",
    "BasicRC",
]

GroundSlabSystems: dict[GroundSlabSystemName, FlatGroundSlabConstruction] = {
    "BasicConcrete": BasicConcreteGroundSlab,
    "BasicRC": BasicRCGroundSlab,
}
for name in get_args(GroundSlabSystemName):
    if name not in GroundSlabSystems:
        msg = f"Ground slab system {name} not found in GroundSlabSystems."
        raise ValueError(msg)
