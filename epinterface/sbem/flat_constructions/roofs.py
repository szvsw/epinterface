"""Roof construction objects for SBEM assemblies."""

from epinterface.sbem.components.envelope import (
    ConstructionAssemblyComponent,
    ConstructionLayerComponent,
)
from epinterface.sbem.flat_constructions.materials import (
    ACOUSTIC_TILE,
    CONCRETE_MC_LIGHT,
    XPS_BOARD,
)


# TODO: make the roof more configurable similar to slab and walls
def build_roof_assembly(
    r_value: float,
):
    """Build a roof assembly with the given R-value."""
    roof = ConstructionAssemblyComponent(
        Name="Roof",
        Type="FlatRoof",
        Layers=[
            ConstructionLayerComponent(
                ConstructionMaterial=CONCRETE_MC_LIGHT,
                Thickness=0.15,
                LayerOrder=0,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=XPS_BOARD,
                Thickness=0.1,
                LayerOrder=1,
            ),
            ConstructionLayerComponent(
                ConstructionMaterial=ACOUSTIC_TILE,
                Thickness=0.02,
                LayerOrder=2,
            ),
        ],
    )

    roof_r_value_without_xps = roof.r_value - roof.sorted_layers[1].r_value
    roof_r_value_delta = r_value - roof_r_value_without_xps
    required_xps_thickness = XPS_BOARD.Conductivity * roof_r_value_delta
    if required_xps_thickness < 0.003:
        msg = f"Required Roof XPS thickness is less than 3mm because the desired total roof R-value is {r_value} m²K/W but the concrete layers already have a total R-value of {roof_r_value_without_xps} m²K/W."
        raise ValueError(msg)

    roof.sorted_layers[1].Thickness = required_xps_thickness
    return roof
