"""Tests for the component composer."""

import pytest
from prisma import Prisma
from pydantic import ValidationError

from epinterface.sbem.common import NamedObject
from epinterface.sbem.components.composer import (
    ComponentNameConstructor,
    construct_composer_model,
    construct_graph,
    recursive_tree_dict_merge,
)
from epinterface.sbem.components.envelope import (
    GlazingConstructionSimpleComponent,
    ZoneEnvelopeComponent,
)
from epinterface.sbem.components.operations import ZoneOperationsComponent
from epinterface.sbem.components.space_use import ZoneSpaceUseComponent
from epinterface.sbem.components.zones import ZoneComponent
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
    db = preseeded_readonly_db
    _space_use, space_use_comp = deep_fetcher.SpaceUse.get_deep_object("default", db)
    root_graph = construct_graph(ZoneSpaceUseComponent)
    SelectorModel = construct_composer_model(
        root_graph, ZoneSpaceUseComponent, use_children=False
    )

    selector = SelectorModel(selector=ComponentNameConstructor(source_fields=["basic"]))

    comp = selector.get_component({"basic": "default"}, db=db)
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

    alt_comp = alt_selector.get_component(
        {
            "basic": "default",
            "typology": "office",
            "age": "new",
        },
        db=db,
    )
    assert isinstance(alt_comp, ZoneSpaceUseComponent)
    assert alt_comp != comp
    assert alt_comp.Equipment.Name == "new_office"
    assert pytest.approx(alt_comp.Equipment.PowerDensity) == 10 * 0.83  # from seed_fn
    assert alt_comp.Equipment != comp.Equipment
    assert alt_comp.Occupancy == comp.Occupancy
    assert alt_comp.WaterUse == comp.WaterUse
    assert alt_comp.Lighting == comp.Lighting
    assert alt_comp.Thermostat == comp.Thermostat


def test_operations_selector(preseeded_readonly_db: Prisma):
    """Test the operations selector to include deeply nested target components."""
    db = preseeded_readonly_db
    root_graph = construct_graph(ZoneOperationsComponent)
    SelectorModel = construct_composer_model(
        root_graph, ZoneOperationsComponent, use_children=False
    )

    selector = SelectorModel(selector=ComponentNameConstructor(source_fields=["basic"]))

    comp = selector.get_component({"basic": "default_ops"}, db=db)

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

    alt_comp = alt_selector.get_component(
        {
            "defaulter_ops": "default_ops",
            "defaulter_space": "default",
            "location": "cold",
            "typology": "office",
            "age": "new",
        },
        db=db,
    )
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
    assert (
        pytest.approx(alt_comp.SpaceUse.Equipment.PowerDensity) == 10 * 0.83
    )  # from seed_fn

    assert alt_comp.HVAC.Ventilation != comp.HVAC.Ventilation
    assert alt_comp.HVAC.Ventilation.Name == "cold_office"
    assert alt_comp.HVAC.Ventilation.Rate == 0.5  # from seed_fn
    assert alt_comp.HVAC.Ventilation.MinFreshAir == 0.4  # from seed_fn


