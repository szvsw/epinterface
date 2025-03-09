"""Tests for the component composer."""

import pytest
from prisma import Prisma
from pydantic import ValidationError

from epinterface.sbem.common import NamedObject
from epinterface.sbem.components.composer import (
    ComponentNameConstructor,
    construct_composer_model,
    construct_graph,
)
from epinterface.sbem.components.operations import ZoneOperationsComponent
from epinterface.sbem.components.space_use import ZoneSpaceUseComponent
from epinterface.sbem.prisma.client import deep_fetcher


@pytest.fixture(scope="module")
def root_nodes():
    """A fixture that returns a tuple of the root nodes for the test."""

    class OmittedLeafComponent(NamedObject):
        a: int

    class OmittedComponent(NamedObject):
        a: int
        b: OmittedLeafComponent

    class TruncatedLeafAComponent(NamedObject):
        a: int
        b: str
        c: list[float]
        d: list[OmittedComponent]

    class LeafBComponent(NamedObject):
        d: bool
        e: list[str]

    class LeafCComponent(NamedObject):
        a: int
        b: str

    class MiddleComponent(NamedObject):
        a1: TruncatedLeafAComponent
        a2: TruncatedLeafAComponent
        b: LeafBComponent

    class RootComponent(NamedObject):
        a: MiddleComponent
        b: MiddleComponent
        c: LeafCComponent

    return (
        RootComponent,
        MiddleComponent,
        LeafCComponent,
        LeafBComponent,
        OmittedComponent,
        TruncatedLeafAComponent,
    )


def test_construct_graph(root_nodes: tuple[type[NamedObject], ...]):
    """Test the construction of a graph."""
    (
        RootComponent,
        MiddleComponent,
        LeafCComponent,
        LeafBComponent,
        OmittedComponent,
        TruncatedLeafAComponent,
    ) = root_nodes
    root_graph = construct_graph(RootComponent)
    middle_graph = construct_graph(MiddleComponent)
    leaf_c_graph = construct_graph(LeafCComponent)
    leaf_b_graph = construct_graph(LeafBComponent)
    truncated_leaf_a_graph = construct_graph(TruncatedLeafAComponent)
    omitted_graph = construct_graph(OmittedComponent)

    assert len(omitted_graph.edges) == 1
    assert len(omitted_graph.nodes) == 2
    assert len(truncated_leaf_a_graph.edges) == 0
    assert len(truncated_leaf_a_graph.nodes) == 0
    assert len(leaf_b_graph.edges) == 0
    assert len(leaf_b_graph.nodes) == 0
    assert len(leaf_c_graph.edges) == 0
    assert len(leaf_c_graph.nodes) == 0
    assert len(middle_graph.edges) == 2 * (
        len(truncated_leaf_a_graph.edges) + 1
    ) + 1 * (len(leaf_b_graph.edges) + 1)
    assert len(root_graph.edges) == 2 * (len(middle_graph.edges) + 1) + 1 * (
        len(leaf_c_graph.edges) + 1
    )

    assert (
        sum(
            1
            for edge in root_graph.edges(data=True)
            if edge[-1]["data"]["type"] is MiddleComponent
        )
        == 2
    )
    assert (
        sum(
            1
            for edge in root_graph.edges(data=True)
            if edge[-1]["data"]["type"] is LeafCComponent
        )
        == 1
    )
    assert (
        sum(
            1
            for edge in root_graph.edges(data=True)
            if edge[-1]["data"]["type"] is LeafBComponent
        )
        == 2
    )
    assert (
        sum(
            1
            for edge in root_graph.edges(data=True)
            if edge[-1]["data"]["type"] is TruncatedLeafAComponent
        )
        == 2 * 2
    )
    assert len(root_graph.edges) == 9


@pytest.fixture(scope="module")
def root_node_no_recursion_error():
    """A fixture that returns a tuple of the root nodes for the test."""

    class OmittedLeafComponent(NamedObject):
        aolc: int

    class OmittedComponent(NamedObject):
        aoc: int
        boc: OmittedLeafComponent

    class TruncatedLeafAComponent(NamedObject):
        atl: int
        btl: str
        ctl: list[float]
        dtl: list[OmittedComponent]

    class LeafBComponent(NamedObject):
        alb: bool
        blb: list[str]

    class LeafCComponent(NamedObject):
        alc: int
        blc: str

    class MiddleComponent(NamedObject):
        a1mc: TruncatedLeafAComponent
        a2mc: TruncatedLeafAComponent
        bmc: LeafBComponent

    class RootComponent(NamedObject):
        ar: MiddleComponent
        br: MiddleComponent
        cr: LeafCComponent

    return RootComponent, TruncatedLeafAComponent


