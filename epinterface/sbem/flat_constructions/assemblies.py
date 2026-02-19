"""Envelope assembly builders for semi-flat construction definitions."""

from epinterface.sbem.components.envelope import (
    ConstructionAssemblyComponent,
    ConstructionLayerComponent,
    EnvelopeAssemblyComponent,
)
from epinterface.sbem.flat_constructions.materials import (
    CEMENT_MORTAR,
    CONCRETE_RC_DENSE,
    GYPSUM_BOARD,
    GYPSUM_PLASTER,
    SOFTWOOD_GENERAL,
    URETHANE_CARPET,
)
from epinterface.sbem.flat_constructions.roofs import (
    SemiFlatRoofConstruction,
    build_roof_assembly,
)
from epinterface.sbem.flat_constructions.slabs import (
    SemiFlatSlabConstruction,
    build_slab_assembly,
)
from epinterface.sbem.flat_constructions.walls import (
    SemiFlatWallConstruction,
    build_facade_assembly,
)


def build_partition_assembly(
    *, name: str = "Partition"
) -> ConstructionAssemblyComponent:
    """Build the default interior partition assembly."""
    return ConstructionAssemblyComponent(
        Name=name,
        Type="Partition",
        Layers=[
            ConstructionLayerComponent(
                ConstructionMaterial=GYPSUM_PLASTER,
                Thickness=0.02,
                LayerOrder=0,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=SOFTWOOD_GENERAL,
                Thickness=0.02,
                LayerOrder=1,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=GYPSUM_PLASTER,
                Thickness=0.02,
                LayerOrder=2,
            ),
        ],
    )


def build_floor_ceiling_assembly(
    *,
    name: str = "FloorCeiling",
) -> ConstructionAssemblyComponent:
    """Build the default interstitial floor/ceiling assembly."""
    return ConstructionAssemblyComponent(
        Name=name,
        Type="FloorCeiling",
        Layers=[
            ConstructionLayerComponent(
                ConstructionMaterial=URETHANE_CARPET,
                Thickness=0.02,
                LayerOrder=0,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=CEMENT_MORTAR,
                Thickness=0.02,
                LayerOrder=1,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=CONCRETE_RC_DENSE,
                Thickness=0.15,
                LayerOrder=2,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=GYPSUM_BOARD,
                Thickness=0.02,
                LayerOrder=3,
            ),
        ],
    )


def build_envelope_assemblies(
    *,
    facade_wall: SemiFlatWallConstruction,
    roof: SemiFlatRoofConstruction,
    slab: SemiFlatSlabConstruction,
) -> EnvelopeAssemblyComponent:
    """Build envelope assemblies from the flat model construction semantics."""
    facade = build_facade_assembly(facade_wall, name="Facade")
    roof_assembly = build_roof_assembly(roof, name="Roof")
    partition = build_partition_assembly(name="Partition")
    floor_ceiling = build_floor_ceiling_assembly(name="FloorCeiling")
    ground_slab = build_slab_assembly(
        slab,
        name="GroundSlabAssembly",
    )

    return EnvelopeAssemblyComponent(
        Name="EnvelopeAssemblies",
        FacadeAssembly=facade,
        FlatRoofAssembly=roof_assembly,
        AtticRoofAssembly=roof_assembly,
        PartitionAssembly=partition,
        FloorCeilingAssembly=floor_ceiling,
        AtticFloorAssembly=floor_ceiling,
        BasementCeilingAssembly=floor_ceiling,
        GroundSlabAssembly=ground_slab,
        GroundWallAssembly=ground_slab,
        ExternalFloorAssembly=ground_slab,
    )