def test_envelope_selector(preseeded_readonly_db: Prisma):
    """Test the envelope selector to include deeply nested target components."""
    db = preseeded_readonly_db
    root_graph = construct_graph(ZoneEnvelopeComponent)
    SelectorModel = construct_composer_model(
        root_graph, ZoneEnvelopeComponent, use_children=False
    )

    selector = SelectorModel(selector=ComponentNameConstructor(source_fields=["basic"]))

    comp = selector.get_component({"basic": "default_env"}, db=db)

    assert isinstance(comp, ZoneEnvelopeComponent)
    assert comp.Name == "default_env"

    alt_selector = SelectorModel(
        selector=ComponentNameConstructor(source_fields=["default_env"]),
        **{
            "Infiltration": {
                "selector": ComponentNameConstructor(
                    source_fields=["typology", "weatherization"]
                )
            },
        },
    )

    alt_comp = alt_selector.get_component(
        {
            "default_env": "default_env",
            "typology": "residential",
            "weatherization": "heavily",
        },
        db=db,
    )
    assert isinstance(alt_comp, ZoneEnvelopeComponent)
    assert alt_comp != comp
    assert alt_comp.Infiltration.Name == "residential_heavily"
    assert (
        pytest.approx(alt_comp.Infiltration.AirChangesPerHour) == 0.8 * 0.3
    )  # from seed_fn
    assert alt_comp.Assemblies == comp.Assemblies

    component_selectors_dict = {
        "Assemblies": {
            "selector": ComponentNameConstructor(source_fields=["default_assembly"])
        },
        "Infiltration": {
            "selector": ComponentNameConstructor(
                source_fields=["typology", "weatherization"]
            )
        },
        "Window": {"selector": ComponentNameConstructor(source_fields=["window_type"])},
    }
    alt_selector = SelectorModel(
        **component_selectors_dict,  # pyright: ignore [reportArgumentType]
    )

    alt_comp_2 = alt_selector.get_component(
        {
            "default_assembly": "default",
            "typology": "residential",
            "weatherization": "moderately",
            "window_type": "double",
        },
        db=db,
    )

    assert isinstance(alt_comp_2, ZoneEnvelopeComponent)
    assert alt_comp_2.Assemblies == alt_comp.Assemblies
    assert alt_comp_2.Infiltration != alt_comp.Infiltration
    assert alt_comp_2.Infiltration.Name == "residential_moderately"
    assert pytest.approx(alt_comp_2.Infiltration.AirChangesPerHour) == 1.0 * 0.3
    assert alt_comp_2.Window != alt_comp.Window
    assert isinstance(alt_comp_2.Window, GlazingConstructionSimpleComponent)
    assert alt_comp_2.Window.Name == "double"
    assert alt_comp_2.Window.UValue == 0.5
    assert alt_comp_2.Window.SHGF == 0.5


def test_zone_selector(preseeded_readonly_db: Prisma):
    """Test the zone selector to include deeply nested target components."""
    db = preseeded_readonly_db
    root_graph = construct_graph(ZoneComponent)
    SelectorModel = construct_composer_model(
        root_graph, ZoneComponent, use_children=False
    )

    selector = SelectorModel(selector=ComponentNameConstructor(source_fields=["basic"]))

    comp = selector.get_component({"basic": "default_zone"}, db=db)

    assert isinstance(comp, ZoneComponent)
    assert comp.Name == "default_zone"

    multi_level_selector = SelectorModel(
        selector=ComponentNameConstructor(source_fields=["default_zone"]),
        **{
            "Operations": {
                "SpaceUse": {
                    "Equipment": {
                        "selector": ComponentNameConstructor(
                            source_fields=["age", "typology"]
                        )
                    }
                }
            }
        },
    )

    alt_comp = multi_level_selector.get_component(
        {
            "default_zone": "default_zone",
            "age": "new",
            "typology": "office",
        },
        db=db,
    )

    assert isinstance(alt_comp, ZoneComponent)
    assert alt_comp != comp
    assert alt_comp.Envelope == comp.Envelope
    assert alt_comp.Operations.HVAC == comp.Operations.HVAC
    assert alt_comp.Operations.DHW == comp.Operations.DHW
    assert alt_comp.Operations.SpaceUse.Equipment != comp.Operations.SpaceUse.Equipment
    assert alt_comp.Operations.SpaceUse.Equipment.Name == "new_office"
    assert (
        pytest.approx(alt_comp.Operations.SpaceUse.Equipment.PowerDensity) == 10 * 0.83
    )  # from seed_fn
    assert alt_comp.Operations.SpaceUse.Occupancy == comp.Operations.SpaceUse.Occupancy
    assert alt_comp.Operations.SpaceUse.WaterUse == comp.Operations.SpaceUse.WaterUse
    assert alt_comp.Operations.SpaceUse.Lighting == comp.Operations.SpaceUse.Lighting
    assert (
        alt_comp.Operations.SpaceUse.Thermostat == comp.Operations.SpaceUse.Thermostat
    )