@pytest.fixture(scope="module")
def conflicting_keys_pointing_to_different_classes():
    """A fixture that returns a type with conflicting keys pointing to different classes.

    In other words, a parent type is using a field name that a child type is also using,
    which triggers a recursion error right now.
    """

    class A(NamedObject):
        height: int

    class B(NamedObject):
        age: str
        bio: A

    class C(NamedObject):
        info: B

    class E(NamedObject):
        junk: str

    class D(NamedObject):
        info: C  # this is conflicting with C.info
        help: E

    return D


@pytest.mark.xfail(
    reason="Recursion error since the info key is used to point to two different classes I think."
)
def test_construct_pydantic_models_from_graph_conflicting_keys(
    conflicting_keys_pointing_to_different_classes: type[NamedObject],
):
    """Test the construction of pydantic models from a graph."""
    root_node_class = conflicting_keys_pointing_to_different_classes
    root_graph = construct_graph(root_node_class)
    _SelectorModel = construct_composer_model(
        root_graph, root_node_class, use_children=False
    )


def test_construct_pydantic_models_from_graph_no_recursion(
    root_node_no_recursion_error: tuple[type[NamedObject], type[NamedObject]],
):
    """Test the construction of pydantic models from a graph."""
    # TODO: break this up into multiple tests
    (RootComponent, TruncatedLeafAComponent) = root_node_no_recursion_error
    root_graph = construct_graph(RootComponent)
    SelectorModelForbiddenExtra = construct_composer_model(
        root_graph, RootComponent, use_children=False, extra_handling="forbid"
    )
    SelectorModelIgnoreExtra = construct_composer_model(
        root_graph, RootComponent, use_children=False, extra_handling="ignore"
    )

    selector1 = SelectorModelForbiddenExtra(
        selector=ComponentNameConstructor(source_fields=["age", "typology"])
    )
    assert getattr(selector1, "ar", "Fail") is None
    assert getattr(selector1, "br", "Fail") is None
    assert getattr(selector1, "cr", "Fail") is None

    selector2 = SelectorModelForbiddenExtra(
        selector=ComponentNameConstructor(source_fields=["age"]),
        **{
            "ar": {
                "selector": ComponentNameConstructor(
                    source_fields=["typology", "system"]
                )
            },
            "br": None,
            "cr": None,
        },
    )
    ar = getattr(selector2, "ar", "Fail")
    assert ar is not None
    ar_selector = getattr(ar, "selector", "Fail")
    assert isinstance(ar_selector, ComponentNameConstructor)
    assert ar_selector.source_fields == ["typology", "system"]
    assert getattr(ar, "a1mc", "Fail") is None

    with pytest.raises(ValidationError):
        SelectorModelForbiddenExtra(
            selector=ComponentNameConstructor(source_fields=["age"]),
            **{
                "asdf": {
                    "selector": ComponentNameConstructor(
                        source_fields=["typology", "system"]
                    )
                },
            },
        )

    SelectorModelIgnoreExtra(
        selector=ComponentNameConstructor(source_fields=["age"]),
        **{
            "asdf": {
                "selector": ComponentNameConstructor(
                    source_fields=["typology", "system"]
                )
            }
        },
    )

    deep_selector = SelectorModelForbiddenExtra(
        selector=ComponentNameConstructor(source_fields=["age", "typology"]),
        **{
            "ar": {
                "a1mc": {
                    "selector": ComponentNameConstructor(
                        source_fields=["envelope_type", "retrofit_status"]
                    )
                }
            }
        },
    )
    a1mc_truncated_leaf = getattr(getattr(deep_selector, "ar", "Fail"), "a1mc", "Fail")
    assert a1mc_truncated_leaf is not None
    assert getattr(a1mc_truncated_leaf, "ValClass", "Fail") is TruncatedLeafAComponent
    a1mc_truncated_leaf_selector = getattr(a1mc_truncated_leaf, "selector", "Fail")
    assert isinstance(a1mc_truncated_leaf_selector, ComponentNameConstructor)
    assert a1mc_truncated_leaf_selector.source_fields == [
        "envelope_type",
        "retrofit_status",
    ]


