"""Envelope assembly builders for semi-flat construction definitions."""

from epinterface.sbem.components.envelope import (
    ConstructionAssemblyComponent,
    ConstructionLayerComponent,
    EnvelopeAssemblyComponent,
)
from epinterface.sbem.flat_constructions.materials import (
    CEMENT_MORTAR,
    CERAMIC_TILE,
    CONCRETE_MC_LIGHT,
    CONCRETE_RC_DENSE,
    GYPSUM_BOARD,
    GYPSUM_PLASTER,
    SOFTWOOD_GENERAL,
    URETHANE_CARPET,
    XPS_BOARD,
)
from epinterface.sbem.flat_constructions.walls import (
    SemiFlatWallConstruction,
    build_facade_assembly,
)

MIN_INSULATION_THICKNESS_M = 0.003


def _set_insulation_layer_for_target_r_value(
    *,
    construction: ConstructionAssemblyComponent,
    insulation_layer_index: int,
    target_r_value: float,
    context: str,
) -> ConstructionAssemblyComponent:
    """Back-solve insulation thickness so an assembly meets a target total R-value."""
    insulation_layer = construction.sorted_layers[insulation_layer_index]
    non_insulation_r = construction.r_value - insulation_layer.r_value
    r_delta = target_r_value - non_insulation_r
    required_thickness = insulation_layer.ConstructionMaterial.Conductivity * r_delta

    if required_thickness < MIN_INSULATION_THICKNESS_M:
        msg = (
            f"Required {context} insulation thickness is less than "
            f"{MIN_INSULATION_THICKNESS_M * 1000:.0f} mm because the desired total "
            f"R-value is {target_r_value} m²K/W but the non-insulation layers already "
            f"sum to {non_insulation_r} m²K/W."
        )
        raise ValueError(msg)

    insulation_layer.Thickness = required_thickness
    return construction


def build_flat_roof_assembly(
    *,
    target_r_value: float,
    name: str = "Roof",
) -> ConstructionAssemblyComponent:
    """Build the flat-roof assembly and tune insulation to a target R-value."""
    roof = ConstructionAssemblyComponent(
        Name=name,
        Type="FlatRoof",
        Layers=[
            ConstructionLayerComponent(
                ConstructionMaterial=XPS_BOARD,
                Thickness=0.1,
                LayerOrder=0,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=CONCRETE_MC_LIGHT,
                Thickness=0.15,
                LayerOrder=1,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=CONCRETE_RC_DENSE,
                Thickness=0.2,
                LayerOrder=2,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=GYPSUM_BOARD,
                Thickness=0.02,
                LayerOrder=3,
            ),
        ],
    )
    return _set_insulation_layer_for_target_r_value(
        construction=roof,
        insulation_layer_index=0,
        target_r_value=target_r_value,
        context="Roof",
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


def build_ground_slab_assembly(
    *,
    target_r_value: float,
    name: str = "GroundSlabAssembly",
) -> ConstructionAssemblyComponent:
    """Build the ground slab assembly and tune insulation to a target R-value."""
    slab = ConstructionAssemblyComponent(
        Name=name,
        Type="GroundSlab",
        Layers=[
            ConstructionLayerComponent(
                ConstructionMaterial=XPS_BOARD,
                Thickness=0.02,
                LayerOrder=0,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=CONCRETE_RC_DENSE,
                Thickness=0.15,
                LayerOrder=1,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=CONCRETE_MC_LIGHT,
                Thickness=0.04,
                LayerOrder=2,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=CEMENT_MORTAR,
                Thickness=0.03,
                LayerOrder=3,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=CERAMIC_TILE,
                Thickness=0.02,
                LayerOrder=4,
            ),
        ],
    )
    return _set_insulation_layer_for_target_r_value(
        construction=slab,
        insulation_layer_index=0,
        target_r_value=target_r_value,
        context="Ground slab",
    )


def build_envelope_assemblies(
    *,
    facade_wall: SemiFlatWallConstruction,
    roof_r_value: float,
    slab_r_value: float,
) -> EnvelopeAssemblyComponent:
    """Build envelope assemblies from the flat model construction semantics."""
    facade = build_facade_assembly(facade_wall, name="Facade")
    roof = build_flat_roof_assembly(target_r_value=roof_r_value, name="Roof")
    partition = build_partition_assembly(name="Partition")
    floor_ceiling = build_floor_ceiling_assembly(name="FloorCeiling")
    ground_slab = build_ground_slab_assembly(
        target_r_value=slab_r_value,
        name="GroundSlabAssembly",
    )

    return EnvelopeAssemblyComponent(
        Name="EnvelopeAssemblies",
        FacadeAssembly=facade,
        FlatRoofAssembly=roof,
        AtticRoofAssembly=roof,
        PartitionAssembly=partition,
        FloorCeilingAssembly=floor_ceiling,
        AtticFloorAssembly=floor_ceiling,
        BasementCeilingAssembly=floor_ceiling,
        GroundSlabAssembly=ground_slab,
        GroundWallAssembly=ground_slab,
        ExternalFloorAssembly=ground_slab,
    )