# etc
def test_recursive_tree_dict_merger():
    """Test the recursive tree dict merger."""
    d1 = {
        "a1": {
            "b1": {
                "c": 1,
                "d": None,
            },
            "b2": {
                "e": {
                    "g": 5,
                },
                "f": 4,
            },
        },
        "a2": {
            "b1": {
                "c": 7,
                "d": 13,
            },
            "b2": {
                "e": {
                    "g": 21,
                },
                "f": 54,
            },
        },
    }
    d2 = {
        "a1": {
            "b1": {
                "d": 2,
            },
        },
        "a2": {
            "b2": {
                "f": 100,
            },
        },
    }

    recursive_tree_dict_merge(d1, d2)
    assert d1 == {
        "a1": {
            "b1": {
                "c": 1,
                "d": 2,
            },
            "b2": {
                "e": {
                    "g": 5,
                },
                "f": 4,
            },
        },
        "a2": {
            "b1": {
                "c": 7,
                "d": 13,
            },
            "b2": {
                "e": {
                    "g": 21,
                },
                "f": 100,
            },
        },
    }

    d1 = {"a": {"b": {"c": 1, "d": None}}}
    d2 = {"a": {"c": 3}}
    with pytest.raises(ValueError, match="c is not in the d1 target dictionary."):
        recursive_tree_dict_merge(d1, d2)

    d1 = {"a": 2}
    d2 = {"a": {"b": 3}}
    with pytest.raises(
        ValueError, match="a is not a dict in the d1 target dictionary."
    ):
        recursive_tree_dict_merge(d1, d2)


@pytest.mark.xfail(
    reason="Currently errors out due to checking if b is in None, but None is not iterable."
)
def test_overwriting_a_none_key_with_dict():
    """Test that a None key can be overwritten with a dict."""
    d1 = {"a": None}
    d2 = {"a": {"b": 3}}
    recursive_tree_dict_merge(d1, d2)
    assert d1 == {"a": {"b": 3}}

    d1 = {"a": {"b": None}}
    d2 = {"a": {"b": {"c": 3}}}
    recursive_tree_dict_merge(d1, d2)
    assert d1 == {"a": {"b": {"c": 3}}}


@pytest.mark.skip(reason="not yet implemented")
def test_scoped_db_compositions_work(preseeded_readonly_db: Prisma):
    """Test that scoped db compositions work."""
    # 1. copy the preseeded_readonly_db to a new path in the same directory
    # 2. create and connect to a new db instance
    # 3. mutate the value of something like equipment power density
    # 4. run the same zone composition on both dbs, one scoped, one unscoped
    # 5. ensure that the scoped db composition uses the mutated value, while the unscoped uses the original.
    pass


def test_validate_successful_resolution():
    """Test the validate_successful_resolution method."""
    graph = construct_graph(ZoneComponent)
    SelectorModel = construct_composer_model(graph, ZoneComponent, use_children=False)

    selector = SelectorModel(selector=ComponentNameConstructor(source_fields=["basic"]))

    is_valid, errors = selector.validate_successful_resolution(raise_on_failure=False)
    assert is_valid, "\n".join(errors)
    assert len(errors) == 0


def test_validate_successful_resolution_with_one_level_of_children():
    """Test the validate_successful_resolution method."""
    graph = construct_graph(ZoneComponent)
    SelectorModel = construct_composer_model(graph, ZoneComponent, use_children=False)

    selector = SelectorModel.model_validate(
        {
            "Envelope": {"selector": ComponentNameConstructor(source_fields=["basic"])},
            "Operations": {
                "selector": ComponentNameConstructor(source_fields=["basic"])
            },
        },
    )

    is_valid, errors = selector.validate_successful_resolution(raise_on_failure=False)
    assert is_valid, "\n".join(errors)
    assert len(errors) == 0