def test_composer_on_space_uses(
    preseeded_readonly_db: Prisma,
):
    """Test the composer on space uses (only one level deep)."""
    _space_use, space_use_comp = deep_fetcher.SpaceUse.get_deep_object("default")
    root_graph = construct_graph(ZoneSpaceUseComponent)
    SelectorModel = construct_composer_model(
        root_graph, ZoneSpaceUseComponent, use_children=False
    )

    selector = SelectorModel(selector=ComponentNameConstructor(source_fields=["basic"]))

    comp = selector.get_component({"basic": "default"})
    assert isinstance(comp, ZoneSpaceUseComponent)
    assert comp == space_use_comp

    alt_selector = SelectorModel(
        selector=ComponentNameConstructor(source_fields=["basic"]),
        **{
            "Equipment": {
                "selector": ComponentNameConstructor(source_fields=["age", "typology"])
            }
        },
    )

    alt_comp = alt_selector.get_component({
        "basic": "default",
        "typology": "office",
        "age": "new",
    })
    assert isinstance(alt_comp, ZoneSpaceUseComponent)
    assert alt_comp != comp
    assert alt_comp.Equipment.Name == "new_office"
    assert alt_comp.Equipment.PowerDensity == 10 * 0.83  # from seed_fn
    assert alt_comp.Equipment != comp.Equipment
    assert alt_comp.Occupancy == comp.Occupancy
    assert alt_comp.WaterUse == comp.WaterUse
    assert alt_comp.Lighting == comp.Lighting
    assert alt_comp.Thermostat == comp.Thermostat

    # TODO: test behavior when provided context dict to get_component is missing fields

    # TODO: test extra fields

    # TODO: test not found/fallbacks (either due to name not in db, or due to pre-fetch check that field value, e.g. typology="office" is valid)


def test_operations_selector(preseeded_readonly_db: Prisma):
    """Test the operations selector to include deeply nested target components."""
    root_graph = construct_graph(ZoneOperationsComponent)
    SelectorModel = construct_composer_model(
        root_graph, ZoneOperationsComponent, use_children=False
    )

    selector = SelectorModel(selector=ComponentNameConstructor(source_fields=["basic"]))

    comp = selector.get_component({"basic": "default_ops"})

    assert isinstance(comp, ZoneOperationsComponent)
    assert comp.Name == "default_ops"

    alt_selector = SelectorModel(
        selector=ComponentNameConstructor(source_fields=["defaulter_ops"]),
        **{
            "SpaceUse": {
                "Equipment": {
                    "selector": ComponentNameConstructor(
                        source_fields=["age", "typology"]
                    )
                },
            },
            "HVAC": {
                "Ventilation": {
                    "selector": ComponentNameConstructor(
                        source_fields=["location", "typology"]
                    )
                }
            },
        },
    )

    alt_comp = alt_selector.get_component({
        "defaulter_ops": "default_ops",
        "defaulter_space": "default",
        "location": "cold",
        "typology": "office",
        "age": "new",
    })
    assert isinstance(alt_comp, ZoneOperationsComponent)
    assert alt_comp != comp
    assert alt_comp.HVAC.Ventilation != comp.HVAC.Ventilation

    assert alt_comp.HVAC.ConditioningSystems == comp.HVAC.ConditioningSystems
    assert alt_comp.DHW == comp.DHW
    assert alt_comp.SpaceUse.Lighting == comp.SpaceUse.Lighting
    assert alt_comp.SpaceUse.Occupancy == comp.SpaceUse.Occupancy
    assert alt_comp.SpaceUse.WaterUse == comp.SpaceUse.WaterUse
    assert alt_comp.SpaceUse.Thermostat == comp.SpaceUse.Thermostat

    assert alt_comp.SpaceUse.Equipment != comp.SpaceUse.Equipment
    assert alt_comp.SpaceUse.Equipment.Name == "new_office"
    assert alt_comp.SpaceUse.Equipment.PowerDensity == 10 * 0.83  # from seed_fn

    assert alt_comp.HVAC.Ventilation != comp.HVAC.Ventilation
    assert alt_comp.HVAC.Ventilation.Name == "cold_office"
    assert alt_comp.HVAC.Ventilation.Rate == 0.5  # from seed_fn
    assert alt_comp.HVAC.Ventilation.MinFreshAir == 0.4  # from seed_fn

    # TODO: test skipping 2 levels
    # TODO: test using 3 consecutive levels from top

    # etc