def test_validate_successful_resolution_with_multiple_levels_of_children():
    """Test the validate_successful_resolution method."""
    graph = construct_graph(ZoneComponent)
    SelectorModel = construct_composer_model(graph, ZoneComponent, use_children=False)

    selector = SelectorModel.model_validate(
        {
            "Envelope": {
                "Assemblies": {
                    "selector": ComponentNameConstructor(source_fields=["basic"])
                },
                "Window": {
                    "selector": ComponentNameConstructor(source_fields=["basic"])
                },
                "Infiltration": {
                    "selector": ComponentNameConstructor(source_fields=["basic"])
                },
            },
            "Operations": {
                "SpaceUse": {
                    "Equipment": {
                        "selector": ComponentNameConstructor(source_fields=["basic"])
                    },
                    "Occupancy": {
                        "selector": ComponentNameConstructor(source_fields=["basic"])
                    },
                    "WaterUse": {
                        "selector": ComponentNameConstructor(source_fields=["basic"])
                    },
                    "Lighting": {
                        "selector": ComponentNameConstructor(source_fields=["basic"])
                    },
                    "Thermostat": {
                        "selector": ComponentNameConstructor(source_fields=["basic"])
                    },
                },
                "HVAC": {
                    "Ventilation": {
                        "selector": ComponentNameConstructor(source_fields=["basic"])
                    },
                    "ConditioningSystems": {
                        "selector": ComponentNameConstructor(source_fields=["basic"])
                    },
                },
                "DHW": {"selector": ComponentNameConstructor(source_fields=["basic"])},
            },
        },
    )

    is_valid, errors = selector.validate_successful_resolution(raise_on_failure=False)
    assert is_valid, "\n".join(errors)
    assert len(errors) == 0


def test_validate_successful_resolution_with_multiple_mixed_levels_of_children():
    """Test the validate_successful_resolution method."""
    graph = construct_graph(ZoneComponent)
    SelectorModel = construct_composer_model(graph, ZoneComponent, use_children=False)

    selector = SelectorModel.model_validate({
        "Envelope": {
            "selector": ComponentNameConstructor(source_fields=["basic"]),
            "Window": {"selector": ComponentNameConstructor(source_fields=["basic"])},
            "Infiltration": {
                "selector": ComponentNameConstructor(source_fields=["basic"])
            },
        },
        "Operations": {
            "selector": ComponentNameConstructor(source_fields=["basic"]),
            "SpaceUse": {
                "WaterUse": {
                    "Schedule": {
                        "selector": ComponentNameConstructor(source_fields=["basic"])
                    },
                },
                "Lighting": {
                    "selector": ComponentNameConstructor(source_fields=["basic"])
                },
                "Thermostat": {
                    "selector": ComponentNameConstructor(source_fields=["basic"])
                },
            },
            "HVAC": {
                "Ventilation": {
                    "selector": ComponentNameConstructor(source_fields=["basic"])
                },
                "ConditioningSystems": {
                    "selector": ComponentNameConstructor(source_fields=["basic"])
                },
            },
            "DHW": {"selector": ComponentNameConstructor(source_fields=["basic"])},
        },
    })

    is_valid, errors = selector.validate_successful_resolution(raise_on_failure=False)
    assert is_valid, "\n".join(errors)
    assert len(errors) == 0


def test_validate_successful_resolution_with_top_level_missing_selector():
    """Test the validate_successful_resolution method."""
    graph = construct_graph(ZoneComponent)
    SelectorModel = construct_composer_model(graph, ZoneComponent, use_children=False)

    selector = SelectorModel.model_validate({
        "Envelope": {"selector": ComponentNameConstructor(source_fields=["basic"])},
    })

    is_valid, errors = selector.validate_successful_resolution(raise_on_failure=False)
    error_message = "\n".join(errors)
    assert not is_valid
    error_message_contains = "Operations:NoSelectorSpecified"
    assert error_message_contains == error_message
    with pytest.raises(ValueError, match=error_message_contains):
        selector.validate_successful_resolution()
    with pytest.raises(ValueError, match=error_message_contains):
        selector.get_component({"basic": "default_zone"})


def test_validate_successful_resolution_with_low_level_missing_selector():
    """Test the validate_successful_resolution method."""
    graph = construct_graph(ZoneComponent)
    SelectorModel = construct_composer_model(graph, ZoneComponent, use_children=False)

    selector = SelectorModel.model_validate({
        "Envelope": {"selector": ComponentNameConstructor(source_fields=["basic"])},
        "Operations": {
            "SpaceUse": {
                "Equipment": {
                    "selector": ComponentNameConstructor(source_fields=["basic"])
                },
            },
        },
    })

    is_valid, errors = selector.validate_successful_resolution(raise_on_failure=False)
    assert not is_valid
    error_message_strs = [
        "Operations:SpaceUse:Occupancy:NoSelectorSpecified",
        "Operations:SpaceUse:Lighting:NoSelectorSpecified",
        "Operations:SpaceUse:Thermostat:NoSelectorSpecified",
        "Operations:SpaceUse:WaterUse:NoSelectorSpecified",
        "Operations:HVAC:NoSelectorSpecified",
        "Operations:DHW:NoSelectorSpecified",
    ]
    assert set(errors) == set(error_message_strs)
    with pytest.raises(ValueError, match="\n".join(list(error_message_strs))):
        selector.validate_successful_resolution()
    with pytest.raises(ValueError, match="\n".join(list(error_message_strs))):
        selector.get_component({"basic": "default_zone"})


def test_bad_fields_in_constructor():
    """Test that bad fields in the constructor raise a ValidationError."""
    graph = construct_graph(ZoneComponent)
    SelectorModel = construct_composer_model(graph, ZoneComponent, use_children=False)

    with pytest.raises(ValidationError, match="junk"):
        SelectorModel.model_validate({
            "Envelope": {"selector": ComponentNameConstructor(source_fields=["basic"])},
            "junk": {"selector": ComponentNameConstructor(source_fields=["basic"])},
        })

    with pytest.raises(ValidationError, match="junkyjunk"):
        SelectorModel.model_validate({
            "Envelope": {"selector": ComponentNameConstructor(source_fields=["basic"])},
            "Operations": {
                "selector": ComponentNameConstructor(source_fields=["basic"]),
                "SpaceUse": {"junkyjunk": 2},
            },
        })

    with pytest.raises(ValidationError, match="source_fields"):
        SelectorModel.model_validate({
            "Envelope": {"selector": {"source_fields": ["typology", "age"]}},
            "Operations": {"selector": {"source_fields": "asdf"}},
        })


def test_bad_selector_in_dict():
    """Test that a bad selector in a dict raises a ValidationError."""
    graph = construct_graph(ZoneComponent)
    SelectorModel = construct_composer_model(graph, ZoneComponent, use_children=False)

    with pytest.raises(ValidationError, match="Extra"):
        SelectorModel.model_validate({
            "Envelope": {"selector": ComponentNameConstructor(source_fields=["basic"])},
            "Operations": {"selector": {"dfasdf": "asdf"}},
        })


def test_dict_for_component_name_constructor():
    """Test that a dict for a component name constructor is valid."""
    graph = construct_graph(ZoneComponent)
    SelectorModel = construct_composer_model(graph, ZoneComponent, use_children=False)

    sel = SelectorModel.model_validate({
        "Envelope": {"selector": {"source_fields": ["typology", "age"]}},
    })
    assert sel.Envelope.selector.source_fields == ["typology", "age"]  # pyright: ignore [reportAttributeAccessIssue]


# TODO: test field failures etc during get_component

# TODO: test behavior when provided context dict to get_component is missing fields

# TODO: test extra fields

# TODO: test not found/fallbacks (either due to name not in db, or due to pre-fetch check that field value, e.g. typology="office" is valid)
# TODO: test using 3 consecutive levels from top


@pytest.mark.skip(reason="not yet implemented")
def test_der_deser():
    """Test that the der and deser works."""
    pass


@pytest.mark.skip(reason="Not yet implemented")
def test_yaml_template_generator():
    """Test that the yaml template generator works."""
    pass
